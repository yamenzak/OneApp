"""One person's own numbers: their recent days, and what leave they have left.

The other half of the question `presence.py` answers. "Is Omar in today" is a
state; "how has Omar been" is a shape, and the shape is the thing a manager
opening somebody's record is usually actually after — a run of red in the third
week of a month says more than any single day's verdict does.

**Why this is on the record and not on a dashboard.** A screen's dashboard view
measures the *population*: headcount by department, how many are on leave this
week, the attendance rate. Those are questions about a workforce and they are
already answered, over the rows that screen narrows to, by the widgets the
manifest declares. Nothing there can answer a question about one person, because
a dashboard over one row is a number with no comparison in it. So the line is:

    a screen's dashboard   how is the workforce
    a person's record      how is this person

and a widget that would say "eight people are on leave" belongs on the first
while one that says "Omar has twelve days left" belongs on the second. Both, and
never the same one twice.

`WEEKS` of days rather than a year: a strip somebody reads at a glance is about
two months, and the full year is what the Attendance screen's own calendar is
for. This is the summary that makes opening that screen a decision rather than a
habit.
"""

import frappe
from frappe.utils import add_days, getdate

from . import own

#: How far back the strip runs. Eight weeks is two months of context in a row
#: narrow enough to sit above a tab strip without becoming the page.
WEEKS = 8
DAYS = WEEKS * 7

#: What a day can have been. `none` is a day with no record at all — before
#: somebody joined, or a day the attendance job has not reached yet — and it is
#: drawn as a gap rather than as an absence, because those are not the same
#: thing and colouring them alike is how a strip lies.
DAY_STATES = ("present", "half", "leave", "holiday", "absent", "none")

#: Attendance's own vocabulary, mapped onto ours. Anything HRMS adds later that
#: is not in here reads as `present`, which is the safe direction: a status
#: nobody here has heard of is far more likely to be a kind of attending than a
#: kind of absence.
FROM_STATUS = {
	"Present": "present",
	"Work From Home": "present",
	"Half Day": "half",
	"On Leave": "leave",
	"Absent": "absent",
}


def installed() -> bool:
	return bool(frappe.db.exists("DocType", "Attendance"))


@frappe.whitelist(methods=["GET"])
def of(employee: str) -> dict:
	"""The last `WEEKS` of days, and the leave this person has left.

	One call rather than two: both halves are drawn in the same band and a page
	that fetched them separately would draw half a band, twice.
	"""
	if not employee or not installed():
		return {"days": [], "balance": [], "weeks": WEEKS}

	if not frappe.has_permission("Employee", "read", doc=employee):
		return {"days": [], "balance": [], "weeks": WEEKS}

	# Reading the record is not reading the numbers. Being able to open a
	# colleague is what the Employee seat is *for* — a directory nobody can open
	# is not a directory — and it is not the same question as how much leave
	# they have left or how many days they missed last month. `own.may_read`
	# draws that line in one place: your own, always; anybody else's, only with
	# the grant the people officer holds and the Employee seat does not.
	#
	# Each half separately, because the two doctypes are granted separately and
	# a strip with no balance beside it is still worth drawing.
	today = getdate()
	first = add_days(today, -(DAYS - 1))

	return {
		"days": _days(employee, first, today)
		if own.may_read("Attendance", employee) else [],
		"balance": _balance(employee, today)
		if own.may_read("Leave Allocation", employee) else [],
		"weeks": WEEKS,
	}


def _days(employee: str, first, today) -> list[dict]:
	"""Every day in the window, in order, whether or not it has a record.

	Built from the calendar rather than from the rows: a list of only the days
	Attendance knows about is a strip with holes in it that line up with
	nothing, and the whole point of a strip is that the seventh cell is always
	the same weekday.
	"""
	marked = {
		getdate(row["attendance_date"]): row["status"]
		for row in frappe.get_all(
			"Attendance",
			filters={
				"employee": employee,
				"docstatus": 1,
				"attendance_date": ["between", [first, today]],
			},
			fields=["attendance_date", "status"],
			limit_page_length=0,
		)
	}
	holidays = _holidays(employee, first, today)

	days = []
	day = getdate(first)
	while day <= today:
		status = marked.get(day)
		if status:
			state = FROM_STATUS.get(status, "present")
		elif day in holidays:
			state = "holiday"
		else:
			state = "none"
		days.append({"date": str(day), "state": state})
		day = add_days(day, 1)
	return days


def _holidays(employee: str, first, today) -> set:
	"""Their own list, then their company's. Same rule as `presence._on_holiday`."""
	found = frappe.db.get_value("Employee", employee, ["holiday_list", "company"],
	                            as_dict=True) or {}
	holidays = found.get("holiday_list")
	if not holidays:
		holidays = frappe.db.get_value("Company", found.get("company"),
		                               "default_holiday_list")
	if not holidays:
		return set()
	return {
		getdate(row["holiday_date"])
		for row in frappe.get_all(
			"Holiday",
			filters={"parent": holidays, "holiday_date": ["between", [first, today]]},
			fields=["holiday_date"],
			limit_page_length=0,
		)
	}


def _balance(employee: str, today) -> list[dict]:
	"""Allocated, taken and left, per leave type, for the period covering today.

	Off Leave Allocation rather than off HRMS's own balance function: that one
	is a report the desk calls per type per employee, and it opens a transaction
	per call. This is the same arithmetic over rows we already have — allocated
	minus what approved applications used — and it is a summary rather than the
	number a payroll run should trust.
	"""
	allocated = frappe.get_all(
		"Leave Allocation",
		filters={
			"employee": employee,
			"docstatus": 1,
			"from_date": ["<=", today],
			"to_date": [">=", today],
		},
		fields=["leave_type", "total_leaves_allocated"],
		limit_page_length=0,
	)
	if not allocated:
		return []

	taken = {}
	for row in frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"status": "Approved",
			"docstatus": 1,
			"from_date": ["<=", today],
		},
		fields=["leave_type", "total_leave_days"],
		limit_page_length=0,
	):
		taken[row["leave_type"]] = taken.get(row["leave_type"], 0) + (
			row["total_leave_days"] or 0
		)

	balance = []
	for row in allocated:
		kind = row["leave_type"]
		total = row["total_leaves_allocated"] or 0
		used = taken.get(kind, 0)
		balance.append({
			"leave_type": kind,
			"allocated": total,
			"taken": used,
			# Never below zero on the page. A negative balance is real and is
			# payroll's business; here it is a bar, and a bar of minus two days
			# is a drawing problem rather than information.
			"left": max(total - used, 0),
		})
	return balance
