"""OneTask — work that is nobody's project, and work that is.

`docs/WORK.md` is the argument. Two sentences of it matter here.

**One task table.** A site installs the union of what its granted spaces need,
so a workspace that bought nothing using ERPNext does not carry ERPNext — and
this is the general answer for any business at all, so it is built on `One
Task`, which is ours. `requires_apps` is empty and a bare site can enable it.

**A board is a project.** There is no second container: the board in this space
*is* the project screen drawn as a board, and a task with no project on it is
the inbox. Every competitor with both spends its documentation explaining the
difference and every customer still asks.

What this space is not is an assignment list. An assignment is Frappe's ToDo —
a pointer at a record that already exists — and it stays exactly where it is.
The two meet where a task is assigned, which goes through the framework's own
path so the task lands in somebody's work list beside everything else.
"""

import json

SPACE = {
	"space_code": "onetask",
	"space_label": "OneTask",
	"module": "OneTask",
	"role_name": "OneSpace Task",
	# Nothing. The work is ours — see the docstring — which is the whole reason
	# the doctype is.
	"requires_apps": "",
	"icon": "lucide-circle-check",
	"brand": "onetask",
	"sort_order": 35,
	"availability": "Restricted",
	"description": "Everything there is to do, on a board, in a list or on a day.",
	# Light, because a board is dense and a dark ground under sixty cards is a
	# screen people squint at. The accent is the mark's own green.
	"theme": json.dumps({
		"mode": "light",
		"accent": "#16a34a",
		"radius": "soft",
	}),
}


# --------------------------------------------------------------------------- #
# The two jobs
#
# Two and not three, and the line is the same one OneProject draws: somebody
# *does the work* and somebody *decides what the work is*. A third seat would
# be a reporting one, and a report is a screen rather than a role.
#
# `member` is the default, so entitling OneTask to a workspace gives everybody
# their own list and the boards they are on — which is what a task app is for —
# and nobody the ability to delete a project out from under a team.
# --------------------------------------------------------------------------- #
ROLES = [
	{
		"role_key": "member",
		"label": "Member",
		"is_default": 1,
		"description": "Pick up tasks, move them, write new ones and check "
		               "them off. Everything in this space except what a "
		               "project *is*.",
	},
	{
		"role_key": "lead",
		"label": "Lead",
		"description": "Decide what the projects are, what their columns are "
		               "called, and which labels the workspace uses.",
	},
]


DOCTYPES = [
	# ----- Everybody --------------------------------------------------- #
	#
	# The work itself is Write for a member, which is the point of the space: a
	# task app where somebody has to ask permission to write a task is a task
	# app nobody uses. What they cannot do is decide what a project *is*.
	("One Task", "Write", 0),
	("One Task Step", "Write", 0),
	("One Task Label", "Write", 0),
	# Read: a member works inside the columns and the labels a lead set, and
	# renaming a column under a team mid-sprint is a lead's decision.
	("One Task State", "Read", 0),
	("One Label", "Read", 0),
	("One Project", "Read", 0),
	# The engine's own, because a screen that cannot save a view is a screen
	# people stop using by the second week. `if_owner`, so a member's saved
	# views are a member's.
	("OneSpace Saved View", "Write", 1),
	# Who a task is assigned to, which is Frappe's own store and the one place
	# this space and the assignment system meet — `docs/WORK.md` §2.
	("ToDo", "Write", 0),

	# ----- Lead --------------------------------------------------------- #
	("One Project", "Write", 0, "lead"),
	("One Task State", "Write", 0, "lead"),
	("One Label", "Write", 0, "lead"),
]


#: The columns a workspace starts with, and the ones a new project copies.
#: Four, because four is what a board needs to be a board — and because a fifth
#: is the first thing a team argues about, which is a decision they should have
#: rather than one we make for them.
STATES = [
	("Backlog", "Backlog", "gray", 0),
	("In progress", "Started", "blue", 1),
	("In review", "Started", "amber", 2),
	("Done", "Done", "green", 3),
]

#: The order the board draws them in. Declared, because a Link column has no
#: order of its own — the engine says so and refuses a board that does not
#: answer. Which is also the honest bound on "a board defines its own columns"
#: today: the *set* is data and a workspace may rename, recolour and add to it,
#: and the order a board opens in is this. `docs/WORK.md` §5.
STATE_ORDER = [name for name, _category, _colour, _at in STATES]


SCREENS = [
	{
		# The front page: what is on this person's plate, which is the question
		# a task app is opened with.
		"screen": "home", "label": "Home", "singular": "Day",
		"icon": "lucide-layout-grid",
		"component": "home",
		"view_settings": json.dumps({
			"home": {"blocks": ["my-tasks", "inbox", "projects"]},
		}),
	},
	{
		# The reader's own, first, because this is the screen the space exists
		# for. `@me` rather than a second doctype or a second filter language:
		# `onespace/mine.py` resolves it before the list, the board, the
		# calendar and the dashboard read it, so all four narrow the same way.
		"screen": "my-tasks", "label": "My tasks", "singular": "Task",
		"icon": "lucide-user-round", "document_type": "One Task",
		"fields": "subject,state,priority,project,due_on,labels",
		"order_by": "due_on asc",
		"filters": json.dumps({"assigned_to": "@me"}),
		"view_types": "board,list,calendar,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {
				"column_field": "state",
				"arrangement": {"order": STATE_ORDER},
				"card_fields": ["project", "due_on", "priority"],
			},
			"calendar": {
				"start_field": "starts_on", "end_field": "due_on",
				"diary": True,
				# It is already narrowed to the reader, so the diary needs no
				# second declaration — but saying it costs nothing and keeps
				# the source personal if the filter above ever changes.
				"about": {"assigned_to": "@me"},
			},
			"tags": ["priority", "project"],
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Tasks", "width": 3},
				{"kind": "donut", "label": "Where they stand",
				 "group_by": "state", "width": 4},
				{"kind": "donut", "label": "Priority", "group_by": "priority",
				 "width": 4},
			]},
		}),
	},
	{
		# Everything, whoever it belongs to. The board is the default because a
		# task list that opens as a list is a list somebody has to sort before
		# it means anything.
		"screen": "tasks", "label": "Tasks", "singular": "Task",
		"icon": "lucide-circle-check", "document_type": "One Task",
		"fields": "subject,state,priority,project,assigned_to,due_on,labels",
		"order_by": "due_on asc",
		"view_types": "board,list,calendar,dashboard",
		"status_field": "status",
		"field_icons": json.dumps({
			"priority": "lucide-flag",
			"due_on": "lucide-calendar",
		}),
		"view_settings": json.dumps({
			"board": {
				"column_field": "state",
				"arrangement": {"order": STATE_ORDER},
				"card_fields": ["project", "assigned_to", "due_on"],
			},
			"calendar": {
				"start_field": "starts_on", "end_field": "due_on",
				"diary": True,
				# Whose it is, for the diary's Mine lens — `docs/WORK.md` §6.
				"about": {"assigned_to": "@me"},
			},
			"tags": ["priority", "project"],
			"showcase": {
				"tabs": [
					{"screen": "tasks", "field": "parent_task",
					 "label": "Sub-tasks", "icon": "lucide-list-tree"},
				],
			},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Tasks", "width": 3},
				{"kind": "number", "label": "Estimated", "aggregate": "sum",
				 "field": "estimate_minutes", "width": 3},
				{"kind": "donut", "label": "Where they stand",
				 "group_by": "state", "width": 3},
				{"kind": "donut", "label": "Priority", "group_by": "priority",
				 "width": 3},
				{"kind": "bar", "label": "By project", "group_by": "project",
				 "width": 6},
				{"kind": "bar", "label": "By owner", "group_by": "assigned_to",
				 "width": 6},
			]},
		}),
	},
	{
		# The inbox: what nobody has placed yet. Not a separate store and not a
		# flag — a task with no project *is* unplaced, so this is one filter
		# over the screen above it.
		"screen": "inbox", "label": "Inbox", "singular": "Task",
		"icon": "lucide-inbox", "document_type": "One Task",
		"fields": "subject,priority,assigned_to,due_on,labels",
		"order_by": "creation desc",
		"filters": json.dumps({"project": ["is", "not set"]}),
		"view_types": "list,board",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {
				"column_field": "priority",
				"card_fields": ["assigned_to", "due_on"],
			},
			"tags": ["priority"],
		}),
	},
	{
		# The containers. A board of projects by state is the portfolio, which
		# is the one view a lead opens on Monday.
		"screen": "projects", "label": "Projects", "singular": "Project",
		"icon": "lucide-layers", "document_type": "One Project",
		"fields": "project_name,status,lead,due_on,open_tasks,done_tasks",
		"order_by": "due_on asc",
		"filters": json.dumps({"archived": 0}),
		"view_types": "board,list,calendar,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {
				"column_field": "status",
				"card_fields": ["lead", "due_on", "open_tasks"],
			},
			"calendar": {"start_field": "starts_on", "end_field": "due_on"},
			"tags": ["status"],
			"showcase": {
				"facts": [
					{"field": "open_tasks", "label": "Open"},
					{"field": "done_tasks", "label": "Done"},
					{"field": "due_on", "label": "Due"},
				],
				# What this project is *for*, and what its own calendar is made
				# of — `docs/WORK.md` §6(c) reads this same list.
				"tabs": [
					{"screen": "tasks", "field": "project",
					 "label": "Tasks", "icon": "lucide-circle-check"},
				],
			},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Projects", "width": 4},
				{"kind": "donut", "label": "Status", "group_by": "status",
				 "width": 4},
				{"kind": "bar", "label": "By lead", "group_by": "lead",
				 "width": 4},
			]},
		}),
	},
	{
		# What a board is made of, for the person who decides. A lead's screen:
		# a member reads these and works inside them.
		"screen": "states", "label": "Columns", "singular": "Column",
		"icon": "lucide-columns-3", "document_type": "One Task State",
		"fields": "state_name,category,colour,position",
		"order_by": "position asc",
		"view_types": "list",
		"view_settings": json.dumps({"tags": ["category"]}),
	},
	{
		"screen": "labels", "label": "Labels", "singular": "Label",
		"icon": "lucide-tag", "document_type": "One Label",
		"fields": "label_name,colour,description",
		"order_by": "label_name asc",
		"view_types": "list",
		"view_settings": json.dumps({"tags": ["colour"]}),
	},
]
