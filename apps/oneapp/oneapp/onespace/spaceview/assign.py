"""Who a record is assigned to.

Frappe's own model, unchanged: `_assign` is a JSON list of user ids on the
document, and `frappe.desk.form.assign_to` keeps a ToDo beside each one so the
person sees it in their own list. Both halves matter — writing `_assign`
directly would put a face on the record and no task in anybody's day — so the
framework's functions do the writing here and this only decides who may ask.

Which half is the *truth* is the thing to keep straight. The ToDo is; `_assign`
is a cache of it, and the two can come apart. `_shed_ghosts` is what happens
when they have.
"""

import json

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
	from oneapp.onespace.sync import _granted_roles

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

	_shed_ghosts(doctype, name)

	# Who holds this now, read off the ToDos rather than off `_assign`. See
	# `_shed_ghosts` for why those are not the same question.
	held = _holders(doctype, name)

	for one in wanted:
		if one not in held:
			assign_add({"doctype": doctype, "name": name, "assign_to": [one]})
	for one in held:
		if one not in wanted:
			assign_remove(doctype, name, one)

	after = frappe.db.get_value(doctype, name, "_assign")
	return {"assigned": _people(after)}


def _holders(doctype: str, name: str) -> list[str]:
	"""Who has an open assignment on this record.

	An assignment *is* a ToDo — `_assign` on the document is Frappe's own
	denormalisation of them, kept up to date by `ToDo.update_in_reference`. So
	this is the question, and `_assign` is the cache of the answer.
	"""
	return frappe.get_all(
		"ToDo",
		filters={"reference_type": doctype, "reference_name": name, "status": "Open"},
		pluck="allocated_to",
	)


def _shed_ghosts(doctype: str, name: str) -> None:
	"""Drop any name in `_assign` that no open ToDo backs.

	This is not tidiness, it is the bug it was found through. `assign_add`
	skips somebody who is already in `_assign`, and `assign_remove` returns
	without doing anything when it cannot find their ToDo — so a name in
	`_assign` with nothing behind it is a person the record can never be
	assigned to *and* never unassigned from. The control does nothing, twice,
	and says it worked both times.

	`_assign` gets into that state easily: an import that copied the field, a
	patch, a ToDo deleted out from under it. The dev fixture does it on
	purpose — the tasks screen lists ToDos, so seeding through the assignment
	API would put the API's own bookkeeping in the list being seeded — which is
	how this surfaced, and is a fair reproduction of the real thing.
	"""
	named = frappe.parse_json(frappe.db.get_value(doctype, name, "_assign") or "[]")
	named = named if isinstance(named, list) else []
	if not named:
		return

	real = set(_holders(doctype, name))
	if set(named) - real:
		# Written straight rather than through `assign_remove`, which is the
		# whole point: there is no ToDo for it to find. `update_modified` off
		# because dropping a name nobody put there is not an edit to the
		# record — the age on a list row should not move for it.
		frappe.db.set_value(
			doctype, name, "_assign",
			json.dumps([one for one in named if one in real]),
			update_modified=False,
		)
