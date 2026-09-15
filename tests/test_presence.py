"""Where somebody is right now, and how they have been.

HRMS holds the answer across four doctypes and shows it in none of them. The
reasoning is `oneapp/onehr/presence.py`, and what is worth pinning is the
*ranking* — the four disagree constantly and the disagreement is not an error.
"""

import types

import pytest


@pytest.fixture
def onehr(stub_frappe):
	from oneapp.onehr import history, presence

	stub_frappe.db.exists = lambda *a, **kw: True
	stub_frappe.has_permission = lambda *a, **kw: True
	return types.SimpleNamespace(presence=presence, history=history, frappe=stub_frappe)


def _answers(frappe, **rows):
	"""Stub `get_all` per doctype, so a test says only what it is about."""
	def get_all(doctype, **kw):
		return rows.get(doctype, [])

	frappe.get_all = get_all


def test_leave_outranks_a_badge_in(onehr):
	"""Somebody on approved leave who came in to collect a laptop is on leave.

	A product that says "in" because a turnstile said so is a product that gets
	somebody's pay wrong — and the turnstile is the source HRMS trusts least.
	"""
	_answers(
		onehr.frappe,
		**{
			"Leave Application": [{"leave_type": "Annual", "to_date": "2026-09-18",
			                       "half_day": 0, "half_day_date": None}],
			"Employee Checkin": [{"log_type": "IN", "time": "2026-09-14 08:02:00",
			                      "shift": "Day", "shift_start": None}],
		},
	)
	found = onehr.presence.of("HR-EMP-1")
	assert found["state"] == "leave"
	assert found["detail"] == "Annual"


def test_a_holiday_outranks_a_log_but_not_leave(onehr):
	"""A weekend badge-in is somebody collecting post, not a working day. But
	leave booked over a holiday is still leave — the list is about the company
	and the application is about the person."""
	onehr.frappe.db.get_value = lambda *a, **kw: (
		{"holiday_list": "Weekends", "company": "Acme"} if kw.get("as_dict") else "Weekend"
	)
	_answers(onehr.frappe, **{
		"Employee Checkin": [{"log_type": "IN", "time": "2026-09-13 10:00:00",
		                      "shift": "", "shift_start": None}],
	})
	assert onehr.presence.of("HR-EMP-1")["state"] == "holiday"


def test_the_last_log_decides_in_or_out(onehr):
	"""And it is the last by *time*, not the newest row: a device uploading a
	batch at noon writes the morning's IN after the morning's OUT, and reading
	the newest row has somebody leaving before they arrived."""
	onehr.frappe.db.get_value = lambda *a, **kw: None
	_answers(onehr.frappe, **{
		"Employee Checkin": [{"log_type": "OUT", "time": "2026-09-14 17:30:00",
		                      "shift": "", "shift_start": None}],
	})
	found = onehr.presence.of("HR-EMP-1")
	assert found["state"] == "out"
	assert found["since"] == "2026-09-14 17:30:00"


def test_late_is_a_fact_about_being_in_rather_than_a_state(onehr):
	"""Somebody who arrived at 09:41 against a 09:00 shift is here. Making that
	its own state means a strip of faces cannot count how many people are in."""
	onehr.frappe.db.get_value = lambda *a, **kw: None
	_answers(onehr.frappe, **{
		"Employee Checkin": [{"log_type": "IN", "time": "2026-09-14 09:41:00",
		                      "shift": "Day", "shift_start": "2026-09-14 09:00:00"}],
	})
	found = onehr.presence.of("HR-EMP-1")
	assert found["state"] == "in"
	assert found["late"] is True


def test_a_minute_late_is_not_a_story(onehr):
	"""`GRACE`. A page that calls somebody late for arriving at 09:03 is a page
	that starts an argument every morning."""
	onehr.frappe.db.get_value = lambda *a, **kw: None
	_answers(onehr.frappe, **{
		"Employee Checkin": [{"log_type": "IN", "time": "2026-09-14 09:03:00",
		                      "shift": "Day", "shift_start": "2026-09-14 09:00:00"}],
	})
	assert onehr.presence.of("HR-EMP-1")["late"] is False


def test_attendance_answers_only_where_nothing_else_did(onehr):
	"""It is a verdict written after the day rather than a fact about now — and
	Present with no log is somebody whose attendance was typed in, which is
	worth saying differently."""
	onehr.frappe.db.get_value = lambda doctype, *a, **kw: (
		"Present" if doctype == "Attendance" else None
	)
	_answers(onehr.frappe)
	found = onehr.presence.of("HR-EMP-1")
	assert found["state"] == "in"
	assert found["label"] == "Marked present"


def test_a_workspace_without_hrms_says_it_does_not_know(onehr):
	"""OnePeople is one space on a workspace that may carry others. A record page
	that 500s because an app is missing is worse than one that says nothing."""
	onehr.frappe.db.exists = lambda *a, **kw: False
	assert onehr.presence.of("HR-EMP-1")["state"] == "unknown"
	assert onehr.history.of("HR-EMP-1")["days"] == []


def test_somebody_you_may_not_read_is_not_answered_about(onehr):
	"""Reading the Employee is what entitles you to know whether they are in."""
	onehr.frappe.has_permission = lambda *a, **kw: False
	assert onehr.presence.of("HR-EMP-1")["state"] == "unknown"


def test_a_day_with_no_record_is_a_gap_and_not_an_absence(onehr):
	"""The two are not the same thing, and colouring them alike is how a strip
	lies about somebody who had not joined yet."""
	onehr.frappe.db.get_value = lambda *a, **kw: (
		{"holiday_list": "", "company": ""} if kw.get("as_dict") else None
	)
	_answers(onehr.frappe)
	days = onehr.history.of("HR-EMP-1")["days"]
	assert days, "the window is built from the calendar, not from the rows"
	assert {one["state"] for one in days} == {"none"}
	assert len(days) == onehr.history.DAYS


def test_every_status_hrms_has_maps_onto_one_of_ours(onehr):
	"""And anything it adds later reads as present, which is the safe direction:
	a status nobody here has heard of is far more likely to be a kind of
	attending than a kind of absence."""
	assert set(onehr.history.FROM_STATUS.values()) <= set(onehr.history.DAY_STATES)
	assert onehr.history.FROM_STATUS.get("Work From Home") == "present"
