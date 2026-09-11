"""A change the assistant asked for is now a suggestion of a kind.

`OneSpace Chat Change` could hold one thing: a record save, proposed in a chat
thread. What broke that shape was mail noticing a date and offering to put it
in somebody's diary — see `onespace/ai/actions.py`. So there is one doctype
with a `kind` now, and the record save is the first registered handler rather
than the only thing the table can describe.

Every row carries over, whatever state it is in. An applied one is what the
thread says happened; a discarded one is what somebody said no to; and a
proposal still sitting in `Proposed` is a question nobody answered, which is
exactly the row that would be missed if this only moved the interesting ones.

`space`, `screen`, `docname` and `changes` were four columns because there was
one kind. They fold into the handler's own `payload`, which is what
`kinds.RecordSave` reads back.
"""

import json

import frappe

OLD = "OneSpace Chat Change"
NEW = "OneSpace Suggestion"


def execute():
	if not frappe.db.table_exists(OLD):
		return

	rows = frappe.db.sql(
		f"""select name, session, after_message, state, space, screen, docname,
		           summary, changes, `before`, applied_name, applied_on, error,
		           owner, creation, modified
		    from `tab{OLD}`""",
		as_dict=True,
	)

	for row in rows:
		if frappe.db.exists(NEW, row.name):
			continue
		doc = frappe.get_doc({
			"doctype": NEW,
			"name": row.name,
			"kind": "record.save",
			"state": row.state or "Proposed",
			"summary": row.summary or "",
			"payload": json.dumps({
				"space": row.space or "",
				"screen": row.screen or "",
				"docname": row.docname or "",
				"values": _read(row.changes),
			}),
			"before": row["before"] or "{}",
			# Only where the thread is still there. A chat deleted while one
			# of its cards was open leaves a row pointing at nothing, and a
			# dangling Link is a `LinkValidationError` that would take the
			# whole migration down rather than one card's provenance.
			"session": row.session if _thread(row.session) else "",
			"after_message": row.after_message or "",
			# Nothing to fill in: a chat change was always about the thread it
			# was asked in, and the thread is `session`. `about_*` is for the
			# surfaces that have no session.
			"about_doctype": "",
			"about_name": "",
			"applied_name": row.applied_name or "",
			"applied_on": row.applied_on,
			"error": row.error or "",
		})
		doc.flags.name_set = 1
		doc.insert(ignore_permissions=True, set_name=row.name)
		# The owner is who asked, and `if_owner` is the whole of this
		# doctype's privacy — inserting as whoever runs the migration would
		# hand every card to the administrator.
		frappe.db.set_value(NEW, doc.name, {
			"owner": row.owner, "creation": row.creation, "modified": row.modified,
		}, update_modified=False)

	frappe.delete_doc("DocType", OLD, force=True, ignore_missing=True)
	frappe.db.sql_ddl(f"drop table if exists `tab{OLD}`")
	frappe.clear_cache()


def _thread(session: str) -> bool:
	return bool(session and frappe.db.exists("OneSpace Chat Session", session))


def _read(raw):
	try:
		found = json.loads(raw or "{}")
	except (TypeError, ValueError):
		return {}
	return found if isinstance(found, dict) else {}
