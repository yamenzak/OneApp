"""Who is carrying a task, kept in one place and mirrored into a column.

`docs/WORK.md` §2 is the rule: **an assignment is Frappe's ToDo and stays
Frappe's ToDo.** A task is not a second assignment store, and nothing here
copies one — a ToDo is still the row that puts the task in somebody's own work
list beside everything else they have been asked to look at.

What a ToDo cannot do is be a *column*. A board groups by a field; a list sorts
and filters by one; a dashboard counts by one. None of them can group by a JSON
blob, which is what `_assign` is, and none of them can join a ToDo. So `One
Task.assigned_to` is a mirror of it: written from the assignment, never instead
of it, and on the same save.

Both directions, because both happen:

  * a **rule** assigns — `docs/WORK.md` stage 7, Frappe's Assignment Rule —
    and the board must show the person it landed on;
  * somebody **edits the field** on the form, because it is a field on a form
    and looks like one, and the ToDo must follow or the task is on nobody's
    list while a column says otherwise.

The second is the one that makes this safe to have at all: without it the field
is a lie the first time anybody types in it.
"""

import frappe

#: The doctype this mirrors for. A hook on ToDo fires for every assignment on
#: the site, and all but ours are somebody else's business.
TASK = "One Task"

#: The statuses that mean somebody is still carrying it.
OPEN = ("Open",)


def follow_todo(doc, method=None) -> None:
	"""A ToDo was written or closed: put the task's column back in step.

	Cheap and unconditional rather than clever: the assignment of one task is
	one query and this runs on one row at a time. A ToDo that is not about a
	task returns before touching anything.
	"""
	if (doc.reference_type or "") != TASK or not doc.reference_name:
		return
	if not frappe.db.exists(TASK, doc.reference_name):
		return
	_mirror(doc.reference_name)


def _mirror(task: str) -> None:
	"""Write whoever holds the task onto the task, from the ToDos that say so.

	The *oldest* open assignment wins where there are several, which is the one
	rule that reads right: two people on a task means the first was asked and
	the second was added to help, and a column that flips to the newest name on
	every addition is a column nobody can sort by.
	"""
	found = frappe.get_all(
		"ToDo",
		filters={"reference_type": TASK, "reference_name": task,
		         "status": ["in", OPEN]},
		fields=["allocated_to"],
		order_by="creation asc",
		limit_page_length=1,
	)
	holder = (found[0].get("allocated_to") if found else None) or None
	if frappe.db.get_value(TASK, task, "assigned_to") != holder:
		# `db_set` and not a save: this is a mirror of a fact that is already
		# written, and re-running the task's controller here would re-run the
		# rollups and the plan's slip for a change that moved no date.
		frappe.db.set_value(TASK, task, "assigned_to", holder, update_modified=False)


def follow_field(doc, method=None) -> None:
	"""The field was edited on the form: make the assignment agree.

	Through `assign_to`, which is the framework's own path and the only one
	that writes the ToDo, the `_assign` cache and the notification together.
	Anything else here would be the second store this module exists to refuse.
	"""
	from frappe.desk.form import assign_to

	was = (doc.get_doc_before_save() or {}).get("assigned_to") if not doc.is_new() else None
	now = doc.assigned_to or None
	if was == now:
		return

	if was:
		try:
			# `_remove` and not `remove`: the public one is the whitelisted
			# endpoint and checks the caller's permission on the record, which
			# is right for a button and wrong for a mirror — a rule assigning
			# on somebody's save must not fail because *they* cannot unassign.
			assign_to._remove(doc.doctype, doc.name, was, ignore_permissions=True)
		except Exception:
			# Already closed, or a ToDo somebody deleted by hand. The field is
			# what the reader asked for either way, and a refusal here would
			# fail a save over bookkeeping.
			frappe.clear_last_message()
	if now:
		try:
			assign_to.add({
				"doctype": doc.doctype,
				"name": doc.name,
				"assign_to": [now],
				"description": doc.subject or doc.name,
			})
		except frappe.ValidationError:
			# Frappe refuses a second identical assignment, which is exactly
			# what a rule that has already assigned this person left behind.
			frappe.clear_last_message()
