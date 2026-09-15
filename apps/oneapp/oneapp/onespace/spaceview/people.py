"""Users as the UI needs them — a name, a face, and nothing else.

Two questions, and the second is why this layer sits above `links`. Who a record
is *assigned to* is a list of ids to resolve. Who is *on this workspace* is a
different question with the same answer shape, and three surfaces ask it: the
assignment control, a Link to User, and anything else that has to offer a person
rather than a record.

Neither is `get_list("User")`. `User` is in the control plane's `NEVER_GRANTED`
— a space handing out the user table is a space handing out the permission
system — so under a space role that answers nothing at all.
"""

import frappe


def _ids(assigned) -> list[str]:
	"""`_assign` — a JSON array of user ids — as a list of ids.

	Frappe stores assignment as JSON on the document and keeps a ToDo beside it.
	Anything else in that column is not an assignment: it is written by the
	framework, but a doctype whose field somebody edited by hand is still a
	doctype we have to render.
	"""
	try:
		ids = frappe.parse_json(assigned or "[]")
	except (TypeError, ValueError):
		# `_assign` is written by the framework and should always be a JSON
		# array. Should is not is: a column edited by hand, or a fixture that
		# put a bare id there, would otherwise take out the whole page rather
		# than one row's faces.
		return []
	if not isinstance(ids, list):
		return []
	return [one for one in dict.fromkeys(ids) if isinstance(one, str) and one]


def _users(ids: list[str]) -> dict[str, dict]:
	"""Those ids as people you can look at, keyed by id.

	Resolved into the same three things every other identity in this product is
	drawn from — a name, a face, and the id underneath — so a stack of
	assignees, a Link cell and the title column are one rendering.

	One query, never one per id, and never one per row: a page of forty cards
	is one lookup over the ids on all of them. A user who no longer exists is
	simply absent from the answer rather than rendering as a blank face —
	`_assign` is not a foreign key and Frappe does not clean it up when an
	account goes.
	"""
	wanted = list(dict.fromkeys(ids))
	if not wanted:
		return {}

	return {
		row["name"]: {
			"value": row["name"],
			"label": row["full_name"] or row["name"],
			"image": row["user_image"],
		}
		for row in frappe.get_all(
			"User",
			filters={"name": ["in", wanted]},
			# `get_all` rather than `get_list`: a name beside a face on a
			# record you can already read is not a directory, and the
			# alternative is a reader seeing "assigned to" with nobody in it.
			fields=["name", "full_name", "user_image"],
		)
	}


def _people(assigned) -> list[dict]:
	"""One document's `_assign`, resolved. In the order the document holds them,
	so the face on the left is the same face on every reload."""
	ids = _ids(assigned)
	found = _users(ids)
	return [found[one] for one in ids if one in found]


def _with_people(rows: list[dict]) -> None:
	"""Who each row is on, in place — one lookup for the page.

	The same shape `_with_links` has and for the same reason. Assignment is the
	one thing on a row that no field carries and that everybody looks for
	first, and the naive version of this is `_people` per row: forty rows is
	forty queries over a table whose ids repeat on almost every one of them.
	"""
	wanted = [_ids(row.pop("_assign", None)) for row in rows]
	found = _users([one for ids in wanted for one in ids])
	for row, ids in zip(rows, wanted):
		row["_assigned"] = [found[one] for one in ids if one in found]


#: A page of people. The bound the assignment control has always had.
PEOPLE_PAGE = 20


def colleagues(query: str = "", limit: int = PEOPLE_PAGE) -> list[dict]:
	"""The workspace's own people, as a picker row each.

	Its own function at its second caller: a **Link to User** asks the same
	question and could not ask it. `User` is in `NEVER_GRANTED` — rightly, a
	space handing out the user table is a space handing out the permission
	system — so `get_list("User")` under a space role returns nothing, and every
	approver field in OnePeople rendered an empty menu. Which meant nobody could be
	given a leave approver, and nobody could be linked to their own login,
	through the product at all.

	The answer is the one this file already worked out: not Frappe's user table,
	but whoever holds a role we granted. See `link_options`.
	"""
	found = frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ["in", _colleagues()]},
		or_filters=(
			{"full_name": ["like", f"%{query}%"], "name": ["like", f"%{query}%"]}
			if query else None
		),
		fields=["name", "full_name", "user_image"],
		limit_page_length=limit,
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
