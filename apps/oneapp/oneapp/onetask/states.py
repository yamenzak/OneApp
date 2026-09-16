"""The columns a board is made of.

`docs/WORK.md` §5: Monday's model is that a board's columns are data, and
writing a `Custom Field` when somebody adds one is a migration per click. So
the *set* is rows — a workspace renames them, recolours them and adds to them —
and what the engine needs from each is a `category`, which is how "is it
finished" has an answer without reading the word somebody chose.

Workspace-wide in this stage, and the bound is honest: a board over a Link
field has no order of its own, so the order its columns open in is declared in
the manifest. Per-project columns wait for the board to learn to read that
order from data, which is one change in one view type rather than a second
table here.
"""

import frappe

STATE = "One Task State"


def ensure(states) -> int:
	"""Write the default columns, once.

	Idempotent by name, and it never edits one that is already there: a
	workspace that renamed a column or moved it should not find it back the way
	it shipped after the next migration. The same rule the manifest's own
	fixtures follow.
	"""
	written = 0
	for name, category, colour, position in states:
		if frappe.db.exists(STATE, name):
			continue
		frappe.get_doc({
			"doctype": STATE, "state_name": name, "category": category,
			"colour": colour, "position": position,
		}).insert(ignore_permissions=True)
		written += 1
	return written


def category_of(state: str) -> str:
	"""What a column means, for the code that has to ask."""
	if not state:
		return "Backlog"
	return frappe.db.get_value(STATE, state, "category") or "Backlog"


#: What a category is, in ERPNext's own words.
#:
#: `docs/WORK.md` §12. A team names a column and the engine needs a category —
#: that much was always true. What is new is that the *status* the category
#: writes is ERPNext's `Task.status`, which their controller, their Gantt and
#: their project rollups all read: a task whose column is called "Signed off"
#: has to be `Completed` over there or the project's percent complete is wrong.
#:
#: Four of their seven, and the three left out are theirs to write rather than
#: ours: `Overdue` is computed from a date, `Template` marks a task that is not
#: work, and `Pending Review` is a word no category means — a team that wants
#: it has a column called it, which is Started until they move it on.
STATUS_OF = {
	"Backlog": "Open",
	"Started": "Working",
	"Done": "Completed",
	"Cancelled": "Cancelled",
}


def status_of(state: str) -> str:
	"""ERPNext's status for the column a task is in."""
	return STATUS_OF.get(category_of(state), "")
