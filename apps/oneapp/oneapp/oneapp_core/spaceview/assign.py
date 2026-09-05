"""Who a record is assigned to.

Frappe's own model, unchanged: `_assign` is a JSON list of user ids on the
document, and `frappe.desk.form.assign_to` keeps a ToDo beside each one so the
person sees it in their own list. Both halves matter — writing `_assign`
directly would put a face on the record and no task in anybody's day — so the
framework's functions do the writing here and this only decides who may ask.
"""

import frappe
from frappe import _
from .resolve import _resolve
from .people import _people


# How many people one picker offers. The same bound the link picker uses, for
# the same reason: a workspace with four hundred users is a scroll, not a list.
ASSIGNEE_PAGE = 20


def _assignable(doctype: str, name: str):
	"""The document, if this person may assign it.

	Read permission and nothing more, deliberately. Assigning is how work
	reaches somebody, and a reader who can see a record and cannot ask a
	colleague to look at it is a reader who sends an email instead. Frappe takes
	the same line — `assign_to.add` checks share/read, not write — and it runs
	its own checks under everything below regardless.
	"""
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	return doc


@frappe.whitelist()
def assignees(space_code: str, screen: str, query: str = "") -> list[dict]:
	"""Who this record could be assigned to.

	Everybody who can sign in to *this workspace*: an enabled account holding
	one of the roles this app manages. Not "everybody with a User row" — a
	disabled account is not a colleague — and not Frappe's own filter either,
	which is the mistake this used to make.

	Frappe's assignment dialog asks for `user_type = "System User"`, because on
	a desk site that separates a colleague from a portal customer. Here it
	separates nobody from everybody: our roles are created with `desk_access`
	off — that is what keeps a workspace out of `/app`, docs/ONEADMIN.md, No desk — and
	Frappe recomputes `user_type` from exactly that flag, so **every member of
	every workspace is a Website User by design**. Copying the desk's filter
	therefore offered the Administrator and nobody else, on every real
	workspace, for as long as assignment has existed.

	So the question is asked the way this product answers every other version
	of it: who holds a role we granted. `_granted_roles` is the same set the
	permission sync reconciles against.

	Bounded by the screen like every other read, so a space code somebody
	guessed does not become a directory of the workspace.
	"""
	resolved = _resolve(space_code, screen)
	if not resolved.get("doctype"):
		return []

	found = frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["in", _colleagues()]},
		or_filters=(
			{"full_name": ["like", f"%{query}%"], "name": ["like", f"%{query}%"]}
			if query else None
		),
		fields=["name", "full_name", "user_image"],
		limit_page_length=ASSIGNEE_PAGE,
		order_by="full_name asc",
	)
	return [
		{"value": row["name"], "label": row["full_name"] or row["name"],
		 "image": row["user_image"]}
		for row in found
	]


def _colleagues() -> list[str]:
	"""Everybody on this workspace, by the only definition this site has.

	A role this app granted. The owner and the members hold one; the
	Administrator holds none of them and is added back, because it is the
	account that sets a workspace up and the one a support session arrives as.

	Guest is excluded by holding no such role, which is the right reason rather
	than a name check.
	"""
	from oneapp.oneapp_core.sync import _granted_roles

	roles = _granted_roles()
	holders = set(
		frappe.get_all("Has Role", filters={"role": ["in", list(roles)]}, pluck="parent")
	) if roles else set()
	holders.add("Administrator")
	return sorted(holders)


@frappe.whitelist(methods=["POST"])
def assign(space_code: str, screen: str, name: str, users: str | list) -> dict:
	"""Set who this record is assigned to, whole.

	A list rather than an add and a remove, because that is what the control
	above it is: a set of people, edited. The difference is worked out here and
	handed to Frappe's own `add` and `remove`, so every assignment still writes
	the ToDo that puts the record in that person's own list — and every
	unassignment still closes it.

	Re-read at the end rather than reported from what was asked for: an id that
	is not a user, one Frappe refuses, or a duplicate all end with the document
	holding something other than the argument, and answering with the argument
	is how a control ends up out of step with the record it edits.
	"""
	resolved = _resolve(space_code, screen)
	doctype = resolved.get("doctype")
	if not doctype:
		frappe.throw(_("There is nothing to assign here."))

	_assignable(doctype, name)

	from frappe.desk.form.assign_to import add as assign_add, remove as assign_remove

	wanted = frappe.parse_json(users) if isinstance(users, str) else (users or [])
	wanted = [one for one in dict.fromkeys(wanted) if one]

	held = frappe.parse_json(
		frappe.db.get_value(doctype, name, "_assign") or "[]")
	held = held if isinstance(held, list) else []

	for one in wanted:
		if one not in held:
			assign_add({"doctype": doctype, "name": name, "assign_to": [one]})
	for one in held:
		if one not in wanted:
			assign_remove(doctype, name, one)

	after = frappe.db.get_value(doctype, name, "_assign")
	return {"assigned": _people(after)}
