"""Writing a mapped row, with its attachments and its provenance."""

import frappe
from frappe.utils import cint, get_datetime, now_datetime
from .source import attachments, download
from .mapping import resolve


def _write(plan, step, key: str, said: dict, made: dict, source=None,
           field_map: dict | None = None) -> str:
	"""Insert or update the one record this source row is, and remember which.

	Through `get_doc` and `save`, never a direct write: an imported Sales
	Invoice that skipped its own controller is a row in a table rather than a
	document, and the ledger behind it does not exist. A migration that beats
	validation has imported the shape of the data and not the data.
	"""
	existing = resolve(plan.name, step.source_doctype, key)

	if existing and frappe.db.exists(step.target_doctype, existing):
		doc = frappe.get_doc(step.target_doctype, existing)
		doc.update(made)
		doc.save()
		_remember(plan, step, key, doc.name)
		_attach(source, step, said, doc, field_map)
		return "updated"

	doc = frappe.get_doc({"doctype": step.target_doctype, **made}).insert()
	_remember(plan, step, key, doc.name)
	# After the insert, not before: a File names the record it hangs on, and
	# the record has no name until it exists.
	_attach(source, step, said, doc, field_map)
	return "created"


def _attach(source, step, said: dict, doc, field_map: dict | None):
	if source is None:
		return
	_point_at_ours(doc, said, field_map or {}, carry(source, step, said, doc, field_map or {}))


def carry(source, step, said: dict, doc, field_map: dict) -> dict:
	"""Bring one row's files across and hang them on the record we made.

	Two ways to ask, because there are two kinds. A step saying `carry_files`
	wants everything attached over there attached here — the perspectives on a
	project, the scan behind a compliance document. A *rule* saying `"file":
	true` wants one named field that holds a path rather than a value: a party's
	logo, an employee's photograph, and the field has to end up pointing at our
	copy rather than at a URL on a site the customer is about to switch off.

	Answers what it copied, keyed by the path it had over there, so the rules
	can be pointed at the new one.
	"""
	# Two ways a source field names a file. A *rule* with `"file": true` wants
	# the field on this side to end up pointing at our copy; the step's own
	# `carry_file_fields` wants the file and has nowhere to put the path —
	# which is forty-one of their project perspectives, chosen rather than
	# uploaded and so attached to nothing over there, on a doctype ERPNext
	# gives no image field at all.
	wanted = {
		rule["from"] for rule in (field_map or {}).values()
		if isinstance(rule, dict) and rule.get("file") and rule.get("from")
	}
	wanted |= {
		one.strip() for one in
		str(getattr(step, "carry_file_fields", "") or "").split(",") if one.strip()
	}
	named = {said.get(one) for one in wanted} - {None, ""}

	if not cint(getattr(step, "carry_files", 0)) and not named:
		return {}


	# Already here, from a previous run. Matched on the name it had over there,
	# which is what makes a second run a no-op rather than a second copy of
	# every photograph in the company.
	here = {
		row.file_name
		for row in frappe.get_all("File",
		                          filters={"attached_to_doctype": doc.doctype,
		                                   "attached_to_name": doc.name},
		                          fields=["file_name"])
	}

	made = {}
	for one in attachments(source, step.source_doctype, said.get("name")):
		if not cint(getattr(step, "carry_files", 0)) and one["file_url"] not in named:
			continue
		if one["file_name"] in here:
			# Still worth answering: a rule pointing at it needs our URL even
			# on a run that copied nothing.
			made[one["file_url"]] = frappe.db.get_value(
				"File", {"attached_to_doctype": doc.doctype,
				         "attached_to_name": doc.name,
				         "file_name": one["file_name"]}, "file_url")
			continue

		# Assigned and then inserted, rather than reading what `insert` hands
		# back: what this needs is the URL Frappe gave the copy, and that is on
		# the document either way.
		file = frappe.get_doc({
			"doctype": "File",
			"file_name": one["file_name"],
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"is_private": cint(one.get("is_private")),
			"content": download(source, one["file_url"]),
		})
		file.insert(ignore_permissions=True)
		made[one["file_url"]] = file.file_url

	# A field naming a file that is not attached to anything. Which is the
	# ordinary case for a picture chosen rather than uploaded: forty-one of
	# their projects carry a perspective this way, and every one of them would
	# have arrived as a path pointing at a site about to be switched off.
	for path in named - set(made):
		file = frappe.get_doc({
			"doctype": "File",
			"file_name": path.rsplit("/", 1)[-1],
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"is_private": path.startswith("/private/"),
			"content": download(source, path),
		})
		file.insert(ignore_permissions=True)
		made[path] = file.file_url

	return made


def _point_at_ours(doc, said: dict, field_map: dict, files: dict):
	"""Repoint the fields that hold a path at the copy we just made.

	A logo whose URL is on the site the customer is switching off is a broken
	image the week after the migration, and nobody looks at a logo until then.
	"""
	for target, rule in (field_map or {}).items():
		if not (isinstance(rule, dict) and rule.get("file")):
			continue
		if not doc.meta.has_field(target):
			# `check` says so before a run; here it is one row's worth of
			# nothing rather than a refusal, because the file itself did come
			# across and is attached to the record either way.
			continue
		found = files.get(said.get(rule.get("from")))
		if found and doc.get(target) != found:
			doc.db_set(target, found, update_modified=False)


def _remember(plan, step, source_name: str, target_name: str):
	"""The identity row, written once and read by every link after it."""
	existing, was = frappe.db.get_value(
		"Import Identity",
		{"plan": plan.name, "source_doctype": step.source_doctype, "source_name": source_name},
		["name", "target_doctype"],
	) or (None, None)
	if existing and was and was != step.target_doctype:
		# Two steps off one source doctype, both catching this row. Silently
		# rewriting the identity would repoint every link that already resolved
		# through it, so the row fails and the plan's filters get fixed.
		frappe.throw(
			f"{step.source_doctype} {source_name} is already {was} "
			f"{frappe.db.get_value('Import Identity', existing, 'target_name')} in this plan — "
			f"two steps claim it. Narrow one step's filters."
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


def _issue(run, step, said: dict, raised: Exception, held: list | None = None):
	"""One row that would not import, kept whole.

	The payload as well as the error, because the source site will have moved on
	by the time anybody reads this and a message with no row attached is a
	question nobody can answer.

	`held` is a rehearsal: the run it belongs to is about to be rolled back, so
	writing this now would throw it away with everything else.
	"""
	issue = {
		"doctype": "Import Issue",
		"run": run.name,
		"source_doctype": step.source_doctype,
		"source_name": said.get("name"),
		"error": f"{type(raised).__name__}: {raised}"[:500],
		"payload": frappe.as_json(said),
	}
	if held is not None:
		held.append(issue)
		return
	frappe.get_doc(issue).insert(ignore_permissions=True)


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
