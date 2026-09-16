"""The clock, and what it is allowed to do to somebody's afternoon.

Three claims from `docs/WORK.md` §12, and the first is the one the rest rest
on.

**A running stretch is a `Timesheet Detail` with no `to_time`** — not a flag,
not a cache, not a key in Redis, and not a store of ours. So "what am I timing"
is one query, a browser that closed leaves the same truth on disk, and the row
a Sales Invoice reads is the row the clock wrote.

**One clock per person.** Starting a second stops the first and says which,
because two running clocks is an afternoon somebody has to unpick by hand.

**A day is a sheet.** Stretches land on this person's draft Timesheet for
today and a second one is not made beside it.
"""

import types

import pytest


@pytest.fixture
def timing(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onetask"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onetask.timing")


class Sheet:
	"""Just enough of a `Timesheet` for the clock to append to and save."""

	def __init__(self, name, rows, store, user="somebody@example.com"):
		self.name = name
		self.user = user
		self.docstatus = 0
		self.time_logs = [types.SimpleNamespace(**row) for row in rows]
		self._store = store

	def append(self, field, row):
		fresh = types.SimpleNamespace(
			name=f"row{len(self._store['rows']) + 1}", parent=self.name,
			task=row.get("task"), project=row.get("project"),
			from_time=row.get("from_time"), to_time=None, hours=0,
			description=row.get("description", ""),
			is_billable=row.get("is_billable", 0),
		)
		self.time_logs.append(fresh)
		return fresh

	def save(self):
		self._store["sheets"].setdefault(self.name, self)
		self._store["rows"] = [
			{"name": one.name, "parent": self.name, "task": one.task,
			 "project": one.project, "from_time": one.from_time,
			 "to_time": one.to_time, "description": one.description,
			 "hours": one.hours, "is_billable": one.is_billable}
			for sheet in self._store["sheets"].values()
			for one in sheet.time_logs
		]
		return self


def clock(timing, monkeypatch, rows, today="2026-01-01"):
	"""A person's sheets, as `get_all` and `get_doc` would answer for them."""
	store = {"sheets": {}, "rows": list(rows)}
	if rows:
		store["sheets"]["TS-00001"] = Sheet("TS-00001", rows, store)

	def get_all(doctype, filters=None, fields=None, order_by=None, **kw):
		filters = filters or {}
		if doctype == "Timesheet Detail":
			# A `_dict`, as `get_all` answers: `running` reads `.parent` off
			# the row and a plain dict would only look right.
			found = [one for one in store["rows"] if not one.get("to_time")]
			return [timing.frappe._dict(one) for one in found]
		# A Timesheet, asked for either by name — which is how `running`
		# narrows the open rows to this person — or by the day.
		found = [one for one in store["sheets"].values()
		         if one.user == filters.get("user", one.user)]
		if "name" in filters:
			wanted = filters["name"][1]
			found = [one for one in found if one.name in wanted]
		return [one.name for one in found]

	def get_doc(first, second=None):
		if isinstance(first, dict):
			return Sheet(f"TS-{len(store['sheets']) + 1:05d}", [], store)
		return store["sheets"][second]

	monkeypatch.setattr(timing.frappe, "get_all", get_all)
	monkeypatch.setattr(timing.frappe, "get_doc", get_doc)
	monkeypatch.setattr(timing.frappe.db, "exists", lambda *a, **k: True)
	monkeypatch.setattr(timing.frappe.db, "get_value", lambda *a, **k: "zzA task")
	monkeypatch.setattr(timing.frappe, "has_permission", lambda *a, **k: True)
	monkeypatch.setattr(timing.frappe.session, "user", "somebody@example.com")
	monkeypatch.setattr(timing, "today", lambda: today)
	return store


RUNNING = {
	"name": "row1", "parent": "TS-00001", "task": "TASK-1", "project": "P",
	"from_time": "2025-12-31 23:00:00", "to_time": None, "description": "",
	"hours": 0, "is_billable": 0,
}


def test_nothing_running_is_an_empty_answer(timing, monkeypatch):
	clock(timing, monkeypatch, [])
	assert timing.running() == {}


def test_a_row_with_no_end_is_what_is_running(timing, monkeypatch):
	clock(timing, monkeypatch, [dict(RUNNING)])
	held = timing.running()
	assert held["name"] == "row1"
	assert held["task"] == "TASK-1"
	assert held["sheet"] == "TS-00001"
	# And what it is called, because a surface showing `TASK-1` is showing the
	# database's answer rather than the reader's.
	assert held["subject"] == "zzA task"


def test_somebody_else_s_clock_is_not_yours(timing, monkeypatch):
	"""The rows with no end on them are every clock on the site. Narrowing them
	to this person's sheets is the second query, and without it a person
	pressing Start would stop a colleague's afternoon."""
	store = clock(timing, monkeypatch, [dict(RUNNING)])
	store["sheets"]["TS-00001"].user = "somebody-else@example.com"
	assert timing.running() == {}


def test_starting_one_stops_the_other_and_says_which(timing, monkeypatch):
	store = clock(timing, monkeypatch, [dict(RUNNING)])
	found = timing.start("TASK-2")
	assert found["task"] == "TASK-2"
	assert found["stopped"] == "row1"
	# Stopped on disk, not merely reported.
	assert store["rows"][0]["to_time"]


def test_a_second_stretch_the_same_day_joins_the_same_sheet(timing, monkeypatch):
	"""A day is a sheet. Two clocks in one afternoon on two sheets is two
	documents somebody has to submit and a week that adds up twice."""
	store = clock(timing, monkeypatch, [dict(RUNNING)])
	timing.start("TASK-2")
	assert list(store["sheets"]) == ["TS-00001"]
	assert len(store["sheets"]["TS-00001"].time_logs) == 2


def test_stopping_twice_is_not_an_error(timing, monkeypatch):
	"""A second press, a stale tab and a reload all mean "make sure nothing is
	running", and answering empty is the truthful way to say it already was
	not."""
	clock(timing, monkeypatch, [])
	assert timing.stop() == {}


def test_stopping_writes_the_hours_on_the_row(timing, monkeypatch):
	"""ERPNext computes a row's hours from its two timestamps and the clock
	writes the second one, so the length is derived rather than typed. An hour
	before the stub's `now`, so the number is the hour it was."""
	store = clock(timing, monkeypatch, [dict(RUNNING)])
	timing.stop()
	assert store["rows"][0]["to_time"]
	assert store["rows"][0]["hours"] == 1.0


def test_the_button_hands_over_a_record_and_the_clock_ignores_it(timing, monkeypatch):
	"""The action runner passes the record a button was pressed on, and `stop`
	takes a note in that position — so a bare `stop` wired to a button would
	have filed the task's id as the note on every stretch anybody timed."""
	store = clock(timing, monkeypatch, [dict(RUNNING)])
	timing.stop_for("TASK-1")
	assert store["rows"][0]["to_time"]
	assert store["rows"][0]["description"] == ""


def test_a_task_that_is_not_there_is_refused(timing, monkeypatch):
	clock(timing, monkeypatch, [])
	monkeypatch.setattr(timing.frappe.db, "exists", lambda *a, **k: False)
	with pytest.raises(Exception):
		timing.start("TASK-9")


def test_the_verbs_are_offered_where_the_work_is(timing):
	"""And on OneProject's screens, because after §12 there is no other space
	tasks are worked from."""
	offered = timing.actions()
	assert set(offered) == {"oneproject/tasks", "oneproject/my-tasks",
	                        "oneproject/inbox"}
	assert [one["key"] for one in offered["oneproject/tasks"]] == [
		"start-timing", "stop-timing"]
