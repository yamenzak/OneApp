"""The run itself: steps, batches, and how far it has got."""

import frappe
import json
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime
from .source import BATCH, TIMEOUT, fetch, whole
from .mapping import build, explode, maps_children
from .writing import _issue, _mark, _write


@frappe.whitelist()
def start(plan: str, dry_run: int = 0) -> str:
	"""Queue a run of one plan, and hand back its name to watch.

	Queued rather than run: a migration is minutes to hours and a request that
	waits for one is a request that times out half way through, leaving a run
	nobody is watching and a browser that says it failed.
	"""
	doc = frappe.get_doc("Import Plan", plan)
	doc.check_permission("write")

	if not doc.is_active:
		frappe.throw(_("That plan is switched off."))

	running = frappe.db.exists("Import Run", {"plan": plan, "status": ("in", ("Queued", "Running"))})
	if running:
		# Two runs of one plan race each other through the same identities, and
		# what they produce is not the same as either of them alone.
		frappe.throw(_("{0} is already running.").format(running))

	run = frappe.get_doc({
		"doctype": "Import Run",
		"plan": plan,
		"dry_run": cint(dry_run),
		"status": "Queued",
		"steps": [
			{"source_doctype": s.source_doctype, "target_doctype": s.target_doctype,
			 "status": "Queued" if s.enabled else "Skipped"}
			for s in doc.steps
		],
	}).insert()
	frappe.db.commit()

	frappe.enqueue(
		"oneapp.oneapp_core.importer.execute",
		queue="long",
		timeout=TIMEOUT,
		run=run.name,
		# The job runs as whoever pressed it, so what an import may create is
		# what that person may create. An import that could write what its
		# operator cannot is a way around every permission on the site.
		user=frappe.session.user,
	)
	return run.name


def execute(run: str, user: str | None = None):
	"""The job: every enabled step of the plan, in the order it declares them.

	Order is the author's, and it is dependency order — parties before the
	invoices that link to them. Nothing here sorts it: a plan that got it wrong
	says so as unresolved links on real rows, which is a better error than a
	guess at what depends on what.
	"""
	if user:
		frappe.set_user(user)

	doc = frappe.get_doc("Import Run", run)
	plan = frappe.get_doc("Import Plan", doc.plan)
	source = frappe.get_doc("Import Source", plan.source)

	doc.db_set({"status": "Running", "started_on": now_datetime()})
	frappe.db.commit()

	# A rehearsal is the real run inside a transaction that is thrown away.
	# Nothing else is a rehearsal: validating a document in isolation cannot
	# resolve a link to a record an earlier step would have made, so every step
	# after the first reported failures that only a rehearsal has. Issues are
	# kept in memory instead of written, because the rollback would take them
	# with everything else.
	held: list | None = [] if doc.dry_run else None

	# Paired by position, not by source doctype. Keyed by name, two steps off
	# one source — a party table split into customers and suppliers, the
	# ordinary reason to have two — collapse to whichever came last, and the
	# other silently never runs: seventy-five customers that the run reports as
	# done and never looked at. The run's rows are made from the plan's in
	# order by `start`, so position is the identity; anything else means the
	# plan was edited under the run, which is worth stopping for.
	if len(doc.steps) != len(plan.steps):
		frappe.throw(_("{0} changed since this run was queued.").format(plan.name))

	try:
		for row, step in zip(doc.steps, plan.steps, strict=True):
			if (row.source_doctype, row.target_doctype) != (step.source_doctype,
			                                                step.target_doctype):
				frappe.throw(_("{0} changed since this run was queued.").format(plan.name))
			if not step.enabled:
				continue
			_step(doc, plan, source, step, row, held)
	except Exception:
		doc.reload()
		doc.db_set({"status": "Failed", "finished_on": now_datetime(),
		            "error": frappe.get_traceback(with_context=False)[-500:]})
		frappe.db.commit()
		raise

	counted = [(r.name, r.seen, r.created, r.updated, r.failed) for r in doc.steps]

	if doc.dry_run:
		# Everything the rehearsal wrote, undone — and then the only two things
		# worth keeping written again: what it counted, and what it refused.
		frappe.db.rollback()
		for name, seen, created, updated, failed in counted:
			frappe.db.set_value("Import Run Step", name, {
				"status": "Done", "seen": seen, "created": created,
				"updated": updated, "failed": failed,
			}, update_modified=False)
		for said in held:
			frappe.get_doc(said).insert(ignore_permissions=True)

	doc.reload()
	doc.db_set({
		"status": "Done",
		"finished_on": now_datetime(),
		"total_seen": sum(cint(r.seen) for r in doc.steps),
		"total_created": sum(cint(r.created) for r in doc.steps),
		"total_updated": sum(cint(r.updated) for r in doc.steps),
		"total_failed": sum(cint(r.failed) for r in doc.steps),
	})
	frappe.db.commit()


def _step(run, plan, source, step, row, held: list | None = None):
	"""One doctype, a page at a time, from the watermark forward."""
	counts = {"seen": 0, "created": 0, "updated": 0, "failed": 0}
	_mark(row, {"status": "Running", "watermark_from": step.watermark})

	filters = json.loads(step.filters) if step.filters else []
	if step.watermark:
		# `>=` and not `>`, deliberately. Rows that share the boundary's exact
		# `modified` would otherwise be dropped by the next run — a second of
		# records lost at a page edge, silently. Re-reading them costs an update
		# apiece, and updating is free because every row is an identity.
		filters = filters + [[step.source_doctype, "modified", ">=", str(step.watermark)]]

	field_map = json.loads(step.field_map or "{}")
	fan_out = json.loads(step.fan_out) if step.fan_out else None
	deep = maps_children(field_map)
	start = 0
	# A string, always. The watermark comes back out of the database as a
	# datetime and a row's `modified` arrives from the API as text, and `max`
	# over the two raises — so the *first* run worked, every time, and the
	# second one died before it read a row. Which is the run that matters:
	# incremental is the whole promise.
	newest = str(step.watermark) if step.watermark else None

	while True:
		page = fetch(source, step.source_doctype, filters, start, BATCH)
		if not page:
			break

		for said in page:
			# A step that maps child rows reads its rows twice — see `whole`.
			# Inside the row loop rather than around it so one document that
			# will not load is one issue, not a dead page.
			if deep:
				try:
					said = {**said, **whole(source, step.source_doctype, said.get("name"))}
				except Exception as raised:
					counts["seen"] += 1
					counts["failed"] += 1
					_issue(run, step, said, raised)
					newest = max(filter(None, (newest, said.get("modified"))), default=newest)
					continue

			# `seen` counts source rows and not target ones: it is what the
			# source has, and a number that grew twenty times faster than the
			# thing being read would be unreadable as progress.
			counts["seen"] += 1
			try:
				pieces = explode(said, fan_out)
			except Exception as raised:
				counts["failed"] += 1
				_issue(run, step, said, raised)
				pieces = []

			for key, piece in pieces:
				# One savepoint per row. A failed insert leaves the transaction
				# dirty, and the blanket rollback this used to do took the rest
				# of the page with it — up to a hundred and ninety-nine records
				# already counted as created and then quietly discarded.
				mark = f"imp{counts['seen']}_{counts['created']}"
				frappe.db.savepoint(mark)
				try:
					made = build(piece, field_map, plan.name)
					# `key` and not `piece["name"]`: every piece of one row
					# shares the parent's name, and an identity keyed on that
					# would have twenty thousand rows overwrite each other.
					what = _write(plan, step, key, piece, made, source, field_map)
				except Exception as raised:
					frappe.db.rollback(save_point=mark)
					counts["failed"] += 1
					_issue(run, step, piece, raised, held)
				else:
					frappe.db.release_savepoint(mark)
					counts[what] += 1

			newest = max(filter(None, (newest, said.get("modified"))), default=newest)

		# Per page, not per run. This is what "resumable" means: a step killed
		# at row nineteen hundred restarts near there rather than at one.
		if not run.dry_run:
			frappe.db.set_value("Import Step", step.name, "watermark", newest,
			                    update_modified=False)
		_mark(row, {**counts, "watermark_to": newest})
		if not run.dry_run:
			frappe.db.commit()

		if len(page) < BATCH:
			break
		start += BATCH

	if not run.dry_run:
		frappe.db.set_value("Import Step", step.name, "last_run", run.name,
		                    update_modified=False)
	_mark(row, {"status": "Done", **counts, "watermark_to": newest})
	if not run.dry_run:
		frappe.db.commit()


@frappe.whitelist()
def progress(run: str) -> dict:
	"""Where a run has got to, for something watching it."""
	doc = frappe.get_doc("Import Run", run)
	doc.check_permission("read")
	return {
		"status": doc.status,
		"dry_run": doc.dry_run,
		"started_on": doc.started_on,
		"finished_on": doc.finished_on,
		"error": doc.error,
		"steps": [
			{"source_doctype": r.source_doctype, "target_doctype": r.target_doctype,
			 "status": r.status, "seen": r.seen, "created": r.created,
			 "updated": r.updated, "failed": r.failed}
			for r in doc.steps
		],
		"issues": frappe.db.count("Import Issue", {"run": run, "status": "Open"}),
	}
