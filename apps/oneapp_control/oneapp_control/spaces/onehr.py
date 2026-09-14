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

# How an applicant moves through hiring, in HRMS's own words and its own order.
# `Job Applicant.status` lists them this way and a dashboard widget sorts by
# size, so the funnel has to be told — see `view_settings` on the Applicants
# screen. Hold is where it is because that is where it happens: after somebody
# has been shortlisted and before anybody decides.
APPLICANT_STAGES = [
	"Open",
	"Replied",
	"Shortlisted",
	"Hold",
	"Accepted",
	"Rejected",
]

# A claim's life, and an advance's, in the order they happen. Both doctypes
# list their Select options in an order that is neither alphabetical nor a
# sequence — Expense Claim offers Paid before Unpaid and Submitted after both —
# so a board drawn from the doctype reads as though being paid came before being
# asked for.
CLAIM_STAGES = [
	"Draft",
	"Submitted",
	"Unpaid",
	"Partially Paid",
	"Paid",
	"Rejected",
	"Cancelled",
]

ADVANCE_STAGES = [
	"Draft",
	"Unpaid",
	"Partially Paid",
	"Paid",
	"Claimed",
	"Partly Claimed and Returned",
	"Returned",
	"Cancelled",
]

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
	# Checking yourself in, which is the one thing in OneHR that writes —
	# `oneapp/onehr/checkin.py`. `Write` rather than `Manage` on purpose: a
	# check-in is a log, and somebody who can delete their own arrival time has
	# a log that cannot be used for anything. `if_owner` is the right idiom here
	# because a self check-in *is* filed by its subject, unlike the Attendance
	# row a scheduled job later writes from it.
	("Employee Checkin", "Write", 1),
	# What everybody has to be able to read to plan anything at all.
	("Holiday List", "Read", 0),
	("Leave Type", "Read", 0),
	("Shift Type", "Read", 0),
	# Where a check-in has to happen, which everybody reads and nobody but the
	# people officer writes: the button on somebody's own page says *which*
	# office they have to be at, and a rule you cannot read is a refusal with no
	# sentence behind it.
	("Shift Location", "Read", 0),
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
	("Shift Location", "Write", 0, "people"),
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
# **One**, and the reason it is one is the whole of this note.
#
# The other two spaces each add a field because each was missing a distinction
# every customer makes and ERPNext has no column for — a project's health, a
# deal's next step. HRMS has almost no such hole: it has been written and
# rewritten by people running payroll in a dozen jurisdictions, and nearly every
# field a screen here wants already exists under a name somebody argued about.
# It even has the geofence.
#
# Adding one anyway is the expensive kind of mistake. A Custom Field is applied
# to a workspace's own database and never taken away, so a field added because a
# screen looked thin is a column every future migration has to carry. The test
# for one is not "would this be useful" — it is "is there really nothing here
# that means this", asked after reading the doctype rather than before.
# --------------------------------------------------------------------------- #
CUSTOM_FIELDS = [
	# One, and the paragraph above is still true about the rest.
	#
	# HRMS has the geofence already — a **Shift Location** carries a position and
	# a `checkin_radius`, a Shift Assignment points an employee's shift at one,
	# and `Employee Checkin` refuses a log too far from it. What it has no
	# notion of at all is the *network*, and "you have to be on the office wifi"
	# is the other half of the same question in every workspace that asks the
	# first half. There is nothing under a name somebody argued about to hold
	# it, so this is the exception the rule was written to allow.
	#
	# A browser cannot read an SSID — there is no web API for it and there will
	# not be one — so what is actually checkable is the address a request
	# arrives from, which for an office is its public egress. That is what this
	# holds: one CIDR or address per line, blank meaning no rule.
	{
		"dt": "Shift Location",
		"fieldname": "custom_checkin_networks",
		"label": "Check in only from these networks",
		"fieldtype": "Small Text",
		"insert_after": "checkin_radius",
		"description": (
			"One address or range per line, like 203.0.113.7 or "
			"203.0.113.0/24. Blank means anywhere."
		),
	},
]

# --------------------------------------------------------------------------- #
# What this space tells people about
#
# Eight rules, and every one of them is a sentence a workspace would otherwise
# have to write from an empty settings page: the person who has to approve a
# request should hear that it exists, and the person who asked should hear what
# was decided.
#
# HRMS already knows both. It writes them into `PWA Notification`, which is its
# mobile app's own store — a doctype no seat here grants and no screen reads, so
# every one of those notices is written and never delivered. These are the same
# two sentences said through the notification spine this product actually has:
# in-app and email, per the recipient's own preferences, with somewhere for the
# row to go when it is clicked.
#
# **Seeded once and then the workspace's.** `sync._seed_alerts` writes them
# through `alerts.save`, so they arrive marked exactly as a rule somebody typed
# into Settings is marked and are listed, editable, pausable and deletable
# there. A workspace that reworded one has reworded it; one that deleted one has
# deleted it. Nothing reapplies.
#
# The subject is constant because `Notification.autoname` makes it the primary
# key — the detail goes in the message, which is rendered. `decided` is Frappe's
# Value Change: a rule on `changed` would fire on every save and mail somebody
# about a typo being corrected.
#
# **In-app, not email, and that is the shipped default rather than a preference.**
# Frappe sends both from inside one `try`, so on a workspace with no outgoing
# email account the failed send takes the in-app row down with it — a rule that
# arrives nowhere, logged as "Failed to send Notification" where nobody looks.
# In-app cannot fail that way. Turning email on is one control in Settings, and
# it belongs to the workspace that has configured mail rather than to us.
#
# Attendance Request and Travel Request have no approver field of their own, so
# those two go to the people officer's role rather than to a person.
# --------------------------------------------------------------------------- #

def _asked(doctype, to_field, subject, message):
	"""Somebody filed one of these and it needs a decision.

	`created` rather than `submitted`, and HRMS is the reason: a Leave
	Application refuses to submit until its status is already Approved or
	Rejected, so a rule on Submit tells the approver about a decision they have
	already made. The draft *is* the request — which is why HRMS's own notice
	goes out from `after_insert`.
	"""
	return {
		"doctype": doctype, "when": "created",
		"to_field": to_field, "channel": "app",
		"subject": subject, "message": message,
	}


def _decided(doctype, value_field, subject, message):
	"""And it was decided. Back to whoever filed it."""
	return {
		"doctype": doctype, "when": "decided", "value_field": value_field,
		"to_field": "owner", "channel": "app",
		"subject": subject, "message": message,
	}


ALERTS = [
	_asked(
		"Leave Application", "leave_approver",
		"Leave to approve",
		"{{ doc.employee_name }} asked for {{ doc.total_leave_days }} day(s) of "
		"{{ doc.leave_type }}, from {{ doc.from_date }} to {{ doc.to_date }}.",
	),
	_decided(
		"Leave Application", "status",
		"Your leave request was decided",
		"Your {{ doc.leave_type }} from {{ doc.from_date }} to {{ doc.to_date }} "
		"is now {{ doc.status }}.",
	),
	_asked(
		"Expense Claim", "expense_approver",
		"An expense claim to approve",
		"{{ doc.employee_name }} claimed {{ doc.total_claimed_amount }} "
		"({{ doc.company }}).",
	),
	_decided(
		"Expense Claim", "approval_status",
		"Your expense claim was decided",
		"Your claim {{ doc.name }} is now {{ doc.approval_status }}.",
	),
	_asked(
		"Shift Request", "approver",
		"A shift change to approve",
		"{{ doc.employee_name }} asked for {{ doc.shift_type }} from "
		"{{ doc.from_date }}.",
	),
	_decided(
		"Shift Request", "status",
		"Your shift request was decided",
		"Your request for {{ doc.shift_type }} is now {{ doc.status }}.",
	),
	{
		"doctype": "Attendance Request", "when": "created",
		"to_role_label": ROLES[1]["label"], "channel": "app",
		"subject": "A day to correct",
		"message": "{{ doc.employee_name }} asked to correct "
		           "{{ doc.from_date }} to {{ doc.to_date }}: {{ doc.reason }}.",
	},
	{
		"doctype": "Travel Request", "when": "created",
		"to_role_label": ROLES[1]["label"], "channel": "app",
		"subject": "Somebody asked to travel",
		"message": "{{ doc.employee_name }} asked to travel "
		           "({{ doc.travel_type }}, {{ doc.travel_funding }}).",
	},
]


SCREENS = [
	# ----- The reader's own page ------------------------------------------- #
	#
	# First, and ungrouped, because it is about the person reading rather than
	# about a part of the product. Everything below this line is written for
	# somebody administering people; this is the one screen written for the
	# person each of those rows is about — `oneapp/onehr/me.py`, and
	# `docs/HORILLA.md` §3.1 for why half an HR rail has two readers and only
	# one of them was ever served.
	#
	# A component, because none of it is a list: eight blocks over six doctypes,
	# fetched in one call so the page does not assemble itself in front of the
	# reader. It is `onehr/home` rather than an engine-provided key — a
	# Configuration page is the same page in every space and this one knows what
	# an Employee Checkin is.
	{
		"screen": "home", "label": "Home", "singular": "Day",
		# A heading over one entry, for now. `docs/HORILLA.md` §3.1 is where the
		# rest of it goes: "My leave" above Leave, "My payslips" above Payslips,
		# one rail with two audiences in it. This is the first of them, and a
		# group it can join is cheaper to declare now than to retrofit around a
		# rail people have learned.
		"screen_group": "You",
		"icon": "lucide-layout-grid",
		"component": "onehr/home",
	},
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
			# Not the hero a project gets. A person is a face, a job title, who
			# they answer to and who answers to them — see
			# `lib/screen/recordViews.js` — and the showcase declared below is
			# read by *that* page instead. The same words, a different layout,
			# which is the argument for a library of them rather than one.
			"record": {"as": "person"},
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
		# The grid first, because that is what attendance *is*: one row per
		# person per day, which a list makes you hold in your head and a grid
		# answers at a glance. Every HR product in the world draws this one.
		"view_types": "matrix,calendar,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			# A cell is nothing but its colour, so the colours are declared.
			# `valueTheme` falls back to Frappe's own `guess_style` word lists,
			# which say nothing about Present or On Leave — and a badge can
			# afford to come out grey because it carries its word beside it,
			# while a grid of grey squares carries nothing at all.
			#
			# Green for a day worked, wherever it was worked from; amber for
			# half of one; blue for a planned absence and red for an unplanned
			# one — the same reading `lib/screen/presence.js` argues for, which
			# is that leave is not a problem and being absent without it is.
			"matrix": {
		"row_field": "employee", "date_field": "attendance_date",
		"colours": {
			"Present": "green",
			"Work From Home": "green",
			"Half Day": "amber",
			"On Leave": "blue",
			"Absent": "red",
		},
			},
			"calendar": {"start_field": "attendance_date"},
			# A cell of the grid opens one of these, and what somebody
			# wants from it is why the verdict is the verdict: the shift,
			# the two times, the two flags, and the punches it was
			# computed from. The form has all of that in twenty fields
			# across four sections, which is how settling "I was there"
			# came to mean leaving the record and filtering Check-ins by
			# hand. `lib/screen/recordViews.js`.
			"record": {"as": "day"},
			# Read by that page for one thing: the line above the name.
			"showcase": {"eyebrow_field": "department"},
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
			"calendar": {"start_field": "from_date", "end_field": "to_date",
			             "diary": True},
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
			# A claim's own life, in order. `Expense Claim.status` lists its
			# seven values as Draft, Paid, Partially Paid, Unpaid, Rejected,
			# Submitted, Cancelled — which is neither alphabetical nor a
			# sequence, and reads on a board as though being paid came before
			# being submitted.
			"board": {
		"card_fields": ["posting_date", "total_claimed_amount",
		                "project"],
		"arrangement": {"order": CLAIM_STAGES},
			},
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
		# Asking to go somewhere for work, which is the third thing a person
		# asks the company to pay for and the one that had no screen at all —
		# granted `if_owner` since the space shipped and reachable only from
		# the desk, which is the one place this product does not go.
		#
		# A list and nothing else, and that is the doctype rather than a
		# thin declaration: Travel Request has no status field (its state is
		# the docstatus, which the record header already draws) and no dates
		# of its own — the itinerary is a child table, so there is nothing for
		# a board or a calendar to read. Declaring either would be a view type
		# dropped on the way out, which `_view_types` does silently.
		"screen": "travel", "label": "Travel", "singular": "Travel request",
		"screen_group": "Pay",
		"icon": "lucide-map", "document_type": "Travel Request",
		"fields": "employee_name,purpose_of_travel,travel_type,travel_funding,"
		          "company",
		"order_by": "modified desc",
		"view_types": "list,dashboard",
		"view_settings": json.dumps({
			"dashboard": {"widgets": [
		{"kind": "number", "label": "Requests", "width": 4},
		{"kind": "donut", "label": "Domestic and international",
		 "group_by": "travel_type", "width": 4},
		{"kind": "donut", "label": "Who is paying",
		 "group_by": "travel_funding", "width": 4},
		{"kind": "bar", "label": "By person", "group_by": "employee",
		 "horizontal": True, "width": 12},
			]},
			"showcase": {
		"eyebrow_field": "travel_type",
		"facts": [
			{"field": "purpose_of_travel", "label": "Why"},
			{"field": "travel_funding", "label": "Funding"},
			{"field": "cost_center", "label": "Cost centre"},
			{"field": "company", "label": "Company"},
		],
			},
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
			# The same again, and worse: an advance is asked for, paid, then
			# claimed against or returned, and the Select lists Paid before
			# Unpaid.
			"board": {
		"card_fields": ["posting_date", "advance_amount",
		                "pending_amount"],
		"arrangement": {"order": ADVANCE_STAGES},
			},
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
			# What a hiring manager opens this to ask is "how is it
			# going", and the record page answered "here are twenty
			# fields". So: how long it has been open, what it pays, and
			# where the applicants have got stuck — the funnel for this
			# one role, which the Applicants dashboard draws for every
			# role at once and nothing drew for a single one.
			#
			# `stages` is the same constant the board arranges its
			# columns by and the candidate page fills its strip from, so
			# the three cannot disagree about what hiring looks like.
			"record": {"as": "opening", "stages": APPLICANT_STAGES},
			# Still read, by that page: the eyebrow, the badge, the facts
			# and the tab are the same words in a different layout, which
			# is the argument for a library of record views rather than a
			# component per screen.
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
			# In the order somebody moves through hiring rather than in the
			# order the Select happens to list them, which puts Rejected
			# between Shortlisted and Hold — a board where the bin sits in the
			# middle of the pipeline.
			"board": {
		"card_fields": ["job_title", "source", "applicant_rating"],
		"arrangement": {"order": APPLICANT_STAGES},
			},
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
		# Where a hiring pipeline is sitting, in the order an
		# applicant moves through it — a widget sorts by size, so
		# without `order` this reads Rejected, Shortlisted, Open.
		#
		# A bar rather than a funnel for the reason OneCRM's Value by
		# stage is one: a funnel labels each band as a share of the one
		# above and that only means something where the buckets nest.
		# Rejected is not a subset of Shortlisted.
		{"kind": "bar", "label": "Where they are",
		 "group_by": "status", "order": APPLICANT_STAGES, "width": 6},
		{"kind": "bar", "label": "By source", "group_by": "source",
		 "horizontal": True, "width": 6},
		{"kind": "bar", "label": "By opening", "group_by": "job_title",
		 "series": "status", "stacked": True, "horizontal": True,
		 "width": 12},
			]},
			# Not the showcase a project gets. A candidate is somebody you
			# are *deciding about* rather than somebody you look up, so the
			# page answers the decision — how far along they are, what the
			# rounds scored, which opening — and the hero that suited a
			# building suited nobody here. `lib/screen/recordViews.js`.
			#
			# `stages` is the same constant the board and the Where-they-are
			# widget read, which is why it is named rather than repeated: a
			# manifest is a Python file, so there is one list and nothing to
			# drift.
			"record": {"as": "candidate", "stages": APPLICANT_STAGES},
			# Still read, by that page: the eyebrow, the badge and the tabs are
			# the same words in a different layout, which is the argument for a
			# library of record views rather than one.
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
			"calendar": {"start_field": "scheduled_on", "diary": True},
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
			"calendar": {"start_field": "start_time", "end_field": "end_time",
			             "diary": True},
			"board": {"card_fields": ["training_program", "start_time", "type"]},
		}),
	},
	# ----- Configuration ---------------------------------------------------- #
	#
	# One rail entry, and every table this space is maintained by behind it —
	# `onespace/configuration.py`. Each is an ordinary screen with a route of
	# its own and `hide_in_nav`, so a tab is a *screen* and inherits its
	# columns, its permissions and its New button rather than being a second
	# way to reach a doctype.
	#
	# Twelve of them, which is six more than the Setup group had. The six are
	# the ones that used to be granted for their pickers and given no screen at
	# all — Employee Grade, Employment Type, Grievance Type, Expense Claim Type,
	# Leave Policy, Interview Type — and so could only be edited from the desk.
	# A table you touch twice a year is not a destination; it is also not
	# something a customer should have to leave the product for.
	{
		# A tree, because a department is one and this is the only place in
		# either product that has ever drawn it.
		"screen": "departments", "hide_in_nav": 1, "label": "Departments", "singular": "Department",
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
		"screen": "designations", "hide_in_nav": 1, "label": "Designations",
		"singular": "Designation", "icon": "lucide-user-round", "document_type": "Designation",
		"fields": "designation_name,description",
		"order_by": "designation_name asc",
		"view_types": "list",
	},
	{
		"screen": "leave-types", "hide_in_nav": 1, "label": "Leave types", "singular": "Leave type",
		"icon": "lucide-calendar", "document_type": "Leave Type",
		"fields": "leave_type_name,max_leaves_allowed,is_carry_forward,"
		          "is_lwp,is_earned_leave",
		"order_by": "leave_type_name asc",
		"view_types": "list",
	},
	{
		# Where check-ins are allowed to happen, and on whose network.
		#
		# A map first, because a geofence is a circle on the ground and a list
		# of four decimal places is a spreadsheet of it. The record page is a
		# `place` — `lib/screen/recordViews.js` — which is where the two
		# controls that fill this in without anybody typing live.
		"screen": "places", "hide_in_nav": 1, "label": "Places",
		"singular": "Place", "icon": "lucide-map-pin",
		"document_type": "Shift Location",
		"fields": "location_name,latitude,longitude,checkin_radius,"
		          "custom_checkin_networks",
		"order_by": "location_name asc",
		"view_types": "map,list",
		"view_settings": json.dumps({
			"map": {
				"lat_field": "latitude",
				"lon_field": "longitude",
				"label_field": "location_name",
			},
			"record": {"as": "place"},
		}),
	},
	{
		"screen": "shift-types", "hide_in_nav": 1, "label": "Shift types", "singular": "Shift type",
		"icon": "lucide-clock", "document_type": "Shift Type",
		"fields": "name,start_time,end_time,holiday_list,enable_auto_attendance",
		"order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "salary-components", "hide_in_nav": 1, "label": "Salary components",
		"singular": "Component", "icon": "lucide-wallet", "document_type": "Salary Component",
		"fields": "salary_component,type,is_tax_applicable,"
		          "amount_based_on_formula,disabled",
		"order_by": "salary_component asc",
		"view_types": "list",
	},
	{
		"screen": "salary-structures", "hide_in_nav": 1, "label": "Salary structures",
		"singular": "Structure", "icon": "lucide-file-text", "document_type": "Salary Structure",
		"fields": "name,company,payroll_frequency,is_active,is_default,"
		          "currency",
		"order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "employment-types", "hide_in_nav": 1, "label": "Employment types",
		"singular": "Employment type", "icon": "lucide-briefcase",
		"document_type": "Employment Type",
		"fields": "employee_type_name", "order_by": "employee_type_name asc",
		"view_types": "list",
	},
	{
		"screen": "grades", "hide_in_nav": 1, "label": "Grades",
		"singular": "Grade", "icon": "lucide-layers",
		"document_type": "Employee Grade",
		"fields": "name,default_base_pay", "order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "grievance-types", "hide_in_nav": 1, "label": "Grievance types",
		"singular": "Grievance type", "icon": "lucide-message-square",
		"document_type": "Grievance Type",
		"fields": "name,description", "order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "claim-types", "hide_in_nav": 1, "label": "Claim types",
		"singular": "Claim type", "icon": "lucide-receipt",
		"document_type": "Expense Claim Type",
		"fields": "name,description", "order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "leave-policies", "hide_in_nav": 1, "label": "Leave policies",
		"singular": "Policy", "icon": "lucide-file-text",
		"document_type": "Leave Policy",
		"fields": "title", "order_by": "title asc",
		"view_types": "list",
	},
	{
		"screen": "interview-types", "hide_in_nav": 1, "label": "Interview types",
		"singular": "Interview type", "icon": "lucide-message-square",
		"document_type": "Interview Type",
		"fields": "name,description", "order_by": "name asc",
		"view_types": "list",
	},
	# The page itself, last, and the only one of these in the rail.
	{
		"screen": "configuration", "label": "Configuration",
		"singular": "Table", "icon": "lucide-wrench",
		"component": "configuration",
		"view_settings": json.dumps({"configuration": {"screens": [
			"departments", "designations", "grades", "employment-types",
			"shift-types", "places", "leave-types", "leave-policies",
			"claim-types", "grievance-types", "interview-types",
			"salary-components", "salary-structures",
		]}}),
	},
]


# --------------------------------------------------------------------------- #
# The employee's own view of three of them
#
# `docs/HORILLA.md` §3.1: half the entries in an HR rail have two readers, and
# the difference between them is one word at the front of a label. Leave is a
# queue to whoever approves it and a form to whoever files it; a goal is a
# review to a manager and a commitment to the person who made it.
#
# A twin is an ordinary screen — `dict(parent, …)`, because a manifest is a
# Python file and that is the whole of the reuse. Its columns, view types,
# dashboard widgets and states are the parent's *by identity*, so they cannot
# drift; what differs is the label, the group, and one filter naming the reader
# — `@me:employee`, resolved by `oneapp/onespace/mine.py` through the subject
# `oneapp` registers in its hooks.
#
# Each sits immediately **above its parent, in the parent's own heading**, which
# is where Horilla puts them and is the placement that survives a space with no
# headings at all — OneCRM's rail is flat and My deals sits above Deals there by
# the same rule. The alternative, collecting them under **You** beside Home,
# reads well until a reader looks for leave under Leave and does not find their
# own; a heading is where a thing *is about*, and My leave is about leave.
#
# **You** stays what it is: the one page that is only about the reader.
#
# **Three, and not five.** My attendance and My payslips are not here, and the
# reason is worth writing down rather than leaving as an absence: a screen is a
# doctype grant, and the Employee seat is granted neither Attendance nor Salary
# Slip. `onehr/own.py` crosses that line for a *block* on the Home page — your
# own row needs no grant — and deliberately does not cross it for a screen,
# because a screen that read rows its seat was never granted is the engine
# learning a second permission path. Those two stay on Home.
# --------------------------------------------------------------------------- #

#: The reader, as this space means it. `mine.py` asks `oneapp`'s hook, which
#: answers with the Employee whose `user_id` is the session's user.
ME = "@me:employee"


def _twin(of: str, screen: str, label: str) -> None:
	"""One screen again, narrowed to its reader, inserted above the original.

	The group is the parent's, so the two are adjacent under one heading — the
	rail draws a heading when the group *changes*, and a twin that opened a
	heading of its own would draw "Leave" twice with one entry between them.
	"""
	at = next(i for i, one in enumerate(SCREENS) if one["screen"] == of)
	SCREENS.insert(at, {
		**SCREENS[at],
		"screen": screen, "label": label,
		"filters": json.dumps({"employee": ME}),
	})


# Bottom-up, so an insertion does not move the screen the next one looks for.
_twin("goals", "my-goals", "My goals")
_twin("travel", "my-travel", "My travel")
_twin("claims", "my-claims", "My claims")
_twin("leave", "my-leave", "My leave")
