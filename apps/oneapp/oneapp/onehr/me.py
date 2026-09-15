"""The reader's own page: who they are here, and their whole relationship with HR.

Everything else in OnePeople is written for the person who *administers* people. The
directory, the attendance screen, the leave board, the payroll run — all of them
are an officer's view of a workforce, and the person each of those rows is about
has, until this module, had nowhere to stand. `docs/HORILLA.md` §3.1 is the same
finding read off a competitor: half the entries in an HR rail have two readers,
and only one of them was ever served.

The shape is Horilla's and it is right — **one page, no navigation**. Somebody
asking how much leave they have left should not have to know the answer lives in
a doctype called Leave Allocation, and somebody filing a day off should not have
to find a screen called Leave first. So this is one call returning every block
the page draws: eight calls is eight spinners and a page that assembles itself
in front of the reader.

**Who "me" is, and what it may read**, are both `own.py` — the second is the
rule that makes a self-service page possible without widening a single grant.
Every query below filters on the employee *that* returned, never on one a caller
sent, which is why `home` takes no arguments at all: there is no employee to
pass, so there is no employee to pass somebody else's.

**Pay is here and is not a grant.** A payslip is about somebody and is not owned
by them, so it is the same shape as attendance — `own.may_read` lets a person
see their own without the Salary Slip grant, and anybody else's needs the payroll
seat, which is exactly the line OnePeople already draws. Nothing about the seat
changes; the employee simply stops being the one person in the company who cannot
see their own pay.

**This reads. `checkin.py` is the only thing in OnePeople that writes.**
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate

from . import history, own, presence

#: How many of a list this page shows before it is a screen's job. A block is a
#: reminder that something exists, not a place to work through it.
KEPT = 5

#: How far ahead "what is coming up" looks. A fortnight: far enough to cover the
#: weekend after next, near enough that everything in it is still true.
AHEAD = 14


@frappe.whitelist(methods=["GET"])
def home() -> dict:
	"""Everything the employee's own page draws, in one call.

	`reason` rather than an error on the two ways there is no page to draw. A
	workspace without HRMS and a reader whose login was never linked to a record
	are both ordinary states of a real site, and each has a different sentence
	to say — neither is a failure the browser should render as one.
	"""
	if not own.installed():
		return {"employee": None, "reason": "no-hrms"}

	mine = who()
	if not mine:
		return {"employee": None, "reason": "not-linked"}

	name = mine["name"]
	return {
		"employee": mine,
		"presence": presence.of(name),
		"history": history.of(name),
		"requests": requests(name),
		"payslips": payslips(name),
		"goals": goals(name),
		"team": team(mine),
		"upcoming": upcoming(mine),
		# Whether to draw the control at all. `checkin.file` refuses regardless,
		# and this is so a workspace whose seats may not check in is not shown a
		# button whose only job is to say so.
		"can_check_in": bool(
			frappe.db.exists("DocType", "Employee Checkin")
			and frappe.has_permission("Employee Checkin", "create")
		),
	}


@frappe.whitelist(methods=["GET"])
def who() -> dict | None:
	"""The Employee this session's user is, with the fields a hero draws.

	Whitelisted on its own as well as through `home`, because the shell asks the
	cheap question — *is this reader an employee at all* — before it decides
	whether to offer them a page about it.
	"""
	name = own.employee_of()
	if not name:
		return None

	found = frappe.get_all(
		"Employee",
		filters={"name": name},
		fields=["name", "employee_name", "designation", "department", "branch",
		        "company", "image", "reports_to", "date_of_joining", "status",
		        "employment_type", "grade", "holiday_list"],
		limit=1,
	)
	if not found:
		return None

	mine = found[0]
	mine["reports_to_name"] = frappe.db.get_value(
		"Employee", mine["reports_to"], "employee_name") if mine["reports_to"] else ""
	# ERPNext names a Department `<name> - <company abbreviation>`, so the link
	# value is "Delivery - ZZN" and a page that prints it tells somebody their
	# own company's initials back. The label is a field on the row.
	mine["department_name"] = frappe.db.get_value(
		"Department", mine["department"], "department_name") if mine["department"] else ""
	return mine


def requests(employee: str) -> list[dict]:
	"""What this person has asked for lately, across the four doors they file at.

	One list rather than four blocks, sorted by when it was asked rather than by
	kind: somebody opening this page wants to know whether *anything* is still
	waiting, and four lists of two make that a counting exercise.

	These four are the `if_owner` half — a person files their own — so the grant
	is already the right shape and `may_read` answers yes for the same reason it
	would for a people officer reading their own page.
	"""
	# doctype, the field that says what it is *about*, the field that says where
	# it stands. An Expense Claim has no subject of its own — the what is in a
	# child table — so it falls back to the word for the thing, which is what
	# the reader would have called it anyway.
	kinds = (
		("Leave Application", "leave_type", "status", _("Leave")),
		("Expense Claim", "", "approval_status", _("Expense claim")),
		("Attendance Request", "reason", "", _("Attendance")),
		("Shift Request", "shift_type", "status", _("Shift")),
	)

	found = []
	for doctype, subject, state, label in kinds:
		if not own.may_read(doctype, employee):
			continue
		fields = ["name", "modified", "docstatus"]
		if subject:
			fields.append(f"{subject} as subject")
		if state:
			fields.append(f"{state} as state")
		for row in frappe.get_all(
			doctype,
			filters={"employee": employee},
			fields=fields,
			order_by="modified desc",
			limit=KEPT,
		):
			found.append({
				"doctype": doctype,
				"name": row["name"],
				"subject": row.get("subject") or label,
				"state": row.get("state") or _docstate(row.get("docstatus")),
				"at": str(row["modified"]),
			})

	found.sort(key=lambda one: one["at"], reverse=True)
	return found[:KEPT]


def _docstate(docstatus) -> str:
	"""A submittable with no status field of its own, in words.

	Attendance Request has none: it is a document that is either still being
	written, filed, or withdrawn, and "1" is not a thing to draw on a page.
	"""
	return {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(int(docstatus or 0), "")


def payslips(employee: str) -> list[dict]:
	"""This person's own last few, submitted ones only.

	Draft slips are payroll's working state — a run being checked before it is
	released — and showing somebody a number that is about to change is worse
	than showing them nothing. `docstatus == 1` is the line between the two.
	"""
	if not own.may_read("Salary Slip", employee):
		return []

	return [
		{
			"name": row["name"],
			"from": str(row.get("start_date") or ""),
			"until": str(row.get("end_date") or ""),
			"net": row.get("net_pay") or 0,
			"currency": row.get("currency") or "",
		}
		for row in frappe.get_all(
			"Salary Slip",
			filters={"employee": employee, "docstatus": 1},
			fields=["name", "start_date", "end_date", "net_pay", "currency"],
			order_by="start_date desc",
			limit=KEPT,
		)
	]


def goals(employee: str) -> list[dict]:
	"""What this person is working towards, unfinished first.

	`Goal` is granted `if_owner` to the Employee seat, which for once is the
	right idiom on its own: a goal is filed by the person whose goal it is, or by
	their manager on their behalf, and either way the subject is the employee
	this filters on.
	"""
	if not own.may_read("Goal", employee):
		return []

	return [
		{
			"name": row["name"],
			"subject": row.get("goal_name") or row["name"],
			"state": row.get("status") or "",
			"progress": row.get("progress") or 0,
			"until": str(row.get("end_date") or ""),
		}
		for row in frappe.get_all(
			"Goal",
			filters={"employee": employee},
			fields=["name", "goal_name", "status", "progress", "end_date"],
			order_by="status asc, end_date asc",
			limit=KEPT,
		)
	]


def team(mine: dict) -> list[dict]:
	"""Who this person works with, and where each of them is now.

	Their manager, the people who answer to the same manager, and the people who
	answer to them — one list, because a page about somebody's own day does not
	need three headings to say "these are the people you will speak to today".

	The presence beside each face is the same reasoning the person record draws,
	and it is what this block is actually for: who is in is the one thing people
	open an HR product for every morning. Nothing here is narrowed by `own`,
	deliberately — the Employee seat reads the directory by design, and where
	a colleague is standing is not the same question as what they are owed.
	"""
	name = mine["name"]
	manager = mine.get("reports_to")
	faces: dict[str, dict] = {}

	def add(row, how):
		if row["name"] == name or row["name"] in faces:
			return
		faces[row["name"]] = {
			"name": row["name"],
			"employee_name": row.get("employee_name") or row["name"],
			"designation": row.get("designation") or "",
			"image": row.get("image") or "",
			"how": how,
			"presence": presence.of(row["name"]),
		}

	fields = ["name", "employee_name", "designation", "image"]
	if manager:
		for row in frappe.get_all("Employee", filters={"name": manager},
		                          fields=fields, limit=1):
			add(row, "manager")
		for row in frappe.get_all(
			"Employee",
			filters={"reports_to": manager, "status": "Active"},
			fields=fields, order_by="employee_name asc", limit=KEPT + 1,
		):
			add(row, "peer")

	for row in frappe.get_all(
		"Employee",
		filters={"reports_to": name, "status": "Active"},
		fields=fields, order_by="employee_name asc", limit=KEPT + 1,
	):
		add(row, "report")

	return list(faces.values())[: KEPT + 1]


def upcoming(mine: dict) -> list[dict]:
	"""The next fortnight: this person's approved leave, and everybody's days off.

	Both in one list and sorted by date, because they answer the same question —
	*when am I next not working* — and separating them makes the reader merge two
	calendars in their head.
	"""
	today = getdate()
	last = add_days(today, AHEAD)
	found = []

	if own.may_read("Leave Application", mine["name"]):
		for row in frappe.get_all(
			"Leave Application",
			filters={
				"employee": mine["name"],
				"status": "Approved",
				"docstatus": 1,
				"to_date": [">=", today],
				"from_date": ["<=", last],
			},
			fields=["name", "leave_type", "from_date", "to_date"],
			order_by="from_date asc",
			limit=KEPT,
		):
			found.append({
				"kind": "leave",
				"label": row.get("leave_type") or "",
				"date": str(row["from_date"]),
				"until": str(row["to_date"]),
			})

	for row in _holidays(mine, today, last):
		found.append({"kind": "holiday", "label": row["description"] or "",
		              "date": str(row["holiday_date"]), "until": ""})

	found.sort(key=lambda one: one["date"])
	return found[:KEPT]


def _holidays(mine: dict, first, last) -> list[dict]:
	"""Their own list, then their company's. The same rule `presence` follows."""
	holidays = mine.get("holiday_list")
	if not holidays:
		holidays = frappe.db.get_value("Company", mine.get("company"),
		                               "default_holiday_list")
	if not holidays or not frappe.db.exists("DocType", "Holiday List"):
		return []

	# Not the weekly off. A Saturday is not news a fortnight in advance, and a
	# block whose every line says "Friday" is a block people stop reading — the
	# weekend is already drawn, grey, in the strip above this.
	return frappe.get_all(
		"Holiday",
		filters={"parent": holidays, "weekly_off": 0,
		         "holiday_date": ["between", [first, last]]},
		fields=["holiday_date", "description"],
		order_by="holiday_date asc",
		limit=KEPT,
	)
