"""Taking the register for a whole day.

`oneapp/onehr/roster.py` — and what is worth pinning is not the drawing but the
three kinds of row that are *not a choice*. A register that offered to mark
somebody who is on approved leave would be offering something HRMS overwrites
on the way in, and one that quietly left them off would be a register nobody
can check against the room.
"""

import types

import pytest


@pytest.fixture
def onehr(stub_frappe):
	from oneapp.onehr import roster

	stub_frappe.db.exists = lambda *a, **kw: True
	stub_frappe.has_permission = lambda *a, **kw: True
	stub_frappe.db.get_value = lambda *a, **kw: None
	return types.SimpleNamespace(roster=roster, frappe=stub_frappe)


PEOPLE = [
	{"name": "HR-EMP-1", "employee_name": "Ada", "image": "", "department": "D",
	 "designation": "Engineer", "holiday_list": "Weekends", "company": "Acme"},
	{"name": "HR-EMP-2", "employee_name": "Bo", "image": "", "department": "D",
	 "designation": "Designer", "holiday_list": "Weekends", "company": "Acme"},
]


def _lists(frappe, **rows):
	"""Stub `get_list` per doctype, so a test says only what it is about."""
	def get_list(doctype, **kw):
		return rows.get(doctype, [])

	frappe.get_list = get_list


def test_everybody_starts_present_because_that_is_the_whole_feature(onehr):
	"""The default *is* the design. A register that opened on nothing chosen
	would be the same forty answers the record-at-a-time path already asked
	for."""
	_lists(onehr.frappe, Employee=PEOPLE)
	found = onehr.roster.day("2026-09-15")
	assert [one["status"] for one in found["people"]] == ["Present", "Present"]
	assert all(not one["fixed"] for one in found["people"])


def test_approved_leave_is_not_a_choice(onehr):
	"""HRMS's `Attendance.check_leave_record` overwrites whatever was picked
	with the leave, so offering the five statuses here would be offering four
	that cannot happen."""
	_lists(onehr.frappe, Employee=PEOPLE, **{
		"Leave Application": [{"employee": "HR-EMP-2", "leave_type": "Annual",
		                       "half_day": 0, "half_day_date": None}],
	})
	bo = onehr.roster.day("2026-09-15")["people"][1]
	assert bo["fixed"] == "leave"
	assert bo["status"] == "On Leave"
	assert "Annual" in bo["because"]


def test_half_a_day_of_leave_is_half_a_day(onehr):
	_lists(onehr.frappe, Employee=PEOPLE, **{
		"Leave Application": [{"employee": "HR-EMP-1", "leave_type": "Annual",
		                       "half_day": 1, "half_day_date": "2026-09-15"}],
	})
	ada = onehr.roster.day("2026-09-15")["people"][0]
	assert ada["status"] == "Half Day"


def test_a_day_already_marked_shows_its_verdict_and_a_way_to_it(onehr):
	"""Attendance is submitted the moment it is made and `status` is not
	`allow_on_submit`, so a marked day cannot be re-marked — only cancelled and
	amended, on the record. The row carries the id that gets you there."""
	_lists(onehr.frappe, Employee=PEOPLE, Attendance=[
		{"name": "HR-ATT-9", "employee": "HR-EMP-1", "status": "Absent",
		 "late_entry": 0},
	])
	ada = onehr.roster.day("2026-09-15")["people"][0]
	assert ada["fixed"] == "marked"
	assert ada["status"] == "Absent"
	assert ada["attendance"] == "HR-ATT-9"


def test_a_holiday_is_nobodys_working_day(onehr):
	onehr.frappe.db.get_value = lambda *a, **kw: "New Year"
	_lists(onehr.frappe, Employee=PEOPLE)
	found = onehr.roster.day("2026-01-01")["people"]
	assert [one["fixed"] for one in found] == ["holiday", "holiday"]
	# And no status at all, rather than Present greyed out: there is no verdict
	# to be had about a day nobody was meant to work.
	assert [one["status"] for one in found] == ["", ""]


def test_already_marked_outranks_leave(onehr):
	"""Somebody marked before their leave was approved is *marked*, and the
	page must say so — offering to mark them again is offering the duplicate
	HRMS refuses."""
	_lists(onehr.frappe, Employee=PEOPLE, **{
		"Attendance": [{"name": "HR-ATT-9", "employee": "HR-EMP-1",
		                "status": "Present", "late_entry": 0}],
		"Leave Application": [{"employee": "HR-EMP-1", "leave_type": "Annual",
		                       "half_day": 0, "half_day_date": None}],
	})
	assert onehr.roster.day("2026-09-15")["people"][0]["fixed"] == "marked"


def test_a_punch_after_the_shift_began_is_offered_as_late(onehr):
	"""The one thing a register taken from memory always gets wrong. `shift_start`
	is stamped on the check-in by HRMS and is the only place the *date* of a
	shift's start exists."""
	_lists(onehr.frappe, Employee=PEOPLE, **{
		"Employee Checkin": [
			{"employee": "HR-EMP-1", "time": "2026-09-15 09:41:00",
			 "shift_start": "2026-09-15 09:00:00"},
			{"employee": "HR-EMP-2", "time": "2026-09-15 08:55:00",
			 "shift_start": "2026-09-15 09:00:00"},
		],
	})
	found = onehr.roster.day("2026-09-15")["people"]
	assert [one["late"] for one in found] == [True, False]


def test_the_first_punch_of_the_day_decides(onehr):
	"""A late morning is not undone by coming back from lunch."""
	_lists(onehr.frappe, Employee=PEOPLE, **{
		"Employee Checkin": [
			{"employee": "HR-EMP-1", "time": "2026-09-15 09:41:00",
			 "shift_start": "2026-09-15 09:00:00"},
			{"employee": "HR-EMP-1", "time": "2026-09-15 13:02:00",
			 "shift_start": "2026-09-15 09:00:00"},
		],
	})
	assert onehr.roster.day("2026-09-15")["people"][0]["late"] is True


def test_a_punch_with_no_shift_behind_it_has_no_opinion(onehr):
	"""A Shift Type carries a time of day and nothing to anchor it to, so
	without `shift_start` there is a punch and no verdict about it."""
	_lists(onehr.frappe, Employee=PEOPLE, **{
		"Employee Checkin": [{"employee": "HR-EMP-1", "time": "2026-09-15 11:30:00",
		                      "shift_start": None}],
	})
	assert onehr.roster.day("2026-09-15")["people"][0]["late"] is False


def test_marking_is_refused_without_the_permission_to_write_attendance(onehr):
	import frappe

	onehr.frappe.has_permission = lambda *a, **kw: False
	with pytest.raises(frappe.PermissionError):
		onehr.roster.day("2026-09-15")
	with pytest.raises(frappe.PermissionError):
		onehr.roster.mark("2026-09-15", [])
