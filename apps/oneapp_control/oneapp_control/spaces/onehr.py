"""OnePeople — the people, their time, their pay and how they got here.

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
entitles OnePeople gets the separation without having thought about it, and merging
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
	"space_label": "OnePeople",
	"module": "OnePeople",
	"role_name": "OneSpace HR",
	# HRMS for nearly everything, and ERPNext underneath it: HRMS's own
	# doctypes link Company, Department, Cost Center and Account, so a site
	# with one and not the other is a site where half of these screens refuse
	# their own link fields.
	"requires_apps": "erpnext,hrms",
	"icon": "lucide-user-round",
	"brand": "onehr",
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
	# Worked a holiday, wants the day back. The same shape as an attendance
	# request and it was the one self-service door HRMS has that this space had
	# not opened — the leave allocation it produces was already here, the form
	# that asks for one was not.
	("Compensatory Leave Request", "Manage", 1),
	# What you thought of a course you sat through, which is filed by its
	# subject and by nobody else.
	("Training Feedback", "Manage", 1),
	# Checking yourself in, which is the one thing in OnePeople that writes —
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
	# What is being run, so somebody can say which one they are giving feedback
	# on — and so a training calendar is a thing anybody can read rather than
	# something the people officer forwards.
	("Training Event", "Read", 0),
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

	# The small tables a *form* points at, which nothing lists and everything
	# needs. A Link whose target this space does not grant is a picker that
	# answers nothing — silently, because an empty menu looks like an empty
	# table — so an employee filing a travel request could not say what it was
	# for, and the Employee form offered neither a salutation nor a gender.
	#
	# Read at this level and written by the people officer below, which is the
	# split every other lookup here has.
	("Purpose of Travel", "Read", 0),
	# Where an expense was incurred, and against which piece of work. Both are
	# on the claim form and a claim is the one thing everybody here files, so
	# without these two the picker offers nothing and the field is typed in or
	# left blank. Read and nothing more: a project is a thing you charge time
	# to, not a thing an HR seat administers.
	#
	# They are also what onboarding and exits are *made of* — HRMS builds a
	# checklist out of a Project and a Task each — so the boarding page cannot
	# say what is done without them. See `onehr/boarding.py`.
	("Project", "Read", 0),
	("Task", "Read", 0),
	# And the third thing a claim can be against, which ERPNext puts on the
	# same form: a driver's expenses belong to the run they were incurred on.
	("Delivery Trip", "Read", 0),
	("Identification Document Type", "Read", 0),
	("Gender", "Read", 0),
	("Salutation", "Read", 0),
	("Country", "Read", 0),
	("Overtime Type", "Read", 0),

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
	("Compensatory Leave Request", "Manage", 0, "people"),
	# The middle of leave, which was missing: a Leave Policy and a Leave Period
	# were both granted and the thing that turns them into somebody's balance
	# was not, so a people officer could write the rules and then had to open
	# every allocation by hand.
	("Leave Policy Assignment", "Manage", 0, "people"),
	# And the correction to one, for the balance that is wrong by two days.
	("Leave Adjustment", "Manage", 0, "people"),
	# Which calendar a person keeps, which HRMS moved off the Employee record
	# into a document of its own so it can change mid-year.
	("Holiday List Assignment", "Manage", 0, "people"),
	# A recurring pattern and somebody's enrolment in it. Shift Assignment was
	# granted and is the row this *produces*; without these two a roster is
	# typed one day at a time.
	("Shift Schedule", "Write", 0, "people"),
	("Shift Schedule Assignment", "Manage", 0, "people"),
	# Overtime Type was granted for its picker and the slip that uses it was
	# not, which is a table with nothing that reads it.
	("Overtime Slip", "Manage", 0, "people"),
	# Leaving, the other half. Employee Separation is the checklist; this is the
	# conversation, and HRMS keeps them apart because one is a project and the
	# other is a questionnaire.
	("Exit Interview", "Manage", 0, "people"),
	# Who can do what. The skills are on the child table of this and on a Job
	# Opening's expected set, so the vocabulary has to be writable or both
	# pickers are empty.
	("Employee Skill Map", "Manage", 0, "people"),
	("Skill", "Write", 0, "people"),
	# The four HRMS Singles this seat works in. A Single is a doctype with one
	# document, so none of them has a list, a record id or a New button and
	# every screen mechanism in this product passed over them — which is why all
	# six shipped desk-only. `oneapp/onehr/tools.py` is the door.
	#
	# The rules first, and this is also where the notifications this product
	# knew nothing about become somebody's: four HRMS scheduled jobs send mail
	# — birthdays, work anniversaries, an interview tomorrow, a feedback form
	# nobody filled in — and the switch for every one of them is on HR Settings.
	("HR Settings", "Write", 0, "people"),
	# Then the two bulk tools. Allocating a year's leave one document at a time
	# is the work `Leave Policy Assignment` was granted to avoid and this is the
	# other half of it: everybody who has no allocation yet, in one pass.
	("Leave Control Panel", "Write", 0, "people"),
	("Shift Assignment Tool", "Write", 0, "people"),
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
	# What the interviewer actually said, which is the only part of an
	# interview anybody re-reads.
	("Interview Feedback", "Manage", 0, "people"),
	# The letter at the end of it, and the template it is written from.
	("Appointment Letter", "Manage", 0, "people"),
	("Appointment Letter Template", "Write", 0, "people"),
	# The headcount a requisition is drawn against — `Job Opening.staffing_plan`
	# is a picker this space never filled.
	("Staffing Plan", "Manage", 0, "people"),
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
	# What came out of one, and what the people who sat through it thought.
	("Training Result", "Manage", 0, "people"),
	("Training Feedback", "Manage", 0, "people"),
	# An appraisal is a score and a conversation, and this is the conversation:
	# `Appraisal`'s own feedback table points at the criteria, so the criteria
	# had to be writable for the rating rows to mean anything.
	("Employee Performance Feedback", "Manage", 0, "people"),
	("Employee Feedback Criteria", "Write", 0, "people"),
	# Who ran it, where the trainer was somebody outside. The one field on a
	# training event that points at a doctype this space otherwise never
	# mentions, and without it the picker on the form answers nothing.
	("Supplier", "Read", 0, "people"),
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
	# And the tables above, plus the ones only an administrator fills in: the
	# templates that make onboarding and hiring something other than typing the
	# same six rows again, and the block list that stops leave over a month end.
	("Purpose of Travel", "Write", 0, "people"),
	("Identification Document Type", "Write", 0, "people"),
	("Gender", "Write", 0, "people"),
	("Salutation", "Write", 0, "people"),
	("Overtime Type", "Write", 0, "people"),
	("Employee Onboarding Template", "Write", 0, "people"),
	("Employee Separation Template", "Write", 0, "people"),
	("Job Opening Template", "Write", 0, "people"),
	("Job Offer Term Template", "Write", 0, "people"),
	("Offer Term", "Write", 0, "people"),
	("Leave Block List", "Write", 0, "people"),
	("Employee Health Insurance", "Write", 0, "people"),

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
	# The one-offs a cycle is actually made of. A Salary Detail row points at an
	# Additional Salary, so every payslip in HRMS that is not exactly the
	# structure has one behind it and this space had no way to make one.
	("Additional Salary", "Manage", 0, "payroll"),
	("Employee Incentive", "Manage", 0, "payroll"),
	# And the two ways a cycle is put right afterwards, both of which HRMS
	# added since this manifest was written: back pay for a structure that
	# changed late, and the reversal of a leave-without-pay day marked wrong.
	("Arrear", "Manage", 0, "payroll"),
	("Payroll Correction", "Manage", 0, "payroll"),
	# Holding somebody's pay, which was on the "deliberately not here" list in
	# `docs/ERP-SPACES.md` §6 and has moved off it for the same reason Income
	# Tax Slab did: `Salary Slip.salary_withholding` is a picker on a form this
	# space draws, so a payroll officer who cannot make one is a payroll officer
	# in the desk.
	("Salary Withholding", "Manage", 0, "payroll"),
	# What a leaver is owed on the way out. The people officer runs the
	# separation; the money is this seat's, which is the same line the rest of
	# this space draws.
	("Full and Final Statement", "Manage", 0, "payroll"),
	# Overtime is worked under the people officer and paid here — a slip names
	# the Salary Slip it went out on.
	("Overtime Slip", "Read", 0, "payroll"),
	# And this seat's two Singles: what a working day is worth, and putting
	# everybody on a structure at the start of a year.
	("Payroll Settings", "Write", 0, "payroll"),
	("Bulk Salary Structure Assignment", "Write", 0, "payroll"),
	# Claims are paid out of payroll in most of the world, so this seat reads
	# and settles them as well.
	("Expense Claim", "Manage", 0, "payroll"),
	# What a payroll run posted, and what an advance or a claim is paid with.
	# Both **Read**, and the read is the whole design: this space drafts an
	# accounting document out of HRMS's own arithmetic — the outstanding on an
	# advance, the total on a claim, the payables on a settlement — and posting
	# it belongs to whoever keeps the books. The engine works the rest out from
	# the grant: no New button, no Save, no Submit.
	#
	# Payment Entry moved off §6's list the same way Income Tax Slab and Salary
	# Withholding did, and for the harder version of the same reason. All three
	# verbs on an advance are gated by HRMS on `paid_amount`, which only a
	# Payment Entry writes — so without it an advance could be raised here and
	# then nothing at all. Three verbs that never light up is not a line.
	("Journal Entry", "Read", 0, "payroll"),
	("Payment Entry", "Read", 0, "payroll"),
	# And the one table §6 of `docs/ERP-SPACES.md` drew a line just outside.
	# The line was "OnePeople runs a payroll cycle and shows what came out of it;
	# configuring a tax regime is not in it", which was right about the *rest*
	# of the tax family and wrong about this one: a Salary Structure
	# Assignment's form offers an Income Tax Slab picker, so a payroll officer
	# who cannot make one is a payroll officer in the desk. There is no desk.
	("Income Tax Slab", "Write", 0, "payroll"),
	# The third thing an expense claim can be against, after a project and a
	# delivery trip: `Expense Claim.vehicle_log`. Read and no door — a vehicle
	# log is written wherever the fleet is administered, and a workspace with no
	# fleet has an empty picker on a field nobody fills.
	("Vehicle Log", "Read", 0, "people"),
	("Vehicle Log", "Read", 0, "payroll"),
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
#: The doctypes an alert has to be able to address the *subject* of, and the
#: field each mirror sits after.
#:
#: Every one of them is a row the company writes about somebody: the shift they
#: have been put on, the day they were marked absent for, what they were paid.
#: `owner` is who filed it, which is somebody else.
ABOUT_A_PERSON = [
	("Attendance", "employee_name"),
	("Shift Assignment", "employee_name"),
	("Leave Application", "employee_name"),
	("Expense Claim", "employee_name"),
	("Salary Slip", "employee_name"),
	("Employee Advance", "employee_name"),
	("Goal", "employee_name"),
	("Appraisal", "employee_name"),
]


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

	# And one more, repeated across four doctypes, which is about being *told*
	# rather than about a rule.
	#
	# Almost every alert worth sending in this space is "tell the person this
	# row is about" — you are on the site shift from Monday; you were marked
	# absent yesterday. The person is an `employee` Link holding
	# `HR-EMP-00003`, which is not an address, so `alerts.addressable` refuses
	# it and says so in its own docstring; what it offers instead is `owner`,
	# which is who *filed* the row. That is the same person for a leave
	# application somebody wrote themselves and the wrong person for every row
	# the company writes about somebody.
	#
	# `Employee.user_id` is the bridge and it already exists — what was missing
	# was a way to reach it from the row. A Link to User with `fetch_from` is
	# exactly that, and `addressable` already accepts a Link to User, so this
	# unlocks the whole class with no engine change and no second recipient
	# model. It is the exception the rule above was written to allow for the
	# same reason the network field is: HRMS has nothing here that names a
	# *login*, because HRMS's own notifications go to its mobile app.
	#
	# Read-only, and on no screen. It is not a fact about the record; it is the
	# address of the person in it.
	*[
		{
			"dt": doctype,
			"fieldname": "custom_person",
			"label": "Person's login",
			"fieldtype": "Link",
			"options": "User",
			"fetch_from": "employee.user_id",
			"read_only": 1,
			"no_copy": 1,
			"insert_after": after,
			"description": (
				"Filled in from the employee. Alerts about this record are "
				"sent here."
			),
		}
		for doctype, after in ABOUT_A_PERSON
	],
]

# --------------------------------------------------------------------------- #
# The personnel file, kept out of the directory
#
# The employee seat holds `Employee` unrestricted on purpose — a directory
# nobody can open is not a directory, and looking a colleague up is most of
# what a person wants from an HR app. ERPNext then puts every one of Employee's
# hundred-odd fields at permission level zero, `ctc` and `iban` among them, so
# that same grant handed every employee every colleague's pay, bank account,
# passport number and blood group.
#
# There is no narrowing in a grant that can say "the record except these": a
# grant is about rows and `if_owner` is about whose they are. Frappe's answer is
# the permission level, so these move up to one and only the two seats that
# administer people are given it.
#
# What stays at level zero is the directory: name, photograph, job title,
# department, branch, who they report to, when they joined, and their status.
# That is what a colleague may see, and it is what every screen in this space
# actually lists.
#
# Reconciled every sync rather than seeded once — `sync._seed_field_levels`.
# A workspace that lowered one of these back has not expressed a preference.
# --------------------------------------------------------------------------- #
FIELD_LEVELS = [
	{
		# **Level one: the personnel file.** Not the directory, and not pay.
		#
		# Both seats that administer people reach this, because both of them
		# have to: an exit is a date somebody types and an emergency contact is
		# the number somebody rings.
		"dt": "Employee",
		"level": 1,
		"roles": [ROLES[1]["label"], ROLES[2]["label"]],
		"fields": [
			# Who they are outside work.
			"personal_details", "date_of_birth", "marital_status",
			"blood_group", "health_details", "health_insurance_section",
			"health_insurance_provider", "health_insurance_no",
			"passport_details_section", "passport_number", "valid_upto",
			"date_of_issue", "place_of_issue",
			"personal_email", "person_to_be_contacted",
			"emergency_contact_details", "emergency_phone_number",
			"relation",
			# And the two dates that are somebody else's business.
			"resignation_letter_date", "relieving_date",
		],
	},
	{
		# **Level two: what they are paid, and where it goes.**
		#
		# This is the hole §5 described and left open, said plainly: "a people
		# officer sees what a person earns, and a workspace that cannot live
		# with that gives the HR job to somebody who also holds payroll." The
		# sentence after it was that the thing worth building is a space being
		# able to say otherwise — and it turned out the space already could.
		# `FIELD_LEVELS` has always taken a level and a list of roles; there
		# was only ever one row, at level one, granted to both seats, so pay
		# rode up with the passport number and stopped there.
		#
		# Two levels, because Frappe's permission levels are a ladder and not a
		# set: a role reaching level two does not thereby reach level one, so
		# each is listed with exactly the seats that should have it. Payroll
		# holds both; the people officer holds one.
		#
		# What this costs is one real thing, and it is worth naming rather than
		# discovering: a people officer can no longer *set* somebody's salary
		# on the person's own record. That is the point. It is set from a
		# Salary Structure Assignment, which is the payroll seat's screen, and
		# `ctc` on Employee was only ever a second place to say it.
		"dt": "Employee",
		"level": 2,
		"roles": [ROLES[2]["label"]],
		"fields": [
			"salary_information", "salary_mode", "salary_currency", "ctc",
			"bank_details_section", "bank_name", "bank_ac_no", "iban",
		],
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


#: The field every "this is about you" rule sends to. Written once because it
#: is a fieldname three places have to agree on — the custom field above, the
#: rules below, and `alerts._addressed` checking them.
PERSON = "custom_person"


def _decided(doctype, value_field, subject, message):
	"""And it was decided. Back to whoever it is *about*.

	`owner` is who filed it, which is the same person whenever somebody asked
	for something themselves — and the wrong person the moment an officer files
	one on their behalf, which is half of what an HR team does. Where the
	doctype carries the `custom_person` mirror this space adds, that is the
	subject and it is used; elsewhere `owner` is still the only answer there is.
	"""
	about = {one for one, _after in ABOUT_A_PERSON}
	return {
		"doctype": doctype, "when": "decided", "value_field": value_field,
		"to_field": PERSON if doctype in about else "owner", "channel": "app",
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
	# A grievance, both ways. This is the one door in the space that opened on
	# nothing: somebody files a complaint about their workload and it sits in a
	# list until whoever happens to open that list opens it.
	{
		"doctype": "Employee Grievance", "when": "created",
		"to_role_label": ROLES[1]["label"], "channel": "app",
		"subject": "Somebody raised a grievance",
		"message": "{{ doc.employee_name }} raised {{ doc.grievance_type }}: "
		           "{{ doc.subject }}.",
	},
	# Back to whoever filed it, through the same helper the leave and the claim
	# use: `owner` rather than `raised_by`, because `raised_by` is a Link to
	# Employee and an Employee is not an address — see `alerts.addressable`.
	_decided(
		"Employee Grievance", "status",
		"Your grievance was decided",
		"{{ doc.subject }} is now {{ doc.status }}.",
	),
	# Onboarding and exits are deliberately not here. Every step of one is a
	# Task that HRMS assigns to a person or a role as it is created, and an
	# assignment already notifies — a second alert saying the same thing is the
	# way a product teaches people to ignore both.

	# The two that are about *you* rather than about something you asked for,
	# and the reason `custom_person` exists. Neither could be written before it:
	# the subject of a shift assignment is an Employee id, which is not an
	# address.
	{
		"doctype": "Shift Assignment", "when": "created",
		"to_field": PERSON, "channel": "app",
		"subject": "You have been put on a shift",
		"message": "{{ doc.shift_type }} from {{ doc.start_date }}"
		           "{% if doc.end_date %} to {{ doc.end_date }}{% endif %}.",
	},
	{
		# Growth, both ways round. A goal set *for* somebody by their manager
		# is the one they are least likely to find on their own.
		"doctype": "Goal", "when": "created",
		"to_field": PERSON, "channel": "app",
		"subject": "A goal was set for you",
		"message": "{{ doc.goal_name }}"
		           "{% if doc.end_date %}, by {{ doc.end_date }}{% endif %}.",
	},
	{
		"doctype": "Appraisal", "when": "submitted",
		"to_field": PERSON, "channel": "app",
		"subject": "Your appraisal is finished",
		"message": "{{ doc.appraisal_cycle }}: {{ doc.final_score }} out of 5.",
	},
	# Hiring is deliberately absent, and the reason is the recipient rather
	# than the rules. Everything worth saying there is said to a *candidate* —
	# your interview is on Tuesday, your offer is attached — and a candidate is
	# not a login: `Job Applicant.email_id` is the only address, which makes it
	# mail rather than an alert, with everything mail brings that an in-app row
	# does not have to think about. `docs/EMAIL.md` is where that goes.
	{
		# The one people actually wait for. HRMS tells its mobile app and
		# nothing else, and "is my payslip out" is the question an HR team
		# answers by hand every month.
		"doctype": "Salary Slip", "when": "submitted",
		"to_field": PERSON, "channel": "app",
		"subject": "Your payslip is ready",
		"message": "{{ doc.start_date }} to {{ doc.end_date }}: "
		           "{{ doc.net_pay }} net.",
	},
	_decided(
		"Employee Advance", "status",
		"Your advance was decided",
		"Your advance of {{ doc.advance_amount }} is now {{ doc.status }}.",
	),
	{
		# The one alert here with a condition on it. A day marked Present needs
		# no telling; a day marked Absent is the one somebody has to correct,
		# and the correction is a screen away — which is the whole reason to
		# say it rather than leave it in a grid nobody opens.
		"doctype": "Attendance", "when": "created",
		"condition": {"field": "status", "operator": "is", "value": "Absent"},
		"to_field": PERSON, "channel": "app",
		"subject": "You were marked absent",
		"message": "{{ doc.attendance_date }} was recorded as absent. If that "
		           "is wrong, file an attendance request.",
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
			# Three Links that are not records. A Designation and a Department
			# are Links because ERPNext keeps a table of them, not because
			# anybody wants to open one — drawn as records they are three lines
			# of chrome per cell saying one word. As tags they are a word each,
			# coloured from the word itself, which is what makes a directory
			# scannable by department without anybody choosing a palette.
			"tags": ["designation", "department", "branch"],
			# Not the hero a project gets. A person is a face, a job title, who
			# they answer to and who answers to them — see
			# `lib/screen/recordViews.js` — and the showcase declared below is
			# read by *that* page instead. The same words, a different layout,
			# which is the argument for a library of them rather than one.
			"record": {"as": "person"},
			"dashboard": {
		# The date this dashboard is about. Every question on it has an
		# unspoken "…lately", and asking that through the Filter control
		# means picking a field, an operator and two dates.
		"period_field": "date_of_joining",
		"widgets": [
		# The readings on their own row. A number card is two lines tall
		# and a chart is twelve, so mixing them across one row leaves a
		# hole the height of the chart beside the numbers — which is what
		# this dashboard did.
		{"kind": "number", "label": "People", "width": 4},
		{"kind": "number", "label": "Active", "width": 4,
		 "filters": {"status": "Active"}},
		{"kind": "number", "label": "Left", "width": 4,
		 "filters": {"status": "Left"}},
		{"kind": "donut", "label": "By gender", "group_by": "gender",
		 "width": 4},
		# Stacked by status, and that is the only way a bar chart here gets
		# more than one colour: echarts colours by *series*, so a bar chart
		# of eight departments and nothing else is eight bars of one blue
		# whatever palette it is given. A second grouping is a real series
		# per colour — and headcount split into who is still here is the
		# question somebody opening this was going to ask next anyway.
		{"kind": "bar", "label": "By department", "group_by": "department",
		 "series": "status", "stacked": True,
		 "horizontal": True, "width": 4},
		{"kind": "bar", "label": "By designation",
		 "group_by": "designation", "horizontal": True, "width": 4},
		# Headcount over time, which is the one number a founder asks
		# for and which no list of employees can be read as.
		{"kind": "line", "label": "Joining by month",
		 "group_by": "date_of_joining", "grain": "month", "width": 12},
		# Where people sit. `employment_type` would have been the other
		# one and is deliberately not here: HRMS adds it to Employee as a
		# *Custom Field* in its own `setup.py`, so it exists at runtime and
		# `test_every_field_a_screen_names_is_a_real_field` cannot see it —
		# the guard reads doctype JSON. A widget the guard has to be
		# argued out of is not worth the argument.
		{"kind": "bar", "label": "By branch", "group_by": "branch",
		 "horizontal": True, "width": 12},
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
			# Two the derivation used to find and no longer can. `connections`
			# takes the first six screens in this space whose doctype points
			# back at an Employee, in the manifest's order, and the second HRMS
			# pass put Skills and Exit interviews ahead of both of these — so a
			# person's page silently lost the one control in OnePeople that
			# writes and the one door that opens onto a complaint.
			#
			# Declaring them is the answer the mechanism is built for: a
			# derivation is what is there when nobody said, and the manifest
			# saying so wins. What falls to the derivation now is the rest of
			# the People group, which is where an arbitrary six is fine.
			{"screen": "grievances", "field": "raised_by",
			 "label": "Grievances", "icon": "lucide-message-square"},
			{"screen": "checkins", "field": "employee",
			 "label": "Check-ins", "icon": "lucide-map-pin"},
		],
			},
		}),
	},
	{
		# Who can do what, which is the question a directory cannot answer. One
		# row per person, two child tables on it — the skills they have and the
		# courses they have sat through — and the vocabulary behind both is the
		# Skill table under Configuration.
		#
		# It is also what makes a Job Opening's expected skill set mean
		# anything: a requirement nobody has recorded against a person is a
		# filter over an empty column.
		"screen": "skills", "label": "Skills", "singular": "Person",
		"screen_group": "People",
		"icon": "lucide-graduation-cap", "document_type": "Employee Skill Map",
		"fields": "employee_name,designation",
		"order_by": "employee_name asc",
		"view_types": "list",
		"view_settings": json.dumps({"tags": ["designation"]}),
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
			"tags": ["designation", "department"],
			# A checklist, not a form. See `lib/screen/recordViews.js`.
			"record": {"as": "boarding"},
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
			"tags": ["designation", "department"],
			# The same page as onboarding, and deliberately: an exit is a
			# checklist with the same three questions on it.
			"record": {"as": "boarding"},
		}),
	},
	{
		# The other half of leaving. **Exits** is the checklist — HRMS builds an
		# Employee Separation out of a Project and a Task per step — and this is
		# the conversation, which is a questionnaire with a verdict on the end
		# of it. They are two doctypes because they are two jobs: one is done by
		# whoever collects the laptop, the other by whoever wants to know why.
		"screen": "exit-interviews", "label": "Exit interviews",
		"singular": "Interview", "screen_group": "People",
		"icon": "lucide-message-square", "document_type": "Exit Interview",
		"fields": "employee_name,department,designation,relieving_date,date,"
		          "status,employee_status",
		"order_by": "relieving_date desc",
		"view_types": "board,list,calendar",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["department", "relieving_date", "date"]},
			"calendar": {"start_field": "date"},
			# The second verdict, which is not the state of the interview but
			# its outcome — Retained or Confirmed — and is a word rather than a
			# stage.
			"tags": ["department", "employee_status"],
		}),
	},
	{
		# Somebody moving up, and somebody moving across. Two HRMS doctypes that
		# do the same thing — a dated list of field changes applied to an
		# Employee on the day it takes effect — and both were granted to the
		# people officer and reachable only from the desk.
		#
		# A calendar first, because the question about either is *when*: a
		# promotion is a payroll event and a transfer is a rota one, and both
		# are agreed weeks before they happen.
		"screen": "promotions", "label": "Promotions", "singular": "Promotion",
		"screen_group": "People",
		"icon": "lucide-chart-line", "document_type": "Employee Promotion",
		"fields": "employee_name,promotion_date,department,current_ctc,"
		          "revised_ctc,company",
		"order_by": "promotion_date desc",
		"view_types": "calendar,list",
		"view_settings": json.dumps({
			"calendar": {"start_field": "promotion_date"},
			"tags": ["department"],
		}),
	},
	{
		"screen": "transfers", "label": "Transfers", "singular": "Transfer",
		"screen_group": "People",
		"icon": "lucide-git-compare", "document_type": "Employee Transfer",
		"fields": "employee_name,transfer_date,department,new_company,company",
		"order_by": "transfer_date desc",
		"view_types": "calendar,list",
		"view_settings": json.dumps({
			"calendar": {"start_field": "transfer_date"},
			"tags": ["department"],
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
			# The type only. `raised_by` is a person and stays a person: a face
			# and a name is what you want beside a complaint.
			"tags": ["grievance_type"],
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
			# The shift and the department are Links because HRMS keeps a table
			# of each, not because anybody wants to open one. `status` stays a
			# badge: it is a *state*, and a state keeps the doctype's own
			# colour — green for a day worked is meaning, where a tag's colour
			# means only "not the same as that one".
			"tags": ["shift", "department"],
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
			"dashboard": {
		"period_field": "attendance_date",
		"widgets": [
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
		# Taking the register, which is the other half of the same day and the
		# one screen here that is a form over a *list of people*.
		#
		# It names a doctype and draws none: a component screen has no grant to
		# be hidden by, so without `document_type` this would sit in every
		# employee's rail and refuse them on the way in. `Attendance` is
		# granted to the people officer and to nobody else, which is exactly
		# who this is for — see `spaceview.resolve`, and `onehr/roster.py` for
		# what it does.
		"screen": "roster", "label": "Mark the day", "singular": "Day",
		"screen_group": "Time",
		"icon": "lucide-book-open", "document_type": "Attendance",
		"component": "onehr/roster",
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
			"tags": ["shift"],
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
		"view_types": "calendar,gantt,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "start_date", "end_field": "end_date"},
			"tags": ["shift_type", "department"],
			# The one screen in this group that is really a *roster*, and the
			# question a roster is opened with is "how is everybody spread".
			# Counted rather than read off a Gantt of forty bars.
			"dashboard": {
		"period_field": "start_date",
		"widgets": [
		{"kind": "number", "label": "Assignments", "width": 4},
		{"kind": "number", "label": "Active", "width": 4,
		 "filters": {"status": "Active"}},
		{"kind": "number", "label": "Ended", "width": 4,
		 "filters": {"status": "Inactive"}},
		{"kind": "donut", "label": "By shift", "group_by": "shift_type",
		 "width": 4},
		{"kind": "bar", "label": "By department", "group_by": "department",
		 "series": "shift_type", "stacked": True,
		 "horizontal": True, "width": 8},
			]},
		}),
	},
	{
		# A rota that repeats, which is the thing **Shifts** is the output of.
		# A Shift Assignment is one person on one day; a Shift Schedule is
		# "every second week, these days, this shift", and a Shift Schedule
		# Assignment is somebody enrolled in one. HRMS then writes the
		# assignments forward on a schedule, which is the difference between a
		# roster that is maintained and a roster that is typed.
		#
		# The pattern itself is a table and lives under Configuration; this is
		# the enrolment, which is about people and belongs on the rail.
		"screen": "schedules", "label": "Shift schedules",
		"singular": "Schedule", "screen_group": "Time",
		"icon": "lucide-calendar",
		"document_type": "Shift Schedule Assignment",
		"fields": "employee_name,shift_schedule,shift_location,"
		          "create_shifts_after,shift_status,enabled",
		"order_by": "employee_name asc",
		"view_types": "board,list",
		"status_field": "shift_status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["shift_schedule", "shift_location",
			                          "create_shifts_after"]},
			"tags": ["shift_schedule", "shift_location"],
		}),
	},
	{
		# And the same idea a month at a time: everybody who is not already on a
		# shift over these dates, put on one. HRMS's Shift Assignment Tool,
		# which is a Single — no list, no record, no New button — and was
		# therefore reachable only from the desk.
		#
		# A component screen naming its doctype, which is how it says who it is
		# for: `spaceview.resolve` refuses the page to a reader the space does
		# not grant it to, and `navigable` keeps the entry out of their rail.
		"screen": "assign-shifts", "label": "Assign shifts",
		"singular": "Assignment", "screen_group": "Time",
		"icon": "lucide-users", "document_type": "Shift Assignment Tool",
		"component": "onehr/assign-shifts",
		"fields": "action,company,shift_type,shift_schedule,shift_location,"
		          "status,start_date,end_date,branch,department,designation,"
		          "employment_type,grade",
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
		# **No status field**, which is a decision rather than an omission. An
		# Attendance Request carries no state at all — HRMS gives it
		# `docstatus` and nothing else, because submitting one *is* approving
		# it and it writes the Attendance rows on the way through. `reason` was
		# standing in, and a badge saying "Work From Home" beside a person's
		# name reads as a verdict on a request that has not had one. It is a
		# kind, so it is a tag; the record header says Draft or Submitted,
		# which is the answer to "has this been approved".
		"view_settings": json.dumps({
			"calendar": {"start_field": "from_date", "end_field": "to_date"},
			"tags": ["reason", "shift", "department"],
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
			"tags": ["shift_type"],
		}),
	},
	{
		# Hours worked beyond the shift, and what they are worth. **Overtime
		# types** was already a table under Configuration and nothing read it —
		# a rate card with no document that applies it — because the slip that
		# does was granted to nobody.
		#
		# It sits in Time rather than Pay because it is *measured* here: a slip
		# is drawn from attendance rows and then names the payslip it went out
		# on, which is why the payroll seat reads one and does not write it.
		"screen": "overtime", "label": "Overtime", "singular": "Slip",
		"screen_group": "Time",
		"icon": "lucide-clock", "document_type": "Overtime Slip",
		"fields": "employee_name,department,posting_date,start_date,end_date,"
		          "total_overtime_duration,salary_slip",
		"order_by": "posting_date desc",
		"view_types": "list,calendar,dashboard",
		"view_settings": json.dumps({
			"calendar": {"start_field": "start_date", "end_field": "end_date"},
			"tags": ["department"],
			# Two numbers and who they belong to, which is the whole of what
			# anybody asks an overtime ledger: how much of it there is, and
			# whether it is one team.
			"dashboard": {
		"period_field": "posting_date",
		"widgets": [
		{"kind": "number", "label": "Slips", "width": 4},
		{"kind": "number", "label": "Hours", "aggregate": "sum",
		 "field": "total_overtime_duration", "width": 4},
		{"kind": "donut", "label": "By department", "group_by": "department",
		 "width": 4},
		{"kind": "bar", "label": "Hours by person", "group_by": "employee",
		 "aggregate": "sum", "field": "total_overtime_duration",
		 "horizontal": True, "width": 12},
			]},
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
			# The type is a table HRMS keeps, not a record anybody opens. The
			# approver stays a person: a face beside a name is what you want
			# when you are looking for whose queue this is sitting in.
			"tags": ["leave_type"],
			# An approver's page rather than a form. The one thing deciding a
			# leave request needs and the form has nowhere to put: how much
			# this person has left. See `lib/screen/recordViews.js`.
			"record": {"as": "absence"},
			"dashboard": {
		"period_field": "from_date",
		"widgets": [
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
		# Worked a public holiday, wants the day back. The self-service door
		# HRMS has that this space had not opened — and the odd part is that the
		# *output* was already here: submitting one writes a Leave Allocation,
		# which has had a screen since the space shipped. A balance that
		# appeared from nowhere is a balance nobody can argue with.
		#
		# **No status field**, for the reason **Attendance requests** gives: a
		# compensatory request carries `docstatus` and nothing else, because
		# submitting one is approving it. The leave type is a kind, so it is a
		# tag.
		"screen": "comp-off", "label": "Compensatory leave",
		"singular": "Request", "screen_group": "Leave",
		"icon": "lucide-calendar",
		"document_type": "Compensatory Leave Request",
		"fields": "employee_name,leave_type,work_from_date,work_end_date,reason",
		"order_by": "work_from_date desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "work_from_date",
			             "end_field": "work_end_date"},
			"tags": ["leave_type"],
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
			"tags": ["leave_type", "leave_period"],
			"dashboard": {
		"period_field": "from_date",
		"widgets": [
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
		# The middle of leave, and it was the hole. **Leave policies** says what
		# a grade is entitled to and **Leave periods** says over what year;
		# neither is a balance until somebody assigns one, and the document that
		# does that was granted to nobody — so a people officer could write the
		# rules and then had to make every allocation by hand, which is the
		# thing the rules exist to avoid.
		#
		# A calendar, because an assignment is a span: the question asked of
		# this list is whose policy runs out at the end of the period.
		"screen": "policy-assignments", "label": "Policy assignments",
		"singular": "Assignment", "screen_group": "Leave",
		"icon": "lucide-file-text", "document_type": "Leave Policy Assignment",
		"fields": "employee_name,leave_policy,assignment_based_on,leave_period,"
		          "effective_from,effective_to,leaves_allocated",
		"order_by": "effective_from desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "effective_from",
			             "end_field": "effective_to"},
			"tags": ["leave_policy", "leave_period", "assignment_based_on"],
		}),
	},
	{
		# And the balance that is wrong by two days, which every leave system
		# produces and most of them make somebody fix by editing a submitted
		# allocation. HRMS gives it a document of its own so the correction is
		# a row somebody signed rather than a number that changed.
		#
		# `adjustment_type` is Allocate or Reduce, which is a *kind* and not a
		# state — the same distinction Attendance requests draws — so it is a
		# tag and the record header says whether it went through.
		"screen": "adjustments", "label": "Adjustments",
		"singular": "Adjustment", "screen_group": "Leave",
		"icon": "lucide-git-compare", "document_type": "Leave Adjustment",
		"fields": "employee_name,leave_type,adjustment_type,from_date,to_date,"
		          "leaves_to_adjust,leaves_after_adjustment",
		"order_by": "posting_date desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "from_date", "end_field": "to_date"},
			"tags": ["leave_type", "adjustment_type"],
		}),
	},
	{
		# A year's leave for everybody who has none yet, in one pass.
		#
		# The other half of **Policy assignments**: that screen is one person at
		# a time and this is the same document written for everybody the filters
		# describe. HRMS's Leave Control Panel, and the interesting part is what
		# its finder leaves out — anybody who already holds an allocation
		# overlapping the period, so ticking everybody is never wrong.
		"screen": "allocate", "label": "Allocate leave",
		"singular": "Allocation", "screen_group": "Leave",
		"icon": "lucide-users", "document_type": "Leave Control Panel",
		"component": "onehr/allocate",
		"fields": "company,allocate_based_on_leave_policy,leave_policy,"
		          "leave_type,dates_based_on,leave_period,from_date,to_date,"
		          "no_of_days,carry_forward,branch,department,designation,"
		          "employment_type,employee_grade",
	},
	{
		"screen": "holidays", "label": "Holidays", "singular": "Holiday list",
		"screen_group": "Leave",
		"icon": "lucide-book-open", "document_type": "Holiday List",
		"fields": "holiday_list_name,from_date,to_date,total_holidays,"
		          "weekly_off",
		"order_by": "from_date desc",
		# A list and nothing else, which is the right answer rather than a gap.
		# The *holidays* are child rows of this document rather than records of
		# their own, so there is nothing for a calendar to place — every view
		# type in the engine draws a doctype's rows, and a Holiday List has one
		# row per country per year. The dates are read on the record.
		"view_types": "list",
		"view_settings": json.dumps({
			"tags": ["weekly_off"],
		}),
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
			# A payslip is a document somebody *reads*, and what it says is in
			# two child tables the form draws as grids. See
			# `lib/screen/recordViews.js`.
			"record": {"as": "payslip"},
			"dashboard": {
		"period_field": "start_date",
		"widgets": [
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
			"tags": ["payroll_frequency", "department"],
		}),
		# No dashboard, and not an omission: a payroll run is a handful of rows
		# a year and every number worth counting about one is a number about
		# the *payslips* it made. Those are on the screen above, where they can
		# be narrowed to a month.
	},
	{
		# Everybody onto a salary structure at the start of a year. The one
		# bulk tool that carries a number per person — a structure assignment
		# needs a base, and the finder fills it in from the employee's grade for
		# somebody to correct.
		"screen": "assign-structures", "label": "Assign structures",
		"singular": "Assignment", "screen_group": "Pay",
		"icon": "lucide-users",
		"document_type": "Bulk Salary Structure Assignment",
		"component": "onehr/assign-structures",
		"fields": "company,salary_structure,from_date,income_tax_slab,"
		          "payroll_payable_account,currency,branch,department,"
		          "designation,employment_type,grade",
	},
	{
		# What a payslip is, other than the structure. A Salary Detail row on
		# every slip HRMS produces points back at an Additional Salary, so the
		# bonus, the deduction and the one-month allowance all live here — and
		# this space granted the components and the structures and no way at all
		# to say "this person, this month, this much".
		#
		# A calendar first, because the field that matters is `payroll_date`:
		# what an ad-hoc pay list is opened with is "what is landing in this
		# run", and that is a month rather than a filter.
		"screen": "additional-pay", "label": "Additional pay",
		"singular": "Entry", "screen_group": "Pay",
		"icon": "lucide-wallet", "document_type": "Additional Salary",
		# `type` is not a column, though it is a field: HRMS labels it "Salary
		# Component Type" and it sits beside the component itself, so the list
		# drew two headings a word apart saying zzBonus and Earning. It is a
		# tag, where the word is the whole of it.
		"fields": "employee_name,salary_component,amount,payroll_date,"
		          "is_recurring",
		"order_by": "payroll_date desc",
		"view_types": "list,calendar,dashboard",
		"view_settings": json.dumps({
			"calendar": {"start_field": "payroll_date"},
			"tags": ["salary_component", "type"],
			"dashboard": {
		"period_field": "payroll_date",
		"widgets": [
		{"kind": "number", "label": "Entries", "width": 4},
		{"kind": "number", "label": "Total", "aggregate": "sum",
		 "field": "amount", "width": 4},
		{"kind": "donut", "label": "By component",
		 "group_by": "salary_component", "width": 4},
		{"kind": "bar", "label": "By person", "group_by": "employee",
		 "aggregate": "sum", "field": "amount", "horizontal": True,
		 "width": 12},
			]},
		}),
	},
	{
		# The same idea with a reason on it. HRMS keeps Employee Incentive
		# separate from Additional Salary because one is a decision somebody
		# makes about a person and the other is a line on a payslip — and
		# submitting an incentive writes the additional salary, which is why
		# both are here and only one of them is typed.
		"screen": "incentives", "label": "Incentives", "singular": "Incentive",
		"screen_group": "Pay",
		"icon": "lucide-wallet", "document_type": "Employee Incentive",
		"fields": "employee_name,department,salary_component,incentive_amount,"
		          "payroll_date",
		"order_by": "payroll_date desc",
		"view_types": "list,calendar,dashboard",
		"view_settings": json.dumps({
			"calendar": {"start_field": "payroll_date"},
			"tags": ["department", "salary_component"],
			"dashboard": {
		"period_field": "payroll_date",
		"widgets": [
		{"kind": "number", "label": "Incentives", "width": 4},
		{"kind": "number", "label": "Paid out", "aggregate": "sum",
		 "field": "incentive_amount", "width": 4},
		{"kind": "donut", "label": "By department", "group_by": "department",
		 "width": 4},
			]},
		}),
	},
	{
		# Back pay. A salary structure agreed in April and effective from
		# January is three months somebody is owed, and the arithmetic is not
		# something to do in a spreadsheet next to a payroll run.
		"screen": "arrears", "label": "Arrears", "singular": "Arrear",
		"screen_group": "Pay",
		"icon": "lucide-wallet", "document_type": "Arrear",
		"fields": "employee_name,payroll_period,salary_structure,"
		          "arrear_start_date,payroll_date",
		"order_by": "payroll_date desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "payroll_date"},
			"tags": ["payroll_period", "salary_structure"],
		}),
	},
	{
		# And the run that was wrong. A day marked leave-without-pay and
		# corrected afterwards is a payslip that has already been submitted, so
		# HRMS reverses it forward rather than editing it — which is the only
		# way a payroll ledger stays a ledger.
		"screen": "corrections", "label": "Corrections",
		"singular": "Correction", "screen_group": "Pay",
		"icon": "lucide-git-compare", "document_type": "Payroll Correction",
		"fields": "employee_name,payroll_period,salary_slip_reference,"
		          "lwp_days,days_to_reverse,payroll_date",
		"order_by": "payroll_date desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "payroll_date"},
			"tags": ["payroll_period"],
		}),
	},
	{
		# Pay held back, which `docs/ERP-SPACES.md` §6 listed as deliberately
		# out and is now in — the same correction Income Tax Slab got, for the
		# same reason. `Salary Slip.salary_withholding` is a picker on a form
		# this space draws; a payroll officer who cannot make one is a payroll
		# officer in the desk, and there is no desk.
		"screen": "withholdings", "label": "Withheld pay",
		"singular": "Withholding", "screen_group": "Pay",
		"icon": "lucide-shield", "document_type": "Salary Withholding",
		"fields": "employee_name,from_date,to_date,payroll_frequency,"
		          "number_of_withholding_cycles,status",
		"order_by": "from_date desc",
		"view_types": "board,list,calendar",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["from_date", "to_date",
			                          "number_of_withholding_cycles"]},
			"calendar": {"start_field": "from_date", "end_field": "to_date"},
			"tags": ["payroll_frequency"],
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
			"dashboard": {
		"period_field": "posting_date",
		"widgets": [
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
			"tags": ["travel_type", "travel_funding", "purpose_of_travel"],
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
		"view_types": "board,list,dashboard",
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
			# Money out against money still owed, which is the one question an
			# advance ledger is opened with and the board cannot answer: a
			# column of cards tells you how many are outstanding and not how
			# much.
			"dashboard": {
		"period_field": "posting_date",
		"widgets": [
		{"kind": "number", "label": "Advances", "width": 4},
		{"kind": "number", "label": "Advanced", "aggregate": "sum",
		 "field": "advance_amount", "width": 4},
		{"kind": "number", "label": "Still owed", "aggregate": "sum",
		 "field": "pending_amount", "width": 4},
		{"kind": "donut", "label": "Where each one stands",
		 "group_by": "status", "width": 4},
		{"kind": "bar", "label": "Owed by person", "group_by": "employee",
		 "aggregate": "sum", "field": "pending_amount",
		 "horizontal": True, "width": 8},
			]},
		}),
	},
	{
		# And what paid it. The counterpart of **Journal entries**: a payroll run
		# posts an accrual, an advance and a claim are paid out, and ERPNext
		# writes the second with a Payment Entry rather than a journal.
		"screen": "payments", "label": "Payments", "singular": "Payment",
		"screen_group": "Pay",
		"icon": "lucide-wallet", "document_type": "Payment Entry",
		"fields": "party_name,posting_date,payment_type,paid_amount,"
		          "mode_of_payment,company",
		"order_by": "posting_date desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "posting_date"},
			"tags": ["payment_type", "mode_of_payment"],
		}),
	},
	{
		# What the run posted, and the screen that makes an old sentence true.
		#
		# `Journal Entry` has been granted Read to this seat since the space
		# shipped, with a comment saying it is "the only way to get from a
		# payslip to the money leaving the account" — and there was no way to
		# look at one. **Make the bank entry** now answers with the entry it
		# wrote and the engine opens it here, which is the whole reason this
		# exists.
		#
		# Read and nothing more, which the engine works out for itself: the New
		# button and the form's controls come from `frappe.has_permission`, and
		# a journal entry is posted by whoever keeps the books. This is the
		# payroll officer's window onto it, not their ledger.
		"screen": "journal", "label": "Journal entries", "singular": "Entry",
		"screen_group": "Pay",
		"icon": "lucide-file-text", "document_type": "Journal Entry",
		"fields": "title,posting_date,voucher_type,total_debit,company,"
		          "user_remark",
		"order_by": "posting_date desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "posting_date"},
			"tags": ["voucher_type", "company"],
		}),
	},
	{
		# What a leaver is owed on the way out, and what they still owe. The
		# people officer runs the separation — that is **Exits** — and the money
		# is this seat's, which is the same line drawn everywhere else here.
		#
		# Three totals on one row, which is the whole document: payable,
		# receivable, and the cost of whatever did not come back.
		"screen": "settlements", "label": "Final settlements",
		"singular": "Settlement", "screen_group": "Pay",
		"icon": "lucide-receipt", "document_type": "Full and Final Statement",
		"fields": "employee_name,department,relieving_date,transaction_date,"
		          "total_payable_amount,total_receivable_amount,status",
		"order_by": "relieving_date desc",
		"view_types": "board,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["relieving_date", "total_payable_amount",
			                          "total_receivable_amount"]},
			"tags": ["department"],
			"dashboard": {
		"period_field": "relieving_date",
		"widgets": [
		{"kind": "number", "label": "Settlements", "width": 4},
		{"kind": "number", "label": "Payable", "aggregate": "sum",
		 "field": "total_payable_amount", "width": 4},
		{"kind": "number", "label": "Receivable", "aggregate": "sum",
		 "field": "total_receivable_amount", "width": 4},
		{"kind": "donut", "label": "Where each one stands",
		 "group_by": "status", "width": 4},
			]},
		}),
	},
	# ----- Hiring ---------------------------------------------------------- #
	{
		# The step before *that*: how many of each role there is budget for,
		# over a period, in a department. `Job Opening.staffing_plan` is a
		# picker this space drew and never filled, so an opening could not be
		# tied to the headcount it was agreed against and the number of
		# positions was a figure somebody remembered.
		"screen": "staffing", "label": "Staffing plans", "singular": "Plan",
		"screen_group": "Hiring",
		"icon": "lucide-chart-line", "document_type": "Staffing Plan",
		"fields": "company,department,from_date,to_date,total_estimated_budget",
		"order_by": "from_date desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "from_date", "end_field": "to_date"},
			"tags": ["department", "company"],
		}),
	},
	{
		# The step *before* an opening exists: a manager saying a role is
		# needed, and somebody agreeing. A board, because that is its whole
		# life — Pending, Open, Filled, Cancelled — and the question anybody
		# has about one is which of those it is stuck at.
		#
		# Granted to the people officer since the space shipped and reachable
		# only from the desk, which is the one place this product does not go.
		"screen": "requisitions", "label": "Requisitions",
		"singular": "Requisition", "screen_group": "Hiring",
		"icon": "lucide-file-text", "document_type": "Job Requisition",
		"fields": "designation,department,no_of_positions,expected_by,"
		          "requested_by_name,status",
		"order_by": "expected_by asc",
		"view_types": "board,list,calendar",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["department", "no_of_positions",
			                          "expected_by"]},
			"calendar": {"start_field": "expected_by"},
			"tags": ["designation", "department"],
		}),
	},
	{
		# Somebody handing you a candidate. The one hiring screen with two
		# readers — an employee files one about a friend, the recruiter works
		# the queue — so it gets a twin like leave and claims do.
		"screen": "referrals", "label": "Referrals", "singular": "Referral",
		"screen_group": "Hiring",
		"icon": "lucide-users", "document_type": "Employee Referral",
		"fields": "full_name,for_designation,current_employer,referrer_name,"
		          "date,status",
		"order_by": "date desc",
		"view_types": "board,list",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["for_designation", "referrer_name",
			                          "date"]},
			"tags": ["for_designation"],
		}),
	},
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
			"tags": ["designation", "department", "location", "employment_type"],
			"dashboard": {
		"period_field": "closes_on",
		"widgets": [
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
			# The two that are tables somebody keeps. `job_title` is a Link to
			# a real Job Opening and stays a record — it is the one thing on an
			# applicant card you actually want to open.
			"tags": ["designation", "source"],
			# No period control, and that is the doctype: a Job Applicant
			# carries no date of its own at all. When somebody applied is the
			# row's `creation`, which is Frappe's bookkeeping rather than a
			# field, and `HIDDEN` keeps it out of every column list for the
			# reason a customer reading a `modified_by` is always an accident.
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
		"view_types": "calendar,board,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "scheduled_on", "diary": True},
			"board": {"card_fields": ["job_applicant", "scheduled_on",
			                          "interview_type"]},
			"tags": ["interview_type", "designation"],
			# How the rounds are going, which the calendar cannot say: a month
			# of chips tells you when they are and nothing about how many are
			# still unheld or what they scored.
			"dashboard": {
		"period_field": "scheduled_on",
		"widgets": [
		{"kind": "number", "label": "Interviews", "width": 4},
		{"kind": "number", "label": "Still to hold", "width": 4,
		 "filters": {"status": "Pending"}},
		{"kind": "number", "label": "Average score", "aggregate": "avg",
		 "field": "average_rating", "width": 4},
		{"kind": "donut", "label": "Where each one stands",
		 "group_by": "status", "width": 4},
		{"kind": "bar", "label": "By round", "group_by": "interview_type",
		 "horizontal": True, "width": 8},
			]},
		}),
	},
	{
		# What the interviewer actually said, which is the only part of an
		# interview anybody re-reads. HRMS keeps it off the Interview because
		# there is one per interviewer and each is submitted separately — a
		# panel of three is three verdicts and an average, and the average is
		# the number the offer gets argued over.
		"screen": "interview-feedback", "label": "Interview feedback",
		"singular": "Feedback", "screen_group": "Hiring",
		"icon": "lucide-message-square", "document_type": "Interview Feedback",
		"fields": "interview,job_applicant,interviewer,interview_type,"
		          "average_rating,result",
		"order_by": "creation desc",
		"view_types": "board,list",
		"status_field": "result",
		"view_settings": json.dumps({
			"board": {"card_fields": ["job_applicant", "interviewer",
			                          "average_rating"]},
			"tags": ["interview_type", "interviewer"],
		}),
	},
	{
		"screen": "offers", "label": "Offers", "singular": "Offer",
		"screen_group": "Hiring",
		"icon": "lucide-file-text", "document_type": "Job Offer",
		"fields": "applicant_name,designation,offer_date,status",
		"order_by": "offer_date desc",
		"view_types": "board,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["designation", "offer_date"]},
			"tags": ["designation"],
			# The last step of the funnel, and the only one that is a *rate*:
			# how many offers were accepted is the number a head of people is
			# asked for and the board can only be counted by eye.
			"dashboard": {
		"period_field": "offer_date",
		"widgets": [
		{"kind": "number", "label": "Offers", "width": 4},
		{"kind": "number", "label": "Accepted", "width": 4,
		 "filters": {"status": "Accepted"}},
		{"kind": "number", "label": "Still out", "width": 4,
		 "filters": {"status": "Awaiting Response"}},
		{"kind": "donut", "label": "How they went", "group_by": "status",
		 "width": 4},
		{"kind": "bar", "label": "By role", "group_by": "designation",
		 "series": "status", "stacked": True, "horizontal": True,
		 "width": 8},
			]},
		}),
	},
	{
		# The paper at the end of it. An offer is a number somebody accepted; an
		# appointment letter is the document they sign, written from a template
		# so the terms are not retyped per hire — and `docs/PRINTING.md` is how
		# it comes out.
		"screen": "appointment-letters", "label": "Appointment letters",
		"singular": "Letter", "screen_group": "Hiring",
		"icon": "lucide-file-text", "document_type": "Appointment Letter",
		"fields": "applicant_name,job_applicant,appointment_date,"
		          "appointment_letter_template,company",
		"order_by": "appointment_date desc",
		"view_types": "list,calendar",
		"view_settings": json.dumps({
			"calendar": {"start_field": "appointment_date"},
			"tags": ["appointment_letter_template", "company"],
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
			"tags": ["kra"],
			"dashboard": {
		"period_field": "end_date",
		"widgets": [
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
			"tags": ["appraisal_cycle", "designation", "department"],
			# No record view of its own, and that is the honest answer rather
			# than a gap. An appraisal's content is the ratings its reviewers
			# type into HRMS's own feedback flow — a child table filled in by
			# several people over a cycle — and a page here that drew them
			# read-only would be a second, worse copy of a form we do not
			# replace. What this space adds is the *comparison*, which is the
			# dashboard below.
			"dashboard": {
		"period_field": "end_date",
		"widgets": [
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
		# An appraisal is a score and a conversation, and this is the
		# conversation. HRMS keeps it off the Appraisal for the same reason it
		# keeps interview feedback off the Interview: there is one per reviewer,
		# each is submitted on its own, and the appraisal's total is what they
		# add up to.
		#
		# **Feedback criteria** under Configuration is the vocabulary the
		# ratings are against — granted here for the first time, because an
		# Appraisal's own rating table points at it and the picker was empty.
		"screen": "feedback", "label": "Feedback", "singular": "Feedback",
		"screen_group": "Growth",
		"icon": "lucide-message-square",
		"document_type": "Employee Performance Feedback",
		"fields": "employee_name,appraisal,reviewer_name,reviewer_designation,"
		          "total_score,added_on",
		"order_by": "added_on desc",
		"view_types": "list,dashboard",
		"view_settings": json.dumps({
			"tags": ["department", "reviewer_designation"],
			"dashboard": {
		"period_field": "added_on",
		"widgets": [
		{"kind": "number", "label": "Reviews", "width": 4},
		{"kind": "number", "label": "Average score", "aggregate": "avg",
		 "field": "total_score", "width": 4},
		{"kind": "donut", "label": "By department", "group_by": "department",
		 "width": 4},
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
			"tags": ["department", "designation"],
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
			"tags": ["training_program", "type", "level"],
		}),
	},
	{
		# How it went, per person. A Training Event says who was invited; a
		# Training Result says who passed, and it is what an appraisal cycle
		# reads when somebody claims a course.
		"screen": "training-results", "label": "Training results",
		"singular": "Result", "screen_group": "Growth",
		"icon": "lucide-graduation-cap", "document_type": "Training Result",
		"fields": "training_event",
		"order_by": "creation desc",
		"view_types": "list",
		"view_settings": json.dumps({"tags": ["training_event"]}),
	},
	{
		# And what the people who sat through it thought, which is filed by its
		# subject and by nobody else — `if_owner` on the Employee seat, so this
		# screen is your own feedback and the people officer's is everybody's.
		# The same shape as **My claims** and **Claims**, decided by the grant
		# rather than by a filter.
		"screen": "training-feedback", "label": "Training feedback",
		"singular": "Feedback", "screen_group": "Growth",
		"icon": "lucide-message-square", "document_type": "Training Feedback",
		"fields": "employee_name,training_event,event_name,course,trainer_name,"
		          "feedback",
		"order_by": "creation desc",
		"view_types": "list",
		"view_settings": json.dumps({"tags": ["training_event", "department"]}),
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
	# ----- The rest of the tables, which had no door at all ---------------- #
	#
	# Everything below is granted to a seat and was reachable only from the
	# desk, which is the one place this product does not go. Each is an
	# ordinary `hide_in_nav` screen, so a tab inherits its columns, its
	# permissions and its New button.
	{
		"screen": "branches", "hide_in_nav": 1, "label": "Branches",
		"singular": "Branch", "icon": "lucide-map-pin", "document_type": "Branch",
		"fields": "branch", "order_by": "branch asc", "view_types": "list",
	},
	{
		"screen": "genders", "hide_in_nav": 1, "label": "Genders",
		"singular": "Gender", "icon": "lucide-user-round", "document_type": "Gender",
		"fields": "gender", "order_by": "gender asc", "view_types": "list",
	},
	{
		"screen": "salutations", "hide_in_nav": 1, "label": "Salutations",
		"singular": "Salutation", "icon": "lucide-user-round",
		"document_type": "Salutation",
		"fields": "salutation", "order_by": "salutation asc", "view_types": "list",
	},
	{
		"screen": "id-types", "hide_in_nav": 1, "label": "ID document types",
		"singular": "Document type", "icon": "lucide-file-text",
		"document_type": "Identification Document Type",
		"fields": "name", "order_by": "name asc", "view_types": "list",
	},
	{
		"screen": "insurance", "hide_in_nav": 1, "label": "Health insurance",
		"singular": "Provider", "icon": "lucide-stethoscope",
		"document_type": "Employee Health Insurance",
		"fields": "health_insurance_name", "order_by": "health_insurance_name asc",
		"view_types": "list",
	},
	{
		"screen": "overtime-types", "hide_in_nav": 1, "label": "Overtime types",
		"singular": "Overtime type", "icon": "lucide-clock",
		"document_type": "Overtime Type",
		"fields": "name", "order_by": "name asc", "view_types": "list",
	},
	{
		"screen": "leave-periods", "hide_in_nav": 1, "label": "Leave periods",
		"singular": "Leave period", "icon": "lucide-calendar",
		"document_type": "Leave Period",
		"fields": "from_date,to_date,company,is_active",
		"order_by": "from_date desc", "view_types": "list",
	},
	{
		"screen": "leave-blocks", "hide_in_nav": 1, "label": "Leave block lists",
		"singular": "Block list", "icon": "lucide-calendar",
		"document_type": "Leave Block List",
		"fields": "leave_block_list_name,company,applies_to_all_departments",
		"order_by": "leave_block_list_name asc", "view_types": "list",
	},
	{
		"screen": "payroll-periods", "hide_in_nav": 1, "label": "Payroll periods",
		"singular": "Payroll period", "icon": "lucide-wallet",
		"document_type": "Payroll Period",
		"fields": "name,start_date,end_date,company",
		"order_by": "start_date desc", "view_types": "list",
	},
	{
		# Not a table anybody keeps twice a year — one row per person per
		# change — and it is here rather than in the rail because it is what
		# somebody setting payroll *up* reaches for, beside the structures it
		# points at. The transactions it feeds are the payslips above.
		"screen": "salary-assignments", "hide_in_nav": 1,
		"label": "Salary assignments", "singular": "Assignment",
		"icon": "lucide-wallet", "document_type": "Salary Structure Assignment",
		"fields": "employee_name,salary_structure,from_date,base,company",
		"order_by": "from_date desc", "view_types": "list",
	},
	{
		"screen": "tax-slabs", "hide_in_nav": 1, "label": "Tax slabs",
		"singular": "Tax slab", "icon": "lucide-receipt",
		"document_type": "Income Tax Slab",
		"fields": "name,effective_from,company,currency,disabled",
		"order_by": "effective_from desc", "view_types": "list",
	},
	{
		"screen": "travel-purposes", "hide_in_nav": 1, "label": "Travel purposes",
		"singular": "Purpose", "icon": "lucide-map",
		"document_type": "Purpose of Travel",
		"fields": "purpose_of_travel", "order_by": "purpose_of_travel asc",
		"view_types": "list",
	},
	{
		"screen": "applicant-sources", "hide_in_nav": 1,
		"label": "Applicant sources", "singular": "Source",
		"icon": "lucide-route", "document_type": "Job Applicant Source",
		"fields": "source_name", "order_by": "source_name asc",
		"view_types": "list",
	},
	{
		"screen": "opening-templates", "hide_in_nav": 1,
		"label": "Opening templates", "singular": "Template",
		"icon": "lucide-briefcase", "document_type": "Job Opening Template",
		"fields": "name,designation", "order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "offer-terms", "hide_in_nav": 1, "label": "Offer terms",
		"singular": "Term", "icon": "lucide-file-text",
		"document_type": "Offer Term",
		"fields": "offer_term", "order_by": "offer_term asc",
		"view_types": "list",
	},
	{
		"screen": "offer-templates", "hide_in_nav": 1,
		"label": "Offer term templates", "singular": "Template",
		"icon": "lucide-file-text",
		"document_type": "Job Offer Term Template",
		"fields": "name", "order_by": "name asc", "view_types": "list",
	},
	{
		"screen": "onboarding-templates", "hide_in_nav": 1,
		"label": "Onboarding templates", "singular": "Template",
		"icon": "lucide-graduation-cap",
		"document_type": "Employee Onboarding Template",
		"fields": "name,department,designation,company",
		"order_by": "name asc", "view_types": "list",
	},
	{
		"screen": "exit-templates", "hide_in_nav": 1,
		"label": "Exit templates", "singular": "Template",
		"icon": "lucide-git-compare",
		"document_type": "Employee Separation Template",
		"fields": "name,department,designation,company",
		"order_by": "name asc", "view_types": "list",
	},
	{
		"screen": "kras", "hide_in_nav": 1, "label": "Result areas",
		"singular": "Result area", "icon": "lucide-chart-line",
		"document_type": "KRA",
		"fields": "title", "order_by": "title asc", "view_types": "list",
	},
	{
		"screen": "appraisal-templates", "hide_in_nav": 1,
		"label": "Appraisal templates", "singular": "Template",
		"icon": "lucide-chart-pie", "document_type": "Appraisal Template",
		"fields": "template_title", "order_by": "template_title asc",
		"view_types": "list",
	},
	{
		"screen": "training-programs", "hide_in_nav": 1,
		"label": "Training programmes", "singular": "Programme",
		"icon": "lucide-graduation-cap", "document_type": "Training Program",
		"fields": "training_program,trainer_name,supplier,status",
		"order_by": "training_program asc", "view_types": "list",
	},
	{
		# The pattern a roster repeats on — every second week, these days, this
		# shift. The enrolment is **Shift schedules** on the rail; this is the
		# thing it enrols somebody in, and there are three of them in a company.
		"screen": "shift-patterns", "hide_in_nav": 1,
		"label": "Shift patterns", "singular": "Pattern",
		"icon": "lucide-calendar", "document_type": "Shift Schedule",
		"fields": "frequency,shift_type",
		"order_by": "creation desc", "view_types": "list",
	},
	{
		# Which calendar a person keeps. HRMS moved this off the Employee
		# record into a document of its own so it can change mid-year and so a
		# whole company can be assigned in one row.
		"screen": "holiday-assignments", "hide_in_nav": 1,
		"label": "Holiday assignments", "singular": "Assignment",
		"icon": "lucide-calendar", "document_type": "Holiday List Assignment",
		"fields": "holiday_list,applicable_for,assigned_to,from_date,"
		          "holiday_list_start,holiday_list_end",
		"order_by": "from_date desc", "view_types": "list",
	},
	{
		# The vocabulary two pickers read and neither could fill: the skills on
		# somebody's **Skills** row and the expected set on an interview type.
		"screen": "skill-types", "hide_in_nav": 1,
		"label": "Skill types", "singular": "Skill",
		"icon": "lucide-graduation-cap", "document_type": "Skill",
		"fields": "skill_name,description",
		"order_by": "skill_name asc", "view_types": "list",
	},
	{
		# What an appointment letter is written from, so the terms are not
		# retyped per hire.
		"screen": "letter-templates", "hide_in_nav": 1,
		"label": "Letter templates", "singular": "Template",
		"icon": "lucide-file-text",
		"document_type": "Appointment Letter Template",
		"fields": "template_name",
		"order_by": "template_name asc", "view_types": "list",
	},
	{
		# What performance feedback is rated against. An Appraisal's own rating
		# table points here, so this table being ungranted is why that section
		# of an appraisal was a list of empty pickers.
		"screen": "feedback-criteria", "hide_in_nav": 1,
		"label": "Feedback criteria", "singular": "Criterion",
		"icon": "lucide-message-square",
		"document_type": "Employee Feedback Criteria",
		"fields": "criteria",
		"order_by": "criteria asc", "view_types": "list",
	},
	{
		# The rules this workspace runs on, and the first Configuration tab in
		# this product that is not a table.
		#
		# HR Settings is a Single — one document, no list — so it had no door of
		# any kind and every decision on it was a desk trip: how long people
		# have to work before they retire, whether a leave application needs an
		# approver, whether somebody may approve their own, how far back a leave
		# day may be dated, and the seven switches that decide what this
		# workspace sends without being asked.
		#
		# Those last seven are why this tab closes more than one gap. Four HRMS
		# scheduled jobs mail people — a birthday, a work anniversary, an
		# interview tomorrow, a feedback form nobody filled in — and until this
		# page existed they ran on whatever the site was installed with and
		# nobody here could see, let alone change, whether they were on.
		#
		# The fields are curated rather than the whole form:
		# `oneapp/onehr/tools.py` lists them and says what was cut and why.
		"screen": "hr-rules", "hide_in_nav": 1,
		"label": "Rules", "singular": "Rule",
		"icon": "lucide-shield", "document_type": "HR Settings",
		"component": "onehr/hr-rules",
		# The allowlist, and it is the *screen's* rather than a second list in
		# `tools.py`: the guards that check a fieldname against the real
		# doctype read this, and so does `check_screens` when it looks for a
		# Link pointing at something this space does not grant.
		#
		# The cuts are all of one kind — a link to something this workspace has
		# no door onto. HR Settings names five Email Templates, two Email
		# Accounts, a Web Form and a Role, and every one of those pickers would
		# be empty here. Two more go for a different reason:
		# `allow_employee_checkin_from_mobile_app` and
		# `allow_geolocation_tracking` govern HRMS's own mobile app, and ours is
		# a browser with the geofence on the Shift Location. A switch over
		# something this workspace does not run is a switch that lies.
		"fields": "retirement_age,emp_created_by,"
		          "leave_approver_mandatory_in_leave_application,"
		          "prevent_self_leave_approval,"
		          "restrict_backdated_leave_application,"
		          "show_leaves_of_all_department_members_in_calendar,"
		          "auto_leave_encashment,send_leave_notification,"
		          "expense_approver_mandatory_in_expense_claim,"
		          "prevent_self_expense_approval,"
		          "enable_multi_currency_expense_claim,"
		          "unlink_payment_on_cancellation_of_employee_advance,"
		          "standard_working_hours,allow_multiple_shift_assignments,"
		          "send_holiday_reminders,frequency,remind_before,"
		          "send_birthday_reminders,send_work_anniversary_reminders,"
		          "send_interview_reminder,send_interview_feedback_reminder,"
		          "check_vacancies",
	},
	{
		# And the rules about pay, which belong to the other seat: what counts
		# as a working day, what an unmarked one is taken to mean, and whether
		# a payslip leaves the building by email and under a password.
		"screen": "payroll-rules", "hide_in_nav": 1,
		"label": "Payroll rules", "singular": "Rule",
		"icon": "lucide-shield", "document_type": "Payroll Settings",
		"component": "onehr/payroll-rules",
		# Same cut: the sender, the sender's copy and the payslip email template
		# are Email Accounts and an Email Template, which are One's to
		# configure. And no benefit application, which §6 keeps out.
		"fields": "payroll_based_on,consider_unmarked_attendance_as,"
		          "consider_marked_attendance_on_holidays,"
		          "include_holidays_in_total_working_days,"
		          "daily_wages_fraction_for_half_day,"
		          "max_working_hours_against_timesheet,"
		          "disable_rounded_total,show_leave_balances_in_salary_slip,"
		          "create_overtime_slip,email_salary_slip_to_employee,"
		          "encrypt_salary_slips_in_emails,password_policy,"
		          "process_payroll_accounting_entry_based_on_employee",
	},
	# The page itself, last, and the only one of these in the rail.
	{
		# Every table this space can write, and nothing it only reads: a
		# Company, a Currency, an Account are administered somewhere else and
		# are here as pickers, which is the one honest reason for a grant with
		# no door. Everything that *is* ours has one now — the alternative was
		# the desk, and there is no desk.
		#
		# Grouped, because thirty is a rail rather than a strip. The headings
		# are the rail's own, one level in; `onespace/configuration.py` says
		# why that is better than four Configuration entries.
		"screen": "configuration", "label": "Configuration",
		"singular": "Table", "icon": "lucide-wrench",
		"component": "configuration",
		"view_settings": json.dumps({"configuration": {"screens": [
			# The two that are not tables, first, because they are the ones
			# that decide how the tables below behave.
			{"label": "Rules", "screens": [
				"hr-rules", "payroll-rules",
			]},
			{"label": "People", "screens": [
				"departments", "designations", "grades", "employment-types",
				"branches", "genders", "salutations", "id-types", "insurance",
			]},
			{"label": "Time", "screens": [
				"shift-types", "shift-patterns", "places", "overtime-types",
			]},
			{"label": "Leave", "screens": [
				"leave-types", "leave-policies", "leave-periods",
				"leave-blocks", "holiday-assignments",
			]},
			{"label": "Pay", "screens": [
				"salary-components", "salary-structures", "salary-assignments",
				"payroll-periods", "tax-slabs", "claim-types",
				"travel-purposes",
			]},
			{"label": "Hiring", "screens": [
				"interview-types", "skill-types", "applicant-sources",
				"opening-templates", "offer-terms", "offer-templates",
				"letter-templates", "onboarding-templates", "exit-templates",
			]},
			{"label": "Growth", "screens": [
				"kras", "appraisal-templates", "feedback-criteria",
				"training-programs", "grievance-types",
			]},
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
