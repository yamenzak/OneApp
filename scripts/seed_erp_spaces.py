"""OneProject, OneCRM and OneHR on the dev tenant, with enough to look at.

Its own file rather than another six hundred lines inside
`seed_dev_space.py`, for one reason: everything in there is over Frappe's own
doctypes and runs on a bare site, and everything in here needs ERPNext and
HRMS. Keeping them apart is what lets the fixture say "skipped, no ERPNext"
in one sentence instead of failing in the middle.

**One company, made once.** A fresh site has never run ERPNext's setup wizard,
so it has no Warehouse Type, no UOM and no chart of accounts, and the first
`Company` insert dies on a link to a record nobody made. `_ground` installs
ERPNext's own preset fixtures and one company; it takes about six seconds and
only on a site that has not had it. Every run after that finds them and does
nothing, which is what keeps `dev.sh seed` at the three seconds the rest of it
costs.

**Deterministic.** Every date is an offset from today and every number is
written down, so two runs produce the same screens and a screenshot is
comparable between them. Names are prefixed `zz` like the rest of the fixture,
so they sort last and are obvious as fixture data.
"""

import frappe
from frappe.utils import add_to_date, getdate, nowdate

COMPANY = "zzNorthgate"
ABBR = "ZZN"


def _day(offset: int) -> str:
	"""A date, as a string, `offset` days from today."""
	return str(getdate(add_to_date(nowdate(), days=offset)))


def _one(doctype: str, key_field: str, key: str, values: dict) -> str:
	"""Upsert by natural key. The same helper the rest of the fixture uses; a
	copy rather than an import because this file is loaded on sites where that
	one's module-level ERPNext assumptions do not hold."""
	name = frappe.db.get_value(doctype, {key_field: key}, "name")
	if name:
		doc = frappe.get_doc(doctype, name)
		if _same(doc, values):
			# The second run of a fixture is almost entirely this branch, and
			# saving a document to write back what it already says is what made
			# `dev.sh seed` three times slower than it needed to be. Child
			# tables are not compared — a row is cheap to rewrite and expensive
			# to diff — so anything carrying one is saved every time.
			return doc.name
		doc.update(values)
		doc.save(ignore_permissions=True)
		return doc.name
	return frappe.get_doc({"doctype": doctype, key_field: key, **values}).insert(
		ignore_permissions=True
	).name


def _same(doc, values: dict) -> bool:
	"""Whether a document already says everything it is being asked to say."""
	for field, wanted in values.items():
		if isinstance(wanted, (list, dict)):
			return False
		held = doc.get(field)
		if str(held or "") != str(wanted if wanted is not None else ""):
			return False
	return True


def _named(doctype: str, name: str, values: dict) -> str:
	"""The same, for a doctype whose id *is* its title — `autoname` is a
	prompt or a field, and the natural key is the document name."""
	if frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		if _same(doc, values):
			return doc.name
		doc.update(values)
		doc.save(ignore_permissions=True)
		return doc.name
	return frappe.get_doc({"doctype": doctype, "name": name, **values}).insert(
		ignore_permissions=True
	).name


def _submit(doc) -> bool:
	"""Submit, and say which document refused rather than stopping the pass."""
	try:
		doc.submit()
		return True
	except Exception as raised:
		frappe.clear_last_message()
		print(f"  ! {doc.doctype} {doc.name} would not submit: {raised}")
		return False


def _once(doctype: str, key_field: str, key: str, values: dict) -> str:
	"""Made if it is not there, and left alone if it is.

	For a doctype with a `set_only_once` field. Goal's `employee` is one, so
	the ordinary upsert fails with `Value cannot be changed for Employee` the
	second time a fixture runs — which is a re-run that works on a fresh site
	and not on anybody's.
	"""
	found = frappe.db.get_value(doctype, {key_field: key}, "name")
	if found:
		return found
	return frappe.get_doc({"doctype": doctype, key_field: key, **values}).insert(
		ignore_permissions=True
	).name


def _submitted(doctype: str, filters: dict, values: dict):
	"""A submittable document, made and submitted once.

	Half of HRMS is submittable, and a draft in a fixture is a screen whose
	every badge says Draft — which is exactly the thing these screens are
	meant to show the shape of.
	"""
	found = frappe.db.get_value(doctype, filters, "name")
	if found:
		return found
	doc = frappe.get_doc({"doctype": doctype, **filters, **values})
	doc.insert(ignore_permissions=True)
	try:
		doc.submit()
	except Exception as raised:
		# A fixture that dies halfway leaves a site nobody can seed again. Say
		# which document refused and carry on — the screen is thinner and the
		# rest of the pass still runs.
		frappe.clear_last_message()
		print(f"  ! {doctype} {doc.name} would not submit: {raised}")
	return doc.name


def _excused(name: str, person: str, day) -> None:
	"""Point a day of leave at the application that granted it."""
	found = frappe.get_all(
		"Leave Application",
		filters={
			"employee": frappe.db.get_value("Employee", {"employee_name": person}, "name"),
			"status": "Approved",
			"from_date": ["<=", day],
			"to_date": [">=", day],
		},
		fields=["name", "leave_type"],
		limit=1,
	)
	if not found:
		return
	frappe.db.set_value("Attendance", name, {
		"leave_type": found[0].leave_type,
		"leave_application": found[0].name,
	}, update_modified=False)


def _clocked(name: str, person: str, at: int, letter: str) -> None:
	"""Put a day on the clock: the two times, the hours, and any flag.

	Written with `db.set_value` rather than on the way in, for two reasons. An
	Attendance is submitted the moment it is made, so the ordinary write path is
	closed after that; and every run rewrites these, so a site seeded before
	this existed gets the times on the next pass instead of needing the fixture
	torn down.
	"""
	day = frappe.db.get_value("Attendance", name, "attendance_date")

	odd = ATTENDANCE_ODD.get((person, at))
	if odd:
		start, end, hours, flag = odd
	elif letter in ATTENDANCE_CLOCK:
		start, end, hours = ATTENDANCE_CLOCK[letter]
		flag = ""
	else:
		# A day nobody worked. No times to write — but where an approved Leave
		# Application covers it, the two links HRMS writes when *it* marks the
		# day, which is what lets the day page say why rather than just "On
		# Leave".
		_excused(name, person, day)
		return

	frappe.db.set_value("Attendance", name, {
		"in_time": f"{day} {start}",
		"out_time": f"{day} {end}",
		"working_hours": hours,
		"standard_working_hours": ATTENDANCE_SHIFT_HOURS,
		"late_entry": int(flag == "late_entry"),
		"early_exit": int(flag == "early_exit"),
		# The other half of a half day, which is the one thing that verdict
		# does not say on its own.
		"half_day_status": "Absent" if letter == "H" else "",
	}, update_modified=False)


# --------------------------------------------------------------------------- #
# The ground a fixture needs before it can write anything
# --------------------------------------------------------------------------- #

def ready() -> bool:
	"""Whether this site carries the apps these spaces are over."""
	return bool(frappe.db.exists("DocType", "Project")
	            and frappe.db.exists("DocType", "Employee"))


def _ground() -> str:
	"""ERPNext's own presets and one company, both made once.

	`install_fixtures` is what the setup wizard runs — warehouse types, units,
	sales stages, territories, industries, the lot. A site that has never had
	it refuses the first Company insert with `Could not find Warehouse Type:
	Transit`, which is a confusing way to be told the wizard never ran.
	"""
	if not frappe.db.exists("Warehouse Type", "Transit"):
		from erpnext.setup.setup_wizard.operations import install_fixtures

		install_fixtures.install("United Arab Emirates")

	# And ERPNext's own `after_install`, which is a different list: the custom
	# fields it puts on Frappe's Address and Contact, the print settings, the
	# role profiles. A site where it never finished fails much later and much
	# further away — the first Contact query dies with `Unknown column
	# tabContact.is_billing_contact`, which says nothing about install order.
	if not frappe.db.exists("Custom Field", {"dt": "Contact",
	                                         "fieldname": "is_billing_contact"}):
		from erpnext.setup import install as erpnext_install

		erpnext_install.after_install()

	if not frappe.db.exists("Company", COMPANY):
		frappe.get_doc({
			"doctype": "Company", "company_name": COMPANY, "abbr": ABBR,
			"default_currency": "AED", "country": "United Arab Emirates",
		}).insert(ignore_permissions=True)

	# And the one every document that needs a company falls back to. Without a
	# global default, `Project.company` is mandatory with nothing behind it, so
	# an ordinary `frappe.client.insert` of a Project is refused — which is what
	# three of `chat.spec.js`'s tests do before they have anything to talk
	# about. A site with exactly one company should have it as the default.
	if not frappe.defaults.get_defaults().get("company"):
		frappe.db.set_default("company", COMPANY)

	# Cost centres, which ERPNext normally makes with the company. A company
	# whose first insert died half way — on this bench, on a missing Warehouse
	# Type — has its accounts and none of these, and the failure surfaces much
	# later as "Cost Center None does not belong to company" on the first
	# invoice.
	#
	# ERPNext's own method rather than two inserts here: the root cost centre
	# is the one document in the system that is allowed no parent, and it is
	# allowed that by a flag their code sets and a manifest cannot.
	if not frappe.db.exists("Cost Center", {"company": COMPANY, "is_group": 0}):
		frappe.get_doc("Company", COMPANY).create_default_cost_center()
		frappe.db.set_value("Company", COMPANY, {
			"cost_center": f"Main - {ABBR}",
			"round_off_cost_center": f"Main - {ABBR}",
		})

	# The two accounts ERPNext resolves without being asked and refuses to
	# invent. A company built by the wizard has them; this one is missing them
	# for the same reason it was missing its cost centres, and the first
	# invoice stops with "Please mention 'Round Off Account' in Company".
	for field, kind in (("round_off_account", "Round Off"),
	                    ("default_income_account", "Income Account"),
	                    ("default_expense_account", "Expense Account")):
		if frappe.db.get_value("Company", COMPANY, field):
			continue
		found = frappe.db.get_value("Account", {
			"company": COMPANY, "is_group": 0, "account_type": kind,
		}, "name")
		if found:
			frappe.db.set_value("Company", COMPANY, field, found)

	# A year to post into. Nothing here writes a ledger entry, but Leave
	# Period, Payroll Period and a Salary Slip all resolve one, and its absence
	# surfaces as a validation error three doctypes away from the cause.
	year = str(getdate(nowdate()).year)
	if not frappe.db.exists("Fiscal Year", year):
		frappe.get_doc({
			"doctype": "Fiscal Year", "year": year,
			"year_start_date": f"{year}-01-01", "year_end_date": f"{year}-12-31",
		}).insert(ignore_permissions=True)

	# Frappe ships these as install fixtures and a site that was built before
	# somebody ran them has none, which surfaces as `Could not find Gender:
	# Female` four doctypes into a fixture about projects.
	for gender in ("Male", "Female"):
		if not frappe.db.exists("Gender", gender):
			frappe.get_doc({"doctype": "Gender", "gender": gender}).insert(
				ignore_permissions=True)

	_named("Holiday List", "zzWeekends", {
		"holiday_list_name": "zzWeekends",
		"from_date": f"{year}-01-01", "to_date": f"{year}-12-31",
		"weekly_off": "Friday",
	})
	# And filled. `weekly_off` is the *setting*, not the days: HRMS writes the
	# rows when somebody presses "Get Weekly Off Dates" in the desk, and a list
	# made by a fixture has none — so every weekend read as a day with no record
	# rather than as a holiday, and the attendance strip on a person's record
	# was two months of gaps.
	holidays = frappe.get_doc("Holiday List", "zzWeekends")
	if not holidays.holidays:
		holidays.get_weekly_off_dates()
		holidays.save(ignore_permissions=True)
	# And one that is not a weekend, a week out. The employee's own page keeps
	# weekly offs out of "coming up" on purpose — a block whose every line says
	# "Friday" is a block people stop reading — so a fixture with nothing but
	# weekends has an empty one and nothing to look at.
	_holiday(holidays, _day(7), "zzFounders' day")
	frappe.db.set_value("Company", COMPANY, "default_holiday_list", "zzWeekends")

	# HRMS checks the *role*, not the permission: a leave application whose
	# approver does not hold `Leave Approver` is refused with "Only Approvers
	# can Approve this Request", and the same for expenses. ERPNext's own
	# `after_install` hands Administrator every role it knows about, and HRMS
	# was installed after it — so on this bench the three that matter are
	# missing and the whole HR half of the fixture stops.
	me = frappe.get_doc("User", frappe.session.user)
	held = {row.role for row in me.roles}
	for role in ("Leave Approver", "Expense Approver", "HR Manager", "HR User"):
		if frappe.db.exists("Role", role) and role not in held:
			me.append("roles", {"role": role})
	me.save(ignore_permissions=True)

	# And the assignment, which is how this version of HRMS actually finds it.
	# The `holiday_list` field on an Employee is no longer the answer: every
	# attendance and leave document resolves a Holiday List Assignment and
	# refuses with "No Holiday List was found" when there is none, naming a
	# screen rather than the rule.
	if not frappe.db.exists("Holiday List Assignment", {"assigned_to": COMPANY}):
		frappe.get_doc({
			"doctype": "Holiday List Assignment", "holiday_list": "zzWeekends",
			"applicable_for": "Company", "assigned_to": COMPANY,
			"from_date": f"{year}-01-01",
		}).insert(ignore_permissions=True).submit()
	return COMPANY


def _holiday(holidays, on, description: str) -> None:
	"""One named day off, added to a list that is otherwise weekends.

	Through the child table rather than as a Holiday row of its own: `Holiday`
	is a child doctype and a row inserted without its parent's save is a row
	`get_weekly_off_dates` will happily duplicate the next time it runs.
	"""
	on = str(on)
	if any(str(row.holiday_date) == on for row in holidays.holidays):
		return
	holidays.append("holidays", {"holiday_date": on, "description": description,
	                             "weekly_off": 0})
	holidays.save(ignore_permissions=True)


CUSTOMERS = [
	("zzMeridian Group", "Commercial", "All Territories"),
	("zzAlmond Holdings", "Commercial", "All Territories"),
	("zzCity of Harbour", "Government", "All Territories"),
]


def _customers() -> list[str]:
	made = []
	for name, group, territory in CUSTOMERS:
		group = group if frappe.db.exists("Customer Group", group) else "All Customer Groups"
		made.append(_one("Customer", "customer_name", name, {
			"customer_type": "Company", "customer_group": group,
			"territory": territory,
		}))
	return made


DEPARTMENTS = ["zzDelivery", "zzDesign", "zzCommercial", "zzPeople"]

# name, designation, department, reports to (index into this list), joined
#: Which of them the dev site's own login is. See `_seat`.
SEATED = "zzSami Rahal"
SEAT = "Administrator"

PEOPLE = [
	("zzNoor Haddad", "Managing Director", "zzDelivery", None, -1600),
	("zzSami Rahal", "Projects Manager", "zzDelivery", 0, -1200),
	("zzLeila Amari", "Designer", "zzDesign", 1, -900),
	("zzOmar Fadel", "Engineer", "zzDelivery", 1, -700),
	("zzRania Sabbagh", "Accounts Manager", "zzCommercial", 0, -1100),
	("zzKarim Nassar", "Engineer", "zzDelivery", 1, -400),
	("zzHala Zayed", "HR Manager", "zzPeople", 0, -1400),
	("zzTarek Jaber", "Business Development Manager", "zzCommercial", 0, -300),
]


def _people(company: str) -> dict[str, str]:
	"""The eight people the three spaces share, and the chain between them.

	`reports_to` is written in a second pass, because an Employee cannot report
	to somebody who has not been made yet — and the org chart is the whole
	reason this fixture has a chain at all rather than eight peers.
	"""
	# The root first. ERPNext's Department is a nested set and its own
	# `on_update` points a parentless one at the root — so on a site where no
	# root exists the first department becomes its own parent, and every save
	# after that dies with `Item cannot be added to its own descendants`. The
	# setup wizard makes this row; a site that never ran it has not got it.
	root = f"zzAll departments - {ABBR}"
	if not frappe.db.exists("Department", root):
		frappe.get_doc({
			"doctype": "Department", "department_name": "zzAll departments",
			"company": company, "is_group": 1,
		}).insert(ignore_permissions=True)
	for department in DEPARTMENTS:
		_one("Department", "department_name", department, {
			"company": company, "parent_department": root,
		})

	made = {}
	for full_name, designation, department, _reports, joined in PEOPLE:
		first, last = full_name.split(" ", 1)
		if not frappe.db.exists("Designation", designation):
			_named("Designation", designation, {"designation_name": designation})
		made[full_name] = _one("Employee", "employee_name", full_name, {
			"first_name": first, "last_name": last, "company": company,
			"gender": "Female" if full_name in (
				"zzNoor Haddad", "zzLeila Amari", "zzRania Sabbagh", "zzHala Zayed",
			) else "Male",
			"date_of_birth": _day(-12000), "date_of_joining": _day(joined),
			"designation": designation,
			"department": frappe.db.get_value(
				"Department", {"department_name": department}, "name"),
			"holiday_list": "zzWeekends", "status": "Active",
		})

	for full_name, _designation, _department, reports, _joined in PEOPLE:
		if reports is None:
			continue
		frappe.db.set_value("Employee", made[full_name], "reports_to",
		                    made[PEOPLE[reports][0]])

	_seat(made[SEATED])
	return made


def _seat(employee: str) -> None:
	"""Link one of them to the login the dev site is read as.

	Without this there is nobody whose own page OneHR's Home screen could draw:
	`onehr/me.py` finds the reader by `user_id` and by nothing else, on purpose,
	so an unlinked fixture renders the "your login is not linked" sentence and
	the eight blocks are never seen.

	Sami is the one with a manager above him, three people under him and peers
	beside him, which is the only arrangement in this fixture where the team
	block has all three kinds in it.

	`Administrator` rather than a made-up login, because that is who a browser
	pass signs in as — and it is the one user Frappe exempts from User
	Permissions, so linking it writes the row ERPNext always writes and narrows
	nothing for the other two hundred specs that read this site.

	Written with `db.set_value` rather than through the document: `Employee.
	update_user` copies the name, the date of birth and the photograph onto the
	User it is linked to, and renaming the dev site's Administrator to a seeded
	person is a surprise nobody asked the fixture for.
	"""
	if frappe.db.get_value("Employee", employee, "user_id") == SEAT:
		return
	frappe.db.set_value("Employee", employee, {
		"user_id": SEAT, "create_user_permission": 0,
	})


# --------------------------------------------------------------------------- #
# OneProject
# --------------------------------------------------------------------------- #

PROJECT_TYPES = ["zzFit-out", "zzRefurbishment", "zzNew build"]

ACTIVITY_TYPES = [
	("zzDesign", 180, 320),
	("zzSite work", 120, 210),
	("zzProject management", 220, 380),
]

# name, type, customer, health, status, percent, budget, spent, billed,
# start offset, end offset, manager (index into PEOPLE)
PROJECTS = [
	("zzHarbour Point fit-out", "zzFit-out", "zzMeridian Group",
	 "On track", "Open", 62, 480000, 271000, 240000, -60, 30, 1),
	("zzAlmond Court refurbishment", "zzRefurbishment", "zzAlmond Holdings",
	 "At risk", "Open", 35, 265000, 132000, 80000, -30, 45, 1),
	("zzCivic Library atrium", "zzNew build", "zzCity of Harbour",
	 "Off track", "Open", 15, 720000, 198000, 0, -90, 40, 3),
	("zzRiverside offices", "zzFit-out", "zzMeridian Group",
	 "On track", "Completed", 100, 190000, 176000, 190000, -200, -20, 1),
]

# project index, subject, status, priority, progress, start, end, milestone
TASKS = [
	(0, "zzSurvey the existing shell", "Completed", "Medium", 100, -58, -50, 0),
	(0, "zzCeiling and services coordination", "Working", "High", 55, -40, 5, 0),
	(0, "zzJoinery shop drawings", "Working", "Medium", 40, -30, 8, 0),
	(0, "zzClient sign-off on finishes", "Pending Review", "High", 80, -12, 2, 1),
	(0, "zzPractical completion", "Open", "High", 0, 20, 30, 1),
	(1, "zzAsbestos survey", "Completed", "Urgent", 100, -28, -22, 0),
	(1, "zzStrip out", "Working", "High", 60, -20, 6, 0),
	(1, "zzMechanical first fix", "Open", "Medium", 0, 4, 22, 0),
	(1, "zzHandover to the client", "Open", "Medium", 0, 38, 45, 1),
	(2, "zzPlanning submission", "Completed", "Urgent", 100, -88, -70, 1),
	(2, "zzSteelwork package", "Overdue", "Urgent", 45, -60, -8, 0),
	(2, "zzGlazing package", "Open", "High", 0, -5, 25, 0),
	(2, "zzRevised programme", "Pending Review", "Urgent", 70, -10, 1, 0),
	(3, "zzSnagging", "Completed", "Low", 100, -40, -28, 0),
	(3, "zzFinal account", "Completed", "Medium", 100, -30, -20, 1),
]

# Two of them hang under another, so the tree is a tree.
SUBTASKS = [
	("zzCeiling and services coordination", "zzDuctwork routing", "Working",
	 "Medium", 50, -38, 2),
	("zzCeiling and services coordination", "zzSprinkler layout", "Open",
	 "Medium", 0, -20, 4),
]


def _projects(company: str, people: dict) -> int:
	for one in PROJECT_TYPES:
		_named("Project Type", one, {"project_type": one})
	for one, costing, billing in ACTIVITY_TYPES:
		_named("Activity Type", one, {
			"activity_type": one, "costing_rate": costing, "billing_rate": billing,
		})

	made = []
	for (name, kind, customer, health, status, percent, budget, spent, billed,
	     start, end, manager) in PROJECTS:
		made.append(_one("Project", "project_name", name, {
			"company": company, "status": status, "project_type": kind,
			"customer": frappe.db.get_value("Customer", {"customer_name": customer}, "name"),
			"expected_start_date": _day(start), "expected_end_date": _day(end),
			"percent_complete_method": "Manual", "percent_complete": percent,
			"estimated_costing": budget,
			"priority": "High" if health == "Off track" else "Medium",
			"custom_health": health,
			"custom_manager": frappe.session.user,
			"holiday_list": "zzWeekends",
		}))

	by_subject = {}
	for (project, subject, status, priority, progress, start, end, milestone) in TASKS:
		by_subject[subject] = _one("Task", "subject", subject, {
			"project": made[project], "company": company, "status": status,
			"priority": priority, "progress": progress,
			"exp_start_date": _day(start), "exp_end_date": _day(end),
			"is_milestone": milestone, "expected_time": 8 * max(1, (end - start) // 3),
		})
	# A Task with children has to say it is a group first: ERPNext refuses the
	# child otherwise, and the message names the parent rather than the rule.
	for parent in {row[0] for row in SUBTASKS}:
		frappe.db.set_value("Task", by_subject[parent], "is_group", 1,
		                    update_modified=False)
	for parent, subject, status, priority, progress, start, end in SUBTASKS:
		by_subject[subject] = _one("Task", "subject", subject, {
			"project": frappe.db.get_value("Task", by_subject[parent], "project"),
			"parent_task": by_subject[parent], "company": company,
			"status": status, "priority": priority, "progress": progress,
			"exp_start_date": _day(start), "exp_end_date": _day(end),
			"expected_time": 16,
		})

	# Three weeks of hours against the two live projects, so the calendar has
	# spans on it and the dashboard has something to add up.
	# Five weeks of hours, but *not* five consecutive weeks back: a calendar
	# opens on the month you are in, and a fixture spread over six weeks puts
	# four of its five sheets in the month before it. So two people work the
	# same weeks instead, which is also what a real timesheet screen looks
	# like.
	sheets = 0
	for person, project, activity, hours, start in [
		("zzOmar Fadel", 0, "zzSite work", 34, -4),
		("zzLeila Amari", 0, "zzDesign", 28, -4),
		("zzKarim Nassar", 1, "zzSite work", 40, -11),
		("zzSami Rahal", 2, "zzProject management", 22, -11),
		("zzOmar Fadel", 2, "zzSite work", 37, -18),
	]:
		found = frappe.db.get_value("Timesheet", {
			"employee": people[person], "start_date": _day(start),
		}, ["name", "docstatus"], as_dict=True)
		if found:
			# A draft one a previous run left behind. Submitted rather than
			# skipped: a project's spend and billing are rolled up *on submit*,
			# so a fixture of drafts is four screens of zeroes.
			if found.docstatus == 0:
				_submit(frappe.get_doc("Timesheet", found.name))
			continue
		# A row per weekday rather than one row spanning the week: ERPNext
		# computes a log's hours from its own two timestamps, so a single row
		# from Monday morning to Friday evening is a hundred and four hours.
		# ERPNext computes a log's hours from its two timestamps and ignores
		# the number you give it, so the day has to be the right *length*
		# rather than the right label — otherwise every person on the Hours by
		# person chart works the same identical week.
		each = round(hours / 5, 2)
		ends = f"{9 + int(each):02d}:{int((each % 1) * 60):02d}:00"
		sheet = frappe.get_doc({
			"doctype": "Timesheet", "company": company, "employee": people[person],
			"parent_project": made[project],
			"time_logs": [{
				"activity_type": activity, "project": made[project],
				"from_time": _day(start + day) + " 09:00:00",
				"to_time": _day(start + day) + " " + ends,
				"hours": each, "is_billable": 1, "billing_hours": each,
			} for day in range(5)],
		})
		sheet.insert(ignore_permissions=True)
		_submit(sheet)
		sheets += 1

	# What has been billed, so the portfolio's Spent and Billed are numbers
	# ERPNext worked out rather than numbers this file asserted. They used to
	# be written straight to the column and were quietly zeroed again the
	# moment anything else saved a project — which is what a derived field
	# does, and is why a fixture has to produce the documents it derives from.
	for project, customer, amount, when in (
		(0, "zzMeridian Group", 140000, -45),
		(0, "zzMeridian Group", 100000, -12),
		(3, "zzMeridian Group", 190000, -60),
	):
		if frappe.db.exists("Sales Invoice", {
			"project": made[project], "grand_total": amount,
		}):
			continue
		invoice = frappe.get_doc({
			"doctype": "Sales Invoice", "company": company,
			"customer": frappe.db.get_value(
				"Customer", {"customer_name": customer}, "name"),
			"project": made[project],
			# ERPNext ignores a posting date unless it is told the time was
			# set deliberately, so without this every invoice posts today and
			# the due date computed from the *intended* date is in the past —
			# which is refused, and the message blames the due date.
			"set_posting_time": 1,
			"posting_date": _day(when), "due_date": _day(when + 30),
			"currency": "AED", "conversion_rate": 1,
			"selling_price_list": _price_list(), "price_list_currency": "AED",
			"plc_conversion_rate": 1,
			"debit_to": _receivable_account(company),
			"items": [{
				"item_code": _service_item(), "qty": 1, "rate": amount,
				"income_account": _income_account(company),
				# Only where there is one. A company made without the wizard
				# may have no leaf cost center, and naming a blank one is
				# refused with "Cost Center None does not belong to company".
				**({"cost_center": _cost_center(company)}
				   if _cost_center(company) else {}),
			}],
		})
		try:
			invoice.insert(ignore_permissions=True)
			invoice.submit()
		except Exception as raised:
			frappe.clear_last_message()
			print(f"  ! invoice for {customer} would not post: {raised}")

	_drawings(made)
	return len(made)


#: The one file every project carries. Named without a millisecond in it on
#: purpose: the dev seeder sweeps `<something> <Date.now()>` as a browser pass's
#: litter, and a fixture that looked like litter would be swept with it.
DRAWING = "zzIssue sheet.txt"


def _drawings(projects: list[str]) -> None:
	"""An attachment on every project, and put back if a pass binned it.

	The Drive's Records place lists the *kinds of record that have a file on
	them*, so a project with nothing attached is a kind that is not there —
	and `drive.spec.js` has three specs that upload onto the first project and
	one that ticks everything on it and bins the lot. That left the fixture
	with eight trashed files and no live one, and the Records spec read as the
	tree being broken rather than as the tree being empty.

	One per project rather than one in total, because the specs all reach for
	the first row and the first row moves with `modified`: whichever they
	empty, three are still filed.
	"""
	for project in projects:
		found = frappe.db.get_value(
			"File",
			{"attached_to_doctype": "Project", "attached_to_name": project,
			 "file_name": DRAWING},
			["name", "custom_status"], as_dict=True,
		)
		if found:
			# Binned by a browser pass. Put back rather than duplicated: a
			# second row with the same name is how a fixture grows a page of
			# itself over a month of runs.
			if found.custom_status and found.custom_status != "Active":
				frappe.db.set_value("File", found.name, "custom_status", "Active",
				                    update_modified=False)
			continue
		frappe.get_doc({
			"doctype": "File",
			"file_name": DRAWING,
			"attached_to_doctype": "Project",
			"attached_to_name": project,
			"is_private": 1,
			"content": (
				"Issue sheet\n"
				"===========\n\n"
				"Rev C to site. Setting-out unchanged; see the RFI log for the\n"
				"two queries still open against the ceiling void.\n"
			),
		}).insert(ignore_permissions=True)


def _service_item() -> str:
	"""The one thing this fixture sells. Shared by the quotations and the
	invoices, because two items called the same thing is a link that resolves
	to whichever was made first."""
	return _one("Item", "item_code", "zzProfessional services", {
		"item_name": "zzProfessional services", "is_stock_item": 0,
		"item_group": "Services" if frappe.db.exists("Item Group", "Services")
		else "All Item Groups",
		"stock_uom": "Nos" if frappe.db.exists("UOM", "Nos") else "Unit",
	})


def _receivable_account(company: str) -> str:
	return (frappe.db.get_value("Account", {"company": company, "is_group": 0,
	                                        "account_type": "Receivable"}, "name") or "")


def _income_account(company: str) -> str:
	"""Where a sale lands. `account_type` first and `root_type` only as a
	fallback: the first Income leaf in ERPNext's own chart is Exchange Gain,
	which is an income account and not the one anybody means."""
	return (frappe.db.get_value("Company", company, "default_income_account")
	        or frappe.db.get_value("Account", {
		        "company": company, "is_group": 0,
		        "account_type": "Income Account"}, "name")
	        or frappe.db.get_value("Account", {
		        "company": company, "is_group": 0,
		        "root_type": "Income"}, "name") or "")


def _cost_center(company: str) -> str:
	return (frappe.db.get_value("Cost Center", {"company": company, "is_group": 0},
	                            "name") or "")


# --------------------------------------------------------------------------- #
# OneCRM
# --------------------------------------------------------------------------- #

SOURCES = ["zzWebsite", "zzReferral", "zzExhibition", "zzCold call"]

# company, industry, size, revenue, owner
PROSPECTS = [
	("zzHalcyon Developments", "Real Estate", "201-500", 42000000),
	("zzBrightwater Hotels", "Hospitality", "501-1000", 88000000),
	("zzNorth Ridge Schools", "Education", "51-200", 12000000),
	("zzPeregrine Logistics", "Transportation", "1000+", 210000000),
]

# name, organisation, qualification, status, source, job title, next step, in days
LEADS = [
	("zzAdel Mroue", "zzHalcyon Developments", "Qualified", "Open",
	 "zzReferral", "Head of Projects", "zzSend the fit-out case study", 1),
	("zzMira Choueiri", "zzBrightwater Hotels", "In Process", "Replied",
	 "zzExhibition", "Development Director", "zzAgree a site visit", 3),
	("zzFouad Kassem", "zzNorth Ridge Schools", "Unqualified", "Lead",
	 "zzCold call", "Bursar", "zzCheck the budget cycle", 9),
	("zzYara Chehab", "zzPeregrine Logistics", "Qualified", "Interested",
	 "zzWebsite", "Facilities Manager", "zzScope the warehouse offices", -2),
	("zzHadi Srour", "zzHalcyon Developments", "In Process", "Open",
	 "zzWebsite", "Procurement Lead", "zzChase the drawings", 6),
	("zzLina Traboulsi", "zzBrightwater Hotels", "Qualified", "Opportunity",
	 "zzReferral", "Operations Director", "", 0),
	("zzGhassan Daher", "zzPeregrine Logistics", "Unqualified", "Do Not Contact",
	 "zzCold call", "Analyst", "", 0),
	("zzSalma Rizk", "zzNorth Ridge Schools", "In Process", "Replied",
	 "zzExhibition", "Estates Manager", "zzSend revised rates", -5),
	("zzWalid Baroudi", "zzHalcyon Developments", "Qualified", "Quotation",
	 "zzWebsite", "Commercial Manager", "zzFollow up on the quotation", 2),
	("zzNadia Fares", "zzBrightwater Hotels", "Unqualified", "Lead",
	 "zzWebsite", "Marketing Manager", "", 0),
]

# title, customer, stage, status, amount, probability, closing in days,
# next step, next step in days
DEALS = [
	("zzHarbour Point phase two", "zzMeridian Group", "Prospecting", "Open",
	 320000, 20, 60, "zzArrange the walk-round", 2),
	("zzAlmond Court common parts", "zzAlmond Holdings", "Qualification", "Open",
	 145000, 35, 30, "zzConfirm the specification", -1),
	("zzCivic Library phase two", "zzCity of Harbour", "Needs Analysis", "Open",
	 610000, 40, 90, "zzMeet the estates team", 7),
	("zzMeridian head office refit", "zzMeridian Group", "Proposal/Price Quote",
	 "Quotation", 275000, 60, 21, "zzChase the signature", 1),
	("zzAlmond warehouse mezzanine", "zzAlmond Holdings", "Negotiation/Review",
	 "Quotation", 198000, 75, 14, "zzAgree the retention", 4),
	("zzHarbour Point signage", "zzMeridian Group", "Identifying Decision Makers",
	 "Open", 42000, 25, 45, "zzFind out who signs", 12),
	("zzCity depot offices", "zzCity of Harbour", "Value Proposition", "Replied",
	 88000, 45, 35, "zzSend the comparison", -3),
	("zzAlmond Court roof terrace", "zzAlmond Holdings", "Prospecting", "Lost",
	 64000, 10, -10, "", 0),
	("zzMeridian studio fit-out", "zzMeridian Group", "Negotiation/Review",
	 "Converted", 410000, 100, -20, "", 0),
	("zzHarbour Point cafe", "zzMeridian Group", "Qualification", "Open",
	 76000, 30, 55, "zzPrice the joinery", 5),
]

# customer, deal, total, valid for, status
QUOTES = [
	("zzMeridian Group", "zzMeridian head office refit", 275000, 30, "Open"),
	("zzAlmond Holdings", "zzAlmond warehouse mezzanine", 198000, 21, "Replied"),
	("zzMeridian Group", "zzMeridian studio fit-out", 410000, 45, "Ordered"),
	("zzCity of Harbour", "zzCity depot offices", 88000, 14, "Open"),
	("zzAlmond Holdings", "zzAlmond Court roof terrace", 64000, 7, "Lost"),
]

# Four people who are not leads. ERPNext's Appointment makes a Lead out of the
# name and email it is given, and a name that already has one is refused for a
# duplicate email address — so a fixture that booked calls with its own leads
# died on the third row.
APPOINTMENTS = [
	("zzPriya Menon", "priya@zzcallers.test", 1, "Open"),
	("zzJonas Weber", "jonas@zzcallers.test", 3, "Open"),
	("zzRuth Oyelaran", "ruth@zzcallers.test", -4, "Closed"),
	("zzTomas Silva", "tomas@zzcallers.test", 6, "Open"),
]


def _price_list() -> str:
	"""Something to quote against. ERPNext's presets make one; a site that
	somehow has not got it gets one here rather than a mandatory-field error
	on the first quotation."""
	found = frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name")
	if found:
		return found
	return frappe.get_doc({
		"doctype": "Price List", "price_list_name": "zzSelling", "selling": 1,
		"enabled": 1, "currency": "AED",
	}).insert(ignore_permissions=True).name


def _colleague() -> str:
	"""The second person on this site, if the dev fixture has made them yet.

	`seed_dev_space` makes Robin and this module runs before some of it, so a
	missing one is an ordinary state rather than a failure — everything falls
	back to the session's own user and the narrowing simply has nothing to
	narrow away.
	"""
	from seed_dev_space import COLLEAGUE

	return COLLEAGUE if frappe.db.exists("User", COLLEAGUE) else ""


def _crm(company: str) -> int:
	for source in SOURCES:
		_named("UTM Source", source, {})

	item = _service_item()

	for name, industry, size, revenue in PROSPECTS:
		_one("Prospect", "company_name", name, {
			"company": company, "no_of_employees": size,
			"annual_revenue": revenue, "territory": "All Territories",
			"prospect_owner": frappe.session.user,
			"industry": industry if frappe.db.exists("Industry Type", industry) else None,
		})

	for (full_name, organisation, qualification, status, source, job_title,
	     step, step_in) in LEADS:
		first, last = full_name.split(" ", 1)
		_one("Lead", "lead_name", full_name, {
			"first_name": first, "last_name": last, "company": company,
			"company_name": organisation, "status": status,
			"qualification_status": qualification, "job_title": job_title,
			"email_id": (f"{first[2:]}@{organisation[2:].split(' ')[0]}.test"
			             .lower()),
			"mobile_no": f"+9715{abs(hash(full_name)) % 10_000_000:07d}",
			"territory": "All Territories", "utm_source": source,
			"lead_owner": frappe.session.user,
			"custom_next_step": step,
			"custom_next_step_on": _day(step_in) if step else None,
		})

	# Not all of them the reader's. OneCRM's **My deals** is the same screen as
	# Deals narrowed to `opportunity_owner`, and a fixture where one person owns
	# every row draws the two identically — which is a narrowing nobody can see
	# working and a spec that would pass with the filter deleted.
	colleague = _colleague()

	deals = {}
	for at, (title, customer, stage, status, amount, probability, closing,
	         step, step_in) in enumerate(DEALS):
		party = frappe.db.get_value("Customer", {"customer_name": customer}, "name")
		found = frappe.db.get_value("Opportunity", {"title": title}, "name")
		values = {
			"opportunity_from": "Customer", "party_name": party, "title": title,
			"company": company, "status": status, "sales_stage": stage,
			"opportunity_amount": amount, "probability": probability,
			"transaction_date": _day(closing - 45),
			"expected_closing": _day(closing),
			# Every third one to somebody else. See `_colleague`.
			"opportunity_owner": (colleague if colleague and at % 3 == 2
			                      else frappe.session.user),
			"territory": "All Territories",
			# Where the deal came from. Spread across the four sources rather
			# than left blank: a By source chart whose only bucket is None is
			# indistinguishable from one that is broken.
			"utm_source": SOURCES[abs(hash(title)) % len(SOURCES)],
			"custom_next_step": step,
			"custom_next_step_on": _day(step_in) if step else None,
		}
		if found:
			doc = frappe.get_doc("Opportunity", found)
			if not _same(doc, values):
				doc.update(values)
				doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc({"doctype": "Opportunity", **values})
			doc.insert(ignore_permissions=True)
		deals[title] = doc.name

	for customer, deal, total, valid, status in QUOTES:
		party = frappe.db.get_value("Customer", {"customer_name": customer}, "name")
		if frappe.db.exists("Quotation", {"opportunity": deals[deal]}):
			continue
		quote = frappe.get_doc({
			"doctype": "Quotation", "quotation_to": "Customer",
			"party_name": party, "company": company,
			"transaction_date": _day(-14), "valid_till": _day(valid),
			"opportunity": deals[deal],
			# Named rather than left to the defaults: a dev site has no
			# Selling Settings and no session company, so ERPNext's own
			# fallbacks find nothing and the document is refused for three
			# mandatory fields nobody chose.
			"currency": "AED", "conversion_rate": 1,
			"selling_price_list": _price_list(),
			"price_list_currency": "AED", "plc_conversion_rate": 1,
			"items": [{"item_code": item, "qty": 1, "rate": total,
			           "description": deal}],
		})
		quote.insert(ignore_permissions=True)
		if status != "Draft":
			try:
				quote.submit()
				frappe.db.set_value("Quotation", quote.name, "status", status,
				                    update_modified=False)
			except Exception as raised:
				frappe.clear_last_message()
				print(f"  ! quotation {quote.name} would not submit: {raised}")

	for name, email, when, status in APPOINTMENTS:
		# Made in the future and then moved, because ERPNext refuses to
		# *schedule* one in the past — which is right for a person booking a
		# call and wrong for a fixture that wants a calendar with history on
		# it, so the date is written to the column afterwards.
		made = _one("Appointment", "customer_name", name, {
			"customer_email": email, "status": status,
			"scheduled_time": _day(max(when, 1)) + " 10:30:00",
			"customer_phone_number": "+97150000000",
		})
		if when < 0:
			frappe.db.set_value("Appointment", made, "scheduled_time",
			                    _day(when) + " 10:30:00", update_modified=False)

	for customer, deal, total, valid, status in QUOTES[:2]:
		party = frappe.db.get_value("Customer", {"customer_name": customer}, "name")
		_submitted("Contract", {"party_type": "Customer", "party_name": party}, {
			"start_date": _day(-30), "end_date": _day(300),
			"contract_terms": f"Fixed price against {deal}.",
			"status": "Active", "fulfilment_status": "Partially Fulfilled",
		})
	return len(DEALS)


# --------------------------------------------------------------------------- #
# OneHR
# --------------------------------------------------------------------------- #

LEAVE_TYPES = [
	("zzAnnual leave", 25, 0),
	("zzSick leave", 10, 0),
	("zzUnpaid leave", 0, 1),
]

SHIFT_TYPES = [("zzDay shift", "09:00:00", "18:00:00"),
               ("zzSite shift", "07:00:00", "16:00:00")]

# person, leave type, from, to, days, status
LEAVE = [
	("zzOmar Fadel", "zzAnnual leave", 6, 10, 5, "Open"),
	("zzLeila Amari", "zzSick leave", -3, -3, 1, "Approved"),
	("zzKarim Nassar", "zzAnnual leave", -12, -8, 5, "Approved"),
	("zzSami Rahal", "zzAnnual leave", 20, 27, 8, "Open"),
	("zzRania Sabbagh", "zzSick leave", -20, -19, 2, "Approved"),
	("zzTarek Jaber", "zzUnpaid leave", 13, 14, 2, "Rejected"),
]

# The people whose days are recorded, and how the fortnight went for each.
# A letter per weekday: P present, A absent, L on leave, H half day, W at home.
ATTENDANCE = [
	("zzOmar Fadel", "PPPPPPPPPWPPPP"),
	# Her leave is the *last* weekday of the fortnight because that is the day
	# her Leave Application covers — a day marked On Leave with no application
	# behind it is the ordinary state of one somebody typed, and a fixture
	# where every leave day is one of those cannot draw the line that says why.
	("zzLeila Amari", "PPPPPPPPPPPPPL"),
	("zzKarim Nassar", "PPPPPPPPPPPPAP"),
	("zzSami Rahal", "PPWPPPPPPPPPPP"),
	("zzRania Sabbagh", "PPPPPHPPPPPPPP"),
	("zzTarek Jaber", "PPPPPPPAAPPPPP"),
]

ATTENDANCE_STATUS = {
	"P": "Present", "A": "Absent", "L": "On Leave", "H": "Half Day",
	"W": "Work From Home",
}

# What a day of each kind looks like on the clock: in, out, hours.
#
# HRMS computes these from the punches when auto attendance runs, and auto
# attendance needs a cron and a shift that has been processed — neither of
# which a fixture has. Without them every day page draws a person, a verdict
# and nothing about the day, which is the one thing that page exists for.
#
# A leave and an absence are absent from this table on purpose: a day nobody
# worked has no times, and writing 00:00 into them would draw somebody
# arriving at midnight.
ATTENDANCE_CLOCK = {
	"P": ("08:52:00", "18:04:00", 9.2),
	"W": ("09:05:00", "17:30:00", 8.4),
	"H": ("08:55:00", "13:00:00", 4.1),
}

# What the shift asked for, which is what the hours above are read against.
ATTENDANCE_SHIFT_HOURS = 8.0

# Two days that are not like the others, keyed by person and by where they
# fall in the fortnight.
#
# The flags are half of what a day page is for — a late arrival and an early
# finish are marks on a day that is otherwise counted as worked — and a
# fixture where nobody is ever late draws a page that cannot show them.
ATTENDANCE_ODD = {
	("zzOmar Fadel", 3): ("09:41:00", "18:10:00", 8.5, "late_entry"),
	("zzLeila Amari", 9): ("08:50:00", "15:20:00", 6.5, "early_exit"),
}

# title, designation, department, closes in days, status, range, vacancies
#
# The last number is what the opening page measures its funnel against, and it
# is deliberately more than one on the first: three site engineers with three
# applicants is a different morning from one engineer with three.
OPENINGS = [
	("zzSite engineer", "Engineer", "zzDelivery", 21, "Open", (14000, 19000), 3),
	("zzInterior designer", "Designer", "zzDesign", 35, "Open", (12000, 17000), 1),
	("zzQuantity surveyor", "Accounts Manager", "zzCommercial", -5, "Closed",
	 (16000, 22000), 2),
]

# name, opening, status, rating, source
APPLICANTS = [
	("zzDana Khoury", "zzSite engineer", "Shortlisted", 4, "zzWebsite"),
	("zzRami Btaddini", "zzSite engineer", "Open", 3, "zzReferral"),
	("zzJude Obeid", "zzSite engineer", "Rejected", 2, "zzWebsite"),
	# Four more against the same opening, and the reason is the funnel on its
	# record page: one applicant in each stage draws six bars of equal length,
	# which is a drawing of nothing. A pipeline has a shape — wide at the top,
	# one or two at the bottom — and a fixture that cannot show it is a fixture
	# nobody can tell a broken funnel from.
	("zzHadi Zeineddine", "zzSite engineer", "Open", 3, "zzWebsite"),
	("zzLina Haddad", "zzSite engineer", "Open", 2, "zzCold call"),
	("zzGhassan Mroue", "zzSite engineer", "Replied", 4, "zzReferral"),
	("zzYara Chalhoub", "zzSite engineer", "Replied", 3, "zzExhibition"),
	("zzMaya Seif", "zzInterior designer", "Accepted", 5, "zzReferral"),
	("zzElias Moussa", "zzInterior designer", "Replied", 3, "zzExhibition"),
	("zzNour Ayoub", "zzInterior designer", "Hold", 3, "zzWebsite"),
	("zzSalim Doueiri", "zzQuantity surveyor", "Rejected", 2, "zzCold call"),
	("zzFarah Kanaan", "zzQuantity surveyor", "Shortlisted", 4, "zzReferral"),
]

# goal, person, progress, status, starts, ends, parent goal
# HRMS refuses a goal whose parent belongs to somebody else — "Goal should be
# owned by the same employee as its parent goal" — so the tree here is one
# person's breakdown of their own objective rather than a company cascade.
# That is the model the doctype actually supports, and a fixture that pretended
# otherwise would be showing a tree nobody can build.
GOALS = [
	("zzDeliver the year's programme", "zzSami Rahal", 55, "In Progress",
	 -180, 185, None),
	("zzHarbour Point handed over on time", "zzSami Rahal", 62, "In Progress",
	 -120, 30, "zzDeliver the year's programme"),
	("zzCivic Library back on programme", "zzSami Rahal", 20, "In Progress",
	 -90, 40, "zzDeliver the year's programme"),
	("zzZero reportable incidents", "zzOmar Fadel", 100, "Completed",
	 -180, -1, None),
	("zzTwo new clients", "zzTarek Jaber", 40, "In Progress", -90, 90, None),
	("zzDesign library rebuilt", "zzLeila Amari", 25, "In Progress", -60, 120,
	 None),
	("zzPayroll moved in house", "zzRania Sabbagh", 0, "Pending", 30, 210, None),
]

CLAIMS = [
	("zzOmar Fadel", 1450, 1450, -12, "zzHarbour Point fit-out"),
	("zzKarim Nassar", 620, 620, -25, "zzAlmond Court refurbishment"),
	("zzSami Rahal", 2300, 1900, -6, "zzCivic Library atrium"),
	("zzLeila Amari", 310, 310, -2, None),
]


def _hr(company: str, people: dict) -> int:
	for name, allowed, unpaid in LEAVE_TYPES:
		_named("Leave Type", name, {
			"leave_type_name": name, "max_leaves_allowed": allowed,
			"is_lwp": unpaid, "include_holiday": 0,
		})
	for name, start, end in SHIFT_TYPES:
		_named("Shift Type", name, {
			"start_time": start, "end_time": end, "holiday_list": "zzWeekends",
		})

	# A year's allocation each, because a leave application against a paid type
	# with no allocation behind it is refused — and the refusal names the type
	# rather than the missing row.
	year = getdate(nowdate()).year
	for person, employee in people.items():
		for name, allowed, unpaid in LEAVE_TYPES:
			if unpaid:
				continue
			_submitted("Leave Allocation", {
				"employee": employee, "leave_type": name,
				"from_date": f"{year}-01-01",
			}, {
				"to_date": f"{year}-12-31", "new_leaves_allocated": allowed,
				"company": company,
			})

	for person, kind, start, end, days, status in LEAVE:
		name = _submitted("Leave Application", {
			"employee": people[person], "leave_type": kind,
			"from_date": _day(start),
		}, {
			"to_date": _day(end), "company": company, "status": "Approved",
			"posting_date": _day(min(start, 0) - 2),
			"leave_approver": frappe.session.user,
			"description": "zzFixture",
		})
		if status != "Approved" and name:
			frappe.db.set_value("Leave Application", name, "status", status,
			                    update_modified=False)

	# A fortnight of weekdays, most recent last, so the calendar opens on a
	# month with something in it.
	days = []
	offset = -1
	while len(days) < 14:
		if getdate(add_to_date(nowdate(), days=offset)).weekday() < 5:
			days.append(offset)
		offset -= 1
	days.reverse()

	marked = 0
	marks = {}
	for person, pattern in ATTENDANCE:
		for at, (offset, letter) in enumerate(zip(days, pattern)):
			name = _submitted("Attendance", {
				"employee": people[person], "attendance_date": _day(offset),
			}, {
				"company": company, "status": ATTENDANCE_STATUS[letter],
				"shift": "zzDay shift",
			})
			if not name:
				continue
			marked += 1
			marks[(person, offset)] = name
			# The verdict too, and every run: a row made under an earlier
			# pattern is submitted and so closed to the ordinary write path,
			# which would leave a site seeded last week disagreeing with the
			# fixture it was seeded from.
			frappe.db.set_value("Attendance", name, "status",
			                    ATTENDANCE_STATUS[letter], update_modified=False)
			_clocked(name, person, at, letter)

	# Two punches a day for one person over the same fortnight, which is what
	# the Check-ins screen is for: the raw log behind a day that is disputed —
	# and, linked back to the day they were counted into, what the day page
	# draws under its verdict.
	for offset in days[-5:]:
		for log, at in (("IN", "08:52:00"), ("OUT", "18:04:00")):
			when = _day(offset) + " " + at
			found = frappe.db.get_value("Employee Checkin", {
				"employee": people["zzOmar Fadel"], "time": when,
			}, "name")
			if not found:
				found = frappe.get_doc({
					"doctype": "Employee Checkin", "employee": people["zzOmar Fadel"],
					"log_type": log, "time": when,
					"shift": "zzDay shift",
				}).insert(ignore_permissions=True).name
			# The link auto attendance writes when it marks a day from the
			# punches. Set every run rather than on insert, so a site seeded
			# before this existed gets it too.
			frappe.db.set_value("Employee Checkin", found, "attendance",
			                    marks.get(("zzOmar Fadel", offset)),
			                    update_modified=False)

	_today(company, people)

	# Where the site shift is worked, and on whose network. HRMS carries the
	# geofence on a Shift Location and OneHR adds the network beside it — see
	# `oneapp/onehr/place.py` — and a fixture without one draws a Places screen
	# with nothing on the map and a check-in with no rule to refuse.
	#
	# Dubai Marina, because the seeded company is in the UAE and a geofence in
	# the Atlantic is a pin nobody can place on sight.
	site = _one("Shift Location", "location_name", "zzNorthgate yard", {
		"latitude": 25.0805, "longitude": 55.1403, "checkin_radius": 150,
		"custom_checkin_networks": "203.0.113.0/24",
	})

	for person in ("zzOmar Fadel", "zzKarim Nassar"):
		_submitted("Shift Assignment", {
			"employee": people[person], "start_date": _day(-30),
		}, {
			"shift_type": "zzSite shift", "end_date": _day(60),
			"company": company, "status": "Active",
			"shift_location": site,
		})

	# Two of the third thing a person asks the company to pay for. `Purpose of
	# Travel` is a table HRMS ships empty, so the fixture makes its own rather
	# than leaving the required Link blank and the screen with no rows.
	for purpose in ("zzClient visit", "zzSite inspection"):
		_named("Purpose of Travel", purpose, {"purpose_of_travel": purpose})
	for who, kind, purpose, funding in (
		("zzSami Rahal", "International", "zzClient visit", "Require Full Funding"),
		("zzOmar Fadel", "Domestic", "zzSite inspection",
		 "Partially Sponsored, Require Partial Funding"),
	):
		_submitted("Travel Request", {"employee": people[who]}, {
			"travel_type": kind, "purpose_of_travel": purpose,
			"travel_funding": funding, "company": company,
			"description": "zzFixture",
		})

	_submitted("Attendance Request", {
		"employee": people["zzSami Rahal"], "from_date": _day(-4),
	}, {
		"to_date": _day(-4), "company": company, "reason": "Work From Home",
		"explanation": "zzWorking from the Almond Court site office.",
	})
	# HRMS reads the approver off the *employee* or their department, not off
	# the role: a shift request whose approver is neither is refused with "Only
	# Approvers can Approve this Request", which reads like a permission error
	# and is a missing link field.
	for field in ("leave_approver", "expense_approver", "shift_request_approver"):
		if frappe.get_meta("Employee").has_field(field):
			frappe.db.set_value("Employee", people["zzKarim Nassar"], field,
			                    frappe.session.user, update_modified=False)
	_submitted("Shift Request", {
		"employee": people["zzKarim Nassar"], "from_date": _day(7),
	}, {
		"to_date": _day(21), "company": company, "shift_type": "zzDay shift",
		"approver": frappe.session.user,
	})

	# ----- Money ---------------------------------------------------------- #
	claim_type = _named("Expense Claim Type", "zzTravel", {
		"expense_type": "zzTravel",
		"accounts": [{"company": company,
		              "default_account": _expense_account(company)}],
	})
	for person, claimed, sanctioned, when, project in CLAIMS:
		_submitted("Expense Claim", {
			"employee": people[person], "posting_date": _day(when),
		}, {
			"company": company, "approval_status": "Approved",
			"expense_approver": frappe.session.user,
			"payable_account": _payable_account(company),
			"project": frappe.db.get_value("Project", {"project_name": project}, "name")
			if project else None,
			"expenses": [{
				"expense_date": _day(when), "expense_type": claim_type,
				"description": "zzFixture", "amount": claimed,
				"sanctioned_amount": sanctioned,
			}],
		})

	_submitted("Employee Advance", {
		"employee": people["zzKarim Nassar"], "posting_date": _day(-40),
	}, {
		"company": company, "purpose": "zzSite mobilisation",
		"advance_amount": 5000, "advance_account": _advance_account(company),
		"exchange_rate": 1, "currency": "AED",
	})

	# ----- Hiring ---------------------------------------------------------- #
	# Where a role is worked and on what terms. Both are Links the openings
	# screen lists and neither ships with a site: HRMS leaves Employment Type
	# and Branch empty, so every opening page drew two facts as em dashes.
	_named("Employment Type", "zzFull time", {"employee_type_name": "zzFull time"})
	_named("Branch", "zzNorthgate office", {"branch": "zzNorthgate office"})

	for title, designation, department, closes, status, (low, high), seats in OPENINGS:
		# Always Open on the way in, and closed below once the applicants are
		# in: HRMS refuses "a Job Applicant against a closed Job Opening", and
		# a closed opening with nobody against it is the one row this screen
		# most needs to show.
		_one("Job Opening", "job_title", title, {
			"company": company, "designation": designation, "status": "Open",
			"department": frappe.db.get_value(
				"Department", {"department_name": department}, "name"),
			"posted_on": _day(closes - 45) + " 09:00:00",
			"closes_on": _day(closes), "publish": 1,
			"currency": "AED", "lower_range": low, "upper_range": high,
			"salary_per": "Month", "vacancies": seats,
			"employment_type": "zzFull time", "location": "zzNorthgate office",
			"description": f"<p>zzWe are hiring a {title[2:].lower()}.</p>",
		})
	for source in SOURCES:
		_named("Job Applicant Source", source, {"source_name": source})
	for full_name, opening, status, rating, source in APPLICANTS:
		_one("Job Applicant", "applicant_name", full_name, {
			"email_id": f"{full_name[2:].split(' ')[0].lower()}@zzapplicants.test",
			"job_title": frappe.db.get_value("Job Opening", {"job_title": opening}, "name"),
			"status": status, "applicant_rating": rating / 5,
			"source": source,
			"designation": frappe.db.get_value(
				"Job Opening", {"job_title": opening}, "designation"),
		})

	for title, designation, department, closes, status, (low, high), seats in OPENINGS:
		if status != "Open":
			frappe.db.set_value("Job Opening", {"job_title": title},
			                    {"status": status, "closed_on": _day(closes)},
			                    update_modified=False)

	if not frappe.db.exists("Skill", "zzSite experience"):
		frappe.get_doc({"doctype": "Skill", "skill_name": "zzSite experience"}).insert(
			ignore_permissions=True)
	_named("Interview Type", "zzFirst interview", {
		"interview_type_name": "zzFirst interview", "description": "zzFixture",
		"expected_skill_set": [{"skill": "zzSite experience"}],
		"interviewers": [{"user": frappe.session.user}],
	})
	for full_name, when in (("zzDana Khoury", 2), ("zzFarah Kanaan", 4),
	                        ("zzMaya Seif", -6)):
		applicant = frappe.db.get_value("Job Applicant",
		                                {"applicant_name": full_name}, "name")
		_submitted("Interview", {
			"job_applicant": applicant, "scheduled_on": _day(when),
		}, {
			"interview_type": "zzFirst interview",
			"from_time": "10:00:00", "to_time": "11:00:00",
			"interview_details": [{"interviewer": frappe.session.user}],
		})

	_named("Offer Term", "zzStart date", {"offer_term": "zzStart date"})
	# Two, and the difference between them is the point. Maya's applicant status
	# is Accepted, so her offer is Accepted — a fixture where the two disagreed
	# was a fixture where **Hire** could never succeed, and the verb that turns
	# an accepted offer into an employee is the one thing about an offer worth
	# looking at. Elias's is still out, which is the other half: the same verb
	# refuses it, and a fixture with only one of those tests half a rule.
	for who, status in (("zzMaya Seif", "Accepted"), ("zzElias Moussa", "Awaiting Response")):
		applicant = frappe.db.get_value("Job Applicant", {"applicant_name": who}, "name")
		if not applicant:
			continue
		made = _submitted("Job Offer", {"job_applicant": applicant}, {
			"company": company, "offer_date": _day(-3), "status": status,
			"designation": "Designer",
			"offer_terms": [{"offer_term": "zzStart date", "value": _day(30)}],
		})
		# And again on a row that was already there. `_submitted` makes one or
		# finds one and never edits, which is right for everything else in this
		# fixture and wrong here: `status` is the one field on an offer that
		# moves, it is `allow_on_submit`, and a re-seed that left an old value
		# is a site where **Hire** silently cannot work.
		frappe.db.set_value("Job Offer", made, "status", status)

	# ----- Growing --------------------------------------------------------- #
	_named("KRA", "zzDelivery", {"title": "zzDelivery", "description": "zzFixture"})
	cycle = _one("Appraisal Cycle", "cycle_name", "zzThis year", {
		"company": company, "start_date": _day(-180), "end_date": _day(185),
		"status": "In Progress", "kra_evaluation_method": "Manual Rating",
	})

	# Parents first, and flagged as groups on the way in: HRMS refuses a child
	# under a leaf *and* refuses to change `employee` afterwards, so there is
	# no second pass that can fix either. The list is ordered so a parent comes
	# before its children; this sorts on it rather than trusting it.
	parents = {row[6] for row in GOALS if row[6]}
	by_goal = {}
	for goal, person, progress, status, start, end, parent in sorted(
		GOALS, key=lambda row: row[6] is not None
	):
		by_goal[goal] = _once("Goal", "goal_name", goal, {
			"employee": people[person], "company": company, "status": status,
			"start_date": _day(start), "end_date": _day(end),
			"progress": progress, "kra": "zzDelivery",
			"is_group": 1 if goal in parents else 0,
			"parent_goal": by_goal.get(parent) if parent else None,
		})

	_submitted("Training Event", {"event_name": "zzSite safety refresher"}, {
		"company": company, "event_status": "Scheduled", "type": "Workshop",
		"level": "Intermediate", "location": "zzHarbour Point site office",
		"start_time": _day(12) + " 09:00:00", "end_time": _day(12) + " 13:00:00",
		"introduction": "zzFixture",
	})
	_submitted("Training Event", {"event_name": "zzRevit for designers"}, {
		"company": company, "event_status": "Completed", "type": "Seminar",
		"level": "Beginner", "location": "zzStudio",
		"start_time": _day(-30) + " 09:00:00", "end_time": _day(-30) + " 17:00:00",
		"introduction": "zzFixture",
	})
	return marked


def _expense_account(company: str) -> str:
	return (frappe.db.get_value("Account", {"company": company, "is_group": 0,
	                                        "root_type": "Expense"}, "name") or "")


def _payable_account(company: str) -> str:
	return (frappe.db.get_value("Account", {"company": company, "is_group": 0,
	                                        "account_type": "Payable"}, "name") or "")


def _advance_account(company: str) -> str:
	return (frappe.db.get_value("Account", {"company": company, "is_group": 0,
	                                        "account_type": "Receivable"}, "name")
	        or _payable_account(company))


# --------------------------------------------------------------------------- #
# Pay, and how somebody is doing — the two halves of OneHR that need a
# structure behind them before a single row can exist.
# --------------------------------------------------------------------------- #

# person, what they are paid a month
SALARIES = [
	("zzNoor Haddad", 48000),
	("zzSami Rahal", 26000),
	("zzLeila Amari", 17000),
	("zzOmar Fadel", 16000),
	("zzRania Sabbagh", 21000),
	("zzKarim Nassar", 14500),
	("zzHala Zayed", 23000),
	("zzTarek Jaber", 19000),
]

APPRAISALS = [("zzSami Rahal", 4.2), ("zzLeila Amari", 3.8),
              ("zzOmar Fadel", 4.5), ("zzKarim Nassar", 3.1)]


def _today(company: str, people: dict) -> None:
	"""Enough happening *now* that "where is everybody" has an answer.

	`presence.of` reads four doctypes and ranks them, and a fixture whose most
	recent anything is last Friday makes every one of those answers "not known"
	— which is a correct answer to an empty question and tells nobody whether
	the thing works. So today carries one of each state worth drawing:

	    in, late   arrived after the shift began
	    in         arrived on time
	    out        came and went
	    on leave   an approved application covering today
	    absent     marked so, and no log to contradict it

	Only on a weekday. Seeding a check-in onto a Friday in a fixture whose
	holiday list calls Friday a weekly off is a person who is simultaneously
	at work and on holiday, and `presence` ranks holiday above in — so the whole
	band would say Holiday and none of this would be visible.
	"""
	today = getdate(nowdate())
	if today.weekday() >= 5 or frappe.db.exists(
		"Holiday", {"parent": "zzWeekends", "holiday_date": today}
	):
		return

	shift = frappe.db.get_value("Shift Type", "zzDay shift",
	                            ["start_time", "end_time"], as_dict=True) or {}
	begins = f"{today} {shift.get('start_time') or '09:00:00'}"

	# `shift_start` is what `presence._late` measures against, and HRMS only
	# stamps it where auto-attendance is running. A fixture has to say it, or
	# nobody is ever late and the one state with a story in it never draws.
	for person, log, at, start in (
		("zzOmar Fadel", "IN", "09:41:00", begins),
		("zzLeila Amari", "IN", "08:47:00", begins),
		("zzKarim Nassar", "IN", "07:58:00", None),
		("zzKarim Nassar", "OUT", "15:12:00", None),
	):
		when = f"{today} {at}"
		if frappe.db.exists("Employee Checkin", {
			"employee": people[person], "time": when,
		}):
			continue
		frappe.get_doc({
			"doctype": "Employee Checkin", "employee": people[person],
			"log_type": log, "time": when, "shift": "zzDay shift",
			**({"shift_start": start} if start else {}),
		}).insert(ignore_permissions=True)

	# Somebody on leave over today, and somebody marked absent. Both are states
	# that outrank or stand in for a log, so both need a person with no log.
	_submitted("Leave Application", {
		"employee": people["zzHala Zayed"], "from_date": _day(-1),
	}, {
		"leave_type": "zzAnnual leave", "to_date": _day(2), "company": company,
		"status": "Approved", "leave_approver": frappe.session.user,
		"description": "zzFour days in Tripoli.",
	})

	_submitted("Attendance", {
		"employee": people["zzTarek Jaber"], "attendance_date": str(today),
	}, {
		"company": company, "status": "Absent", "shift": "zzDay shift",
	})


def _payroll(company: str, people: dict) -> int:
	"""A structure, an assignment each, and last month's payslips.

	The one part of this fixture that cannot be written row by row: a Salary
	Slip is *computed* from a Salary Structure Assignment, so the three have to
	exist in order and the amounts on the screen are the structure's arithmetic
	rather than numbers chosen here.
	"""
	income = _expense_account(company)
	_named("Salary Component", "zzBasic", {
		"salary_component": "zzBasic", "salary_component_abbr": "ZZB",
		"type": "Earning", "amount_based_on_formula": 1, "formula": "base",
		"accounts": [{"company": company, "account": income}],
	})
	_named("Salary Component", "zzHousing", {
		"salary_component": "zzHousing", "salary_component_abbr": "ZZH",
		"type": "Earning", "amount_based_on_formula": 1, "formula": "base * 0.15",
		"accounts": [{"company": company, "account": income}],
	})
	_named("Salary Component", "zzPension", {
		"salary_component": "zzPension", "salary_component_abbr": "ZZP",
		"type": "Deduction", "amount_based_on_formula": 1, "formula": "base * 0.05",
		"accounts": [{"company": company, "account": income}],
	})

	structure = frappe.db.get_value("Salary Structure",
	                                {"name": "zzMonthly"}, "name")
	if not structure:
		doc = frappe.get_doc({
			"doctype": "Salary Structure", "name": "zzMonthly",
			"company": company, "payroll_frequency": "Monthly",
			"currency": "AED", "is_active": "Yes", "is_default": "Yes",
			"payment_account": _payable_account(company),
			"earnings": [
				{"salary_component": "zzBasic", "amount_based_on_formula": 1,
				 "formula": "base"},
				{"salary_component": "zzHousing", "amount_based_on_formula": 1,
				 "formula": "base * 0.15"},
			],
			"deductions": [
				{"salary_component": "zzPension", "amount_based_on_formula": 1,
				 "formula": "base * 0.05"},
			],
		})
		doc.insert(ignore_permissions=True)
		doc.submit()
		structure = doc.name

	# The month before this one, whole, so a payslip covers a period that has
	# finished — a slip whose end date is in the future is refused.
	first = getdate(nowdate()).replace(day=1)
	end = add_to_date(first, days=-1)
	start = getdate(end).replace(day=1)

	for person, base in SALARIES:
		_submitted("Salary Structure Assignment", {
			"employee": people[person], "salary_structure": structure,
		}, {
			"from_date": str(getdate(add_to_date(str(start), months=-6))),
			"company": company, "base": base, "currency": "AED",
		})

	slips = 0
	for person, base in SALARIES:
		if frappe.db.exists("Salary Slip", {
			"employee": people[person], "start_date": str(start),
		}):
			continue
		slip = frappe.get_doc({
			"doctype": "Salary Slip", "employee": people[person],
			"company": company, "start_date": str(start), "end_date": str(end),
			"posting_date": str(end), "payroll_frequency": "Monthly",
			"salary_structure": structure,
		})
		try:
			slip.insert(ignore_permissions=True)
			slip.submit()
			slips += 1
		except Exception as raised:
			frappe.clear_last_message()
			print(f"  ! payslip for {person} would not post: {raised}")
	return slips


def _appraisals(company: str, people: dict, cycle: str) -> int:
	"""How a handful of people are doing, against one template.

	`final_score` is written afterwards rather than computed: HRMS derives it
	from ratings a person types into a form, and a fixture that filled the form
	in would be asserting something about the rating widget rather than about
	the screen this is for.
	"""
	if not frappe.db.exists("Employee Feedback Criteria", "zzDelivery"):
		frappe.get_doc({"doctype": "Employee Feedback Criteria",
		                "criteria": "zzDelivery"}).insert(ignore_permissions=True)
	template = _one("Appraisal Template", "template_title", "zzDelivery review", {
		"description": "zzFixture",
		"goals": [{"key_result_area": "zzDelivery", "per_weightage": 100}],
		"rating_criteria": [{"criteria": "zzDelivery", "per_weightage": 100}],
	})

	made = 0
	for person, score in APPRAISALS:
		name = _submitted("Appraisal", {
			"employee": people[person], "appraisal_cycle": cycle,
		}, {
			"company": company, "appraisal_template": template,
		})
		if name:
			frappe.db.set_value("Appraisal", name, {
				"final_score": score, "total_score": score,
			}, update_modified=False)
			made += 1
	return made


# --------------------------------------------------------------------------- #
# The whole thing
# --------------------------------------------------------------------------- #

def install(module):
	"""One shipped space on this dev tenant: its role, its schema, its grants.

	The same shape `_seed_rua` returns, and for the same reason — the caller
	reconciles permissions once across every space, because `sync_permissions`
	*removes* what it is not given and two calls leave whichever ran last.
	"""
	from oneapp.onespace import sync

	# The fields the screens read. On a real tenant the entitlement sync does
	# this; a dev site has no control plane, so a space whose manifest declares
	# a column nobody made renders one column short and says nothing.
	sync._seed_custom_fields(getattr(module, "CUSTOM_FIELDS", []))

	from seed_dev_space import _grants_of, _hold_every_role

	# Every seat, not just the default one. OneHR keeps pay away from the
	# people officer on purpose, and a dev box holding only the employee role
	# opens Attendance and is told it is not part of OneHR.
	_hold_every_role(module)

	# `component` is carried, unlike RUA's and the mock space's, which declare
	# none and were handed `component=None` for safety. These declare one — the
	# Configuration page — and nulling it is why that screen rendered as "this
	# screen has nothing to show yet" for as long as it took to look.
	# `alerts` rides along because the control plane sends it in the same row —
	# `entitlements/registry.SPACE_FIELDS` — and the dev fixture seeds them from
	# the state it writes, the way a tenant's sync does. Not here: a rule
	# addressed to a role needs the role to exist and the site state to know
	# about it, and neither is true yet.
	return (
		{
			**module.SPACE,
			"alerts": getattr(module, "ALERTS", []),
			"screens": [dict(one) for one in module.SCREENS],
		},
		_grants_of(module),
	)


def seed(records: bool = True):
	"""The three ERPNext spaces, and what is in them.

	Returns `(spaces, grants)` — or `([], [])` on a site without ERPNext,
	which is the honest answer rather than a failure: OneMobility needs no
	ERPNext and the dev fixture has to keep working on a bare site.

	`records=False` is the manifest half, for the loop that is editing a
	screen declaration and does not care whether there are four projects.
	"""
	from oneapp_control.spaces import onecrm, onehr, oneproject

	if not ready():
		print("erp spaces: skipped, no ERPNext on this site")
		return [], []

	spaces, grants = [], []
	for module in (oneproject, onecrm, onehr):
		space, rows = install(module)
		spaces.append(space)
		grants += rows

	if not records:
		return spaces, grants

	company = _ground()
	_customers()
	people = _people(company)
	projects = _projects(company, people)
	deals = _crm(company)
	marked = _hr(company, people)
	slips = _payroll(company, people)
	cycle = frappe.db.get_value("Appraisal Cycle", {"cycle_name": "zzThis year"},
	                            "name")
	reviews = _appraisals(company, people, cycle) if cycle else 0

	print(
		f"erp spaces: {projects} projects and {frappe.db.count('Task')} tasks, "
		f"{deals} deals under {len(LEADS)} leads, "
		f"{len(people)} people with {marked} days marked, "
		f"{slips} payslips and {reviews} appraisals"
	)
	return spaces, grants
