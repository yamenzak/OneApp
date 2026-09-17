"""OneProject — the work, the schedule and the hours behind it.

Read `docs/ERP-SPACES.md` first: it is the argument for cutting ERPNext into
three spaces rather than shipping it whole, and this is the first of them.

Everything here is over a doctype ERPNext already ships. Nothing is invented,
because a project, a task and a timesheet are solved problems and re-solving
them would be a second schema for a workspace to keep in step. What is ours is
**the presentation**: which of the module's sixteen doctypes a person is shown,
which of them are a place to go and work rather than a table to maintain, and —
the part the desk never had — what each screen opens *as*.

That last one is most of the difference. ERPNext gives every doctype a list and
the same form under it, so a portfolio, a backlog and a month of hours are three
lists that differ only in their columns. Here the portfolio opens as a board of
projects by state, the backlog opens as a board of tasks, the schedule opens as
a Gantt, the hours open as a calendar, and every one of those screens carries a
dashboard of its own numbers — measured over the rows the screen already
narrows to, so the chart and the list can never disagree.

**Generally available.** This is not one company's system: it says Project and
Task rather than anybody's house words, and it has to survive people who do not
work the way the first customer does.
"""

import json

SPACE = {
	"space_code": "oneproject",
	"space_label": "OneProject",
	"module": "OneProject",
	"role_name": "OneSpace Project",
	# Every doctype below is ERPNext's. A site without it is a site where every
	# screen here is empty, and `entitlements/apps.py` refuses the grant with
	# the app named rather than succeeding into that.
	"requires_apps": "erpnext",
	"icon": "lucide-briefcase",
	"brand": "oneproject",
	"sort_order": 40,
	# Ships Restricted like everything else; an operator turns it on for the
	# marketplace. `install()` writes this only on the way in, so the switch
	# stays where the operator put it.
	"availability": "Restricted",
	"description": "Projects, the work inside them, and the hours against it.",
	# Light, because a Gantt and a board are dense and a dark ground under a
	# hundred bars is a screen people squint at. The accent is a working blue —
	# it moves the solid buttons, the tab indicator and the progress fill, which
	# on this space is mostly the progress fill.
	"theme": json.dumps({
		"mode": "light",
		"accent": "#3f5bd9",
		"radius": "soft",
	}),
}

# --------------------------------------------------------------------------- #
# The two jobs
#
# A project team is two kinds of person and pretending otherwise is how every
# member of a workspace ends up able to close somebody else's project. Somebody
# *does the work* — picks up tasks, moves them, logs hours against them — and
# somebody *runs the portfolio*, which is the seat that decides what a project
# is, what it is worth and when it is finished.
#
# Two and not three, because there is no third honest one. A finance seat would
# be a different space's, and a client seat is somebody who is not a member of
# this workspace at all.
# --------------------------------------------------------------------------- #
ROLES = [
	{
		"role_key": "member",
		"label": "Member",
		"is_default": 1,
		"description": "Do the work: pick up tasks, move them, and log the "
		               "hours against them. Reads the portfolio and changes "
		               "nothing about it.",
	},
	{
		"role_key": "manager",
		"label": "Manager",
		"description": "Run the portfolio — open and close projects, set what "
		               "they are worth and when they are due, and keep the "
		               "types, templates and rates behind them.",
	},
]

# Four parts, not three: the fourth is the role the grant belongs to, and no
# fourth part means every role in the space. Read it as two columns — a member
# gets everything with no role named, and the manager adds one column on top.
# `sync.sync_permissions` keeps the wider of two rows for one doctype, so the
# repeats below are deliberate rather than a mistake.
DOCTYPES = [
	# ----- Everybody ------------------------------------------------------ #
	#
	# The portfolio, read. A member needs to see a project to log time against
	# it, and needs to see nothing else about it.
	("Project", "Read", 0),
	# The work itself, at Manage: a task is the one record in this space a
	# member both makes and finishes, and `Manage` is what lets it be deleted
	# when it turns out to be a duplicate of the one beside it.
	("Task", "Manage", 0),
	# Their own hours. `if_owner`, so a member files and submits their own
	# timesheet and cannot read the person next to them's — which is the one
	# place in this space where a record is genuinely private.
	("Timesheet", "Manage", 1),
	# The five tables of ours that ERPNext's Task hangs off — `docs/WORK.md`
	# §12. A member works inside the columns, labels and cycles a lead set;
	# what they write is their own task's checklist and which labels are on it.
	("One Task State", "Read", 0),
	("One Label", "Read", 0),
	("One Cycle", "Read", 0),
	("One Task Step", "Write", 0),
	("One Task Label", "Write", 0),
	# The masters every screen resolves a link against. Read, because picking a
	# type is not permission to invent one.
	("Project Type", "Read", 0),
	("Activity Type", "Read", 0),
	("Task Type", "Read", 0),
	("Project Template", "Read", 0),
	("Company", "Read", 0),
	("Customer", "Read", 0),
	("Department", "Read", 0),
	("Cost Center", "Read", 0),
	("Currency", "Read", 0),
	("Holiday List", "Read", 0),
	# What has been billed against a project, read and never written. This
	# space reads the money; it does not do the money — see the Invoices screen
	# and its `hide_new`.
	("Sales Invoice", "Read", 0),
	# The engine's own. A screen that cannot save a view is a screen people stop
	# using by the second week; `if_owner`, so a member's saved views are theirs.
	("OneSpace Saved View", "Write", 1),

	# ----- Manager -------------------------------------------------------- #
	("Project", "Manage", 0, "manager"),
	# Every timesheet rather than their own: signing off somebody's hours is
	# most of what this seat is for, and it cannot be done through a filter that
	# hides them.
	("Timesheet", "Manage", 0, "manager"),
	("Project Type", "Write", 0, "manager"),
	("Activity Type", "Write", 0, "manager"),
	("Task Type", "Write", 0, "manager"),
	("Project Template", "Write", 0, "manager"),
	# What the board is made of, and the vocabulary a workspace works in:
	# renaming a column under a team mid-sprint is a manager's decision.
	("One Task State", "Write", 0, "manager"),
	("One Label", "Write", 0, "manager"),
	("One Cycle", "Write", 0, "manager"),
]

#: The columns a workspace starts with, and the ones every board opens in.
#:
#: Four, because four is what a board needs to be a board — and because a fifth
#: is the first thing a team argues about, which is a decision they should have
#: rather than one we make for them. Each carries the category ERPNext's own
#: `status` is written from: `docs/WORK.md` §12.
STATES = [
	("Backlog", "Backlog", "gray", 0),
	("In progress", "Started", "blue", 1),
	("In review", "Started", "amber", 2),
	("Done", "Done", "green", 3),
]

#: The order a board draws them in is no longer declared here.
#:
#: `columns_from` reads it off `One Task State.position`, so a workspace that
#: renames a column or moves one does it by editing a row and every board
#: follows — `docs/ONECRM.md` stage 1 is where that came from, and it closes
#: the "per-project columns" item `onetask/README.md` §4 has been carrying.

# --------------------------------------------------------------------------- #
# The schema its screens read
#
# Two fields, and both are a distinction every portfolio makes and ERPNext has
# no column for.
#
# `status` is Open / On hold / Completed / Cancelled, which says whether a
# project is *running* — and the question anybody actually opens a portfolio to
# ask is whether the running ones are *all right*. Those are different
# questions and a project can be Open and in trouble, so the board that matters
# cannot be drawn off `status`.
#
# The second is smaller and worse: ERPNext's Project has a `users` child table
# and no single person who runs it, so a portfolio list has no "whose is this"
# column and the answer lives in a grid you have to open the record to read.
#
# Applied by the tenant sync the first time it sees the space and never again,
# exactly as a naming series is — so a workspace that widens one keeps it.
# --------------------------------------------------------------------------- #

# The three words a status meeting actually uses. Ordered worst-first on
# purpose: SQL sorts a Select alphabetically, and "At risk" before "Off track"
# before "On track" is alphabetical *and* urgent, which means a list ordered by
# this field leads with the projects somebody has to do something about.
HEALTH = [
	"At risk",
	"Off track",
	"On track",
]

#: The colours a project may be painted, which is the set every other colour
#: control in this product offers — `One Task State.colour` and `One Label`.
COLOURS = "gray\nblue\ngreen\namber\nred\nviolet\ncyan\norange\npink"

# --------------------------------------------------------------------------- #
# What ERPNext's Projects module has no notion of
#
# `docs/WORK.md` §12. This space is ERPNext's Projects the way OnePeople is
# Frappe HR: their Project is the record, their Task is the unit of work, their
# Timesheet is the time, and *nothing here duplicates any of them*. What is
# added is the five things their Task cannot express and the two their Project
# cannot — each one a field, in the shape `custom_checkin_networks` is.
#
# The one that carries the argument is `custom_state`. ERPNext's `status` is
# seven fixed words and three are machinery — Template, Overdue, Pending
# Review — so a team that wants a Design review column cannot have one. A state
# is a row (`One Task State`), it carries a category, and `status` stays
# ERPNext's, written from that category on save: one word for the team, one for
# the code that has to ask whether a thing is finished.
# --------------------------------------------------------------------------- #
CUSTOM_FIELDS = [
	{"dt": "Task", "fieldname": "custom_state", "label": "State",
	 "fieldtype": "Link", "options": "One Task State", "insert_after": "status",
	 "in_list_view": 1,
	 "description": "The column this is in, which a team names. ERPNext's "
	                "Status is seven fixed words and three of them are "
	                "machinery; this is a row, and Status is written from its "
	                "category."},
	{"dt": "Task", "fieldname": "custom_assigned_to", "label": "Assigned to",
	 "fieldtype": "Link", "options": "User", "insert_after": "custom_state",
	 "in_list_view": 1,
	 "description": "Who is carrying it. A mirror of Frappe's own assignment "
	                "and never a second store — `onetask/assignment.py` — "
	                "because a board groups by a field and `_assign` is a JSON "
	                "blob nothing can group by."},
	{"dt": "Task", "fieldname": "custom_rank", "label": "Rank",
	 "fieldtype": "Data", "insert_after": "custom_assigned_to", "hidden": 1,
	 "description": "Where it sits in its column, as a string that sorts. "
	                "Fractional, so dragging one card rewrites one row rather "
	                "than the whole column — `onetask/ranking.py`."},
	{"dt": "Task", "fieldname": "custom_cycle", "label": "Cycle",
	 "fieldtype": "Link", "options": "One Cycle", "insert_after": "project",
	 "description": "The window of time a team pulled this into, where they "
	                "work in them. Not a second container — the project is the "
	                "container."},
	{"dt": "Task", "fieldname": "custom_labels", "label": "Labels",
	 "fieldtype": "Table MultiSelect", "options": "One Task Label",
	 "insert_after": "priority",
	 "description": "What a board filters by. ERPNext has a type per task and "
	                "no way to say a task is two things at once."},
	{"dt": "Task", "fieldname": "custom_steps", "label": "Checklist",
	 "fieldtype": "Table", "options": "One Task Step",
	 "insert_after": "description",
	 "description": "Three lines and a tick, which is not three sub-tasks. "
	                "Sub-tasks are `parent_task`, and a backlog fills with "
	                "noise when a checklist has to be one."},
	{"dt": "Project", "fieldname": "custom_key", "label": "Key",
	 "fieldtype": "Data", "length": 8, "insert_after": "project_name",
	 "description": "Two to five letters, upper case. A task on this project "
	                "is named after it — REEM-14 — because that is what people "
	                "say to each other and TASK-00042 is not."},
	{"dt": "Project", "fieldname": "custom_colour", "label": "Colour",
	 "fieldtype": "Select", "options": COLOURS, "default": "blue",
	 "insert_after": "custom_manager",
	 "description": "The dot beside it on a board and in a list."},
	{"dt": "Project", "fieldname": "custom_health", "label": "Health",
	 "fieldtype": "Select", "options": "\n" + "\n".join(HEALTH),
	 "insert_after": "status", "default": "On track",
	 "description": "Whether a running project is all right. ERPNext's status "
	                "says whether it is running, which is a different question "
	                "— a project can be Open and in trouble."},
	{"dt": "Project", "fieldname": "custom_manager", "label": "Project manager",
	 "fieldtype": "Link", "options": "User", "insert_after": "custom_health",
	 "description": "Who runs it. ERPNext has a table of users on a project "
	                "and no single owner, so a portfolio list had no column "
	                "for the first thing anybody asks about a row."},
]

#: The Project Type OnePeople stamps on an onboarding or an exit checklist, which
#: this space's projects screen leaves out. Mirrors `onehr.boarding.BOARDING`;
#: `tests/test_manifests.py` keeps the two in step.
BOARDING_PROJECTS = "Employee boarding"

#: And the Task Type stamped on each of its steps, which the work screens leave
#: out for the same reason and by the same `!=`. Mirrors `onehr.boarding.BOARDING`
#: too; the same guard keeps all three in step.
#:
#: Only visible once this space moved onto ERPNext's own Task: "Return the
#: laptop" is not delivery work, and twelve induction steps in a None column on
#: the quarter's board is the projects complaint one level down.
BOARDING_TASKS = "Employee boarding"

#: What the three task screens all say: not a template — ERPNext stores a
#: project template as Tasks with a status of Template — and not a checklist
#: step.
NOT_A_CHORE = {"is_template": 0, "type": ["!=", BOARDING_TASKS]}


SCREENS = [
	{
		# The front page: what this space is about, in the four lists somebody
		# opening it in the morning actually wants. Every block is another
		# screen of this space — `onespace/homepage.py` — so a block draws that
		# screen's own columns and is checked where every list is checked, and
		# a block whose screen this reader cannot open is not sent at all.
		"screen": "home", "label": "Home", "singular": "Day",
		"icon": "lucide-layout-grid",
		"component": "home",
		"view_settings": json.dumps({"home": {"blocks": ["projects", "tasks", "milestones", "invoices"]}}),
	},
	{
		# The spine. Everything else in this space hangs off a project, and it
		# is the first thing anybody opens.
		#
		# Five ways to look at one list, which is the whole argument for the
		# view types: the same rows are a board when you are running a status
		# meeting, a Gantt when you are explaining a slip, a dashboard when
		# somebody asks what the quarter looks like, and a list when you are
		# hunting for one project by name.
		"screen": "projects", "label": "Projects", "singular": "Project",
		"icon": "lucide-briefcase", "document_type": "Project",
		"fields": "project_name,custom_health,status,customer,custom_manager,"
		          "expected_end_date,percent_complete,estimated_costing",
		"order_by": "expected_end_date asc",
		# Not the induction checklists. HRMS builds an onboarding or an exit
		# out of a Project and a Task per step, so without this somebody's
		# first week sits in the list beside a client's building — see
		# `onehr/boarding.py`, which types them. A Frappe `!=` keeps the rows
		# that have no type at all, which is every project anybody made.
		"filters": json.dumps({"project_type": ["!=", BOARDING_PROJECTS]}),
		"view_types": "board,list,gantt,calendar,dashboard",
		# The badge beside a project's name is its health and not its status:
		# a reader scanning a list already knows the open ones are open.
		"status_field": "custom_health",
		"field_icons": json.dumps({
			"custom_health": "lucide-flag",
			"percent_complete": "lucide-chart-pie",
		}),
		"view_settings": json.dumps({
			"board": {
				# Columns of health, cards carrying the three facts a status
				# meeting reads off them.
				"column_field": "custom_health",
				"card_fields": ["customer", "expected_end_date", "percent_complete"],
			},
			"gantt": {
				"start_field": "expected_start_date",
				"end_field": "expected_end_date",
				"progress_field": "percent_complete",
			},
			"calendar": {
				"start_field": "expected_start_date",
				"end_field": "expected_end_date",
			},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Projects", "width": 3},
				{"kind": "number", "label": "Budgeted", "aggregate": "sum",
				 "field": "estimated_costing", "width": 3},
				{"kind": "number", "label": "Spent", "aggregate": "sum",
				 "field": "total_costing_amount", "width": 3},
				{"kind": "number", "label": "Billed", "aggregate": "sum",
				 "field": "total_billed_amount", "width": 3},
				{"kind": "donut", "label": "Health", "group_by": "custom_health",
				 "width": 4},
				{"kind": "donut", "label": "Status", "group_by": "status", "width": 4},
				{"kind": "bar", "label": "By type", "group_by": "project_type",
				 "width": 4},
				# The one plot on this screen a list could never be: budget
				# against a customer, which is the question a portfolio is for
				# and which nobody can answer by reading a column of numbers.
				{"kind": "bar", "label": "Budget by client", "group_by": "customer",
				 "aggregate": "sum", "field": "estimated_costing",
				 "horizontal": True, "width": 12},
			]},
			# Opening a project is not opening a form. It is what it is worth,
			# what it has cost, how far along it is and who is due what — and
			# under that, every task, hour and invoice written against it. See
			# `onespace/showcase.py`.
			"showcase": {
				# The hero is a dark band with or without one — `images` only
				# decides whether a picture filed against the record fills it.
				# So it costs nothing on a project nobody has photographed and
				# is the whole top of the page on one somebody has, which is
				# most construction and refurbishment work.
				"images": True,
				"eyebrow_field": "customer",
				"badge_field": "custom_health",
				"facts": [
					{"field": "estimated_costing", "label": "Budget"},
					{"field": "total_costing_amount", "label": "Spent"},
					{"field": "percent_complete", "label": "Complete"},
					{"field": "expected_end_date", "label": "Due"},
				],
				# Each names a screen in this space and the field on it pointing
				# back here, so the columns are the ones that screen shows and
				# the permissions are the ones it already checks.
				"tabs": [
					{"screen": "tasks", "field": "project",
					 "label": "Tasks", "icon": "lucide-layout-grid"},
					{"screen": "milestones", "field": "project",
					 "label": "Milestones", "icon": "lucide-map-pin"},
					{"screen": "time", "field": "parent_project",
					 "label": "Time", "icon": "lucide-clock"},
					{"screen": "invoices", "field": "project",
					 "label": "Invoices", "icon": "lucide-receipt"},
				],
			},
		}),
	},
	{
		# The work in flight. A board first, because a task list that opens as
		# a list is a backlog and a task list that opens as a board is a
		# standup.
		#
		# `is_template` is filtered out and that is not tidiness: ERPNext keeps
		# project templates as Tasks with a status of Template, so an unfiltered
		# board of this doctype has a seventh column holding things nobody can
		# do, sitting between Pending Review and Completed.
		"screen": "tasks", "label": "Tasks", "singular": "Task",
		"icon": "lucide-layout-grid", "document_type": "Task",
		"fields": "subject,custom_state,custom_assigned_to,priority,project,"
		          "custom_cycle,exp_end_date,progress,custom_labels",
		"order_by": "exp_end_date asc",
		"filters": json.dumps(NOT_A_CHORE),
		"view_types": "board,list,gantt,calendar,tree,dashboard",
		"status_field": "status",
		"field_icons": json.dumps({
			"status": "lucide-flag",
			"priority": "lucide-chart-line",
		}),
		"view_settings": json.dumps({
			# Columns a team names, not ERPNext's seven words — `custom_state`
			# is a Link to `One Task State` and `status` is written from its
			# category. A Link column has no order of its own, so the order is
			# declared and the set is data: a workspace may rename, recolour
			# and add to it. `docs/WORK.md` §12.
			"board": {
				"column_field": "custom_state",
				"columns_from": {"order_by": "position asc, name asc"},
				"card_fields": ["custom_assigned_to", "project", "exp_end_date"],
			},
			# The plan. ERPNext already stores what a task waits for — a `Task
			# Depends On` row per edge — so the arrows are theirs and the only
			# thing declared here is where to read them. `is_milestone` is
			# theirs too, and draws as a diamond.
			"gantt": {
				"start_field": "exp_start_date",
				"end_field": "exp_end_date",
				"progress_field": "progress",
				"depends_field": "depends_on",
				"milestone_field": "is_milestone",
			},
			"calendar": {
				"start_field": "exp_start_date",
				"end_field": "exp_end_date",
			},
			# A task can hang under a task, and until there is a tree of them
			# the only way to see a breakdown is to read the parent column.
			"tree": {"parent_field": "parent_task", "label_field": "subject"},
			"tags": ["priority", "custom_state", "custom_cycle"],
			"showcase": {
				"tabs": [
					{"screen": "tasks", "field": "parent_task",
					 "label": "Sub-tasks", "icon": "lucide-list-tree"},
					# The plan read backwards: what is waiting on this one.
					# ERPNext's own dependency table, through the engine's
					# child-table filter — no second store and no endpoint.
					{"screen": "tasks", "field": "depends_on.task",
					 "label": "Blocks", "icon": "lucide-git-branch"},
				],
			},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Tasks", "width": 3},
				{"kind": "number", "label": "Planned hours", "aggregate": "sum",
				 "field": "expected_time", "width": 3},
				{"kind": "number", "label": "Actual hours", "aggregate": "sum",
				 "field": "actual_time", "width": 3},
				{"kind": "number", "label": "Average progress", "aggregate": "avg",
				 "field": "progress", "suffix": "%", "width": 3},
				{"kind": "donut", "label": "Where they stand", "group_by": "status",
				 "width": 4},
				{"kind": "donut", "label": "Priority", "group_by": "priority",
				 "width": 4},
				{"kind": "bar", "label": "By type", "group_by": "type", "width": 4},
				# Open work per project, stacked by where each task stands. The
				# plot a delivery lead opens on a Monday.
				{"kind": "bar", "label": "By project", "group_by": "project",
				 "series": "status", "stacked": True, "horizontal": True,
				 "width": 12},
			]},
		}),
	},
	{
		# The reader's own, beside the whole board and made from it —
		# `dict(TASKS, …)` is not used here only because the declaration is
		# long; what matters is that it is the same doctype, the same columns
		# and the same view types, narrowed by one filter.
		#
		# `_assign` and not a field of ours: an assignment is Frappe's ToDo and
		# the column beside it is a JSON array, so "mine" is a `like` against
		# it — `onespace/mine.py` puts the wildcards on.
		"screen": "my-tasks", "label": "My tasks", "singular": "Task",
		"icon": "lucide-user-round", "document_type": "Task",
		"fields": "subject,custom_state,priority,project,exp_end_date,"
		          "progress,custom_labels",
		"order_by": "exp_end_date asc",
		"filters": json.dumps({"_assign": ["like", "@me"], **NOT_A_CHORE}),
		"view_types": "board,list,calendar,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {
				"column_field": "custom_state",
				"columns_from": {"order_by": "position asc, name asc"},
				"card_fields": ["project", "exp_end_date", "priority"],
			},
			"calendar": {
				"start_field": "exp_start_date", "end_field": "exp_end_date",
				"diary": True, "about": {"_assign": "@me"},
			},
			"tags": ["priority", "custom_state"],
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Tasks", "width": 3},
				{"kind": "donut", "label": "Where they stand",
				 "group_by": "custom_state", "width": 4},
				{"kind": "donut", "label": "Priority", "group_by": "priority",
				 "width": 4},
			]},
		}),
	},
	{
		# What nobody has placed yet. Not a separate store and not a flag:
		# ERPNext's Task has an optional project, so a task with none *is*
		# unplaced — which is what makes the applet's capture box cost nothing.
		"screen": "inbox", "label": "Inbox", "singular": "Task",
		"icon": "lucide-inbox", "document_type": "Task",
		"fields": "subject,custom_state,custom_assigned_to,priority,"
		          "exp_end_date,custom_labels",
		"order_by": "creation desc",
		"filters": json.dumps({"project": ["is", "not set"], **NOT_A_CHORE}),
		"view_types": "list,board",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {
				"column_field": "custom_state",
				"columns_from": {"order_by": "position asc, name asc"},
				"card_fields": ["custom_assigned_to", "exp_end_date"],
			},
			"tags": ["priority"],
		}),
	},
	{
		# The windows a team pulls work into, where they work in them. Not a
		# second container — the project is the container — so a cycle holds no
		# tasks: the tasks say which cycle they are in.
		"screen": "cycles", "label": "Cycles", "singular": "Cycle",
		"icon": "lucide-calendar", "document_type": "One Cycle",
		"fields": "cycle_name,status,starts_on,ends_on,goal",
		"order_by": "starts_on desc",
		"view_types": "list,board,calendar",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {
				"column_field": "status",
				"arrangement": {"order": ["Planned", "Running", "Done"]},
				"card_fields": ["starts_on", "ends_on"],
			},
			"calendar": {"start_field": "starts_on", "end_field": "ends_on"},
			"tags": ["status"],
			"showcase": {
				"tabs": [
					{"screen": "tasks", "field": "custom_cycle",
					 "label": "Work", "icon": "lucide-layout-grid"},
				],
			},
		}),
	},
	{
		# The dates a client asks about, which are a handful of the tasks and
		# never the rest of them. ERPNext has the flag and no way to look at it:
		# `is_milestone` is a checkbox on a form and nothing in the desk reads
		# it back.
		#
		# A calendar first, because a milestone is a date before it is a record.
		"screen": "milestones", "label": "Milestones", "singular": "Milestone",
		"icon": "lucide-map-pin", "document_type": "Task",
		"fields": "subject,project,status,exp_end_date,progress",
		"order_by": "exp_end_date asc",
		"filters": json.dumps({"is_milestone": 1, **NOT_A_CHORE}),
		"view_types": "calendar,list,board",
		"status_field": "status",
		"view_settings": json.dumps({
			# One date and no span. A milestone that lasted a fortnight would
			# not be one, so there is deliberately no `end_field` here and
			# therefore deliberately no Gantt.
			# A milestone belongs to whoever is carrying it, which on a task
			# is the assignment. Everybody else sees it in the Everyone lens,
			# where a milestone is exactly the kind of thing that belongs.
			"calendar": {"start_field": "exp_end_date", "diary": True,
			             "about": {"_assign": "@me"}},
			"board": {"card_fields": ["project", "exp_end_date"]},
		}),
	},
	{
		# Hours, as a fortnight rather than as a table. A timesheet is a span
		# with a start and an end, which is the one shape a list renders worst
		# and a calendar renders for free.
		#
		# The limit worth stating: every number here is the *sheet's*, because
		# the hours themselves live in a child table and no chart in this
		# engine can reach one. So this screen answers who logged how much and
		# how much of it was billable, and "hours by project this month" is a
		# question it cannot answer — see `docs/ERP-SPACES.md`, §C4.
		"screen": "time", "label": "Time", "singular": "Timesheet",
		"icon": "lucide-clock", "document_type": "Timesheet",
		"fields": "employee_name,parent_project,start_date,end_date,total_hours,"
		          "total_billable_hours,per_billed,status",
		"order_by": "start_date desc",
		"view_types": "calendar,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "start_date", "end_field": "end_date"},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Timesheets", "width": 3},
				{"kind": "number", "label": "Hours", "aggregate": "sum",
				 "field": "total_hours", "width": 3},
				{"kind": "number", "label": "Billable hours", "aggregate": "sum",
				 "field": "total_billable_hours", "width": 3},
				{"kind": "number", "label": "Billed", "aggregate": "sum",
				 "field": "total_billed_amount", "width": 3},
				{"kind": "bar", "label": "Hours by person", "group_by": "employee",
				 "aggregate": "sum", "field": "total_hours", "horizontal": True,
				 "width": 6},
				{"kind": "bar", "label": "Hours by project",
				 "group_by": "parent_project", "aggregate": "sum",
				 "field": "total_hours", "horizontal": True, "width": 6},
				{"kind": "line", "label": "Hours a month", "group_by": "start_date",
				 "grain": "month", "aggregate": "sum", "field": "total_hours",
				 "width": 12},
			]},
		}),
	},
	{
		# What has been billed against the work. Read only and `hide_new`,
		# which is the honest shape of it: a project team needs to know whether
		# an invoice went out and is not the seat that raises one.
		"screen": "invoices", "label": "Invoices", "singular": "Invoice",
		"icon": "lucide-receipt", "document_type": "Sales Invoice",
		"fields": "customer,project,posting_date,due_date,grand_total,"
		          "outstanding_amount,status",
		"order_by": "posting_date desc",
		"hide_new": 1,
		"view_types": "list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Invoices", "width": 4},
				{"kind": "number", "label": "Billed", "aggregate": "sum",
				 "field": "grand_total", "width": 4},
				{"kind": "number", "label": "Outstanding", "aggregate": "sum",
				 "field": "outstanding_amount", "width": 4},
				{"kind": "bar", "label": "Billed by project", "group_by": "project",
				 "aggregate": "sum", "field": "grand_total", "horizontal": True,
				 "width": 12},
			]},
		}),
	},
	# ----- Configuration ---------------------------------------------------- #
	#
	# One rail entry with the space's own tables behind it —
	# `onespace/configuration.py`. Each is an ordinary screen with a route and
	# `hide_in_nav`, so a tab inherits that screen's columns, permissions and
	# New button rather than being a second way to reach a doctype.
	#
	# Four tables that are maintained rather than worked in, under one heading
	# at the end of the rail. The rail draws a heading when the group changes,
	# so these have to stay adjacent and last.
	#
	# This is most of what "cleaner" means on this space: ERPNext's Projects
	# workspace puts Activity Type beside Task, so the list of places to go and
	# work has a rate card in the middle of it.
	{
		# What a board is made of, for the person who decides. ERPNext's status
		# is seven fixed words; these are rows, so a workspace renames a column,
		# recolours it and adds a fifth — `docs/WORK.md` §12.
		"screen": "states", "hide_in_nav": 1, "label": "Columns",
		"singular": "Column", "icon": "lucide-columns-3",
		"document_type": "One Task State",
		"fields": "state_name,category,colour,position",
		"order_by": "position asc",
		"view_types": "list",
		"view_settings": json.dumps({"tags": ["category"]}),
	},
	{
		"screen": "labels", "hide_in_nav": 1, "label": "Labels",
		"singular": "Label", "icon": "lucide-tag", "document_type": "One Label",
		"fields": "label_name,colour,description",
		"order_by": "label_name asc",
		"view_types": "list",
		"view_settings": json.dumps({"tags": ["colour"]}),
	},
	{
		"screen": "project-types", "hide_in_nav": 1, "label": "Project types",
		"singular": "Project type", "icon": "lucide-layers", "document_type": "Project Type",
		"fields": "project_type,description",
		"order_by": "project_type asc",
		"view_types": "list",
	},
	{
		"screen": "task-types", "hide_in_nav": 1, "label": "Task types", "singular": "Task type",
				"icon": "lucide-layers", "document_type": "Task Type",
		"fields": "name,description",
		"order_by": "name asc",
		"view_types": "list",
	},
	{
		# The rate card. Two numbers per activity — what an hour costs and what
		# an hour is sold for — and every billable line in the space reads them.
		"screen": "activity-types", "hide_in_nav": 1, "label": "Activity types",
		"singular": "Activity type", "icon": "lucide-clock", "document_type": "Activity Type",
		"fields": "activity_type,costing_rate,billing_rate,disabled",
		"order_by": "activity_type asc",
		"view_types": "list",
	},
	{
		"screen": "templates", "hide_in_nav": 1, "label": "Templates", "singular": "Template",
				"icon": "lucide-file-text", "document_type": "Project Template",
		"fields": "name,project_type,disabled",
		"order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "configuration", "label": "Configuration",
		"singular": "Table", "icon": "lucide-wrench",
		"component": "configuration",
		"view_settings": json.dumps({"configuration": {"screens": [
			"states", "labels",
			"project-types", "task-types", "activity-types", "templates",
		]}}),
	},
]
