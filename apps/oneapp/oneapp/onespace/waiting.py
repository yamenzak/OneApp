"""What is waiting on you, across every space.

`docs/FRAPPE.md` named this as the second half of the workflow gap. The engine
has driven Frappe's workflow properly since the record shell was built —
`docflow.py` reads it through `get_workflow` and `docstate.py` applies
transitions with `apply_workflow` — and the framework has been writing a
`Workflow Action` row per approver on every one of those events the whole time.
Nobody read them back. So approval worked, one record at a time, for somebody
who already knew which record to open, and there was no answer at all to the
question an approver actually asks.

**It decides nothing.** Frappe's own `get_permission_query_conditions` on
`Workflow Action` joins the permitted roles and filters to `status='Open'`, so
a plain `get_list` *is* the scoping: the rows that come back are the ones whose
transition this reader's roles permit, and there is no second reading of who
may approve what. `docflow._transitions` then says which verbs, which is the
same call the record header makes.

**And it writes nothing.** Acting on a row is `spaceview/docstate.workflow_action`,
the endpoint the record header already uses, called with the space and screen
this module placed the row in. An inbox that had its own write path would be a
second door onto the same transition, with its own idea of who may open it.

**A row is placed through `finding.placed`**, so an approval opens on the
screen that shows it. A document no screen shows is still listed — being asked
to approve something is not made untrue by the manifest — but it is marked
`placed: false` and carries no verbs, because there is nowhere to send the
action. The same direction `navigable` fails in: a mistake somebody can see
beats one nobody can.
"""

import frappe

from oneapp.onespace import docflow, finding

#: Rows in one answer. An inbox is a list somebody clears, not a report — past
#: this many the question stops being "what is waiting" and becomes "where do I
#: start", which is a different screen nobody has asked for.
MOST = 50

#: What the framework calls a row nobody has acted on yet.
OPEN = "Open"


def _rows() -> list[dict]:
	"""Every open action addressed to this reader, newest first.

	One `get_list`, and the permission conditions Frappe hangs off this doctype
	are the whole of the narrowing. `status` is filtered there as well as here:
	restating it costs nothing and means this still answers the right question
	if that condition ever changes shape.
	"""
	return frappe.get_list(
		"Workflow Action",
		filters={"status": OPEN},
		fields=["name", "reference_doctype", "reference_name", "workflow_state",
		        "creation"],
		order_by="creation desc",
		limit_page_length=MOST * 2,
	)


def _title(doctype: str, name: str) -> str:
	"""What to call the document, or its id.

	The doctype's own title field, read with `get_value` rather than by loading
	the document: an inbox of fifty would otherwise be fifty `get_doc` calls
	before anything is drawn.
	"""
	try:
		title = frappe.get_meta(doctype).title_field
	except Exception:
		return name
	if not title:
		return name
	from frappe.utils import strip_html_tags

	shown = strip_html_tags(str(frappe.db.get_value(doctype, name, title) or ""))
	return " ".join(shown.split()) or name


def _verbs(doctype: str, name: str) -> list[dict]:
	"""What this reader may do to it, from the state it is in.

	`docflow._transitions`, which is `frappe.model.workflow.get_transitions` —
	the same call the record header makes, filtering by state, by the roles
	held and by each transition's own condition. A document that has gone since
	the row was written answers nothing rather than raising: an inbox is read
	after the fact by definition.
	"""
	try:
		return docflow._transitions(frappe.get_doc(doctype, name))
	except Exception:
		frappe.clear_messages()
		return []


@frappe.whitelist(methods=["GET"])
def mine() -> dict:
	"""Every document waiting on this reader, placed and with its verbs.

	Deduplicated by document rather than by row: the framework writes one
	`Workflow Action` per permitted *role*, so somebody holding two of them is
	asked twice about one expense claim.
	"""
	where = finding.placed()

	found, seen = [], set()
	for row in _rows():
		doctype = row.get("reference_doctype") or ""
		name = str(row.get("reference_name") or "")
		if not doctype or not name or (doctype, name) in seen:
			continue
		seen.add((doctype, name))

		target = where.get(doctype)
		found.append({
			"action": row["name"],
			"doctype": doctype,
			"name": name,
			"title": _title(doctype, name),
			"state": row.get("workflow_state") or "",
			"since": row.get("creation"),
			"placed": bool(target),
			"space": (target or {}).get("space") or "",
			"space_label": (target or {}).get("space_label") or "",
			"screen": (target or {}).get("screen") or "",
			"label": (target or {}).get("label") or doctype,
			"icon": (target or {}).get("icon") or "lucide-inbox",
			# No screen, no verbs: `docstate.workflow_action` is reached through
			# a space and a screen, so an unplaced row has nowhere to send an
			# action even though the reader is the one being asked.
			"verbs": _verbs(doctype, name) if target else [],
		})
		if len(found) >= MOST:
			break

	return {"rows": found, "count": len(found)}


@frappe.whitelist(methods=["GET"])
def how_many() -> int:
	"""Just the number, for the badge.

	Its own endpoint because the badge is asked for on every page and the list
	is asked for on one: this is a single `get_list` of ids, where `mine` loads
	a document per row for its verbs.

	Deduplicated the same way `mine` is, so the badge and the list cannot
	disagree — one document asked of somebody holding two permitted roles is
	one thing waiting on them, and a badge saying two over a list of one is the
	kind of small lie that costs trust in the number.

	`frappe.db.count` is not the cheaper version of this: it does not apply the
	permission query conditions this doctype hangs off itself, so it would
	count the whole workspace's approvals for everybody.
	"""
	return len({(row["reference_doctype"], row["reference_name"])
	            for row in _rows()})
