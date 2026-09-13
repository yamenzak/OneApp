"""OneHR — the people, their time, their pay and how they got here.

Read `docs/ERP-SPACES.md` first: it is the argument for cutting ERPNext into
three spaces rather than shipping it whole, and this is the third and by far
the largest of them.

HRMS ships around two hundred doctypes. Nearly all of them are real and almost
none of them is a *place a person goes to work* — Leave Ledger Entry is an
accounting artefact, Employee Property History is an audit trail, Salary Detail
is a row inside a slip. The desk cannot tell the difference, so its HR workspace
is a wall of links and the first thing every HR officer does is learn which
nine of them they actually use.

So this space is a choice, and the choice is the product. Twenty-nine screens
under seven headings, every one of them somewhere a person has a job to do, and
everything else reachable the way it should be — as the far end of a link on a
record that needed it.

Two things beyond the choosing are worth naming.

**Pay is a separate seat.** Every HR department in the world keeps salary away
from the people who administer leave, and ERPNext's answer is a role list you
assemble by hand. Here it is one of three declared roles, so a workspace that
entitles OneHR gets the separation without having thought about it, and merging
the two is a decision somebody makes rather than one they inherit.

**A person is not a form.** Opening somebody shows their face, who they report
to, who reports to *them*, and their leave, attendance, payslips and claims —
all of it drawn by the same showcase a project uses, from a manifest.

**Generally available.**
"""

import json

SPACE = {
	"space_code": "onehr",
	"space_label": "OneHR",
	"module": "OneHR",
	"role_name": "OneSpace HR",
	# HRMS for nearly everything, and ERPNext underneath it: HRMS's own
	# doctypes link Company, Department, Cost Center and Account, so a site
	# with one and not the other is a site where half of these screens refuse
	# their own link fields.
	"requires_apps": "erpnext,hrms",
	"icon": "lucide-user-round",
	"sort_order": 60,
	"availability": "Restricted",
	"description": "People, attendance, leave, pay, hiring and how each one is doing.",
	# Light and a warm teal. This is the space people open to look at each
	# other, and the accent that reads best under a wall of faces is one that
	# does not compete with them.
	"theme": json.dumps({
		"mode": "light",
		"accent": "#0d9488",
		"radius": "soft",
	}),
}

# --------------------------------------------------------------------------- #
# The three jobs
#
# The split that matters is the second cut, not the first. Everyone expects
# "the staff" and "the HR department"; what is worth declaring is that **pay is
# neither of them**.
#
# An HR officer administers leave, attendance, hiring and appraisals and in most
# companies is deliberately not shown what anybody earns. ERPNext's answer is a
# bag of roles somebody assembles by hand and gets subtly wrong, and the failure
# is silent — a payslip is readable by whoever holds Employee read and nobody
# finds out until they do.
#
# So `payroll` is a seat here, and the Pay screens belong to it alone. A
# workspace that wants one person doing both hands out both roles, which is a
# decision somebody made.
# --------------------------------------------------------------------------- #
ROLES = [
	{
		"role_key": "employee",
		"label": "Employee",
		"is_default": 1,
		"description": "Self-service: ask for leave, correct your own "
		               "attendance, claim expenses, keep your goals. Sees the "
		               "directory and nobody else's records.",
	},
	{
		"role_key": "people",
		"label": "People officer",
		"description": "Administer the people — attendance, leave, hiring, "
		               "onboarding, appraisals and the tables behind them. "
		               "Deliberately not pay.",
	},
	{
		"role_key": "payroll",
		"label": "Payroll",
		"description": "Run the pay: structures, payroll cycles, payslips and "
		               "advances. The one seat that can see what anybody earns.",
	},
]

DOCTYPES = [
	# ----- Everybody ------------------------------------------------------- #
	#
	# The directory. Read for all three seats, because nearly every screen in
	# this space resolves an employee link and a colleague's name is not a
	# secret from a colleague.
	("Employee", "Read", 0),
	# The self-service doors. `if_owner` on every one of them, which is what
	# makes the Employee seat honest: you file your own and you cannot read the
	# person next to you's.
	("Leave Application", "Manage", 1),
	("Attendance Request", "Manage", 1),
	("Shift Request", "Manage", 1),
	("Expense Claim", "Manage", 1),
	("Travel Request", "Manage", 1),
	("Employee Grievance", "Manage", 1),
	("Goal", "Manage", 1),
	# What everybody has to be able to read to plan anything at all.
	("Holiday List", "Read", 0),
	("Leave Type", "Read", 0),
	("Shift Type", "Read", 0),
	("Department", "Read", 0),
	("Designation", "Read", 0),
	("Branch", "Read", 0),
	("Employee Grade", "Read", 0),
	("Employment Type", "Read", 0),
	("Grievance Type", "Read", 0),
	("Expense Claim Type", "Read", 0),
	("Company", "Read", 0),
	("Currency", "Read", 0),
	("Cost Center", "Read", 0),
	("KRA", "Read", 0),
	("OneSpace Saved View", "Write", 1),

	# ----- People officer --------------------------------------------------- #
	#
	# The same doctypes again without the `if_owner`, plus everything that is
	# administered rather than asked for. `sync.sync_permissions` keeps the
	# wider of the two rows, so the repeats are the point.
	("Employee", "Manage", 0, "people"),
	("Leave Application", "Manage", 0, "people"),
	("Leave Allocation", "Manage", 0, "people"),
	("Leave Policy", "Write", 0, "people"),
	("Leave Period", "Write", 0, "people"),
	("Attendance", "Manage", 0, "people"),
	("Attendance Request", "Manage", 0, "people"),
	("Employee Checkin", "Manage", 0, "people"),
	("Shift Assignment", "Manage", 0, "people"),
	("Shift Request", "Manage", 0, "people"),
	("Employee Onboarding", "Manage", 0, "people"),
	("Employee Separation", "Manage", 0, "people"),
	("Employee Grievance", "Manage", 0, "people"),
	("Employee Promotion", "Manage", 0, "people"),
	("Employee Transfer", "Manage", 0, "people"),
	("Travel Request", "Manage", 0, "people"),
	("Expense Claim", "Manage", 0, "people"),
	# Hiring, end to end.
	("Job Opening", "Manage", 0, "people"),
	("Job Applicant", "Manage", 0, "people"),
	("Job Offer", "Manage", 0, "people"),
	("Job Requisition", "Manage", 0, "people"),
	("Interview", "Manage", 0, "people"),
	("Interview Type", "Write", 0, "people"),
	("Job Applicant Source", "Write", 0, "people"),
	("Employee Referral", "Manage", 0, "people"),
	# Growing.
	("Goal", "Manage", 0, "people"),
	("Appraisal", "Manage", 0, "people"),
	("Appraisal Cycle", "Manage", 0, "people"),
	("Appraisal Template", "Write", 0, "people"),
	("KRA", "Write", 0, "people"),
	("Training Program", "Write", 0, "people"),
	("Training Event", "Manage", 0, "people"),
	# The tables behind all of it.
	("Department", "Write", 0, "people"),
	("Designation", "Write", 0, "people"),
	("Branch", "Write", 0, "people"),
	("Employee Grade", "Write", 0, "people"),
	("Employment Type", "Write", 0, "people"),
	("Leave Type", "Write", 0, "people"),
	("Shift Type", "Write", 0, "people"),
	("Holiday List", "Write", 0, "people"),
	("Grievance Type", "Write", 0, "people"),
	("Expense Claim Type", "Write", 0, "people"),

	# ----- Payroll ---------------------------------------------------------- #
	#
	# The one seat that sees what anybody earns. Note what is *not* repeated
	# here: no Leave Application, no hiring, no appraisals. A payroll officer
	# who needs those holds the other role as well, and somebody decided that.
	("Salary Slip", "Manage", 0, "payroll"),
	("Salary Structure", "Manage", 0, "payroll"),
	("Salary Structure Assignment", "Manage", 0, "payroll"),
	("Salary Component", "Write", 0, "payroll"),
	("Payroll Entry", "Manage", 0, "payroll"),
	("Payroll Period", "Write", 0, "payroll"),
	("Employee Advance", "Manage", 0, "payroll"),
	# Claims are paid out of payroll in most of the world, so this seat reads
	# and settles them as well.
	("Expense Claim", "Manage", 0, "payroll"),
	("Mode of Payment", "Read", 0, "payroll"),
	("Account", "Read", 0, "payroll"),
	("Bank Account", "Read", 0, "payroll"),
]

# --------------------------------------------------------------------------- #
# The schema its screens read
#
# **None**, and that is worth writing down rather than leaving as an absence.
#
# The other two spaces each add a field, because each was missing a distinction
# every customer makes and ERPNext has no column for — a project's health, a
# deal's next step. HRMS has no such hole: it has been written and rewritten by
# people running payroll in a dozen jurisdictions, and every field a screen here
# wants already exists under a name somebody argued about.
#
# Adding one anyway would be the expensive kind of mistake. A Custom Field is
# applied to a workspace's own database and never taken away, so a field added
# because a screen looked thin is a column every future migration has to carry.
# --------------------------------------------------------------------------- #
CUSTOM_FIELDS = []

SCREENS = [
	# ----- People ---------------------------------------------------------- #
	{
		# The directory, and the first thing anybody opens.
		#
		# A grid first, because Employee carries a photograph and a page of
		# faces is how a person is actually found — a column of names is a
		# phone book. The tree beside it is the org chart, which HRMS draws in
		# a bespoke desk page and which is `reports_to` and nothing else.
		"screen": "people", "label": "People", "singular": "Person",
		"screen_group": "People",
		"icon": "lucide-users", "document_type": "Employee",
		"fields": "employee_name,designation,department,branch,reports_to,"
		          "date_of_joining,status",
		"order_by": "employee_name asc",
		"view_types": "grid,list,tree,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"grid": {"card_fields": ["designation", "department", "branch"]},
			"tree": {"parent_field": "reports_to", "label_field": "employee_name"},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "People", "width": 3},
				{"kind": "number", "label": "Active", "width": 3,
				 "filters": {"status": "Active"}},
				{"kind": "number", "label": "Left", "width": 3,
				 "filters": {"status": "Left"}},
				{"kind": "donut", "label": "By gender", "group_by": "gender",
				 "width": 3},
				{"kind": "bar", "label": "By department", "group_by": "department",
				 "horizontal": True, "width": 6},
				{"kind": "bar", "label": "By designation",
				 "group_by": "designation", "horizontal": True, "width": 6},
				# Headcount over time, which is the one number a founder asks
				# for and which no list of employees can be read as.
				{"kind": "line", "label": "Joining by month",
				 "group_by": "date_of_joining", "grain": "month", "width": 12},
			]},
			# A person, opened. The picture is the record's own `image`, the
			# eyebrow is what they do, and `children` is the org chart pointing
			# the other way: everybody whose `reports_to` is this person.
			"showcase": {
				"images": True,
				"eyebrow_field": "designation",
				"badge_field": "status",
				"facts": [
					{"field": "department", "label": "Department"},
					{"field": "date_of_joining", "label": "Joined"},
					{"field": "reports_to", "label": "Reports to"},
					{"field": "branch", "label": "Branch"},
				],
				"children": {"screen": "people", "field": "reports_to",
				             "label": "Reports", "icon": "lucide-users"},
				"tabs": [
					{"screen": "leave", "field": "employee",
					 "label": "Leave", "icon": "lucide-calendar"},
					{"screen": "attendance", "field": "employee",
					 "label": "Attendance", "icon": "lucide-clock"},
					{"screen": "claims", "field": "employee",
					 "label": "Claims", "icon": "lucide-receipt"},
					{"screen": "goals", "field": "employee",
					 "label": "Goals", "icon": "lucide-chart-line"},
				],
			},
		}),
	},
	{
		# Arriving. A board, because onboarding is a pipeline with three states
		# and a list of them tells you nothing about where the queue is stuck.
		"screen": "onboarding", "label": "Onboarding", "singular": "Onboarding",
		"screen_group": "People",
		"icon": "lucide-graduation-cap", "document_type": "Employee Onboarding",
		"fields": "employee_name,designation,department,date_of_joining,"
		          "boarding_status",
		"order_by": "date_of_joining asc",
		"view_types": "board,list,calendar",
		"status_field": "boarding_status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["designation", "department",
			                          "date_of_joining"]},
			"calendar": {"start_field": "date_of_joining"},
		}),
	},
	{
		# Leaving. The same shape, and the same argument: a separation that has
		# been Pending for three weeks is the row somebody has to chase.
		"screen": "exits", "label": "Exits", "singular": "Exit",
		"screen_group": "People",
		"icon": "lucide-git-compare", "document_type": "Employee Separation",
		"fields": "employee_name,designation,department,"
		          "resignation_letter_date,boarding_status",
		"order_by": "resignation_letter_date desc",
		"view_types": "board,list",
		"status_field": "boarding_status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["designation", "department",
			                          "resignation_letter_date"]},
		}),
	},
	{
		"screen": "grievances", "label": "Grievances", "singular": "Grievance",
		"screen_group": "People",
		"icon": "lucide-message-square", "document_type": "Employee Grievance",
		"fields": "subject,grievance_type,raised_by,date,status,resolved_by",
		"order_by": "date desc",
		"view_types": "board,list",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["grievance_type", "raised_by", "date"]},
		}),
	},
	# ----- Time ------------------------------------------------------------ #
	{
		# A calendar first, and this is the single clearest case in the repo
		# for view types being worth the machinery. Attendance *is* a grid of
		# days. HRMS knows it — it ships a bespoke "Monthly Attendance Sheet"
		# report to draw one — and the doctype's own list view is twenty
		# thousand rows in date order.
		"screen": "attendance", "label": "Attendance", "singular": "Day",
		"screen_group": "Time",
		"icon": "lucide-clock", "document_type": "Attendance",
		"fields": "employee_name,attendance_date,status,shift,in_time,out_time,"
		          "department",
		"order_by": "attendance_date desc",
		"view_types": "calendar,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "attendance_date"},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Days recorded", "width": 3},
				{"kind": "number", "label": "Present", "width": 3,
				 "filters": {"status": "Present"}},
				{"kind": "number", "label": "Absent", "width": 3,
				 "filters": {"status": "Absent"}},
				{"kind": "number", "label": "On leave", "width": 3,
				 "filters": {"status": "On Leave"}},
				{"kind": "donut", "label": "How the days went",
				 "group_by": "status", "width": 4},
				{"kind": "bar", "label": "By department", "group_by": "department",
				 "series": "status", "stacked": True, "width": 8},
				{"kind": "line", "label": "Day by day",
				 "group_by": "attendance_date", "grain": "day",
				 "series": "status", "width": 12},
			]},
		}),
	},
	{
		# The raw punch log, which is what attendance is *made of*. Worth its
		# own screen for exactly one reason: when a day is marked Absent and
		# somebody swears they were there, this is the only place that can
		# settle it, and HRMS buries it behind a Shift Type setting.
		"screen": "checkins", "label": "Check-ins", "singular": "Check-in",
		"screen_group": "Time",
		"icon": "lucide-map-pin", "document_type": "Employee Checkin",
		"fields": "employee_name,log_type,time,shift,attendance",
		"order_by": "time desc",
		"view_types": "list,calendar,dashboard",
		"status_field": "log_type",
		"view_settings": json.dumps({
			"calendar": {"start_field": "time"},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Punches", "width": 4},
				{"kind": "donut", "label": "In and out", "group_by": "log_type",
				 "width": 4},
				{"kind": "bar", "label": "By shift", "group_by": "shift",
				 "width": 4},
			]},
		}),
	},
	{
		# Who is on which shift, as bars down a week. A shift assignment has a
		# start and an end, which is the one shape a Gantt is for and a list
		# renders as two date columns nobody can compare.
		"screen": "shifts", "label": "Shifts", "singular": "Shift",
		"screen_group": "Time",
		"icon": "lucide-calendar", "document_type": "Shift Assignment",
		"fields": "employee_name,shift_type,start_date,end_date,status,"
		          "department",
		"order_by": "start_date desc",
		"view_types": "calendar,gantt,list",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "start_date", "end_field": "end_date"},
		}),
	},
	{
		# The self-service door for a day the clock got wrong. `if_owner` on
		# the Employee seat, so this screen is your own requests and the People
		# officer's is everybody's — one manifest, two lists, decided by the
		# grant rather than by a filter.
		"screen": "attendance-requests", "label": "Attendance requests",
		"singular": "Request", "screen_group": "Time",
		"icon": "lucide-file-text", "document_type": "Attendance Request",
		"fields": "employee_name,from_date,to_date,reason,shift,department",
		"order_by": "from_date desc",
		"view_types": "list,calendar",
		"status_field": "reason",
		"view_settings": json.dumps({
			"calendar": {"start_field": "from_date", "end_field": "to_date"},
		}),
	},
	{
		"screen": "shift-requests", "label": "Shift requests",
		"singular": "Request", "screen_group": "Time",
		"icon": "lucide-file-text", "document_type": "Shift Request",
		"fields": "employee_name,shift_type,from_date,to_date,status,approver",
		"order_by": "from_date desc",
		"view_types": "list,board,calendar",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "from_date", "end_field": "to_date"},
			"board": {"card_fields": ["shift_type", "from_date", "to_date"]},
		}),
	},
	# ----- Leave ----------------------------------------------------------- #
	{
		# Who is off, and when. A calendar first for the obvious reason and a
		# board second for the less obvious one: a leave application's whole
		# life is Open → Approved or Rejected, and a board of three columns is
		# an approver's entire job on one screen.
		"screen": "leave", "label": "Leave", "singular": "Leave application",
		"screen_group": "Leave",
		"icon": "lucide-calendar", "document_type": "Leave Application",
		"fields": "employee_name,leave_type,from_date,to_date,total_leave_days,"
		          "status,leave_approver",
		"order_by": "from_date desc",
		"view_types": "calendar,board,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "from_date", "end_field": "to_date"},
			"board": {"card_fields": ["leave_type", "from_date",
			                          "total_leave_days"]},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Applications", "width": 3},
				{"kind": "number", "label": "Days asked for", "aggregate": "sum",
				 "field": "total_leave_days", "width": 3},
				{"kind": "number", "label": "Waiting", "width": 3,
				 "filters": {"status": "Open"}},
				{"kind": "number", "label": "Average length", "aggregate": "avg",
				 "field": "total_leave_days", "width": 3},
				{"kind": "donut", "label": "Where each one stands",
				 "group_by": "status", "width": 4},
				{"kind": "bar", "label": "Days by type", "group_by": "leave_type",
				 "aggregate": "sum", "field": "total_leave_days", "width": 8},
				{"kind": "line", "label": "Days off by month",
				 "group_by": "from_date", "grain": "month", "aggregate": "sum",
				 "field": "total_leave_days", "width": 12},
			]},
		}),
	},
	{
		# What everybody is owed. The other half of leave and the half nobody
		# looks at until somebody asks how many days they have left.
		"screen": "allocations", "label": "Allocations", "singular": "Allocation",
		"screen_group": "Leave",
		"icon": "lucide-layers", "document_type": "Leave Allocation",
		"fields": "employee_name,leave_type,from_date,to_date,"
		          "total_leaves_allocated,leave_period",
		"order_by": "from_date desc",
		"view_types": "list,dashboard",
		"view_settings": json.dumps({
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Allocations", "width": 4},
				{"kind": "number", "label": "Days allocated", "aggregate": "sum",
				 "field": "total_leaves_allocated", "width": 4},
				{"kind": "number", "label": "Average per person",
				 "aggregate": "avg", "field": "total_leaves_allocated",
				 "width": 4},
				{"kind": "bar", "label": "Days by type", "group_by": "leave_type",
				 "aggregate": "sum", "field": "total_leaves_allocated",
				 "width": 12},
			]},
		}),
	},
	{
		"screen": "holidays", "label": "Holidays", "singular": "Holiday list",
		"screen_group": "Leave",
		"icon": "lucide-book-open", "document_type": "Holiday List",
		"fields": "holiday_list_name,from_date,to_date,total_holidays,"
		          "weekly_off",
		"order_by": "from_date desc",
		"view_types": "list",
	},
	# ----- Pay ------------------------------------------------------------- #
	{
		# `hide_new`, and it is the clearest example in this repo of what that
		# flag is for. A payslip is *produced* by a payroll run; one made by
		# hand is one that no run will ever reconcile, and ERPNext offers the
		# button anyway because the doctype allows it.
		"screen": "payslips", "label": "Payslips", "singular": "Payslip",
		"screen_group": "Pay",
		"icon": "lucide-wallet", "document_type": "Salary Slip",
		"fields": "employee_name,start_date,end_date,total_working_days,"
		          "gross_pay,total_deduction,net_pay,status",
		"order_by": "start_date desc",
		"hide_new": 1,
		"view_types": "list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Payslips", "width": 3},
				{"kind": "number", "label": "Gross", "aggregate": "sum",
				 "field": "gross_pay", "width": 3},
				{"kind": "number", "label": "Deductions", "aggregate": "sum",
				 "field": "total_deduction", "width": 3},
				{"kind": "number", "label": "Net", "aggregate": "sum",
				 "field": "net_pay", "width": 3},
				{"kind": "bar", "label": "Net by department",
				 "group_by": "department", "aggregate": "sum", "field": "net_pay",
				 "horizontal": True, "width": 6},
				{"kind": "donut", "label": "Where each one stands",
				 "group_by": "status", "width": 6},
				{"kind": "line", "label": "Net by month", "group_by": "start_date",
				 "grain": "month", "aggregate": "sum", "field": "net_pay",
				 "width": 12},
			]},
		}),
	},
	{
		"screen": "payroll", "label": "Payroll runs", "singular": "Payroll run",
		"screen_group": "Pay",
		"icon": "lucide-receipt", "document_type": "Payroll Entry",
		"fields": "posting_date,payroll_frequency,start_date,end_date,"
		          "department,status",
		"order_by": "start_date desc",
		"view_types": "list,board",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["start_date", "end_date",
			                          "payroll_frequency"]},
		}),
	},
	{
		# Money somebody is owed back. A board, because a claim is a queue: it
		# is submitted, it is approved, it is paid, and the only question
		# anybody has is which of those it is stuck at.
		"screen": "claims", "label": "Claims", "singular": "Claim",
		"screen_group": "Pay",
		"icon": "lucide-receipt", "document_type": "Expense Claim",
		"fields": "employee_name,posting_date,total_claimed_amount,"
		          "total_sanctioned_amount,project,status",
		"order_by": "posting_date desc",
		"view_types": "board,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["posting_date", "total_claimed_amount",
			                          "project"]},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Claims", "width": 4},
				{"kind": "number", "label": "Claimed", "aggregate": "sum",
				 "field": "total_claimed_amount", "width": 4},
				{"kind": "number", "label": "Sanctioned", "aggregate": "sum",
				 "field": "total_sanctioned_amount", "width": 4},
				{"kind": "donut", "label": "Where each one stands",
				 "group_by": "status", "width": 6},
				{"kind": "bar", "label": "Claimed by person",
				 "group_by": "employee", "aggregate": "sum",
				 "field": "total_claimed_amount", "horizontal": True,
				 "width": 6},
			]},
		}),
	},
	{
		"screen": "advances", "label": "Advances", "singular": "Advance",
		"screen_group": "Pay",
		"icon": "lucide-wallet", "document_type": "Employee Advance",
		"fields": "employee_name,posting_date,purpose,advance_amount,"
		          "claimed_amount,pending_amount,status",
		"order_by": "posting_date desc",
		"view_types": "board,list",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["posting_date", "advance_amount",
			                          "pending_amount"]},
		}),
	},
	# ----- Hiring ---------------------------------------------------------- #
	{
		# An opening, opened, is the advert and the people who answered it.
		# That is the showcase: what the job is, what it pays, when it closes,
		# and a tab of every applicant against it.
		"screen": "openings", "label": "Openings", "singular": "Opening",
		"screen_group": "Hiring",
		"icon": "lucide-briefcase", "document_type": "Job Opening",
		"fields": "job_title,designation,department,location,employment_type,"
		          "closes_on,status",
		"order_by": "closes_on asc",
		"view_types": "grid,board,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"grid": {"card_fields": ["department", "location", "closes_on"]},
			"board": {"card_fields": ["designation", "department", "closes_on"]},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Openings", "width": 4},
				{"kind": "number", "label": "Open", "width": 4,
				 "filters": {"status": "Open"}},
				{"kind": "donut", "label": "Open and closed", "group_by": "status",
				 "width": 4},
				{"kind": "bar", "label": "By department", "group_by": "department",
				 "horizontal": True, "width": 6},
				{"kind": "bar", "label": "By designation",
				 "group_by": "designation", "horizontal": True, "width": 6},
			]},
			"showcase": {
				"eyebrow_field": "department",
				"badge_field": "status",
				"facts": [
					{"field": "designation", "label": "Role"},
					{"field": "location", "label": "Where"},
					{"field": "employment_type", "label": "Type"},
					{"field": "closes_on", "label": "Closes"},
				],
				"tabs": [
					{"screen": "applicants", "field": "job_title",
					 "label": "Applicants", "icon": "lucide-users"},
				],
			},
		}),
	},
	{
		# The hiring pipeline, and the reason it is a board: an applicant's
		# status *is* a stage — Open, Replied, Shortlisted, Hold, Accepted,
		# Rejected — and a recruiter's week is moving cards between them.
		"screen": "applicants", "label": "Applicants", "singular": "Applicant",
		"screen_group": "Hiring",
		"icon": "lucide-user-round", "document_type": "Job Applicant",
		"fields": "applicant_name,job_title,designation,source,applicant_rating,"
		          "status",
		"order_by": "modified desc",
		"view_types": "board,grid,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["job_title", "source", "applicant_rating"]},
			"grid": {"card_fields": ["designation", "source",
			                          "applicant_rating"]},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Applicants", "width": 4},
				{"kind": "number", "label": "Average rating", "aggregate": "avg",
				 "field": "applicant_rating", "width": 4},
				{"kind": "number", "label": "Shortlisted", "width": 4,
				 "filters": {"status": "Shortlisted"}},
				# Where a hiring funnel leaks, which is the question a head of
				# people actually has and which no list answers.
				{"kind": "funnel", "label": "The funnel", "group_by": "status",
				 "width": 6},
				{"kind": "bar", "label": "By source", "group_by": "source",
				 "horizontal": True, "width": 6},
				{"kind": "bar", "label": "By opening", "group_by": "job_title",
				 "series": "status", "stacked": True, "horizontal": True,
				 "width": 12},
			]},
			"showcase": {
				"eyebrow_field": "designation",
				"badge_field": "status",
				"facts": [
					{"field": "job_title", "label": "Applied for"},
					{"field": "source", "label": "Source"},
					{"field": "applicant_rating", "label": "Rating"},
					{"field": "email_id", "label": "Email"},
				],
				"tabs": [
					{"screen": "interviews", "field": "job_applicant",
					 "label": "Interviews", "icon": "lucide-message-square"},
					{"screen": "offers", "field": "job_applicant",
					 "label": "Offers", "icon": "lucide-file-text"},
				],
			},
		}),
	},
	{
		"screen": "interviews", "label": "Interviews", "singular": "Interview",
		"screen_group": "Hiring",
		"icon": "lucide-message-square", "document_type": "Interview",
		"fields": "job_applicant,interview_type,designation,scheduled_on,"
		          "from_time,average_rating,status",
		"order_by": "scheduled_on desc",
		"view_types": "calendar,board,list",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "scheduled_on"},
			"board": {"card_fields": ["job_applicant", "scheduled_on",
			                          "interview_type"]},
		}),
	},
	{
		"screen": "offers", "label": "Offers", "singular": "Offer",
		"screen_group": "Hiring",
		"icon": "lucide-file-text", "document_type": "Job Offer",
		"fields": "applicant_name,designation,offer_date,status",
		"order_by": "offer_date desc",
		"view_types": "board,list",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["designation", "offer_date"]},
		}),
	},
	# ----- Growth ---------------------------------------------------------- #
	{
		# Goals nest — a company goal has department goals under it and those
		# have people's — and HRMS stores the tree and shows a list. So this is
		# a tree, which is one line of manifest and the whole point of it.
		"screen": "goals", "label": "Goals", "singular": "Goal",
		"screen_group": "Growth",
		"icon": "lucide-chart-line", "document_type": "Goal",
		"fields": "goal_name,employee_name,kra,start_date,end_date,progress,"
		          "status",
		"order_by": "end_date asc",
		"view_types": "tree,board,list,gantt,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"tree": {"parent_field": "parent_goal", "label_field": "goal_name"},
			"board": {"card_fields": ["employee_name", "end_date", "progress"]},
			"gantt": {"start_field": "start_date", "end_field": "end_date",
			          "progress_field": "progress"},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Goals", "width": 4},
				{"kind": "number", "label": "Average progress", "aggregate": "avg",
				 "field": "progress", "suffix": "%", "width": 4},
				{"kind": "number", "label": "Completed", "width": 4,
				 "filters": {"status": "Completed"}},
				{"kind": "donut", "label": "Where each one stands",
				 "group_by": "status", "width": 6},
				{"kind": "bar", "label": "By person", "group_by": "employee",
				 "horizontal": True, "width": 6},
			]},
		}),
	},
	{
		"screen": "appraisals", "label": "Appraisals", "singular": "Appraisal",
		"screen_group": "Growth",
		"icon": "lucide-chart-pie", "document_type": "Appraisal",
		"fields": "employee_name,appraisal_cycle,designation,department,"
		          "start_date,end_date,final_score",
		"order_by": "end_date desc",
		"view_types": "list,dashboard",
		"view_settings": json.dumps({
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Appraisals", "width": 4},
				{"kind": "number", "label": "Average score", "aggregate": "avg",
				 "field": "final_score", "width": 4},
				{"kind": "number", "label": "Highest", "aggregate": "max",
				 "field": "final_score", "width": 4},
				{"kind": "bar", "label": "Average by department",
				 "group_by": "department", "aggregate": "avg",
				 "field": "final_score", "horizontal": True, "width": 6},
				{"kind": "bar", "label": "Average by cycle",
				 "group_by": "appraisal_cycle", "aggregate": "avg",
				 "field": "final_score", "width": 6},
			]},
		}),
	},
	{
		"screen": "cycles", "label": "Appraisal cycles", "singular": "Cycle",
		"screen_group": "Growth",
		"icon": "lucide-layers", "document_type": "Appraisal Cycle",
		"fields": "cycle_name,start_date,end_date,department,designation,status",
		"order_by": "start_date desc",
		"view_types": "list,board,calendar",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "start_date", "end_field": "end_date"},
			"board": {"card_fields": ["start_date", "end_date", "department"]},
		}),
	},
	{
		"screen": "training", "label": "Training", "singular": "Training event",
		"screen_group": "Growth",
		"icon": "lucide-graduation-cap", "document_type": "Training Event",
		"fields": "event_name,training_program,type,level,start_time,end_time,"
		          "event_status",
		"order_by": "start_time desc",
		"view_types": "calendar,list,board",
		"status_field": "event_status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "start_time", "end_field": "end_time"},
			"board": {"card_fields": ["training_program", "start_time", "type"]},
		}),
	},
	# ----- Setup ----------------------------------------------------------- #
	#
	# Six tables, at the end, under one heading. HRMS's own workspace has
	# something like forty entries at this tier; what is here is the six a
	# workspace actually edits after the first month.
	#
	# What is deliberately *not* here is everything a link resolves without a
	# screen: Employee Grade, Employment Type, Interview Type, Grievance Type,
	# Expense Claim Type and the rest are granted above and have no rail entry,
	# because a Link control reads a doctype's own metadata and needs no screen
	# to offer its values. A table you edit twice a year is not a destination.
	{
		# A tree, because a department is one and this is the only place in
		# either product that has ever drawn it.
		"screen": "departments", "label": "Departments", "singular": "Department",
		"screen_group": "Setup",
		"icon": "lucide-layers", "document_type": "Department",
		"fields": "department_name,parent_department,company,is_group,disabled",
		"order_by": "department_name asc",
		"view_types": "tree,list",
		"view_settings": json.dumps({
			"tree": {"parent_field": "parent_department",
			         "label_field": "department_name"},
		}),
	},
	{
		"screen": "designations", "label": "Designations",
		"singular": "Designation", "screen_group": "Setup",
		"icon": "lucide-user-round", "document_type": "Designation",
		"fields": "designation_name,description",
		"order_by": "designation_name asc",
		"view_types": "list",
	},
	{
		"screen": "leave-types", "label": "Leave types", "singular": "Leave type",
		"screen_group": "Setup",
		"icon": "lucide-calendar", "document_type": "Leave Type",
		"fields": "leave_type_name,max_leaves_allowed,is_carry_forward,"
		          "is_lwp,is_earned_leave",
		"order_by": "leave_type_name asc",
		"view_types": "list",
	},
	{
		"screen": "shift-types", "label": "Shift types", "singular": "Shift type",
		"screen_group": "Setup",
		"icon": "lucide-clock", "document_type": "Shift Type",
		"fields": "name,start_time,end_time,holiday_list,enable_auto_attendance",
		"order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "salary-components", "label": "Salary components",
		"singular": "Component", "screen_group": "Setup",
		"icon": "lucide-wallet", "document_type": "Salary Component",
		"fields": "salary_component,type,is_tax_applicable,"
		          "amount_based_on_formula,disabled",
		"order_by": "salary_component asc",
		"view_types": "list",
	},
	{
		"screen": "salary-structures", "label": "Salary structures",
		"singular": "Structure", "screen_group": "Setup",
		"icon": "lucide-file-text", "document_type": "Salary Structure",
		"fields": "name,company,payroll_frequency,is_active,is_default,"
		          "currency",
		"order_by": "name asc",
		"view_types": "list",
	},
]
