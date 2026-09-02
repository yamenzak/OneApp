"""Bringing a customer's data with them, from a Frappe site that is still in use.

Every workspace that replaces something arrives with years of it, and the naive
answer — a script somebody runs once — gets it wrong twice. It runs once, and
the system it read from keeps moving, so the cutover becomes a night nobody
works and a morning of typing in whatever changed.

So this is an engine, and five properties are what make it one:

**Idempotent.** Every source row's target is remembered in `Import Identity`, so
a second run updates the record the first one made rather than making another.
That single table is also what lets a link resolve: an invoice's `party` becomes
the Customer an earlier step created out of the same source row.

**Incremental.** Each step keeps a watermark — the newest `modified` it has
taken across — and asks the source only for rows at or after it. Run it a month
before the cutover to rehearse, run it again at midnight, and the second run
carries only the delta. That is the "up to the last second" part, and it is
three lines rather than a feature.

**Resumable.** The watermark advances per committed batch, not per run. A step
that dies in the middle of two thousand rows resumes near where it stopped.

**Answerable.** A row that will not save is kept whole — what the source said,
what we made of it, and what refused it — as an `Import Issue`. A migration is
then a list to work through rather than a log to read.

**Rehearsable.** A dry run fetches, maps, resolves and validates, and commits
nothing. It is the only honest way to learn what a migration will do before it
does it, and the counts it reports are real.

Nothing here is about any one customer. A plan is data — steps, field maps,
value maps — so the next workspace arriving off its own Frappe site is a plan
and no code.

## The field map

Keyed by *target* fieldname, because what is being built is the target: read it
top to bottom and it is the record you end up with. Each value is one of:

    {"from": "party"}                                    copy a field across
    {"from": "type", "values": {...}, "default": "..."}  copy through a map
    {"from": "project", "link": "RUA Project"}           resolve to what an
                                                         earlier step made of
                                                         that source row
    {"const": "RUA Contracting"}                         the same on every row

A `link` that resolves to nothing is an issue on that row rather than a blank
saved quietly, because a link that silently did not arrive is the failure people
find months later in a report that is missing a third of its rows.
"""

import json
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, now_datetime

# How many rows one request asks for. Frappe's own list endpoint is happy with
# far more; this is sized so a batch commits often enough that a crash costs
# seconds of work rather than minutes.
BATCH = 200

# What a step may spend before the queue takes it away. A migration is a long
# job by nature and the alternative to a long timeout is a partial import that
# looks finished.
TIMEOUT = 60 * 60

# Every field of a source row travels, because the field map decides what is
# read and a map edited later should not need a re-fetch to see a column it did
# not ask for last time.
ALL_FIELDS = '["*"]'


# --------------------------------------------------------------------------- #
# Reaching the other site
# --------------------------------------------------------------------------- #


def _endpoint(source) -> str:
	"""The source's base URL, checked before anything is sent to it.

	A customer types this in, which makes it the one place this feature can be
	pointed somewhere it should not go: an internal address, a metadata service,
	a neighbour's site on the same network. So it is https, it is a hostname
	rather than an address, and it is not a name that resolves inward.

	Not a substitute for the network's own rules, and not trying to be. It is
	the check that costs nothing and catches the mistake somebody makes by
	pasting the wrong thing.
	"""
	raw = (source.base_url or "").strip().rstrip("/")
	parsed = urlparse(raw)

	if parsed.scheme != "https":
		frappe.throw(_("A source has to be https. Credentials travel to it."))
	if not parsed.hostname or parsed.path or parsed.query:
		frappe.throw(_("A source is a host and nothing else, like https://old.example.com."))

	host = parsed.hostname.lower()
	if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".internal"):
		frappe.throw(_("That address is inside this network."))
	# An address rather than a name: the shapes that reach a metadata service or
	# a machine on the same subnet all look like one.
	if host.replace(".", "").replace(":", "").isdigit() or ":" in host:
		frappe.throw(_("A source is named by hostname, not by address."))

	return raw


def _get(source, path: str, params: dict) -> dict:
	"""One GET against the source, as the token's own user over there.

	`requests` rather than anything of Frappe's: this is an ordinary call to
	another site's REST API, and the framework's helpers are built for its own
	integrations with their own retry and logging opinions.
	"""
	import requests

	url = f"{_endpoint(source)}/api/{path}"
	secret = source.get_password("api_secret")
	answer = requests.get(
		url,
		params=params,
		headers={"Authorization": f"token {source.api_key}:{secret}"},
		timeout=60,
	)
	if answer.status_code == 401 or answer.status_code == 403:
		frappe.throw(_("The source refused the key. Check it is still valid over there."))
	answer.raise_for_status()
	return answer.json()


@frappe.whitelist()
def verify(source: str) -> dict:
	"""Ask the source who we are to it, and remember the answer.

	Worth its own button and its own field. An import runs as this user on the
	other site, so a key made from an account with half the permissions imports
	half the data and nothing anywhere says why — the rows it could not read
	simply were not in the answer.
	"""
	doc = frappe.get_doc("Import Source", source)
	doc.check_permission("write")

	try:
		who = _get(doc, "method/frappe.auth.get_logged_user", {}).get("message") or ""
	except Exception as raised:
		doc.db_set({"status": "Refused", "last_error": str(raised)[:500]})
		frappe.db.commit()
		return {"ok": False, "error": str(raised)}

	doc.db_set({
		"status": "Verified",
		"verified_as": who,
		"verified_on": now_datetime(),
		"last_error": "",
	})
	frappe.db.commit()
	return {"ok": True, "user": who}


@frappe.whitelist()
def preview(source: str, doctype: str, filters: str | None = None) -> dict:
	"""How many rows of one doctype are over there, and one of them.

	What somebody wants before writing a field map, and what the plan editor
	shows beside each step: a count to size the job, and a real row to map
	against rather than a memory of the schema.
	"""
	doc = frappe.get_doc("Import Source", source)
	doc.check_permission("read")

	params = {"limit_page_length": 1, "fields": ALL_FIELDS, "order_by": "modified desc"}
	if filters:
		params["filters"] = filters

	rows = _get(doc, f"resource/{doctype}", params).get("data") or []
	count = _get(doc, "method/frappe.client.get_count",
	             {"doctype": doctype, **({"filters": filters} if filters else {})})
	return {"count": count.get("message"), "row": rows[0] if rows else None}


def fetch(source, doctype: str, filters: list, start: int, length: int) -> list[dict]:
	"""One page of a doctype, oldest change first.

	`modified asc` is not a preference. The watermark is only safe if rows
	arrive in the order it advances through, and a page ordered any other way
	leaves a run that stops early having skipped rows it will never ask for
	again.
	"""
	return _get(source, f"resource/{doctype}", {
		"fields": ALL_FIELDS,
		"filters": json.dumps(filters),
		"order_by": "modified asc",
		"limit_start": start,
		"limit_page_length": length,
	}).get("data") or []


# --------------------------------------------------------------------------- #
# Turning one row into another
# --------------------------------------------------------------------------- #


class Unresolved(Exception):
	"""A link that pointed at something no step has made yet.

	Its own exception because it is not a bad row — it is a plan whose steps are
	in the wrong order, and the row is fine and will import once they are not.
	The message says which link, because that is the whole diagnosis.
	"""


def build(row: dict, field_map: dict, plan: str) -> dict:
	"""One source row as the values of one target record.

	Every rule is explicit. There is deliberately no "copy anything whose name
	matches": two systems that happen to share a fieldname mean the same thing
	about a third of the time, and the third that do not are the ones nobody
	notices until the numbers are wrong.
	"""
	values = {}

	for target, rule in (field_map or {}).items():
		if not isinstance(rule, dict):
			# The short form, because `{"customer_name": "party"}` is what
			# somebody writes first and refusing it teaches nothing.
			rule = {"from": rule}

		if "const" in rule:
			values[target] = rule["const"]
			continue

		said = row.get(rule.get("from"))

		if rule.get("link"):
			if said in (None, ""):
				continue
			found = resolve(plan, rule["link"], said)
			if not found:
				raise Unresolved(
					f"{target}: nothing here yet for {rule['link']} {said}. "
					"Run that step first, or move it earlier in the plan."
				)
			values[target] = found
			continue

		if "values" in rule:
			said = rule["values"].get(said, rule.get("default", said))

		if said in (None, "") and "default" in rule:
			said = rule["default"]

		values[target] = said

	return values


def resolve(plan: str, source_doctype: str, source_name: str) -> str:
	"""What this plan made of one source row, or nothing.

	The whole of link resolution, and the reason it is a table rather than a
	naming convention: a source row named by hash whose target is named after a
	field has no other way back to itself.
	"""
	return frappe.db.get_value(
		"Import Identity",
		{"plan": plan, "source_doctype": source_doctype, "source_name": source_name},
		"target_name",
	)


# --------------------------------------------------------------------------- #
# Doing it
# --------------------------------------------------------------------------- #


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

	steps = {s.source_doctype: s for s in plan.steps}
	try:
		for row in doc.steps:
			step = steps.get(row.source_doctype)
			if not step or not step.enabled:
				continue
			_step(doc, plan, source, step, row)
	except Exception:
		doc.reload()
		doc.db_set({"status": "Failed", "finished_on": now_datetime(),
		            "error": frappe.get_traceback(with_context=False)[-500:]})
		frappe.db.commit()
		raise

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


def _step(run, plan, source, step, row):
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
	start = 0
	newest = step.watermark

	while True:
		page = fetch(source, step.source_doctype, filters, start, BATCH)
		if not page:
			break

		for said in page:
			counts["seen"] += 1
			try:
				made = build(said, field_map, plan.name)
				what = _write(plan, step, said, made, run.dry_run)
				counts[what] += 1
			except Exception as raised:
				counts["failed"] += 1
				_issue(run, step, said, raised)
			newest = max(filter(None, (newest, said.get("modified"))), default=newest)

		# Per page, not per run. This is what "resumable" means: a step killed
		# at row nineteen hundred restarts near there rather than at one.
		if not run.dry_run:
			frappe.db.set_value("Import Step", step.name, "watermark", newest,
			                    update_modified=False)
		_mark(row, {**counts, "watermark_to": newest})
		frappe.db.commit()

		if len(page) < BATCH:
			break
		start += BATCH

	if not run.dry_run:
		frappe.db.set_value("Import Step", step.name, "last_run", run.name,
		                    update_modified=False)
	_mark(row, {"status": "Done", **counts, "watermark_to": newest})
	frappe.db.commit()


def _write(plan, step, said: dict, made: dict, dry_run: int) -> str:
	"""Insert or update the one record this source row is, and remember which.

	Through `get_doc` and `save`, never a direct write: an imported Sales
	Invoice that skipped its own controller is a row in a table rather than a
	document, and the ledger behind it does not exist. A migration that beats
	validation has imported the shape of the data and not the data.
	"""
	existing = resolve(plan.name, step.source_doctype, said["name"])

	if dry_run:
		# Built, resolved and validated — and then thrown away. `run_method`
		# rather than `insert`: validation is what a rehearsal is for, and the
		# rest of insert is what it must not do.
		doc = frappe.get_doc({"doctype": step.target_doctype, **made})
		doc.run_method("validate")
		return "updated" if existing else "created"

	if existing and frappe.db.exists(step.target_doctype, existing):
		doc = frappe.get_doc(step.target_doctype, existing)
		doc.update(made)
		doc.save()
		_remember(plan, step, said["name"], doc.name)
		return "updated"

	doc = frappe.get_doc({"doctype": step.target_doctype, **made}).insert()
	_remember(plan, step, said["name"], doc.name)
	return "created"


def _remember(plan, step, source_name: str, target_name: str):
	"""The identity row, written once and read by every link after it."""
	existing = frappe.db.get_value(
		"Import Identity",
		{"plan": plan.name, "source_doctype": step.source_doctype, "source_name": source_name},
		"name",
	)
	if existing:
		frappe.db.set_value("Import Identity", existing,
		                    {"target_name": target_name, "last_seen": now_datetime()},
		                    update_modified=False)
		return

	frappe.get_doc({
		"doctype": "Import Identity",
		"plan": plan.name,
		"source_doctype": step.source_doctype,
		"source_name": source_name,
		"target_doctype": step.target_doctype,
		"target_name": target_name,
		"last_seen": now_datetime(),
	}).insert(ignore_permissions=True)


def _issue(run, step, said: dict, raised: Exception):
	"""One row that would not import, kept whole.

	The payload as well as the error, because the source site will have moved on
	by the time anybody reads this and a message with no row attached is a
	question nobody can answer.
	"""
	frappe.db.rollback()
	frappe.get_doc({
		"doctype": "Import Issue",
		"run": run.name,
		"source_doctype": step.source_doctype,
		"source_name": said.get("name"),
		"error": f"{type(raised).__name__}: {raised}"[:500],
		"payload": frappe.as_json(said),
	}).insert(ignore_permissions=True)
	frappe.db.commit()


def _mark(row, values: dict):
	"""Progress onto the run's own step row, without touching the parent.

	`db_set` on a child rather than saving the run: a run being watched is
	reloaded every few seconds, and saving the parent to move a counter would
	file a Version per page of every step.
	"""
	for key, value in values.items():
		frappe.db.set_value("Import Run Step", row.name, key, value,
		                    update_modified=False)
		row.set(key, value)


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


# --------------------------------------------------------------------------- #
# The one screen
#
# What the person leaving their old system sees: where it is, what will come
# across, and two buttons — rehearse it, then do it. One request rather than
# five, because the panel is one picture and five requests is five spinners.
# --------------------------------------------------------------------------- #


@frappe.whitelist(methods=["GET"])
def console() -> dict:
	"""Everything the import panel draws, in one answer."""
	if not frappe.has_permission("Import Plan", "read"):
		frappe.throw(_("Not yours to see."), frappe.PermissionError)

	sources = frappe.get_all(
		"Import Source",
		fields=["name", "base_url", "api_key", "status", "verified_as",
		        "verified_on", "last_error"],
		order_by="creation asc",
	)

	plans = []
	for plan in frappe.get_all("Import Plan", fields=["name", "source", "is_active"],
	                           order_by="creation asc"):
		doc = frappe.get_doc("Import Plan", plan["name"])
		last = frappe.get_all(
			"Import Run", filters={"plan": plan["name"]},
			fields=["name", "status", "dry_run", "started_on", "finished_on",
			        "total_seen", "total_created", "total_updated", "total_failed"],
			order_by="creation desc", limit=1,
		)
		plans.append({
			**plan,
			"steps": [
				{"source_doctype": s.source_doctype, "target_doctype": s.target_doctype,
				 "enabled": s.enabled, "watermark": s.watermark}
				for s in doc.steps
			],
			"last_run": last[0] if last else None,
			# The whole promise, in one boolean: a plan every step of which has a
			# watermark has been across once, so the next run is a top-up rather
			# than the move.
			"carried": bool(doc.steps) and all(s.watermark for s in doc.steps),
		})

	return {"sources": sources, "plans": plans}


@frappe.whitelist()
def save_source(name: str, base_url: str, api_key: str, api_secret: str | None = None) -> dict:
	"""The customer's own credentials for their own old system.

	The secret is written only when one is given, so an edit to the URL does not
	need it retyped — and it is never sent back out: `console` returns the key
	and never the secret, which is what a Password field is for.
	"""
	known = frappe.db.exists("Import Source", name)
	doc = frappe.get_doc("Import Source", name) if known else frappe.new_doc("Import Source")
	doc.check_permission("write" if known else "create")

	doc.source_name = name
	doc.base_url = base_url
	doc.api_key = api_key
	if api_secret:
		doc.api_secret = api_secret
	doc.save()
	frappe.db.commit()
	return {"name": doc.name}


@frappe.whitelist(methods=["GET"])
def issues(run: str, limit: int = 50) -> list[dict]:
	"""The rows that would not come across, newest first."""
	frappe.get_doc("Import Run", run).check_permission("read")
	return frappe.get_all(
		"Import Issue",
		filters={"run": run, "status": "Open"},
		fields=["name", "source_doctype", "source_name", "error", "payload"],
		order_by="creation desc",
		limit_page_length=cint(limit),
	)


# --------------------------------------------------------------------------- #
# Checking a plan before running it
#
# A fourteen-step field map is a document nobody can read for correctness, and
# the mistakes in one are all quiet: a source field renamed since somebody wrote
# the map, a target field that does not exist on this site's version, a value
# map that covers four of the five values actually in the data, a link resolved
# against a step that runs later.
#
# None of those fails loudly. The first three drop a column, the fourth files an
# issue per row — and all of them are found after the run, in a report somebody
# reads a week later and disbelieves.
#
# So the plan is checked against *both ends* before it is run: the source's own
# metadata over the wire, and this site's own metadata locally. It reads
# everything and writes nothing, which makes it free to run as often as anybody
# likes — and it is what the Check button beside Rehearse does.
# --------------------------------------------------------------------------- #

# How many rows to look at when working out which values a value map has to
# cover. Enough to meet the long tail of a real column, cheap enough to run on
# a button.
SAMPLE = 500


@frappe.whitelist()
def check(plan: str) -> dict:
	"""Everything wrong with a plan that can be known without running it."""
	doc = frappe.get_doc("Import Plan", plan)
	doc.check_permission("read")
	source = frappe.get_doc("Import Source", doc.source)

	# What each step will have made by the time a later one resolves a link
	# against it. Built as the steps are walked, in their declared order, which
	# is exactly the order the run walks them in.
	made = set()
	found = []

	for step in doc.steps:
		if not step.enabled:
			made.add(step.source_doctype)
			continue
		found.append(_check_step(source, doc, step, made))
		made.add(step.source_doctype)

	return {
		"plan": plan,
		"steps": found,
		"problems": sum(len(s["problems"]) for s in found),
		"warnings": sum(len(s["warnings"]) for s in found),
	}


def _check_step(source, plan, step, made: set) -> dict:
	"""One step, against the source's schema and this site's."""
	problems, warnings = [], []

	try:
		field_map = json.loads(step.field_map or "{}")
	except ValueError as raised:
		return {"source_doctype": step.source_doctype, "target_doctype": step.target_doctype,
		        "problems": [f"the field map is not JSON: {raised}"], "warnings": [],
		        "source_rows": None}

	theirs, rows = _their_fields(source, step.source_doctype, problems)
	ours = _our_fields(step.target_doctype, problems)

	for target, rule in field_map.items():
		if not isinstance(rule, dict):
			rule = {"from": rule}

		if ours is not None and target not in ours:
			problems.append(f"{step.target_doctype} has no field `{target}`")

		if "const" in rule:
			continue

		said = rule.get("from")
		if not said:
			problems.append(f"`{target}` names no source field and no constant")
			continue
		if theirs is not None and said not in theirs:
			problems.append(f"{step.source_doctype} has no field `{said}`")

		if rule.get("link") and rule["link"] not in made:
			# Not a warning. A link resolved before its step has run finds
			# nothing on every row, and the run files one issue per record
			# rather than saying the plan is in the wrong order.
			problems.append(
				f"`{target}` resolves against {rule['link']}, which this plan "
				"runs later or not at all"
			)

		# The quiet one: a value map that covers what somebody remembered rather
		# than what is in the column. A warning and not a problem, because
		# `default` may be exactly the intent.
		if "values" in rule and rows:
			unseen = sorted({
				str(row.get(said)) for row in rows
				if row.get(said) not in (None, "") and row.get(said) not in rule["values"]
			})
			if unseen and "default" not in rule:
				warnings.append(
					f"`{said}` also holds {', '.join(unseen[:6])} — "
					"unmapped and with no default, so they cross over as-is"
				)

	return {
		"source_doctype": step.source_doctype,
		"target_doctype": step.target_doctype,
		"problems": problems,
		"warnings": warnings,
		"source_rows": len(rows) if rows is not None else None,
	}


def _their_fields(source, doctype: str, problems: list):
	"""The source's own column names, and a sample of its rows.

	Read off the data rather than off `DocType`/`DocField`: an API user is not
	always allowed to read the schema tables, and every row already carries
	every fieldname. It also means what is checked is what will actually
	arrive.
	"""
	try:
		rows = fetch(source, doctype, [], 0, SAMPLE)
	except Exception as raised:
		problems.append(f"could not read {doctype} from the source: {raised}")
		return None, None

	if not rows:
		problems.append(f"{doctype} has no rows on the source")
		return None, []

	return set(rows[0]), rows


def _our_fields(doctype: str, problems: list):
	"""This site's own column names for the target, or None if it is absent."""
	if not frappe.db.exists("DocType", doctype):
		problems.append(f"{doctype} is not installed on this site")
		return None

	meta = frappe.get_meta(doctype)
	return {df.fieldname for df in meta.fields} | {
		"name", "owner", "creation", "modified", "docstatus", "naming_series",
	}
