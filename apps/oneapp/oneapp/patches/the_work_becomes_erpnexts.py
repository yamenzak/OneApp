"""`One Task` and `One Project` become ERPNext's, and then go.

`docs/WORK.md` §12. The premise those two tables were built on — that a
workspace might carry no ERPNext — is not true of this product, so they were a
second task table and a second project table beside ones every site already
had: a second costing chain, a second billing path, a second accounting
dimension. They are deleted, and a site that has rows in them is a site whose
work has to arrive on the other side first.

Written for a tenant that has real rows and expected to no-op almost
everywhere: the doctypes are days old and carry a dev fixture. That is why it
is careful rather than clever — one pass that copies, one that maps the
columns a team named, one that carries the plan, and then nothing. It never
deletes what it copied: the old tables go with the doctype, and a site where
this half-ran still has both halves to look at.

What is *not* carried, and each for the same reason — ERPNext computes it:
`spent_minutes` (their `actual_time`, from submitted timesheets),
`open_tasks` and `done_tasks` (their `percent_complete`), and `status`, which
`onetask/task.py` writes from the state's category on the first save.
"""

import frappe

#: Ours, on their Task — `oneproject.CUSTOM_FIELDS`.
STATE = "custom_state"
RANK = "custom_rank"
CYCLE = "custom_cycle"
HOLDER = "custom_assigned_to"
KEY = "custom_key"

#: Where a copied row remembers what it was. Not a field: `Bound Record` is the
#: framework's own, so nothing new is added to a schema that is on its way out.
#: A dict in memory is enough because this runs once.


def execute():
	if not frappe.db.table_exists("One Task"):
		return
	if not frappe.db.exists("DocType", "Task"):
		# No ERPNext, which after §12 is not a site this product makes. Leave
		# the rows where they are rather than throwing on a migration: they
		# are still readable from the desk, and somebody has to look.
		return

	projects = _projects()
	tasks = _tasks(projects)
	_plan(tasks)
	frappe.db.commit()


def _projects() -> dict:
	"""Every `One Project` as an ERPNext `Project`, by old name."""
	made = {}
	if not frappe.db.table_exists("One Project"):
		return made

	for row in frappe.db.get_all("One Project", fields=["*"]):
		found = frappe.db.get_value("Project", {"project_name": row.project_name})
		if found:
			made[row.name] = found
			continue
		# Wide enough to hold its own work. ERPNext refuses a task whose end
		# date is after its project's, and a `One Project` never had that rule
		# — so a fixture or a real plan where somebody dated a task past the
		# project would abort the migration on that one row, half-copied. The
		# project's own dates win where they are already the wider.
		starts, ends = _window(row)

		project = frappe.get_doc({
			"doctype": "Project",
			"project_name": row.project_name,
			# Their four words against our five. `Planned` has no counterpart
			# over there and `Open` is the honest one: a project that has not
			# started is still a project nobody has closed.
			"status": {"Done": "Completed", "Cancelled": "Cancelled",
			           "On hold": "Open"}.get(row.status, "Open"),
			"expected_start_date": starts,
			"expected_end_date": ends,
			"notes": row.description,
			KEY: (row.key or "")[:8],
			"custom_manager": row.lead,
			"custom_colour": row.colour or "blue",
		}).insert(ignore_permissions=True, ignore_mandatory=True)
		made[row.name] = project.name
	return made


def _window(row) -> tuple:
	"""A project's dates, widened to cover every task on it."""
	# Two ordered reads rather than a `min()` and a `max()`: Frappe v17 refuses
	# a SQL function written as a string in `fields`, and the dict form it
	# wants back is harder to read than asking twice for something this small.
	first = _edge(row.name, "starts_on", "asc")
	last = _edge(row.name, "due_on", "desc")
	starts = min([one for one in (row.starts_on, first) if one], default=None)
	ends = max([one for one in (row.due_on, last) if one], default=None)
	return starts, ends


def _edge(project: str, field: str, order: str):
	"""The earliest or latest date on this project's tasks."""
	found = frappe.db.get_all(
		"One Task",
		filters={"project": project, field: ["is", "set"]},
		fields=[field], order_by=f"{field} {order}", limit_page_length=1,
	)
	return found[0].get(field) if found else None


def _tasks(projects: dict) -> dict:
	"""Every `One Task` as an ERPNext `Task`, by old name.

	Insert and not `rename`: the two doctypes share no shape and their Task
	names itself from the project's key, which is the point — a copied task
	comes out called `REEM-0004` like one made today.
	"""
	made = {}
	for row in frappe.db.get_all("One Task", fields=["*"], order_by="creation asc"):
		# Idempotent by what a person would recognise, because a patch that
		# threw half way is a patch that runs again on the next migration and
		# a subject on a project is the nearest thing these two tables share.
		# Two tasks with one subject on one project is a real thing and the
		# cost of getting it wrong here is one row not copied, which is
		# visible; the cost the other way is a doubled backlog, which is not.
		already = frappe.db.get_value(
			"Task", {"subject": row.subject,
			         "project": projects.get(row.project) or ""})
		if already:
			made[row.name] = already
			_children(row.name, already)
			continue
		task = frappe.get_doc({
			"doctype": "Task",
			"subject": row.subject,
			"project": projects.get(row.project),
			"priority": row.priority if row.priority in (
				"Low", "Medium", "High", "Urgent") else "Medium",
			"exp_start_date": row.starts_on,
			"exp_end_date": row.due_on,
			"expected_time": (row.estimate_minutes or 0) / 60.0,
			"is_milestone": row.is_milestone or 0,
			"description": row.description,
			"completed_on": row.completed_on,
			"completed_by": row.completed_by,
			STATE: row.state,
			RANK: row.rank,
			CYCLE: row.cycle,
			HOLDER: row.assigned_to,
		}).insert(ignore_permissions=True, ignore_mandatory=True)
		made[row.name] = task.name
		_children(row.name, task.name)
	# The nested set, second: a parent has to exist before a child can name it.
	for was, now in made.items():
		parent = frappe.db.get_value("One Task", was, "parent_task")
		if parent and made.get(parent):
			frappe.db.set_value("Task", made[parent], "is_group", 1,
			                    update_modified=False)
			frappe.db.set_value("Task", now, "parent_task", made[parent],
			                    update_modified=False)
	return made


def _children(was: str, now: str) -> None:
	"""The checklist and the labels, which are the same two tables either side.

	`One Task Step` and `One Task Label` did not move — they are what
	OneProject adds to ERPNext's Task — so this is a reparent rather than a
	copy: the rows keep their ids and change whose they are.
	"""
	for table, field in (("One Task Step", "custom_steps"),
	                     ("One Task Label", "custom_labels")):
		if not frappe.db.table_exists(table):
			continue
		frappe.db.sql(
			f"""update `tab{table}`
			       set parent = %s, parenttype = 'Task', parentfield = %s
			     where parent = %s and parenttype = 'One Task'""",
			(now, field, was),
		)


def _plan(tasks: dict) -> None:
	"""What waits for what, as `Task Depends On` rows.

	Only the edges that are a sequence. `Relates to` was a pointer somebody
	left for somebody and ERPNext has nowhere for it — carrying it into
	`depends_on` would turn a note into a date that pushes other dates, which
	is the one thing that table must not say.

	Written as rows rather than through `task.save()`, and this is the one
	place in the patch where that matters. Saving the parent runs ERPNext's
	`reschedule_dependent_tasks`, which is right when somebody *adds* a
	dependency and wrong here: this is transcribing a plan the team already
	had, and a cascade fired edge by edge walks the last task off the end of
	its own project and is refused there. The dates being carried are the
	dates that were true; the slip belongs to the next real edit.
	"""
	if not frappe.db.table_exists("One Task Link"):
		return
	for row in frappe.db.get_all(
		"One Task Link",
		filters={"parenttype": "One Task", "kind": "Blocked by"},
		fields=["parent", "task"],
	):
		waiting, after = tasks.get(row.parent), tasks.get(row.task)
		if not (waiting and after):
			continue
		if frappe.db.exists("Task Depends On", {"parent": waiting, "task": after}):
			continue
		edge = frappe.new_doc("Task Depends On")
		edge.update({
			"task": after,
			"subject": frappe.db.get_value("Task", after, "subject"),
			# The project their own reschedule keys on, and which nothing in
			# ERPNext ever writes — `onetask/task.py` fills it on a save and
			# this is the same line, by hand.
			"project": frappe.db.get_value("Task", waiting, "project"),
			"parent": waiting,
			"parenttype": "Task",
			"parentfield": "depends_on",
			"idx": _next(waiting),
		})
		edge.name = frappe.generate_hash(length=10)
		edge.db_insert()
		_denormalise(waiting)


def _next(task: str) -> int:
	"""The next row number on this task's `depends_on` table."""
	return len(frappe.db.get_all(
		"Task Depends On", filters={"parent": task, "parenttype": "Task"})) + 1


def _denormalise(task: str) -> None:
	"""`Task.depends_on_tasks`, which their controller keeps as a string.

	Written here because the rows went in without a save. It is a cache of the
	table beside it and nothing reads it but their own report, so the cost of
	leaving it stale is small and the cost of writing it is one update.
	"""
	names = frappe.db.get_all(
		"Task Depends On", filters={"parent": task, "parenttype": "Task"},
		pluck="task",
	)
	frappe.db.set_value("Task", task, "depends_on_tasks",
	                    ",".join([one for one in names if one]) + ("," if names else ""),
	                    update_modified=False)
