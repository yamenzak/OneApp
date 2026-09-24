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
	# A fixture that dies halfway leaves a site nobody can seed again. Say which
	# document refused and carry on — the screen is thinner and the rest of the
	# pass still runs.
	#
	# Both halves, not just the submit. Most of what refuses here refuses in
	# `validate`, which runs on insert: an Overtime Slip whose window overlaps
	# one already on the site is rejected there, and every date in this file is
	# relative to *today*, so seeding twice on different days asks HRMS for two
	# overlapping windows. That killed the whole run, on a site that had been
	# seeded perfectly well the day before.
	try:
		doc.insert(ignore_permissions=True)
		doc.submit()
	except Exception as raised:
		frappe.clear_last_message()
		print(f"  ! {doctype} {doc.name} would not go in: {raised}")
		return ""
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

	# The country's own fields. `setup_complete` installs these and this file
	# inserts the Company directly, so the fixture is the one company on any
	# site that never got them — and ERPNext's UAE code is hooked on Purchase
	# Invoice regardless, so the first bill dies with `'PurchaseInvoice' object
	# has no attribute 'reverse_charge'`, which says nothing about a country.
	if not frappe.db.exists("Custom Field", {"dt": "Purchase Invoice",
	                                         "fieldname": "reverse_charge"}):
		from erpnext.regional.united_arab_emirates import setup as uae

		uae.setup(COMPANY, patch=False)

	# And the defaults ERPNext's chart creates an account for and does not
	# point at. The fixture's company is made directly rather than through
	# `books.create`, so it never had them — and without
	# `stock_received_but_not_billed` a purchase invoice is refused with a
	# sentence about a field on a page this product does not have.
	# `onespace/books.py` is where the real path fills them; this is the same
	# call, over the company this file made.
	from oneapp.onespace import books as company_books

	company_books.name_the_accounts(COMPANY)

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

# name, designation, department, who they report to, the day they joined
#
# The joining date is an *absolute* date and it is the only place in this
# fixture where that is deliberate. Everything else here slides with today so
# the site always looks recent; a joining date that slides is a person whose
# start date changes every morning — and because `_one` saves a document whose
# values have moved, and ERPNext's `Employee.update_user` copies the name onto
# the linked User, the drift renamed the dev site's Administrator to whichever
# person `_seat` had linked. A birthday is the same argument.
PEOPLE = [
	("zzNoor Haddad", "Managing Director", "zzDelivery", None, "2022-04-29"),
	("zzSami Rahal", "Projects Manager", "zzDelivery", 0, "2023-06-03"),
	("zzLeila Amari", "Designer", "zzDesign", 1, "2024-03-29"),
	("zzOmar Fadel", "Engineer", "zzDelivery", 1, "2024-10-15"),
	("zzRania Sabbagh", "Accounts Manager", "zzCommercial", 0, "2023-09-11"),
	("zzKarim Nassar", "Engineer", "zzDelivery", 1, "2025-08-11"),
	("zzHala Zayed", "HR Manager", "zzPeople", 0, "2022-11-15"),
	("zzTarek Jaber", "Business Development Manager", "zzCommercial", 0, "2025-11-19"),
]

#: One birthday for all eight, and absolute for the same reason.
BORN = "1993-11-07"


def _work_email(full_name: str) -> str:
	"""`zzNoor Haddad` as `noor.haddad@zznorthgate.test`.

	The `zz` prefix is on the *name* so the fixture's rows sort last and sweep
	cleanly; it is not part of anybody's address, and leaving it in would make
	every seeded person unfindable by the address a colleague would type.
	"""
	first, last = full_name.removeprefix("zz").lower().split(" ", 1)
	return f"{first}.{last.replace(' ', '.')}@zznorthgate.test"


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
			"date_of_birth": BORN, "date_of_joining": joined,
			"designation": designation,
			"department": frappe.db.get_value(
				"Department", {"department_name": department}, "name"),
			"holiday_list": "zzWeekends", "status": "Active",
			# A work address, which is not decoration: mail (OneDesk's
			# `one_mail` now) resolves the person a message concerns off
			# exactly this field, and a fixture whose eight people have no
			# address is one where that half of the link never fires.
			"company_email": _work_email(full_name),
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
	_unrename()
	if frappe.db.get_value("Employee", employee, "user_id") == SEAT:
		return
	frappe.db.set_value("Employee", employee, {
		"user_id": SEAT, "create_user_permission": 0,
	})


#: What the login is called, and what it has to go on being called.
SEAT_NAME = ("Administrator", "")


def _unrename() -> None:
	"""Put the login's own name back, if an Employee save took it.

	`_seat` links a person to `Administrator` with `db.set_value` precisely so
	`Employee.update_user` does not copy their name onto it — but that only
	covers the linking. Any *later* save of the same Employee through the
	document API does copy it, and `_one` saves whenever a value has moved. So
	the promise in `_seat` was kept on the run that made the link and broken on
	the next one that changed anything.

	It showed up as a browser suite failing on a picker: the assignee menu
	looked for Administrator and found somebody called zzSami Rahal.

	Cheap, and it runs every time rather than being reasoned about: reading two
	fields is nothing, and the rule it is holding to is one sentence.
	"""
	first, last = SEAT_NAME
	found = frappe.db.get_value("User", SEAT, ["first_name", "last_name"])
	if found and tuple(one or "" for one in found) != SEAT_NAME:
		frappe.db.set_value("User", SEAT, {
			"first_name": first, "last_name": last, "full_name": first,
		}, update_modified=False)


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

#: The key each project's tasks are named after — HARB-0001 rather than
#: TASK-2026-00042, which is what people say to each other. `oneproject`'s
#: `custom_key`, read by `onetask/task.py` when a task is named.
PROJECT_KEYS = ["HARB", "ALM", "CIV", "RIV"]

#: Which of the seeded tasks the team pulled into the running cycle.
CYCLE_TASKS = ("zzCeiling and services coordination", "zzJoinery shop drawings")

#: What a board filters by, on the two tasks where it says something.
LABELLED = {
	"zzClient sign-off on finishes": ("zzClient",),
	"zzSteelwork package": ("zzBlocked", "zzClient"),
}

#: Three lines and a tick on one task — which is not three sub-tasks, and the
#: fixture has both so the difference is visible.
CHECKLISTS = {
	"zzJoinery shop drawings": (
		("Ring the fabricator", 1),
		("Ask for the revised rate", 0),
		("Send it on to the client", 0),
	),
}

#: What waits for what. ERPNext stores these as `Task Depends On` rows and the
#: Gantt draws them; the fixture puts three in a line so moving the first moves
#: the rest.
EDGES = [
	("zzJoinery shop drawings", "zzCeiling and services coordination"),
	("zzClient sign-off on finishes", "zzJoinery shop drawings"),
	("zzPractical completion", "zzClient sign-off on finishes"),
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

	# And the five things ERPNext's Task cannot say, which is what OneProject
	# adds — `docs/WORK.md` §12. Written here rather than in the tuples above
	# because they are ours and those rows are ERPNext's shape: the state a
	# board draws its columns from, the key a task is named after, a cycle, a
	# label or two, a checklist, and three dependencies in a line so the plan
	# has arrows on it.
	from oneapp.onetask import states as onetask_states
	from oneapp_control.spaces import oneproject as manifest

	onetask_states.ensure(manifest.STATES)
	for one in ("zzBlocked", "zzClient", "zzQuick win"):
		if not frappe.db.exists("One Label", one):
			frappe.get_doc({
				"doctype": "One Label", "label_name": one,
				"colour": {"zzBlocked": "red", "zzClient": "violet"}.get(one, "green"),
			}).insert(ignore_permissions=True)

	if not frappe.db.exists("One Cycle", "zzSprint 21"):
		frappe.get_doc({
			"doctype": "One Cycle", "cycle_name": "zzSprint 21", "status": "Running",
			"starts_on": _day(-3), "ends_on": _day(11),
			"goal": "zzGet the fit-out to handover.",
		}).insert(ignore_permissions=True)

	#: A key per project, so its tasks read REEM-14 rather than TASK-2026-00042.
	for at, key in enumerate(PROJECT_KEYS):
		if at < len(made) and not frappe.db.get_value("Project", made[at], "custom_key"):
			frappe.db.set_value("Project", made[at], "custom_key", key,
			                    update_modified=False)

	#: What each seeded task is in, in the workspace's own words. ERPNext's
	#: status is written *from* this — `onetask/task.py` — so the two agree by
	#: construction rather than by being seeded twice.
	STATE_OF = {
		"Open": "Backlog", "Working": "In progress",
		"Pending Review": "In review", "Completed": "Done",
		"Cancelled": "Done", "Overdue": "In progress",
	}
	for subject, name in by_subject.items():
		task = frappe.get_doc("Task", name)
		if task.get("custom_state"):
			continue
		task.custom_state = STATE_OF.get(task.status, "Backlog")
		if subject in CYCLE_TASKS:
			task.custom_cycle = "zzSprint 21"
		if subject in LABELLED:
			for label in LABELLED[subject]:
				task.append("custom_labels", {"label": label})
		if subject in CHECKLISTS:
			for step, done in CHECKLISTS[subject]:
				task.append("custom_steps", {"step": step, "done": done})
		task.save(ignore_permissions=True)

	#: Three edges in a line, so moving the first moves the other two — and one
	#: that is drawn on the plan because ERPNext already stores it.
	for waiting, after in EDGES:
		me, other = by_subject.get(waiting), by_subject.get(after)
		if not (me and other):
			continue
		edge = frappe.db.get_value("Task Depends On", {"parent": me, "task": other},
		                           ["name", "project"], as_dict=True)
		if edge:
			# An edge an older run wrote before `onetask/task.py` started
			# filling the project in. Without it ERPNext's own slip finds
			# nothing — it looks dependants up by task *and* project — so the
			# fixture would show a plan that never moves.
			if not edge.project:
				frappe.db.set_value("Task Depends On", edge.name, "project",
				                    frappe.db.get_value("Task", me, "project"),
				                    update_modified=False)
			continue
		task = frappe.get_doc("Task", me)
		task.append("depends_on", {"task": other})
		task.save(ignore_permissions=True)

	# One handover rule, so the panel has something in it and the claim in
	# `docs/WORK.md` stage 7 is visible rather than described: when a task
	# reaches In review it lands on the reviewer, through Frappe's own
	# Assignment Rule and its own ToDo — the only assignment store this
	# product has. On ERPNext's Task, because after §12 there is no other
	# task, and on `custom_state` because that is the word the team uses.
	from oneapp.onespace import routing

	# Taken away rather than left beside the new one where an older run made it
	# about `One Task`: two rules with one title is the fixture disagreeing with
	# itself, and the prompt-named doctype means the title *is* the name.
	if frappe.db.get_value("Assignment Rule", "zzIn review goes to the reviewer",
	                       "document_type") not in (None, "Task"):
		frappe.delete_doc("Assignment Rule", "zzIn review goes to the reviewer",
		                  force=True, ignore_permissions=True)

	if not frappe.db.exists("Assignment Rule", "zzIn review goes to the reviewer"):
		routing.save({
			"title": "zzIn review goes to the reviewer",
			"doctype": "Task",
			"way": "in turn",
			"users": [frappe.session.user],
			"condition": {"field": "custom_state", "operator": "is",
			              "value": "In review"},
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
		# Keyed by who and which project, *not* by the date. Every date in
		# this fixture is relative to today, so a re-seed on the day after the
		# last one asks for a week that has moved — and a second timesheet for
		# the same person a day along overlaps the first, which ERPNext
		# refuses and which took the whole seed down at midnight. Who worked on
		# what is the thing that is meant to be true once.
		found = frappe.db.get_value("Timesheet", {
			"employee": people[person], "parent_project": made[project],
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

	_ordered(company, made)
	_drawings(made)
	return len(made)


#: What the customer agreed, as (project index, customer, two staged amounts).
#:
#: Two rows rather than one, because the number this fixture exists to show is
#: `per_billed` — a contract billed in stages — and an order with one line is
#: either nought or a hundred per cent. `docs/ONEBOOK.md` §5.
ORDER = (0, "zzMeridian Group", (260000, 140000))


def _ordered(company: str, made: list) -> None:
	"""One signed order, half of it billed.

	Without this the fixture's projects know what they have billed and what
	they have cost and not what they were worth: ERPNext fills
	`Project.total_sales_amount` from a Sales Order and from nothing else.

	The invoice against it is made through ERPNext's own mapper rather than by
	hand, which is the same call `onebook/orders.py` makes — so a fixture whose
	`per_billed` looks right is also a fixture that proves the verb works.
	"""
	from erpnext.selling.doctype.sales_order.mapper import make_sales_invoice

	# On an already-installed site this is what `books.roll_up_each_transaction`
	# does at setup: without it ERPNext defers the project roll-up to a
	# scheduled job and `total_sales_amount` stays nought.
	from oneapp.onespace import books as company_books

	company_books.roll_up_each_transaction()

	index, customer, stages = ORDER
	project = made[index]
	party = frappe.db.get_value("Customer", {"customer_name": customer}, "name")
	if not party or frappe.db.exists("Sales Order", {"project": project}):
		return

	order = frappe.get_doc({
		"doctype": "Sales Order", "company": company, "customer": party,
		"project": project,
		"transaction_date": _day(-75), "delivery_date": _day(30),
		"currency": "AED", "conversion_rate": 1,
		"selling_price_list": _price_list(), "price_list_currency": "AED",
		"plc_conversion_rate": 1,
		"items": [{
			"item_code": item, "qty": 1, "rate": amount,
			"delivery_date": _day(30),
			**({"cost_center": _cost_center(company)}
			   if _cost_center(company) else {}),
		} for item, amount in zip((_service_item(), _supervision_item()), stages)],
	})
	try:
		order.insert(ignore_permissions=True)
		order.submit()
	except Exception as raised:
		frappe.clear_last_message()
		print(f"  ! order for {customer} would not post: {raised}")
		return

	# The first stage only. Their mapper copies every row that is still to
	# bill, so dropping the second is what makes this a part-billed order
	# rather than a settled one.
	try:
		invoice = make_sales_invoice(order.name)
		# Two rows in, one row out.
		invoice.items = invoice.items[:1]
		invoice.set_posting_time = 1
		invoice.posting_date = _day(-40)
		invoice.due_date = _day(-10)
		invoice.debit_to = _receivable_account(company)
		for row in invoice.items:
			row.income_account = _income_account(company)
		invoice.insert(ignore_permissions=True)
		invoice.submit()
	except Exception as raised:
		frappe.clear_last_message()
		print(f"  ! the first stage of {order.name} would not bill: {raised}")


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


#: The second thing this fixture sells, and it exists for one reason: ERPNext's
#: Selling Settings refuse the same item twice in one document unless a
#: workspace turns that off, and the staged order in `_ordered` is two rows.
#:
#: Two items rather than the setting, because a two-stage contract *is* two
#: different pieces of work in every services business anybody would recognise,
#: and a fixture that flipped a global to make itself possible would be a
#: fixture hiding a decision a customer has to make.
SUPERVISION = "zzSite supervision"


def _supervision_item() -> str:
	return _one("Item", "item_code", SUPERVISION, {
		"item_name": SUPERVISION, "is_stock_item": 0,
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
# OneBook
#
# The receivable side is already here — `_projects` posts three sales invoices
# so the portfolio's Billed is a number ERPNext worked out. What OneBook adds is
# the other three screens somebody actually opens: what we owe, what has been
# paid, and the journal underneath.
#
# Small on purpose. A books fixture that tried to be a year of trading would be
# a thousand rows nobody reads and an hour of posting; what these screens need
# to be checkable is a handful of rows in each state, and one of each carrying a
# project so `custom_origin` has something to say.
# --------------------------------------------------------------------------- #

#: Who we buy from. One supplier, for the same reason there is one service
#: item: two rows called nearly the same thing is a link that resolves to
#: whichever was made first.
SUPPLIER = "zzHalcyon Joinery"

#: What we owe, as (amount, days ago, against a project). The third is the one
#: that matters: a subcontractor's bill against a job is the other half of
#: billing that job, and it is what makes the Bills screen's `custom_origin`
#: column say `oneproject` on exactly one row.
BILLS = [
	(48000, -30, True),
	(9250, -18, False),
	(16400, -4, False),
]


def _supplier() -> str:
	return _one("Supplier", "supplier_name", SUPPLIER, {
		"supplier_group": "Services"
		if frappe.db.exists("Supplier Group", "Services")
		else frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
		"country": "United Arab Emirates",
	})


#: The ledger account the statement is of. Named rather than found, because a
#: workspace's bank account is a thing somebody opens rather than something a
#: chart of accounts comes with: ERPNext's standard chart ships **Bank
#: Accounts** as an empty group and a **Cash** leaf under it, and the wizard
#: leaves it that way.
#:
#: This fixture used to let the money land in Cash, which posted and looked
#: fine and could not be reconciled: ERPNext's allocator finds a voucher's bank
#: leg with `account_type = "Bank"`, so a payment into a Cash account is a
#: payment that, as far as a bank reconciliation is concerned, never touched
#: the bank. Measured rather than reasoned about — it is the error
#: `docs/ONEBOOK.md` §3 was written on top of.
BANK_LEDGER = "zzCurrent account"


def _bank_ledger(company: str) -> str:
	"""A Bank-type leaf under the chart's Bank group, made if it is not there.

	Set as the Company's `default_bank_account` as well, which is what every
	other part of ERPNext reaches for and what makes the rest of this file's
	`_bank_account_head` a one-line lookup.
	"""
	found = frappe.db.get_value("Account", {"company": company, "is_group": 0,
	                                        "account_type": "Bank"}, "name")
	if not found:
		parent = (frappe.db.get_value("Account", {
			"company": company, "is_group": 1,
			"account_type": "Bank"}, "name")
			or frappe.db.get_value("Account", {
				"company": company, "is_group": 1,
				"account_name": "Bank Accounts"}, "name"))
		if not parent:
			return ""
		found = frappe.get_doc({
			"doctype": "Account", "account_name": BANK_LEDGER,
			"company": company, "parent_account": parent,
			"account_type": "Bank", "is_group": 0,
			"account_currency": "AED",
		}).insert(ignore_permissions=True).name
	if frappe.db.get_value("Company", company, "default_bank_account") != found:
		frappe.db.set_value("Company", company, "default_bank_account", found)
	return found


def _bank_account_head(company: str) -> str:
	"""Where money lands, as a ledger account rather than a `Bank Account`.

	`account_type` first: ERPNext's own chart has a Bank *group* and a leaf
	under it, and naming the group is refused with a message about groups
	rather than about which account was wanted.
	"""
	return (_bank_ledger(company)
	        or frappe.db.get_value("Company", company, "default_bank_account")
	        or frappe.db.get_value("Account", {
		        "company": company, "is_group": 0,
		        "account_type": "Cash"}, "name") or "")


def _rebank(company: str) -> int:
	"""Take this fixture's own receipts off whatever they landed in before.

	Only its own, and only the ones on the wrong account: a receipt `_paid`
	made carries a `TT-` reference nobody else writes, so this cannot reach a
	payroll payment or anything a person entered. Cancelled and deleted rather
	than repointed, because `_paid` will make them again against the bank
	ledger on the way past — and a submitted Payment Entry's accounts are not
	editable anyway, which is the same wall `reconcile.settle` runs into from
	the other side.

	Nothing is live here. On a real workspace this would be a migration and
	would not be written this way.
	"""
	landing = _bank_account_head(company)
	if not landing:
		return 0
	stray = frappe.get_all(
		"Payment Entry",
		filters={"docstatus": 1, "payment_type": "Receive",
		         "reference_no": ("like", "TT-%"),
		         "paid_to": ("!=", landing)},
		pluck="name",
	)
	for name in stray:
		try:
			payment = frappe.get_doc("Payment Entry", name)
			payment.cancel()
			frappe.db.delete("GL Entry", {"voucher_type": "Payment Entry",
			                              "voucher_no": name})
			frappe.db.delete("Payment Ledger Entry", {"voucher_type": "Payment Entry",
			                                          "voucher_no": name})
			frappe.delete_doc("Payment Entry", name, force=True,
			                  ignore_permissions=True)
		except Exception as raised:
			frappe.clear_last_message()
			print(f"  ! {name} would not come off the cash account: {raised}")
	return len(stray)


#: The bank this workspace banks with, and the account it holds there. Two
#: doctypes because ERPNext keeps the institution and the account apart, which
#: is right the moment a workspace has two accounts at one bank.
BANK = "zzGulf Mercantile Bank"
BANK_ACCOUNT = "zzCurrent — AED"

#: The statement, as (days ago, amount, in or out, reference, description).
#:
#: Five lines, chosen so the reconciliation screen says something different on
#: every one of them — a feed where everything matches exactly proves only that
#: an exact match works:
#:
#: * the first two mirror the receipts `_paid` made, amount and reference, so
#:   ERPNext's matcher ranks the right payment top on both — the case somebody
#:   ticks without reading;
#: * the third is a supplier bill paid by transfer with no payment entry in
#:   these books at all, which is the case the screen exists for: a line that
#:   matches nothing and is somebody's afternoon;
#: * the fourth is a bank charge, which will never match anything either and is
#:   what a journal raised from the ledger is for;
#: * the fifth carries the *first* receipt's amount under no reference, so it
#:   ranks on the amount alone against a payment already spoken for — the case
#:   where the ranking is a suggestion and reading it is the job.
#:
#: `None` for an amount means "take it from the payment this line mirrors",
#: which is what `_statement` fills in.
STATEMENT = [
	(-26, None, "in", None, "Transfer received"),
	(-12, None, "in", None, "Transfer received"),
	(-9, 9250.0, "out", "FT-88213", "Payment to zzHalcyon Joinery"),
	(-7, 145.0, "out", "CHG-0419", "Account maintenance charge"),
	(-3, None, "in", "", "Inward remittance"),
]

#: Which payment each line mirrors, by position in `_paid`'s own order. The
#: fifth deliberately repeats the first.
MIRRORS = {0: 0, 1: 1, 4: 0}


def _bank_account(company: str) -> str:
	"""Where the statement comes from.

	A `Bank Account` is not the ledger account — it is the thing a statement
	belongs to, and it *points at* a ledger account, which is how a bank line
	comes to be comparable with the books. A fixture without one leaves the
	reconciliation screen with an empty picker and nothing to say.
	"""
	head = _bank_account_head(company)
	if not head:
		return ""
	bank = _one("Bank", "bank_name", BANK, {})
	return _one("Bank Account", "account_name", BANK_ACCOUNT, {
		"bank": bank,
		"account": head,
		"company": company,
		"is_company_account": 1,
		"is_default": 1,
		"iban": "AE070331234567890123456",
	})


def _statement(company: str) -> int:
	"""Five bank lines, so the Bank feed has rows and the reconciliation screen
	has something to rank.

	The three mirrored lines take their amount from the payment entries `_paid`
	made, read back rather than repeated: a fixture that wrote `TT-00003` here
	and let `_paid` name its payment something else would be a fixture whose
	best match is no match, which is the one thing this screen must not look
	like when it is working.

	And a line that no longer agrees with the payment it mirrors is **replaced**
	rather than left, because `_paid` remakes its receipts whenever the account
	they land in changes — see `_rebank`. A fixture that drifts out of step
	with itself after a reseed is worse than one that was never seeded.
	"""
	account = _bank_account(company)
	if not account:
		print("  ! no bank account; skipping the statement")
		return 0

	payments = frappe.get_all(
		"Payment Entry", filters={"docstatus": 1, "payment_type": "Receive",
		                          "reference_no": ("like", "TT-%")},
		fields=["name", "paid_amount", "reference_no"],
		order_by="posting_date asc, name asc", limit=2,
	)

	made = 0
	for index, (when, amount, way, reference, description) in enumerate(STATEMENT):
		mirrors = MIRRORS.get(index)
		if mirrors is not None:
			if mirrors >= len(payments):
				continue
			amount = float(payments[mirrors]["paid_amount"])
			# `None` means "and its reference too"; `""` means "and
			# deliberately without one".
			if reference is None:
				reference = payments[mirrors]["reference_no"] or ""

		on = _day(when)
		found = frappe.db.get_value(
			"Bank Transaction",
			{"bank_account": account, "description": description, "date": on},
			["name", "deposit", "withdrawal", "reference_number", "status"],
			as_dict=True,
		)
		if found:
			agrees = (
				float(found.deposit if way == "in" else found.withdrawal) == amount
				and (found.reference_number or "") == (reference or "")
			)
			if agrees:
				continue
			if found.status == "Reconciled":
				# Somebody matched it. Leaving a stale line alone beats undoing
				# a reconciliation somebody made while looking at the screen.
				continue
			_undo_line(found.name)

		line = frappe.get_doc({
			"doctype": "Bank Transaction",
			"date": on, "bank_account": account, "company": company,
			"currency": "AED",
			"description": description,
			"reference_number": reference or "",
			"transaction_type": "Transfer" if way == "in" else "Payment",
			"deposit": amount if way == "in" else 0,
			"withdrawal": 0 if way == "in" else amount,
			# The party is left off on every line, deliberately. A real feed
			# carries a name the bank printed and not a link to a Customer, and
			# a fixture that filled the link in would be seeding the answer the
			# matcher is supposed to rank towards.
		})
		try:
			line.insert(ignore_permissions=True)
			line.submit()
			made += 1
		except Exception as raised:
			frappe.clear_last_message()
			print(f"  ! bank line {description} would not post: {raised}")
	return made


def _undo_line(name: str) -> None:
	"""Take one of this fixture's own statement lines back out."""
	try:
		frappe.get_doc("Bank Transaction", name).cancel()
		frappe.delete_doc("Bank Transaction", name, force=True,
		                  ignore_permissions=True)
	except Exception as raised:
		frappe.clear_last_message()
		print(f"  ! bank line {name} would not come back out: {raised}")


def _books(company: str) -> int:
	"""Bills, payments and a journal entry, so three screens are not empty."""
	made = 0
	supplier = _supplier()
	payable = _payable_account(company)
	expense = _expense_account(company)
	centre = _cost_center(company)
	project = frappe.db.get_value("Project", {"project_name": ("like", "zz%")},
	                              "name")

	for amount, when, against_job in BILLS:
		if frappe.db.exists("Purchase Invoice", {"supplier": supplier,
		                                         "grand_total": amount}):
			continue
		bill = frappe.get_doc({
			"doctype": "Purchase Invoice", "company": company,
			"supplier": supplier,
			# Their reference, which is the column a payables clerk reads
			# first — ours is a naming series nobody outside this site knows.
			"bill_no": f"HJ-{abs(when):04d}",
			"bill_date": _day(when),
			"set_posting_time": 1,
			"posting_date": _day(when), "due_date": _day(when + 30),
			"currency": "AED", "conversion_rate": 1,
			"credit_to": payable,
			**({"project": project} if against_job and project else {}),
			"items": [{
				"item_code": _service_item(), "qty": 1, "rate": amount,
				"expense_account": expense,
				**({"cost_center": centre} if centre else {}),
			}],
		})
		try:
			bill.insert(ignore_permissions=True)
			bill.submit()
			made += 1
		except Exception as raised:
			frappe.clear_last_message()
			print(f"  ! bill {amount} would not post: {raised}")

	_reledger()
	_rebank(company)
	made += _paid(company)
	made += _journalled(company)
	# Last of the four, because two of its five lines are the payments `_paid`
	# has just made and read their amount and reference back off them.
	made += _statement(company)

	# And the column on everything that was posted before the field existed,
	# which on this fixture is every sales invoice and every payment HRMS made
	# — `onebook/origin.py`. A books space whose "Raised by" is blank on the
	# rows it is there to tell apart is a space that looks like it does not
	# work.
	from oneapp.onebook import origin

	origin.rewrite_all()
	return made


#: How many of this fixture's sales invoices are paid. Two of three, so the
#: Invoices dashboard's Outstanding is a different number from its Invoiced —
#: which is the one thing a receivables screen is read for, and is invisible on
#: a fixture where everything is owed or nothing is.
SETTLED = 2


def _reledger() -> int:
	"""Post the ledger for any submitted invoice that has not got one — and
	repost the ones whose accounts nobody would have chosen.

	Three of this fixture's sales invoices were submitted at docstatus 1 with
	no `GL Entry` behind them at all — which makes the Ledger screen a page
	with no revenue on it, and makes `get_payment_entry` refuse them with
	"already been fully paid", because outstanding is read off the payment
	ledger rather than off the column.

	*Why* they lost them is not known and is not worth the archaeology: the
	fixture has been reseeded across several ERPNext versions and an invoice
	that posted nothing is not a state this file can produce today. What is
	worth having is the repair, because the same thing on a customer's site
	would be a set of books quietly missing a quarter of its income.
	"""
	posted = 0
	for doctype, field, wrong_ones, correct in (
		("Sales Invoice", "income_account", NOT_AN_INCOME, _income_account),
		("Purchase Invoice", "expense_account", NOT_AN_EXPENSE, _expense_account),
	):
		for name in frappe.get_all(doctype, filters={"docstatus": 1},
		                           pluck="name"):
			doc = frappe.get_doc(doctype, name)
			wrong = [row for row in doc.items
			         if any(one in (row.get(field) or "") for one in wrong_ones)]
			# The party account too. `_payable_account` used to return whichever
			# Payable leaf the chart yielded, which on this fixture was Payroll
			# Payable — so every supplier bill was credited to the account
			# payroll settles through, and the balance sheet showed a company
			# owing its staff for a joinery invoice.
			party = ""
			if doctype == "Purchase Invoice":
				want = _payable_account(doc.company)
				if want and doc.credit_to != want:
					party = want

			if not wrong and not party and frappe.db.count(
					"GL Entry", {"voucher_no": name}):
				continue
			try:
				if wrong or party:
					# The account is on the row, so nothing short of reposting
					# moves the number. The payment ledger is untouched where
					# only the income or expense side changes; where the party
					# account moves it is rewritten with it.
					account = correct(doc.company)
					for row in wrong:
						frappe.db.set_value(f"{doctype} Item", row.name, field,
						                    account, update_modified=False)
					if party:
						frappe.db.set_value(doctype, name, "credit_to", party,
						                    update_modified=False)
						frappe.db.delete("Payment Ledger Entry",
						                 {"voucher_no": name})
					frappe.db.delete("GL Entry", {"voucher_no": name})
					doc = frappe.get_doc(doctype, name)
				doc.make_gl_entries()
				posted += 1
			except Exception as raised:
				frappe.clear_last_message()
				print(f"  ! {name} would not post its ledger: {raised}")
	if posted:
		print(f"  · reposted the ledger for {posted} documents")
	return posted


def _paid(company: str) -> int:
	"""Two of the three sales invoices settled, so Payments has rows and the
	Invoices dashboard's Outstanding is not the same number as Invoiced.

	Built by `get_payment_entry` rather than by hand: a payment entry has nine
	fields that have to agree with each other and one of them is an exchange
	rate. ERPNext already knows how to fill them from the invoice.
	"""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	landing = _bank_account_head(company)
	if not landing:
		print("  ! no bank or cash account; skipping payments")
		return 0

	# Two, counted against what is already settled rather than against what is
	# outstanding. The obvious filter — the two oldest with anything owing —
	# pays a third invoice on the second run and a fourth on the third, because
	# every pass leaves one fewer unpaid: a fixture that grows by one row every
	# time somebody reseeds is a fixture whose numbers nothing can assert.
	settled = frappe.db.count("Payment Entry Reference",
	                          {"reference_doctype": "Sales Invoice", "docstatus": 1})
	if settled >= SETTLED:
		return 0

	made = 0
	invoices = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		pluck="name", order_by="posting_date asc", limit=SETTLED - settled,
	)
	for invoice in invoices:
		try:
			payment = get_payment_entry("Sales Invoice", invoice)
			payment.paid_to = landing
			payment.reference_no = f"TT-{invoice[-5:]}"
			payment.reference_date = payment.posting_date
			payment.insert(ignore_permissions=True)
			payment.submit()
			made += 1
		except Exception as raised:
			frappe.clear_last_message()
			print(f"  ! payment for {invoice} would not post: {raised}")
	return made


#: What the one hand-written journal says. A reclass between two expense heads
#: is the most ordinary journal entry there is and the only kind that needs no
#: party, no invoice and no bank — which is what makes it seedable on a chart
#: this fixture did not choose.
JOURNAL = "zzReclass — site accommodation"


def _journalled(company: str) -> int:
	"""One journal entry nobody else raised, so the screen has a row whose
	`custom_origin` is blank beside whatever payroll posts."""
	if frappe.db.exists("Journal Entry", {"user_remark": JOURNAL}):
		return 0

	accounts = [
		name for name in frappe.get_all(
			"Account", pluck="name", order_by="name asc",
			filters={"company": company, "is_group": 0, "root_type": "Expense"})
		if not any(one in name for one in NOT_AN_EXPENSE)
	][:2]
	if len(accounts) < 2:
		print("  ! fewer than two expense accounts; skipping the journal")
		return 0

	centre = _cost_center(company)
	entry = frappe.get_doc({
		"doctype": "Journal Entry", "company": company,
		"voucher_type": "Journal Entry",
		"posting_date": _day(-9),
		"user_remark": JOURNAL,
		"accounts": [
			{"account": accounts[0], "debit_in_account_currency": 3200,
			 **({"cost_center": centre} if centre else {})},
			{"account": accounts[1], "credit_in_account_currency": 3200,
			 **({"cost_center": centre} if centre else {})},
		],
	})
	try:
		entry.insert(ignore_permissions=True)
		entry.submit()
		return 1
	except Exception as raised:
		frappe.clear_last_message()
		print(f"  ! journal entry would not post: {raised}")
		return 0


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

# The stage is `One Deal Stage` now — `docs/ONECRM.md` stage 1 — so these are
# the five columns the space ships with rather than ERPNext's eight, and the
# status is not seeded at all: `onecrm/deal.py` writes it from the stage's
# category, which is the whole claim and would be untestable if the fixture
# asserted both.
#
# title, customer, stage, amount, probability, closing in days,
# next step, next step in days
DEALS = [
	("zzHarbour Point phase two", "zzMeridian Group", "New",
	 320000, 20, 60, "zzArrange the walk-round", 2),
	("zzAlmond Court common parts", "zzAlmond Holdings", "Qualifying",
	 145000, 35, 30, "zzConfirm the specification", -1),
	("zzCivic Library phase two", "zzCity of Harbour", "Qualifying",
	 610000, 40, 90, "zzMeet the estates team", 7),
	("zzMeridian head office refit", "zzMeridian Group", "Proposal",
	 275000, 60, 21, "zzChase the signature", 1),
	("zzAlmond warehouse mezzanine", "zzAlmond Holdings", "Negotiation",
	 198000, 75, 14, "zzAgree the retention", 4),
	("zzHarbour Point signage", "zzMeridian Group", "New",
	 42000, 25, 45, "zzFind out who signs", 12),
	("zzCity depot offices", "zzCity of Harbour", "Proposal",
	 88000, 45, 35, "zzSend the comparison", -3),
	("zzAlmond Court roof terrace", "zzAlmond Holdings", "Lost",
	 64000, 10, -10, "", 0),
	("zzMeridian studio fit-out", "zzMeridian Group", "Won",
	 410000, 100, -20, "", 0),
	("zzHarbour Point cafe", "zzMeridian Group", "Qualifying",
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

# Calls that actually happened — `docs/ONECRM.md` stage 5. Against deals rather
# than against leads, because the point of the fixture is the *merged* timeline:
# a record whose column has a comment, a field change, a mail and a call on it
# is the only way to see that the merge works at all.
#
# Two of the five are unanswered. A call log where every row says Answered says
# nothing; a pair of attempts before a conversation is what the outcome field
# is for.
#
#: deal, with whom, direction, days ago, minutes, outcome, note
CALLS = [
	("zzHarbour Point cafe", "zzNadia Fares", "Outgoing", -6, 0, "No answer",
	 ""),
	("zzHarbour Point cafe", "zzNadia Fares", "Outgoing", -5, 14, "Answered",
	 "zzWants the fit-out priced by the end of the month. Sending a revised "
	 "schedule on Thursday."),
	("zzMeridian studio fit-out", "zzOmar Haddad", "Incoming", -3, 6,
	 "Answered", "zzChased the delivery date. Told them the 14th."),
	("zzCity depot offices", "zzProcurement desk", "Outgoing", -2, 0,
	 "Voicemail", ""),
	("zzAlmond warehouse mezzanine", "zzLina Traboulsi", "Outgoing", -1, 22,
	 "Answered", "zzThe mezzanine is approved. Contract to follow."),
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


#: Where each deal has been, and for how long — `docs/ONECRM.md` stage 2.
#:
#: Written after the save rather than through it: `onecrm/deal.py` stamps the
#: arrival with *now*, which is right for a person moving a card and useless
#: for a fixture — every deal would read "in this stage since a moment ago" and
#: the one question the log exists to answer would have no answer to look at.
#:
#: The last stage in each list is the one the deal is in, and its number is how
#: many days it has been stuck there. Two are deliberately old: a review opens
#: this pipeline to find them.
#:
#: title: [(stage, days in it), ...]
HISTORY = {
	"zzHarbour Point phase two": [("New", 6)],
	"zzAlmond Court common parts": [("New", 4), ("Qualifying", 11)],
	"zzCivic Library phase two": [("New", 9), ("Qualifying", 52)],
	"zzMeridian head office refit": [("New", 3), ("Qualifying", 8),
	                                 ("Proposal", 14)],
	"zzAlmond warehouse mezzanine": [("New", 5), ("Qualifying", 9),
	                                 ("Proposal", 12), ("Negotiation", 6)],
	"zzHarbour Point signage": [("New", 2)],
	"zzCity depot offices": [("New", 7), ("Qualifying", 21), ("Proposal", 41)],
	"zzAlmond Court roof terrace": [("New", 8), ("Qualifying", 16),
	                                ("Lost", 30)],
	"zzMeridian studio fit-out": [("New", 4), ("Qualifying", 10),
	                              ("Proposal", 9), ("Negotiation", 7),
	                              ("Won", 22)],
	"zzHarbour Point cafe": [("New", 5), ("Qualifying", 3)],
}


def _stage_history(deal: str, path) -> None:
	"""Write one deal's stage log, backdated, as rows.

	Rows rather than a save, and this is the one place in the seeder that
	matters: saving the parent would run `onecrm/deal.py`, which stamps an
	arrival with the current time — which is exactly what this is replacing.
	The child rows go in directly and the parent's `custom_stage_since` is set
	beside them, which is the same pair the controller writes.
	"""
	frappe.db.delete("One Stage Change", {"parent": deal, "parenttype": "Opportunity"})

	ago = sum(days for _stage, days in path)
	for at, (stage, days) in enumerate(path):
		entered = frappe.utils.add_to_date(frappe.utils.now_datetime(), days=-ago)
		ago -= days
		last = at == len(path) - 1
		row = frappe.new_doc("One Stage Change")
		row.update({
			"stage": stage, "entered_on": entered,
			"left_on": None if last else frappe.utils.add_to_date(entered, days=days),
			"days": 0 if last else days,
			"moved_by": frappe.session.user,
			"parent": deal, "parenttype": "Opportunity",
			"parentfield": "custom_stage_log", "idx": at + 1,
		})
		row.name = frappe.generate_hash(length=10)
		row.db_insert()
		if last:
			frappe.db.set_value("Opportunity", deal, "custom_stage_since", entered,
			                    update_modified=False)


def _crm(company: str) -> int:
	# The columns a pipeline is drawn by — `docs/ONECRM.md` stage 1. Written
	# once and never edited afterwards, so a workspace that renamed a stage or
	# moved one keeps it, which is the same rule `onetask/states.ensure`
	# follows and for the same reason.
	from oneapp.onecrm import stages as deal_stages
	from oneapp_control.spaces import onecrm as manifest

	deal_stages.ensure(manifest.STAGES)

	# And what counts as answering in time — `docs/ONECRM.md` stage 6. Same
	# rule: written once, never edited afterwards, because a desk that
	# lengthened its own target should not find it back at four hours after
	# the next migration.
	from oneapp.onecrm import answering

	answering.ensure(manifest.TARGETS)

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
	for at, (title, customer, stage, amount, probability, closing,
	         step, step_in) in enumerate(DEALS):
		party = frappe.db.get_value("Customer", {"customer_name": customer}, "name")
		found = frappe.db.get_value("Opportunity", {"title": title}, "name")
		values = {
			"opportunity_from": "Customer", "party_name": party, "title": title,
			"company": company, "custom_stage": stage,
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
		_stage_history(doc.name, HISTORY.get(title) or [(stage, 3)])

	# One deal that came from a lead, so the fixture has the thing
	# `docs/ONECRM.md` stage 4 is about: a record whose history starts before
	# it existed. `opportunity_from` and `party_name` are ERPNext's own dynamic
	# party — which is why the inheritance is a declaration rather than a rule,
	# since a deal may equally have come from a Customer or a Prospect.
	converted = frappe.db.get_value("Lead", {"lead_name": "zzNadia Fares"}, "name")
	if converted and deals.get("zzHarbour Point cafe"):
		frappe.db.set_value("Opportunity", deals["zzHarbour Point cafe"], {
			"opportunity_from": "Lead", "party_name": converted,
		}, update_modified=False)
		# And something on the lead worth carrying, or the claim is a column
		# that gained one entry saying the lead was created.
		# `comment_type` in the key, and it is not a detail: Frappe writes its
		# own `Comment` rows for every link and status change, so a bare
		# existence check matched three rows saying "Opportunity" and the
		# fixture never wrote the one line stage 4 is about.
		if not frappe.db.exists("Comment", {"reference_doctype": "Lead",
		                                    "reference_name": converted,
		                                    "comment_type": "Comment"}):
			frappe.get_doc({
				"doctype": "Comment", "comment_type": "Comment",
				"reference_doctype": "Lead", "reference_name": converted,
				"content": "zzFirst call went well — they want a price for the "
				           "cafe fit-out by the end of the month.",
				"comment_email": frappe.session.user,
				"comment_by": frappe.session.user,
			}).insert(ignore_permissions=True)

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

	for deal, whom, way, when, minutes, outcome, note in CALLS:
		about = deals.get(deal)
		if not about:
			continue
		# Keyed on the deal, the person *and the outcome*, which is the only
		# combination that is unique here: the same person rang twice about the
		# cafe, so `with_whom` alone would upsert the second call over the
		# first and the pair of attempts — the thing this fixture is showing —
		# would never exist. Not on `at`, which moves every day: a key with
		# today in it is not a key, and the fixture would gain five rows a day.
		key = {"about_doctype": "Opportunity", "about_name": about,
		       "with_whom": whom, "outcome": outcome}
		values = {"way": way, "at": _day(when) + " 11:15:00",
		          "minutes": minutes, "note": note,
		          "number": "+97150000000", "person": frappe.session.user}
		found = frappe.db.get_value("One Call", key, "name")
		if found:
			# Re-dated rather than left alone, so the week the calendar opens
			# on is always this week.
			frappe.db.set_value("One Call", found, values, update_modified=False)
			continue
		frappe.get_doc({"doctype": "One Call", **key, **values}).insert(
			ignore_permissions=True)

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

# Arriving, leaving, and the thing nobody wants to file.
#
# The three screens in the People group a fixture never reached, so all three
# drew "nothing here" — and a board with no cards says nothing about a board.
#
# Onboarding hangs off a *Job Offer*, which HRMS requires, so there are exactly
# as many of these as there are offers. Maya's is In Process because she
# accepted; Elias's stays Pending because his offer is still out and the
# preparation started anyway, which is both true to life and the reason that
# state exists.

# applicant, boarding status, joins in days, activities (name, begins after)
ONBOARDING = [
	("zzMaya Seif", "In Process", 30, [
		("zzContract signed and returned", 0),
		("zzLaptop, phone and access card", 3),
		("zzInduction with the studio", 5),
		("zzPayroll and bank details", 5),
	]),
	("zzElias Moussa", "Pending", 45, [
		("zzContract signed and returned", 0),
		("zzLaptop, phone and access card", 3),
	]),
]

# person, boarding status, letter written days ago, last day in days, activities
#
# Three, one per state, because the whole argument for a board here is that a
# separation stuck in Pending for three weeks is the row somebody has to chase
# — and a board where every card is in one column cannot show that.
EXITS = [
	("zzTarek Jaber", "Pending", -4, 26, [
		("zzHandover notes written", 0),
		("zzEquipment returned", 20),
	]),
	("zzRania Sabbagh", "In Process", -20, 10, [
		("zzHandover notes written", 0),
		("zzAccess revoked", 25),
		("zzFinal settlement", 28),
	]),
	("zzKarim Nassar", "Completed", -60, -30, [
		("zzHandover notes written", 0),
	]),
]

# type, subject, raised by, against (doctype, name), date, status, resolved by
#
# Against a Department rather than a person on two of the three: a grievance
# whose subject is always a colleague is a fixture that hides the dynamic link,
# which is the only unusual field on this doctype.
GRIEVANCE_TYPES = ["zzWorkload", "zzFacilities", "zzConduct"]

GRIEVANCES = [
	("zzFacilities", "zzThe site office has no drinking water",
	 "zzOmar Fadel", ("Department", "zzDelivery"), -9, "Resolved", True),
	("zzWorkload", "zzThree weeks of unplanned overtime",
	 "zzLeila Amari", ("Department", "zzDesign"), -3, "Investigated", False),
	("zzConduct", "zzSpoken to badly in front of the client",
	 "zzKarim Nassar", ("Employee", "zzSami Rahal"), -1, "Open", False),
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

	# Keyed by who and which type, not by the dates: every date here is
	# relative to today, so a re-seed the day after the last one asks for a
	# window that has moved by one — and HRMS refuses a second application
	# overlapping the first, which took the whole seed down at midnight. One
	# application per person per type is what this fixture means.
	for person, kind, start, end, days, status in LEAVE:
		name = _submitted("Leave Application", {
			"employee": people[person], "leave_type": kind,
		}, {
			"from_date": _day(start),
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

	# Keyed by who and which shift, not by the start date: the dates here are
	# relative to today, and HRMS refuses a second assignment overlapping the
	# first — so a re-seed a day later took the whole seed down.
	for person in ("zzOmar Fadel", "zzKarim Nassar"):
		_submitted("Shift Assignment", {
			"employee": people[person], "shift_type": "zzSite shift",
		}, {
			"start_date": _day(-30), "end_date": _day(60),
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

	# A *weekday* four working days back, from the fortnight computed above,
	# rather than a fixed offset: HRMS refuses an attendance request over a
	# holiday, and `_day(-4)` lands on the weekend three days in seven. Keyed
	# without the date for the same reason the applications above are.
	_submitted("Attendance Request", {
		"employee": people["zzSami Rahal"],
	}, {
		"from_date": _day(days[-4]),
		"to_date": _day(days[-4]), "company": company, "reason": "Work From Home",
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
		"employee": people["zzKarim Nassar"], "shift_type": "zzDay shift",
	}, {
		"from_date": _day(7),
		"to_date": _day(21), "company": company,
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
			"employee": people[person], "total_claimed_amount": claimed,
		}, {
			"posting_date": _day(when),
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

	# A second advance, paid and unspent, because the first one is fully
	# claimed. Every verb on the Advances screen is about the *unspent* part —
	# claim against it, take it back, deduct it from salary — so a fixture with
	# only a settled advance is a fixture where all three refuse.
	_submitted("Employee Advance", {
		"employee": people["zzOmar Fadel"], "posting_date": _day(-10),
	}, {
		"company": company, "purpose": "zzTravel float",
		"advance_amount": 2000, "advance_account": _advance_account(company),
		"exchange_rate": 1, "currency": "AED",
		"repay_unclaimed_amount_from_salary": 1,
	})

	# And that one paid, because every verb on an advance is gated by HRMS on
	# `paid_amount` — so a fixture of unpaid advances is a fixture where all
	# four of them refuse. Through the same helper the **Draft the payment**
	# verb uses, then submitted, which is the step this space leaves to whoever
	# keeps the books.
	float_advance = frappe.db.get_value(
		"Employee Advance", {"purpose": "zzTravel float", "docstatus": 1}, "name")
	if float_advance and not frappe.db.get_value(
		"Employee Advance", float_advance, "paid_amount"):
		from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

		try:
			payment = get_payment_entry_for_employee("Employee Advance", float_advance)
			payment = frappe.get_doc(payment) if isinstance(payment, dict) else payment
			payment.insert(ignore_permissions=True)
			payment.submit()
		except Exception as raised:
			frappe.clear_last_message()
			print(f"  ! the advance would not pay out: {raised}")

	# A role asked for and somebody put forward, which are the two hiring
	# screens that have been in the rail since the space shipped with nothing
	# in them — and therefore the two whose verbs nobody could press.
	# Not submittable, so `_one` rather than `_submitted` — keyed on the
	# designation, which is what makes this requisition this requisition.
	_one("Job Requisition", "designation", "Engineer", {
		"company": company, "department": _department("zzDelivery"),
		"no_of_positions": 2, "expected_by": _day(60),
		# An Employee, not a User: HRMS asks who is short-handed rather than
		# who typed it, which is the distinction the whole doctype is about.
		"requested_by": people["zzSami Rahal"],
		"posting_date": _day(-6), "expected_compensation": 48000,
		"description": "zzFixture", "status": "Open & Approved",
	})
	# HRMS stamps a referred applicant with `source = "Employee Referral"`, which
	# is a Job Applicant Source it does not ship — so the verb that turns a
	# referral into an applicant failed on a link nobody had made.
	_named("Job Applicant Source", "Employee Referral",
	       {"source_name": "Employee Referral"})
	_one("Employee Referral", "email", "zzNadia@zzapplicants.test", {
		"first_name": "zzNadia", "last_name": "Rahim",
		"contact_no": "+971500000001",
		"for_designation": "Designer", "referrer": people["zzLeila Amari"],
		"date": _day(-6), "status": "Pending",
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
			"job_applicant": applicant, "interview_type": "zzFirst interview",
		}, {
			"scheduled_on": _day(when),
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

	_boarding(company, people)
	return marked


# --------------------------------------------------------------------------- #
# Arriving, leaving, and the thing nobody wants to file
# --------------------------------------------------------------------------- #

def _boarding(company: str, people: dict) -> None:
	"""Onboarding, exits and grievances — the People group's other three.

	Submitted rather than left as drafts, and that is the whole design of these
	two doctypes rather than a fixture choice: HRMS's boarding controller makes
	a Project and a Task per activity **on submit**, and the checklist is what
	onboarding *is*. A fixture that stopped at draft would draw three empty
	columns and hide the one thing the screens are for.

	It also means these screens leave a trail in somebody else's space — a
	Project per onboarding, in ERPNext's own `Project` table, which OneProject
	lists. That is HRMS's behaviour and not ours, and a fixture that hid it
	would be hiding the finding.

	`boarding_status` is `allow_on_submit` and read-only, and `on_submit` sets
	it to Pending whatever was asked for, so the state is written afterwards —
	every run, like the Job Offer status above and for the same reason.
	"""
	for who, status, joins, activities in ONBOARDING:
		applicant = frappe.db.get_value("Job Applicant", {"applicant_name": who}, "name")
		offer = applicant and frappe.db.get_value(
			"Job Offer", {"job_applicant": applicant}, "name")
		if not offer:
			continue
		made = _submitted("Employee Onboarding", {"job_offer": offer}, {
			"job_applicant": applicant, "employee_name": who, "company": company,
			# A fortnight before they walk in, which is what onboarding is
			# and which HRMS on its own refuses: it makes the Project starting
			# on the joining date and then dates every task from here, and
			# ERPNext's Task will not start before its project. `onehr/boarding`
			# widens the project first, and this is the fixture that would fail
			# without it.
			"date_of_joining": _day(joins),
			"boarding_begins_on": _day(joins - 14),
			"designation": "Designer", "department": _department("zzDesign"),
			# There is no Employee yet to take one from, and the boarding
			# controller dates every task against a holiday list — so without
			# this the submit is refused with "Please set the Holiday List".
			"holiday_list": "zzWeekends",
			"activities": [
				{"activity_name": name, "begin_on": after, "duration": 1}
				for name, after in activities
			],
		})
		if made:
			frappe.db.set_value("Employee Onboarding", made, "boarding_status",
			                    status, update_modified=False)

	for who, status, wrote, last, activities in EXITS:
		# The date is the *person's*, not the separation's: HRMS fetches
		# `resignation_letter_date` from the Employee, so a separation written
		# with one of its own comes back blank and the exits board draws three
		# cards with nothing to chase them by.
		#
		# The status is deliberately left alone. Marking somebody Left is a
		# real change — ERPNext then refuses leave, attendance and payroll
		# against them — and every one of these six people is carrying a
		# fortnight of days, an allocation and a salary in this fixture. So
		# they have resigned and are working their notice, which is what a
		# separation in Pending or In Process means anyway.
		frappe.db.set_value("Employee", people[who], {
			"resignation_letter_date": _day(wrote),
			"relieving_date": _day(last),
		}, update_modified=False)
		made = _submitted("Employee Separation", {"employee": people[who]}, {
			"company": company, "boarding_begins_on": _day(wrote),
			"activities": [
				{"activity_name": name, "begin_on": after, "duration": 1}
				for name, after in activities
			],
		})
		if made:
			frappe.db.set_value("Employee Separation", made, "boarding_status",
			                    status, update_modified=False)

	for name in GRIEVANCE_TYPES:
		_named("Grievance Type", name, {})

	# And the steps of every checklist, typed, so a board of the quarter's work
	# is work. `onehr/boarding.py` stamps them as it makes them; this catches
	# the ones an earlier run made before it did.
	from oneapp.onehr import boarding

	for project in frappe.get_all("Project", filters={
		"project_type": boarding.BOARDING}, pluck="name"):
		boarding.type_tasks(project)

	for kind, subject, who, (party, against), on, status, resolved in GRIEVANCES:
		target = (_department(against) if party == "Department"
		          else people.get(against))
		if not target:
			continue
		# Not submitted. A grievance's `status` is required and *not*
		# `allow_on_submit`, so the one field anybody moves is the one a
		# submitted row would freeze — and HRMS's own list is full of drafts
		# for that reason.
		_one("Employee Grievance", "subject", subject, {
			"grievance_type": kind, "raised_by": people[who], "date": _day(on),
			"status": status, "description": "zzFixture",
			"grievance_against_party": party, "grievance_against": target,
			"cause_of_grievance": subject,
			**({"resolution_details": "zzFixture", "resolved_by": frappe.session.user,
			    "resolution_date": _day(on + 4)} if resolved else {}),
		})


def _department(name: str) -> str | None:
	"""A department by the name a person would say.

	ERPNext names a Department `{name} - {company abbr}`, so nothing that
	stores one can be written with the word somebody typed.
	"""
	return frappe.db.get_value("Department", {"department_name": name}, "name")


#: Expense accounts that are never what somebody means.
#:
#: The first Expense leaf in ERPNext's own chart is **Exchange Loss**, and for
#: a year this fixture booked every supplier bill and every payroll accrual to
#: it. Nothing said a word, because a list of bills shows the supplier and the
#: total and never the account — and it took building a profit and loss
#: (`docs/ONEBOOK.md` stage 1) to see a company whose entire cost base was
#: exchange differences.
#:
#: Named rather than ordered around, because "the second one alphabetically" is
#: the same bug one place along.
NOT_AN_EXPENSE = ("Exchange Loss", "Round Off", "Write Off",
                  "Stock Adjustment", "Expenses Included In Valuation")

#: And the same on the other side. The first **Income** leaf in ERPNext's chart
#: is Exchange Gain, so a fixture that took the first one booked every sale as
#: a currency movement — a profit and loss showing 430,000 of exchange gains
#: and no revenue at all.
NOT_AN_INCOME = ("Exchange Gain",)


def _expense_account(company: str) -> str:
	"""Where a cost lands. The company's own default first.

	`default_expense_account` is what ERPNext itself reaches for, and
	`onespace/books.py` does not fill it — there is no `account_type` that
	identifies one, so `name_the_accounts` cannot and deliberately does not
	guess. Here there is a fixture to make sensible, so the fallbacks are ours:
	cost of goods sold, then the first Expense leaf that is not one of the
	accounts above.
	"""
	found = frappe.db.get_value("Company", company, "default_expense_account")
	if found:
		return found
	found = frappe.db.get_value("Account", {
		"company": company, "is_group": 0,
		"account_type": "Cost of Goods Sold"}, "name")
	if found:
		return found
	for name in frappe.get_all("Account", pluck="name", filters={
			"company": company, "is_group": 0, "root_type": "Expense"},
			order_by="name asc"):
		if not any(one in name for one in NOT_AN_EXPENSE):
			return name
	return ""


def _payable_account(company: str) -> str:
	"""Who we owe. The company's default first, for the same reason.

	The typed fallback returns whichever Payable leaf the chart happens to
	yield, and on this fixture that was **Payroll Payable** — so every
	supplier bill was credited to the account payroll settles through, and the
	balance sheet showed a company that owed its staff for a joinery invoice.
	"""
	return (frappe.db.get_value("Company", company, "default_payable_account")
	        or frappe.db.get_value("Account", {
		        "company": company, "is_group": 0,
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
	# Keyed without the date, like the applications in `_hr` and for the same
	# reason: a re-seed a day later asks for a window one day along, and HRMS
	# refuses a second application that overlaps the first.
	# And re-issued where the one already on the site has aged out from under
	# it. Every date in this file is relative to today, so a window written on
	# Monday stops covering Thursday — and the pill this fixture exists to make
	# say "On leave" quietly starts saying "Not known" instead. Cancelled
	# rather than edited, because a submitted document is not a row to patch.
	_away = {"employee": people["zzHala Zayed"], "leave_type": "zzAnnual leave"}
	stale = frappe.get_all(
		"Leave Application",
		filters={**_away, "docstatus": 1, "to_date": ["<", str(today)]},
		pluck="name",
	)
	for one in stale:
		doc = frappe.get_doc("Leave Application", one)
		doc.cancel()
	_submitted("Leave Application", {**_away, "docstatus": 1}, {
		"from_date": _day(-1), "to_date": _day(2), "company": company,
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

	# And the account it is all payable against, marked as payable.
	#
	# ERPNext's own chart makes "Payroll Payable" with no `account_type` and
	# HRMS refuses to submit a run whose payable account is not typed Payable —
	# so the fixture's company could hold a payroll entry and never submit one.
	# Set rather than created: the account exists, it is the company's own
	# default, and only its type is missing.
	default_payable = frappe.db.get_value(
		"Company", company, "default_payroll_payable_account")
	if default_payable and frappe.db.get_value(
		"Account", default_payable, "account_type") != "Payable":
		frappe.db.set_value("Account", default_payable, "account_type", "Payable")

	# A payroll *run*, as a draft, for the month before the payslips above.
	#
	# The fixture used to make its payslips one at a time, which is not how a
	# workspace gets them and is why the **Payroll runs** screen had nothing on
	# it for as long as it has existed — and a screen with no rows is a screen
	# whose seven verbs nobody ever pressed. `onehr/payroll.py` is those verbs;
	# this is something to press them on.
	#
	# The month *before* the payslips, so `fill_employee_details` finds
	# everybody: HRMS leaves out anybody who already holds a slip for the
	# period, and last month's are all written.
	before_end = add_to_date(str(start), days=-1)
	before_start = getdate(before_end).replace(day=1)
	if not frappe.db.exists("Payroll Entry", {"start_date": str(before_start)}):
		run = frappe.get_doc({
			"doctype": "Payroll Entry", "company": company,
			"posting_date": str(before_end), "payroll_frequency": "Monthly",
			"start_date": str(before_start), "end_date": str(before_end),
			"currency": "AED", "exchange_rate": 1,
			# The *payroll* payable account rather than any payable one, and
			# they are not the same: `get_filtered_employees` joins the run to
			# each Salary Structure Assignment on this field, and HRMS fills the
			# assignment's in from the company's default. A run naming
			# Creditors finds nobody at all and says "no employees found for
			# the mentioned criteria", which names five things and not the one
			# that is wrong.
			"payroll_payable_account": default_payable or _payable_account(company),
			"payment_account": _payable_account(company),
			"cost_center": _cost_center(company),
		})
		try:
			run.insert(ignore_permissions=True)
		except Exception as raised:
			frappe.clear_last_message()
			print(f"  ! payroll run would not open: {raised}")

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
# The second pass at HRMS
#
# `docs/ERP-SPACES.md` §5, "What a second reading of HRMS found": twenty-four
# doctypes that had no door, and a screen with no rows behind it is the same as
# not having looked. One or two rows each, which is all it takes to see whether
# a column reads — the shapes are already proven, what is new is the
# declarations.
# --------------------------------------------------------------------------- #

#: Who is good at what, and what they have sat through.
SKILL_MAPS = [
	("zzLeila Amari", [("zzRevit", 5), ("zzSite experience", 3)],
	 "zzRevit for designers"),
	("zzOmar Fadel", [("zzSite experience", 5), ("zzCost planning", 2)], None),
]


def _more(company: str, people: dict, cycle: str) -> int:
	"""A row or two behind each of the screens the second HRMS pass added."""
	made = 0

	# ----- People ---------------------------------------------------------- #
	for skill in ("zzRevit", "zzCost planning"):
		if not frappe.db.exists("Skill", skill):
			frappe.get_doc({"doctype": "Skill", "skill_name": skill}).insert(
				ignore_permissions=True)
	event = frappe.db.get_value("Training Event",
	                            {"event_name": "zzRevit for designers"}, "name")
	for who, skills, trained in SKILL_MAPS:
		_one("Employee Skill Map", "employee", people[who], {
			"employee_skills": [
				{"skill": skill, "proficiency": rating,
				 "evaluation_date": _day(-30)}
				for skill, rating in skills
			],
			"trainings": ([{"training": event, "training_date": _day(-30)}]
			              if trained and event else []),
		})
		made += 1

	# The conversation on the way out, for the two people working their notice.
	# Not the same document as the separation beside it — one is a checklist and
	# the other is a questionnaire with a verdict.
	for who, status, verdict in (("zzTarek Jaber", "Completed", "Exit Confirmed"),
	                             ("zzRania Sabbagh", "Scheduled", "")):
		name = _once("Exit Interview", "employee", people[who], {
			"company": company, "date": _day(-2), "status": status,
			"employee_status": verdict,
			"interviewers": [{"user": frappe.session.user}],
			"interview_summary": "zzFixture",
		})
		made += 1

	# ----- Time ------------------------------------------------------------ #
	# A pattern and somebody enrolled in it. `create_shifts_after` is in the
	# future on purpose: HRMS writes assignments forward from that date, and a
	# fixture that backdated it would be a fixture that invented a roster.
	pattern = _submitted("Shift Schedule", {"name": "zzSite rota"}, {
		"shift_type": "zzSite shift", "frequency": "Every Week",
		"repeat_on_days": [{"day": day} for day in ("Monday", "Wednesday", "Friday")],
	})
	if pattern:
		for who in ("zzOmar Fadel", "zzKarim Nassar"):
			_one("Shift Schedule Assignment", "employee", people[who], {
				"company": company, "shift_schedule": pattern,
				"shift_status": "Active", "enabled": 1,
				"create_shifts_after": _day(30),
			})
			made += 1

	# ----- Leave ----------------------------------------------------------- #
	# Worked a Saturday, wants the day back. Three rows and every one of them is
	# load-bearing: HRMS refuses a compensatory request for a day that is not on
	# the person's holiday list, and refuses it again unless there is a Present
	# attendance on that day — which is the whole point of the document.
	_named("Leave Type", "zzTime off in lieu", {
		"leave_type_name": "zzTime off in lieu", "is_compensatory": 1,
		"max_leaves_allowed": 0, "include_holiday": 0,
	})
	# The day is read off the holiday list rather than worked out from the
	# calendar: HRMS asks whether *this employee's* list says the date is a
	# holiday, and the fixture's weekly off is Friday. A seeder that assumed
	# Saturday failed with "2026-09-12 is not a holiday", which is the right
	# error for the wrong reason.
	worked = frappe.db.get_value("Holiday", {
		"parent": "zzWeekends", "holiday_date": ("<", nowdate()),
	}, "holiday_date", order_by="holiday_date desc")
	if worked:
		worker = people["zzSami Rahal"]
		_submitted("Attendance", {
			"employee": worker, "attendance_date": str(worked),
		}, {"company": company, "status": "Present", "shift": "zzSite shift"})
		_submitted("Compensatory Leave Request", {
			"employee": worker, "work_from_date": str(worked),
		}, {
			"work_end_date": str(worked), "leave_type": "zzTime off in lieu",
			"reason": "zzFixture",
		})
		made += 1

	# The middle of leave: a policy, and somebody assigned to it. The assignment
	# writes the allocations, which is the work this screen exists to save.
	# Over a leave type nothing else in this fixture allocates. `_hr` gives
	# everybody their annual and sick days directly, and HRMS refuses a second
	# allocation of a type somebody already holds for the period — so a policy
	# made of those two submitted and then allocated nothing, which is the one
	# thing this document is for.
	_named("Leave Type", "zzStudy leave", {
		"leave_type_name": "zzStudy leave", "max_leaves_allowed": 5,
		"is_lwp": 0, "include_holiday": 0,
	})
	policy = _one("Leave Policy", "title", "zzStandard policy", {
		"leave_policy_details": [
			{"leave_type": "zzStudy leave", "annual_allocation": 5},
		],
	})
	year = getdate(nowdate()).year
	# Against a period rather than against two typed dates. Both are legal and
	# only one of them allocates: with `assignment_based_on` blank the
	# assignment submits and ticks nothing, so the screen drew three empty
	# columns and the row did the one thing it exists for — writing the
	# allocations — not at all.
	# Keyed on its start rather than on a name: Leave Period names itself from
	# a series, so a fixture keyed on `name` would make a new one every run.
	period = _one("Leave Period", "from_date", f"{year}-01-01", {
		"to_date": f"{year}-12-31", "company": company, "is_active": 1,
	})
	for who in ("zzHala Zayed", "zzNoor Haddad"):
		_submitted("Leave Policy Assignment", {
			"employee": people[who], "leave_policy": policy,
		}, {
			"company": company, "assignment_based_on": "Leave Period",
			"leave_period": period,
			"effective_from": f"{year}-01-01", "effective_to": f"{year}-12-31",
		})
		made += 1

	# And the balance that is two days wrong.
	allocation = frappe.db.get_value("Leave Allocation", {
		"employee": people["zzLeila Amari"], "leave_type": "zzAnnual leave",
		"docstatus": 1,
	}, "name")
	if allocation:
		_submitted("Leave Adjustment", {
			"employee": people["zzLeila Amari"], "leave_allocation": allocation,
		}, {
			# Reduce rather than Allocate: the annual type is capped at
			# twenty-five and the fixture already allocates all of them, so an
			# adjustment upwards is refused by the cap rather than by anything
			# this screen is about.
			"leave_type": "zzAnnual leave", "adjustment_type": "Reduce",
			"leaves_to_adjust": 2, "posting_date": _day(-1),
			"company": company, "reason_for_adjustment": "zzFixture",
		})
		made += 1

	# **Holiday assignments** needs no row of its own: `_ground` already writes
	# the company's, because this version of HRMS refuses attendance and leave
	# without one. The tab is a door onto a document the fixture has had since
	# the day the space shipped and nobody could open.

	# ----- The three bulk tools -------------------------------------------- #
	#
	# Their filters, stored. A tool's document is not saved *by the tool* —
	# `oneapp/onehr/tools.py` says why — but it is an ordinary Single and HRMS's
	# own desk saves it, so a dev tenant whose three tools open ready to press
	# is the honest fixture rather than a special case. Without this the pages
	# open empty and the first thing anybody does is fill in the company.
	for doctype, held in (
		("Leave Control Panel", {
			"company": company, "dates_based_on": "Leave Period",
			"leave_period": period, "leave_type": "zzStudy leave",
			"no_of_days": 5, "allocate_based_on_leave_policy": 0,
			"carry_forward": 0,
		}),
		("Shift Assignment Tool", {
			"action": "Assign Shift", "company": company,
			"shift_type": "zzSite shift", "status": "Active",
			"start_date": _day(45), "end_date": _day(75),
		}),
		("Bulk Salary Structure Assignment", {
			"company": company, "from_date": _day(45), "currency": "USD",
			"salary_structure": frappe.db.get_value(
				"Salary Structure", {"is_active": "Yes"}, "name"),
		}),
	):
		single = frappe.get_single(doctype)
		single.update({k: v for k, v in held.items() if v})
		single.save(ignore_permissions=True)
		made += 1

	# ----- Hiring ---------------------------------------------------------- #
	_one("Staffing Plan", "name", "zzNext year", {
		"company": company, "from_date": _day(30), "to_date": _day(395),
		"staffing_details": [
			{"designation": "Engineer", "number_of_positions": 3,
			 "estimated_cost_per_position": 42000},
			{"designation": "Designer", "number_of_positions": 1,
			 "estimated_cost_per_position": 36000},
		],
	})
	made += 1

	# What the interviewer said, which is the only part of an interview anybody
	# re-reads.
	for who, verdict, rating in (("zzDana Khoury", "Cleared", 0.8),
	                             ("zzMaya Seif", "Cleared", 1.0)):
		applicant = frappe.db.get_value("Job Applicant",
		                                {"applicant_name": who}, "name")
		interview = applicant and frappe.db.get_value(
			"Interview", {"job_applicant": applicant}, "name")
		if not interview:
			continue
		_submitted("Interview Feedback", {
			"interview": interview, "interviewer": frappe.session.user,
		}, {
			"job_applicant": applicant, "result": verdict,
			"skill_assessment": [{"skill": "zzSite experience",
			                      "rating": rating}],
			"feedback": "zzFixture",
		})
		made += 1

	template = _one("Appointment Letter Template", "template_name",
	                "zzStandard letter", {
		"introduction": "zzFixture", "closing_notes": "zzFixture",
		"terms": [{"title": "zzNotice period", "description": "zzFixture"}],
	})
	accepted = frappe.db.get_value("Job Applicant",
	                               {"applicant_name": "zzMaya Seif"}, "name")
	if accepted:
		_one("Appointment Letter", "job_applicant", accepted, {
			"applicant_name": "zzMaya Seif", "company": company,
			"appointment_date": _day(30),
			"appointment_letter_template": template,
			"introduction": "zzFixture", "closing_notes": "zzFixture",
			"terms": [{"title": "zzNotice period", "description": "zzFixture"}],
		})
		made += 1

	# ----- Growth ---------------------------------------------------------- #
	# One review per appraisal, which is what an appraisal's score is made of.
	for who, score in APPRAISALS[:2]:
		appraisal = cycle and frappe.db.get_value("Appraisal", {
			"employee": people[who], "appraisal_cycle": cycle,
		}, "name")
		if not appraisal:
			continue
		_submitted("Employee Performance Feedback", {
			"employee": people[who], "appraisal": appraisal,
		}, {
			# Not somebody who is being appraised themselves: HRMS refuses
			# feedback a person gives about their own appraisal and names Self
			# Appraisal instead, and two of the four here review each other.
			"reviewer": people["zzNoor Haddad"], "added_on": _day(-10),
			"feedback": "<p>zzFixture</p>", "total_score": score,
			"company": company,
			"feedback_ratings": [{"criteria": "zzDelivery", "rating": 0.8,
			                      "per_weightage": 100}],
		})
		made += 1

	# How the course everybody has already sat through went, and what two of
	# them thought of it.
	#
	# The participants first, and on the *submitted* event: a Training Result
	# and a Training Feedback are both refused for somebody who is not in the
	# event's own list, and `employees` is `allow_on_submit` precisely because
	# a course is filled after it is scheduled.
	attended = ["zzLeila Amari", "zzOmar Fadel"]
	if event:
		doc = frappe.get_doc("Training Event", event)
		if not doc.employees:
			for who in attended:
				doc.append("employees", {
					"employee": people[who], "status": "Completed",
					"attendance": "Present",
				})
			doc.save(ignore_permissions=True)
	if event:
		_submitted("Training Result", {"training_event": event}, {
			"employees": [
				{"employee": people[who], "hours": 8, "grade": grade,
				 "comments": "zzFixture"}
				for who, grade in zip(attended, ("A", "B"))
			],
		})
		made += 1
		for who in attended:
			_submitted("Training Feedback", {
				"employee": people[who], "training_event": event,
			}, {"feedback": "zzFixture"})
			made += 1

	# ----- Pay ------------------------------------------------------------- #
	# The one-offs a cycle is actually made of.
	for who, component, amount, when in (
		("zzOmar Fadel", "zzBonus", 1500, -5),
		("zzLeila Amari", "zzBonus", 900, -5),
	):
		_named("Salary Component", component, {
			"salary_component": component, "type": "Earning",
			"salary_component_abbr": "ZZB",
		})
		_submitted("Additional Salary", {
			"employee": people[who], "payroll_date": _day(when),
		}, {
			"salary_component": component, "amount": amount,
			"company": company, "currency": "USD",
		})
		made += 1

	# Not one of the three people working their notice: HRMS refuses a payroll
	# date after somebody's relieving date, and the fixture's exits are what
	# that date is there for.
	# Hours worked past the shift, against a rate card the space has had a
	# Configuration tab for since the Time audit and nothing that reads one.
	_named("Salary Component", "zzOvertime", {
		"salary_component": "zzOvertime", "type": "Earning",
		"salary_component_abbr": "ZZO",
	})
	# A fixed hourly rate rather than the component-based default: the other
	# method wants a list of the salary components an hourly rate is derived
	# from, and a fixture asserting that arithmetic would be asserting
	# something about HRMS rather than about this screen.
	_named("Overtime Type", "zzWeekday overtime", {
		"overtime_salary_component": "zzOvertime", "standard_multiplier": 1.5,
		"maximum_overtime_hours_allowed": 4, "applicable_for_weekend": 0,
		"overtime_calculation_method": "Fixed Hourly Rate", "hourly_rate": 30,
	})
	# Auto-attendance on one of the two, so **Mark the attendance** has a shift
	# it can run against. Off on the other, which is the honest pair: HRMS
	# refuses the run on a shift that does not ask for it, and a fixture where
	# every shift is the same tests one of the two answers.
	frappe.db.set_value("Shift Type", "zzSite shift", {
		"enable_auto_attendance": 1,
		"determine_check_in_and_check_out": "Alternating entries as IN and OUT during the same shift",
		"working_hours_calculation_based_on": "First Check-in and Last Check-out",
	}, update_modified=False)

	for who, at, hours in (("zzOmar Fadel", -6, 3), ("zzLeila Amari", -7, 2)):
		# `start_date` and `end_date` given rather than inferred: HRMS derives
		# them from the person's payroll frequency and throws when no salary
		# structure is assigned on the day, which names a structure for a
		# question about hours.
		# Keyed on the person alone, not on the window. HRMS refuses a second
		# slip whose dates overlap an existing one, and the dates here move
		# with today — so a key that included `start_date` found nothing on the
		# second day and then asked for the one thing HRMS will not give.
		_submitted("Overtime Slip", {
			"employee": people[who],
		}, {
			"start_date": _day(at - 6),
			"end_date": _day(at), "posting_date": _day(at),
			"company": company, "total_overtime_duration": hours,
			"overtime_details": [{
				"date": _day(at - 1), "overtime_type": "zzWeekday overtime",
				"overtime_duration": hours, "standard_working_hours": 8,
			}],
		})
		made += 1

	_submitted("Employee Incentive", {
		"employee": people["zzOmar Fadel"], "payroll_date": _day(-5),
	}, {
		"salary_component": "zzBonus", "incentive_amount": 600,
		"company": company, "currency": "USD",
	})
	made += 1

	# Pay held while an exit is settled, which is what this document is for
	# everywhere it is used.
	_submitted("Salary Withholding", {
		"employee": people["zzRania Sabbagh"], "from_date": _day(1),
	}, {
		"company": company, "payroll_frequency": "Monthly",
		"number_of_withholding_cycles": 1, "posting_date": _day(-1),
		"reason_for_withholding_salary": "zzFixture",
	})
	made += 1

	# And what the leaver is owed at the end of it. A draft, and that is the
	# honest state rather than a shortcut: HRMS refuses to submit a statement
	# until every payable and receivable on it is settled, which is the whole
	# job somebody opens this screen to do.
	_one("Full and Final Statement", "employee", people["zzRania Sabbagh"], {
		"company": company, "transaction_date": _day(-1), "status": "Unpaid",
	})
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
			"field_levels": getattr(module, "FIELD_LEVELS", []),
			"screens": [dict(one) for one in module.SCREENS],
		},
		_grants_of(module),
	)


def carriable(already=()) -> list:
	"""Every shipped space this site can actually carry, from the modules.

	**Discovered rather than listed** — `docs/CLEANUP.md` stage 9. It was a
	four-name tuple, and it had to be edited in step with
	`oneapp_control/spaces/`, with the dev fixture's "codes the seeders
	rebuild" list, and with the snapshot generator. Stage 7 added OneBook and
	edited two of the four; the dev site ended up with six copies of it on the
	rail, one per seed run.

	Carriable means every app the space declares is installed. That is the
	space's own sentence about itself — `requires_apps`, which the entitlement
	pipeline already refuses a grant on — so a space over a doctype this bench
	has not got is skipped here for the same reason and by the same rule.

	`already` is the codes a caller has installed itself, which on the dev
	fixture is RUA and OneMobility: each has records nothing generic could
	seed, so each keeps its own function, and passing the set back is what
	stops this installing them a second time.
	"""
	from oneapp_control import spaces

	here = set(frappe.get_installed_apps())
	found = []
	for code, module in spaces.shipped().items():
		if code in already:
			continue
		wanted = {app.strip() for app in
		          (module.SPACE.get("requires_apps") or "").split(",")
		          if app.strip()}
		if wanted <= here:
			found.append(module)
	return found


def seed(records: bool = True, already=()):
	"""The three ERPNext spaces, and what is in them.

	Returns `(spaces, grants)` — or `([], [])` on a site without ERPNext,
	which is the honest answer rather than a failure: OneMobility needs no
	ERPNext and the dev fixture has to keep working on a bare site.

	`records=False` is the manifest half, for the loop that is editing a
	screen declaration and does not care whether there are four projects.

	`already` is the space codes the caller installed itself — see
	`carriable`.
	"""
	if not ready():
		print("erp spaces: skipped, no ERPNext on this site")
		return [], []

	spaces, grants = [], []
	for module in carriable(already):
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
	rest = _more(company, people, cycle)
	# Last, and that order matters: `_paid` settles the sales invoices
	# `_projects` posted, so a books pass before the projects pass would find
	# nothing to pay.
	booked = _books(company)

	print(
		f"erp spaces: {projects} projects and {frappe.db.count('Task')} tasks, "
		f"{deals} deals under {len(LEADS)} leads, "
		f"{len(people)} people with {marked} days marked, "
		f"{slips} payslips and {reviews} appraisals, "
		f"{rest} rows behind the rest of HRMS, "
		f"{booked} documents in the books"
	)
	return spaces, grants
