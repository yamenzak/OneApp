"""OneTask — a door onto the same tasks, from wherever you are standing.

`docs/WORK.md` §12. OneTask is **not** a space and owns no table: it is a dock
window over ERPNext's `Task`, the same rows OneProject's board draws, and
everything it does is something a person could have done by going there. The
point is not going there — capturing a line without leaving the document you
are writing, ticking something off without losing the quotation you are in the
middle of.

Four verbs and one read, and the read is the whole of its state:

  * **mine** — what is assigned to me and is not finished
  * **inbox** — what nobody has placed yet, which on ERPNext's Task is free:
    `project` is optional, so a task with none *is* unplaced
  * **capture** — a line of text becomes one of those inbox tasks
  * **tick** — move it to a Done column, or back out of one
  * and the clock, which is `timing.py`'s and is not repeated here

Nothing here is a second permission model. Every read goes through
`frappe.get_all`, which applies the reader's own, and the write is an ordinary
`insert`. A person whose workspace has no OneProject holds no grant on Task, so
this window shows them nothing — which is why the tile is dark for them rather
than empty.
"""

import frappe
from frappe import _

from oneapp.onetask import states, timing

TASK = "Task"

#: What a row carries. Small on purpose: this is a glance beside your work and
#: not a list screen, so there is no column somebody has to widen a window to
#: read.
FIELDS = ["name", "subject", "project", "custom_state", "priority",
          "exp_end_date", "status"]

#: How many of each. Past this the honest answer is the space, and the window
#: says so rather than scrolling for ever.
MOST = 50

#: The categories that mean it is off somebody's plate.
SETTLED = ("Done", "Cancelled")


@frappe.whitelist(methods=["GET"])
def now() -> dict:
	"""Everything the window draws, in one call.

	One round trip rather than three, because this opens on a keystroke beside
	something else somebody is doing: two lists and a clock arriving separately
	is two reflows of a 380px window.
	"""
	return {
		"mine": _rows({"_assign": ["like", f"%{frappe.session.user}%"]}),
		"inbox": _rows({"project": ["is", "not set"]}),
		"running": timing.running(),
		"done": _done() or "",
	}


def _rows(filters: dict) -> list[dict]:
	"""One list, narrowed to what is still somebody's problem."""
	if not frappe.has_permission(TASK, "read"):
		return []
	found = frappe.get_all(
		TASK,
		filters={
			**filters,
			"status": ["not in", ("Completed", "Cancelled", "Template")],
			"is_template": 0,
		},
		fields=FIELDS,
		order_by="exp_end_date asc, modified desc",
		limit_page_length=MOST,
	)
	# The project's name and not its id: `PROJ-0003` beside a task is the
	# database's answer to a question nobody asked.
	names = {one.project for one in found if one.project}
	titles = dict(frappe.get_all(
		"Project", filters={"name": ["in", list(names)]},
		fields=["name", "project_name"], as_list=True,
	)) if names else {}
	return [{**one, "project_name": titles.get(one.project, "")} for one in found]


@frappe.whitelist(methods=["POST"])
def capture(subject: str) -> dict:
	"""A line of text becomes a task nobody has placed yet.

	No project, which is what makes this cost nothing: ERPNext's Task has an
	optional project, so the inbox is a filter rather than a staging table
	somebody has to empty. And assigned to whoever typed it, through
	`assign_to.add` — the framework's own path and the only one that writes the
	ToDo, the `_assign` cache and the notification together.
	"""
	said = (subject or "").strip()
	if not said:
		frappe.throw(_("A task needs a line of text."))

	task = frappe.get_doc({
		"doctype": TASK,
		"subject": said[:140],
		"custom_state": _first(),
	}).insert()

	from frappe.desk.form import assign_to

	try:
		assign_to.add({
			"doctype": TASK, "name": task.name,
			"assign_to": [frappe.session.user], "description": task.subject,
		})
	except frappe.ValidationError:
		# Already assigned, which a rule may have done on the insert above.
		frappe.clear_last_message()
	return {"name": task.name, "subject": task.subject}


@frappe.whitelist(methods=["POST"])
def tick(name: str, done: int = 1) -> dict:
	"""Off the list, or back on it.

	The state and not the status: `custom_state` is the column a team named and
	ERPNext's `status` is written from its category — `onetask/task.py` — so
	writing the status here would be writing the derived half and watching the
	next save undo it.
	"""
	if not name or not frappe.db.exists(TASK, name):
		frappe.throw(_("There is no task at {0}.").format(name or "—"))

	task = frappe.get_doc(TASK, name)
	task.check_permission("write")
	task.custom_state = _done() if int(done or 0) else _first()
	task.save()
	return {"name": task.name, "state": task.custom_state, "status": task.status}


def _first() -> str:
	"""The column a new task lands in — the first one that is not finished."""
	return _state(("Backlog",)) or _state(("Started",)) or ""


def _done() -> str:
	"""The column a tick moves it to."""
	return _state(("Done",))


def _state(categories: tuple) -> str:
	found = frappe.get_all(
		states.STATE,
		filters={"category": ["in", categories]},
		pluck="name",
		order_by="position asc",
		limit_page_length=1,
	)
	return found[0] if found else ""
