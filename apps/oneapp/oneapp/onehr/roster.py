"""Taking attendance for a whole day, in one pass.

The screen behind "Mark the day", and the one thing in OnePeople that is a *form
over a list of people* rather than a list of records.

Marking attendance one record at a time is the desk's answer and it is the
wrong shape for the job. A person taking a register has one question — who was
not here — and the product made them answer the other forty-nine: open New,
pick an employee, pick a date, pick Present, save, again. So this draws the
roll with everybody on it and **Present already chosen**, and the work is
turning off the handful who were not. That is what "all present except" means
and it is the whole design.

Three of the five statuses are not a choice at all, and saying so is most of
what makes the page trustworthy:

* **On leave.** An approved Leave Application covering the day *is* the answer;
  HRMS's own `Attendance.check_leave_record` overwrites whatever you picked
  with it. The row says so and cannot be changed, and the way to change it is
  the application.
* **A holiday.** Nobody is marked on their own holiday list's day off. HRMS's
  auto-attendance skips them and so does this; the row says which holiday.
* **Already marked.** Attendance is submitted the moment it is made and
  `status` is not `allow_on_submit`, so a day that has been marked cannot be
  re-marked — only cancelled and amended, on the record. The row shows the
  verdict it already has and a way to open it.

What is left is the people the register is actually about, and they arrive
carrying whatever the clock knows: somebody with a punch after their shift
began is offered Present *and late*, which is the one thing a register taken
from memory always gets wrong.

Permissions are Frappe's throughout. The roll is `get_list` on Employee, so a
manager restricted to one company sees their own people and nobody else's; the
writes go through HRMS's own `mark_attendance`, which inserts and submits as
the caller. There is no `ignore_permissions` here.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, time_diff_in_seconds

from oneapp.onehr.presence import GRACE, installed

#: The doctype this page is really about. Named here because three things read
#: it: the permission check, the screen's own declaration in the manifest — a
#: component screen names a doctype to say who it is *for* — and the tests.
ABOUT = "Attendance"

#: How many people one day's roll draws. A register is a room; past this it is
#: a payroll run, and marking a thousand people by hand is not the shape of
#: this page whatever the number says.
MOST = 200

#: The five HRMS allows, in the order somebody reads them: the two that mean
#: "here" first, then the two that are asked for, then the one that is not.
STATUSES = ("Present", "Work From Home", "Half Day", "On Leave", "Absent")

#: What the page starts every markable row on. The argument for the whole
#: feature in one constant.
DEFAULT = "Present"

#: Why a row cannot be marked, in the order the reasons are checked. Order
#: matters: somebody on leave on a holiday is on leave, and somebody already
#: marked is already marked whatever else was true.
MARKED, LEAVE, HOLIDAY = "marked", "leave", "holiday"


def _allowed() -> None:
	"""Marking a register is writing attendance, and nothing less."""
	if not installed():
		frappe.throw(_("This workspace does not keep attendance."))
	if not frappe.has_permission(ABOUT, "create"):
		frappe.throw(
			_("Marking the day is for whoever keeps attendance."),
			frappe.PermissionError,
		)


@frappe.whitelist(methods=["GET"])
def day(on: str = "") -> dict:
	"""The roll for one day: everybody, and what is already known about them."""
	_allowed()
	when = getdate(on) if on else getdate()

	people = frappe.get_list(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name", "image", "department", "designation",
		        "holiday_list", "company"],
		order_by="employee_name asc",
		limit_page_length=MOST,
	)
	if not people:
		return {"on": str(when), "statuses": list(STATUSES), "default": DEFAULT,
		        "people": []}

	ids = [one["name"] for one in people]
	marked = _marked(ids, when)
	leave = _leave(ids, when)
	holidays = _holidays(people, when)
	punches = _punches(ids, when)

	rows = []
	for one in people:
		who = one["name"]
		row = {
			"employee": who,
			"label": one.get("employee_name") or who,
			"image": one.get("image") or "",
			"detail": one.get("designation") or "",
			"department": one.get("department") or "",
			"status": DEFAULT,
			"late": False,
			"fixed": "",
			"because": "",
			"attendance": "",
		}

		found = marked.get(who)
		if found:
			row.update(status=found["status"], late=bool(found.get("late_entry")),
			           fixed=MARKED, attendance=found["name"],
			           because=_("Already marked"))
		elif who in leave:
			row.update(status=leave[who]["status"], fixed=LEAVE,
			           because=leave[who]["because"])
		elif who in holidays:
			row.update(status="", fixed=HOLIDAY, because=holidays[who])
		elif who in punches:
			row.update(late=punches[who])

		rows.append(row)

	return {
		"on": str(when),
		"statuses": list(STATUSES),
		"default": DEFAULT,
		"people": rows,
	}


@frappe.whitelist(methods=["POST"])
def mark(on: str, marks) -> dict:
	"""Write the day, and say what happened to each row.

	Through HRMS's `mark_attendance`, which is the solved problem: it inserts,
	submits, applies the leave override and rolls back its own savepoint on a
	duplicate rather than taking the rest of the register down with it. A row
	it declines comes back as skipped, which is the honest answer — somebody
	marked that day while this page was open.
	"""
	_allowed()
	from hrms.hr.doctype.attendance.attendance import mark_attendance

	when = getdate(on) if on else getdate()
	asked = frappe.parse_json(marks) if isinstance(marks, str) else (marks or [])
	if not isinstance(asked, list):
		frappe.throw(_("Nothing to mark."))

	written, skipped = 0, 0
	for row in asked[:MOST]:
		if not isinstance(row, dict):
			continue
		employee = str(row.get("employee") or "").strip()
		status = str(row.get("status") or "").strip()
		if not employee or status not in STATUSES:
			continue

		made = mark_attendance(
			employee=employee,
			attendance_date=when,
			status=status,
			late_entry=bool(row.get("late")) and status in ("Present", "Work From Home"),
		)
		if made:
			written += 1
		else:
			skipped += 1

	return {"on": str(when), "written": written, "skipped": skipped}


# --------------------------------------------------------------------------- #
# What is already known
#
# One query per concern for the whole roll rather than four per person:
# `presence.of` answers this for one employee beside their name, and forty of
# those is a hundred and sixty queries to draw a register.
# --------------------------------------------------------------------------- #

def _marked(ids: list[str], when) -> dict:
	"""The day's attendance rows, by employee. Drafts included: a draft is
	still a row somebody made, and marking over it is the duplicate HRMS
	refuses."""
	found = frappe.get_list(
		ABOUT,
		filters={"attendance_date": when, "docstatus": ["<", 2],
		         "employee": ["in", ids]},
		fields=["name", "employee", "status", "late_entry"],
		limit_page_length=MOST,
	)
	return {one["employee"]: one for one in found}


def _leave(ids: list[str], when) -> dict:
	"""Approved leave covering the day, by employee.

	Submitted *and* Approved, the same pair `presence._on_leave` insists on:
	HRMS keeps `status` on a submitted document, so a rejected application is
	still `docstatus == 1` and reading only the docstatus puts somebody on
	leave their manager turned down.
	"""
	found = frappe.get_list(
		"Leave Application",
		filters={"employee": ["in", ids], "status": "Approved", "docstatus": 1,
		         "from_date": ["<=", when], "to_date": [">=", when]},
		fields=["employee", "leave_type", "half_day", "half_day_date"],
		limit_page_length=MOST,
	)
	out = {}
	for one in found:
		half = one.get("half_day") and getdate(one.get("half_day_date")) == when
		out[one["employee"]] = {
			"status": "Half Day" if half else "On Leave",
			"because": _("Half day — {0}").format(one.get("leave_type") or "")
			if half else _("On {0}").format(one.get("leave_type") or _("leave")),
		}
	return out


def _holidays(people: list[dict], when) -> dict:
	"""Whose own list says the day is off, and what it is called.

	Keyed by list rather than by person: eight people on one list is one query,
	and a company running two shifts across two countries has two lists rather
	than eight.
	"""
	lists = {}
	for one in people:
		holidays = one.get("holiday_list")
		if not holidays:
			holidays = frappe.db.get_value("Company", one.get("company"),
			                               "default_holiday_list")
		if holidays:
			lists.setdefault(holidays, []).append(one["name"])

	out = {}
	for holidays, whom in lists.items():
		on = frappe.db.get_value("Holiday",
		                         {"parent": holidays, "holiday_date": when},
		                         "description")
		if on is None:
			continue
		for who in whom:
			out[who] = on or _("Holiday")
	return out


def _punches(ids: list[str], when) -> dict:
	"""Who clocked in, and whether it was late — by employee.

	`shift_start` is stamped on the check-in by HRMS where auto-attendance is
	on, and it is the only place the *date* of a shift's start exists: a Shift
	Type carries a time of day and nothing to anchor it to. Without one there
	is a punch and no opinion about it, which is the truthful answer.
	"""
	found = frappe.get_list(
		"Employee Checkin",
		filters={"employee": ["in", ids], "log_type": "IN",
		         "time": ["between", [f"{when} 00:00:00", f"{when} 23:59:59"]]},
		fields=["employee", "time", "shift_start"],
		order_by="time asc",
		limit_page_length=MOST * 4,
	)
	out = {}
	for one in found:
		# The *first* punch of the day decides, so a later one does not undo a
		# late morning: the rows arrive earliest first and the first wins.
		if one["employee"] in out:
			continue
		out[one["employee"]] = _late(one["time"], one.get("shift_start"))
	return out


def _late(at, shift_start) -> bool:
	if not shift_start:
		return False
	try:
		return time_diff_in_seconds(get_datetime(at), get_datetime(shift_start)) > GRACE
	except Exception:
		return False
