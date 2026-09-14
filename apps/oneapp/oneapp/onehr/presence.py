"""Where somebody is, right now.

The question every HR product is opened for and none of them answers on the
page you are already on: *is this person in today?* HRMS holds the answer across
four doctypes and shows it in none of them — Employee Checkin is a log, Attendance
is a day's verdict written after the fact by a scheduled job, Leave Application
is an approval, and the Holiday List is a calendar. A person asking "is Omar
here" has to open three of those and do the reasoning themselves.

So this does the reasoning once, in the order the answers actually rank:

    on leave    an approved Leave Application covering today
    holiday     today is in the shift's or the company's Holiday List
    in          the last check-in today was an IN
    out         the last check-in today was an OUT
    absent      Attendance marked them so, and nothing above said otherwise
    unknown     none of the four has anything to say

Ranked rather than merged, and leave first, because the four disagree all the
time and the disagreement is not an error: somebody on approved leave who badged
in to collect a laptop is *on leave*, and a product that says "in" because a
turnstile said so is a product that gets somebody's pay wrong.

`late` is not a state, it is a fact about an `in`. Somebody who arrived at 09:40
against a 09:00 shift is here — they are simply here late, and making that a
separate state means a strip of faces cannot count how many people are in.

**This reads. It never writes.** Auto-attendance is HRMS's job and it runs on a
schedule; a page that marked somebody present because it happened to be open
would be a second writer on the same rows with no lock between them.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, time_diff_in_seconds

#: What a person can be. Ordered by how much they overrule each other, which is
#: the order `of` asks the questions in.
STATES = ("leave", "holiday", "in", "out", "absent", "unknown")

#: How late is late. Frappe's own grace is per Shift Type and is about *marking*
#: attendance; this is about a word on a page, and a minute either side of the
#: hour is not a story anybody wants told about them.
GRACE = 10 * 60

#: The doctypes this needs. A site without HRMS has none of them, and every
#: entry point here answers `unknown` rather than raising: OneHR is one space on
#: a workspace that may carry others, and a record page that 500s because an app
#: is missing is worse than one that says it does not know.
NEEDED = ("Employee Checkin", "Attendance", "Leave Application")


def installed() -> bool:
	return all(frappe.db.exists("DocType", one) for one in NEEDED)


@frappe.whitelist(methods=["GET"])
def of(employee: str) -> dict:
	"""One person's state, now.

	Permission is Frappe's: reading an Employee is what entitles you to know
	whether they are in, and every query below goes through `get_all` as the
	caller. Somebody who cannot see the record gets `unknown` rather than a
	refusal — the page has already refused them the record itself, and this is
	drawn beside a name they can see or not at all.
	"""
	if not employee or not installed():
		return _unknown()

	if not frappe.has_permission("Employee", "read", doc=employee):
		return _unknown()

	today = getdate()

	leave = _on_leave(employee, today)
	if leave:
		return leave

	holiday = _on_holiday(employee, today)
	if holiday:
		return holiday

	checked = _checked_in(employee, today)
	if checked:
		return checked

	marked = _marked(employee, today)
	if marked:
		return marked

	return _unknown()


def _unknown() -> dict:
	return {"state": "unknown", "label": _("Not known"), "detail": "", "since": None,
	        "late": False}


def _on_leave(employee: str, today) -> dict | None:
	"""An approved application covering today, by leave type.

	Submitted *and* Approved: HRMS keeps `status` on a submitted document, and a
	rejected one is still `docstatus == 1`. Reading only the docstatus marks
	somebody on leave for a request their manager turned down.
	"""
	found = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"status": "Approved",
			"docstatus": 1,
			"from_date": ["<=", today],
			"to_date": [">=", today],
		},
		fields=["leave_type", "to_date", "half_day", "half_day_date"],
		limit=1,
	)
	if not found:
		return None

	one = found[0]
	half = one.get("half_day") and getdate(one.get("half_day_date")) == today
	return {
		"state": "leave",
		"label": _("Half day") if half else _("On leave"),
		# The leave type, because "on leave" and "on leave until Friday, and it
		# is sick leave" are different amounts of information for the same
		# space on the page.
		"detail": one.get("leave_type") or "",
		"since": None,
		"until": str(one.get("to_date") or ""),
		"late": False,
	}


def _on_holiday(employee: str, today) -> dict | None:
	"""Today in the list this person's own shift or company keeps.

	Their own first: a company that runs two shifts across two countries has two
	holiday lists, and answering from the company's is answering for the wrong
	half of the workforce.
	"""
	found = frappe.db.get_value("Employee", employee, ["holiday_list", "company"],
	                            as_dict=True) or {}
	holidays = found.get("holiday_list")
	if not holidays:
		holidays = frappe.db.get_value("Company", found.get("company"),
		                               "default_holiday_list")
	if not holidays:
		return None

	on = frappe.db.get_value("Holiday", {"parent": holidays, "holiday_date": today},
	                         "description")
	if on is None:
		return None
	return {"state": "holiday", "label": _("Holiday"), "detail": on or "",
	        "since": None, "late": False}


def _checked_in(employee: str, today) -> dict | None:
	"""The last log today, and which way it pointed.

	`time` descending rather than `creation`: a device that uploads a batch at
	noon writes the morning's IN after the morning's OUT, and reading the newest
	*row* would have somebody leaving before they arrived.
	"""
	found = frappe.get_all(
		"Employee Checkin",
		filters={"employee": employee, "time": ["between", [f"{today} 00:00:00",
		                                                    f"{today} 23:59:59"]]},
		fields=["log_type", "time", "shift", "shift_start"],
		order_by="time desc",
		limit=1,
	)
	if not found:
		return None

	one = found[0]
	at = get_datetime(one["time"])
	if (one.get("log_type") or "IN") == "OUT":
		return {"state": "out", "label": _("Checked out"), "detail": "",
		        "since": str(at), "late": False}

	return {
		"state": "in",
		"label": _("In"),
		"detail": one.get("shift") or "",
		"since": str(at),
		"late": _late(at, one.get("shift_start")),
	}


def _late(at, shift_start) -> bool:
	"""Whether an arrival was after the shift began, by more than the grace.

	`shift_start` is stamped on the check-in by HRMS itself where auto-attendance
	is on, which is the only place the *date* of a shift start exists — Shift
	Type carries a time of day and nothing to anchor it to.
	"""
	if not shift_start:
		return False
	try:
		return time_diff_in_seconds(at, get_datetime(shift_start)) > GRACE
	except Exception:
		return False


def _marked(employee: str, today) -> dict | None:
	"""What the attendance job decided, where nothing above had an answer.

	Last, because it is a verdict written after the day rather than a fact about
	now — and `Present` here with no check-in is somebody whose attendance was
	entered by hand, which is worth saying as "marked present" rather than as
	"in".
	"""
	status = frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": today, "docstatus": 1},
		"status",
	)
	if not status:
		return None
	if status == "Absent":
		return {"state": "absent", "label": _("Absent"), "detail": "",
		        "since": None, "late": False}
	if status == "On Leave":
		return {"state": "leave", "label": _("On leave"), "detail": "",
		        "since": None, "late": False}
	return {
		"state": "in",
		"label": _("Marked present") if status == "Present" else _(status),
		"detail": "",
		"since": None,
		"late": False,
	}
