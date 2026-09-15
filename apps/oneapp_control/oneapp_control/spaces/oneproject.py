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
]

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

CUSTOM_FIELDS = [
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

#: The Project Type OneHR stamps on an onboarding or an exit checklist, which
#: this space's projects screen leaves out. Mirrors `onehr.boarding.BOARDING`;
#: `tests/test_manifests.py` keeps the two in step.
BOARDING_PROJECTS = "Employee boarding"


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
		"fields": "subject,status,priority,project,exp_end_date,progress,"
		          "completed_by",
		"order_by": "exp_end_date asc",
		"filters": json.dumps({"is_template": 0}),
		"view_types": "board,list,gantt,calendar,tree,dashboard",
		"status_field": "status",
		"field_icons": json.dumps({
			"status": "lucide-flag",
			"priority": "lucide-chart-line",
		}),
		"view_settings": json.dumps({
			"board": {
				"card_fields": ["project", "exp_end_date", "priority"],
				# A board draws a column for every option the Select has,
				# whether or not a row is in it — which is right, because an
				# empty column is where you drop something. `Template` is the
				# exception: the screen filters those rows out, so the column
				# can never hold anything and dropping a task into it would be
				# turning it into a template by accident.
				"arrangement": {"hidden": ["Template"]},
			},
			"gantt": {
				"start_field": "exp_start_date",
				"end_field": "exp_end_date",
				"progress_field": "progress",
			},
			"calendar": {
				"start_field": "exp_start_date",
				"end_field": "exp_end_date",
			},
			# A task can hang under a task, and until there is a tree of them
			# the only way to see a breakdown is to read the parent column.
			"tree": {"parent_field": "parent_task", "label_field": "subject"},
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
		"filters": json.dumps({"is_milestone": 1, "is_template": 0}),
		"view_types": "calendar,list,board",
		"status_field": "status",
		"view_settings": json.dumps({
			# One date and no span. A milestone that lasted a fortnight would
			# not be one, so there is deliberately no `end_field` here and
			# therefore deliberately no Gantt.
			"calendar": {"start_field": "exp_end_date", "diary": True},
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
			"project-types", "task-types", "activity-types", "templates",
		]}}),
	},
]
