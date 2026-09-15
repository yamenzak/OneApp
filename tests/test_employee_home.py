"""The employee's own page, and the rule that made it possible.

Two things worth pinning, and neither of them is arithmetic.

**Who "me" is.** By `user_id` and by nothing else. A fallback to matching on
email is one line shorter and hands somebody their namesake's pay on any
workspace where two people share a personal address — so the absence of that
fallback is the thing a test has to hold, because adding it back would look
like a fix.

**What a self-service page may read.** `own.may_read` is the counterpart to
`if_owner`: your own row needs no grant, anybody else's needs the doctype. It
can go wrong in two directions and only one of them is loud. Refusing somebody
their own payslip is a block that does not draw; handing somebody a colleague's
leave balance is a leak that nothing anywhere complains about, which is exactly
what `history.of` did while it asked only whether the reader could open the
Employee *record*.
"""

import types

import pytest


@pytest.fixture
def onehr(stub_frappe):
	from oneapp.onehr import checkin, history, me, own

	stub_frappe.db.exists = lambda *a, **kw: True
	stub_frappe.has_permission = lambda *a, **kw: True
	stub_frappe.get_all = lambda doctype, **kw: []
	return types.SimpleNamespace(
		own=own, me=me, checkin=checkin, history=history, frappe=stub_frappe)


def _answers(frappe, **rows):
	"""Stub `get_all` per doctype, so a test says only what it is about."""
	def get_all(doctype, **kw):
		found = rows.get(doctype, [])
		if callable(found):
			return found(kw)
		return found

	frappe.get_all = get_all


def _seated(frappe, employee="HR-EMP-1", user="somebody@example.com", **rows):
	"""A site where the session's user is one of the people on it."""
	frappe.session.user = user

	def employees(kw):
		filters = kw.get("filters") or {}
		if filters.get("user_id") == user:
			return [employee] if kw.get("pluck") else [{"name": employee}]
		if filters.get("user_id"):
			return []
		return rows.get("Employee", [])

	_answers(frappe, Employee=employees, **rows)


# --------------------------------------------------------------------------- #
# Who "me" is
# --------------------------------------------------------------------------- #

def test_the_reader_is_found_by_their_login_and_by_nothing_else(onehr):
	_seated(onehr.frappe, employee="HR-EMP-7", user="omar@example.com")
	assert onehr.own.employee_of() == "HR-EMP-7"


def test_a_login_nobody_linked_is_nobody(onehr):
	"""Not an error and not a guess. A workspace that has not linked its logins
	is an ordinary state of a real site, and the page says so in a sentence."""
	onehr.frappe.session.user = "stranger@example.com"
	_answers(onehr.frappe)
	assert onehr.own.employee_of() == ""

	found = onehr.me.home()
	assert found["employee"] is None
	assert found["reason"] == "not-linked"


def test_a_workspace_without_hrms_says_so_rather_than_failing(onehr):
	onehr.frappe.db.exists = lambda *a, **kw: False
	found = onehr.me.home()
	assert found["employee"] is None
	assert found["reason"] == "no-hrms"


def test_the_page_takes_no_employee(onehr):
	"""The security property, asserted as a signature rather than as a story.

	There is no employee to pass, so there is no employee to pass somebody
	else's — and an argument added here later would be the whole of the bug.
	"""
	import inspect

	for name in ("home", "who"):
		assert not inspect.signature(getattr(onehr.me, name)).parameters, (
			f"me.{name} grew an argument; a self-service endpoint that takes an "
			f"employee is one that can be pointed at a colleague"
		)

	# `file` takes a position, because the browser is the only thing that knows
	# one. What it must never take is a *subject*: the property is "there is no
	# employee to pass", not "there are no arguments", and the difference is
	# worth stating rather than pinning the parameter count and calling it
	# security.
	taken = set(inspect.signature(onehr.checkin.file).parameters)
	assert taken <= {"latitude", "longitude"}, (
		f"checkin.file takes {sorted(taken)}; anything beyond a position is a "
		f"caller choosing something about somebody else's check-in"
	)


# --------------------------------------------------------------------------- #
# The rule
# --------------------------------------------------------------------------- #

def test_your_own_row_needs_no_grant(onehr):
	"""The half `if_owner` cannot reach: a payslip is about you and is written
	by payroll, so its owner is never its subject."""
	_seated(onehr.frappe, employee="HR-EMP-1")
	onehr.frappe.has_permission = lambda *a, **kw: False

	assert onehr.own.may_read("Salary Slip", "HR-EMP-1") is True


def test_somebody_else_s_row_needs_the_doctype(onehr):
	_seated(onehr.frappe, employee="HR-EMP-1")
	onehr.frappe.has_permission = lambda *a, **kw: False

	assert onehr.own.may_read("Salary Slip", "HR-EMP-2") is False


def test_the_grant_is_still_the_answer_for_everybody_else(onehr):
	"""A people officer holds the wider grant and this does not get in the
	way of it — the rule adds a yes, it never takes one away."""
	_seated(onehr.frappe, employee="HR-EMP-1")
	onehr.frappe.has_permission = lambda *a, **kw: True

	assert onehr.own.may_read("Attendance", "HR-EMP-2") is True


def test_a_doctype_the_site_has_not_got_is_no(onehr):
	_seated(onehr.frappe, employee="HR-EMP-1")
	onehr.frappe.db.exists = lambda *a, **kw: False
	assert onehr.own.may_read("Salary Slip", "HR-EMP-1") is False


def test_reading_a_colleague_s_record_is_not_reading_their_numbers(onehr):
	"""The leak this closed.

	`history.of` asked only whether the reader could read the Employee *record*,
	and OnePeople's Employee seat can read every one of them — a directory nobody
	can open is not a directory. So a colleague's eight weeks of attendance and
	their leave balance came back to anybody in the space.
	"""
	_seated(onehr.frappe, employee="HR-EMP-1")
	# Can open the record; holds no grant on the numbers behind it.
	onehr.frappe.has_permission = lambda doctype, *a, **kw: doctype == "Employee"
	onehr.frappe.db.get_value = lambda *a, **kw: None

	theirs = onehr.history.of("HR-EMP-2")
	assert theirs["days"] == []
	assert theirs["balance"] == []


# --------------------------------------------------------------------------- #
# Checking in
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("state,late,expected", [
	({"state": "out"}, False, "IN"),
	({"state": "unknown"}, False, "IN"),
	({"state": "absent"}, False, "IN"),
	({"state": "in"}, False, "OUT"),
	({"state": "in"}, True, "OUT"),
])
def test_the_direction_is_the_opposite_of_wherever_you_are(onehr, state, late, expected):
	"""Read, not asked. A page open since this morning would send whichever the
	button said when it loaded."""
	assert onehr.checkin._direction({**state, "late": late}) == expected


@pytest.mark.parametrize("state", ["leave", "holiday"])
def test_there_is_no_direction_on_a_day_you_are_not_working(onehr, state):
	"""A badge-in on approved leave is exactly the disagreement `presence`
	exists to rank, and writing one would manufacture it."""
	assert onehr.checkin._direction({"state": state}) == ""


def test_checking_in_refuses_a_login_nobody_linked(onehr):
	onehr.frappe.session.user = "stranger@example.com"
	_answers(onehr.frappe)
	with pytest.raises(onehr.frappe.ValidationError):
		onehr.checkin.file()


def test_checking_in_writes_one_row_for_the_person_asking(onehr):
	_seated(onehr.frappe, employee="HR-EMP-9", user="omar@example.com",
	        **{"Employee Checkin": [], "Leave Application": [], "Attendance": []})
	onehr.frappe.db.get_value = lambda *a, **kw: None

	written = {}

	class _Doc(dict):
		def insert(self, *a, **kw):
			written.update(self)
			return self

	onehr.frappe.get_doc = lambda one: _Doc(one)

	answer = onehr.checkin.file()
	assert written["doctype"] == "Employee Checkin"
	assert written["employee"] == "HR-EMP-9"
	assert written["log_type"] == "IN"
	assert answer["direction"] == "IN"


def test_nothing_here_skips_a_permission(onehr):
	"""`own.py` decides whether OnePeople reads on your behalf. It is not a way
	round Frappe, and an `ignore_permissions` in the write path would make it
	one."""
	from pathlib import Path

	source = Path(onehr.checkin.__file__).with_suffix(".py").read_text()
	assert "ignore_permissions" not in source.split('"""', 2)[-1]
