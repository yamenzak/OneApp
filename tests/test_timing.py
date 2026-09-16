"""The clock, and what it is allowed to do to somebody's afternoon.

Three claims from `docs/WORK.md` stage 6, and the first is the one the rest
rest on.

**A running entry is a row with no end on it** — not a flag, not a cache, not a
key in Redis. So "what am I timing" is one query, and a browser that closed or
a server that restarted leaves the same truth on disk.

**One clock per person.** Starting a second stops the first and says which,
because two running clocks is an afternoon somebody has to unpick by hand.

**A stretch is minutes between two ends**, derived on save. A timesheet where
the length is typed is a timesheet where the length is wrong.
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


class Entry:
	"""Just enough of a `One Time Entry` for the clock to stop it."""

	def __init__(self, name, task, rows):
		self.name = name
		self.task = task
		self.ends_at = None
		self.note = ""
		self.minutes = 0
		self._rows = rows

	def save(self):
		for row in self._rows:
			if row["name"] == self.name:
				row["ends_at"] = self.ends_at
		self.minutes = 25


def clock(timing, monkeypatch, rows):
	"""`One Time Entry` rows, as `get_all` and `get_doc` would answer."""
	made = []

	def get_all(doctype, filters=None, fields=None, order_by=None, **kw):
		running = [row for row in rows if not row.get("ends_at")]
		if filters and filters.get("person"):
			running = [row for row in running if row["person"] == filters["person"]]
		return [dict(row) for row in running]

	def get_doc(first, second=None):
		if isinstance(first, dict):
			row = {**first, "name": f"TIME-{len(rows) + 1:05d}", "ends_at": None}
			rows.append(row)
			made.append(row)
			# `insert` hands the document back, as the framework's does — which
			# is what `start` reads the new row's name off.
			fresh = types.SimpleNamespace(**row)
			fresh.insert = lambda **k: fresh
			return fresh
		return Entry(second, next(r["task"] for r in rows if r["name"] == second), rows)

	monkeypatch.setattr(timing.frappe, "get_all", get_all)
	monkeypatch.setattr(timing.frappe, "get_doc", get_doc)
	monkeypatch.setattr(timing.frappe.db, "exists", lambda *a, **k: True)
	monkeypatch.setattr(timing.frappe.db, "get_value", lambda *a, **k: "zzA task")
	monkeypatch.setattr(timing.frappe, "has_permission", lambda *a, **k: True)
	monkeypatch.setattr(timing.frappe.session, "user", "somebody@example.com")
	return made


def test_nothing_running_is_an_empty_answer(timing, monkeypatch):
	clock(timing, monkeypatch, [])
	assert timing.running() == {}


def test_a_row_with_no_end_is_what_is_running(timing, monkeypatch):
	clock(timing, monkeypatch, [{
		"name": "TIME-00001", "task": "TASK-1", "project": "P",
		"person": "somebody@example.com", "starts_at": "2026-01-01 09:00:00",
		"note": "", "ends_at": None,
	}])
	held = timing.running()
	assert held["name"] == "TIME-00001"
	assert held["task"] == "TASK-1"
	# And what it is called, because a surface showing `TASK-1` is showing the
	# database's answer rather than the reader's.
	assert held["subject"] == "zzA task"


def test_starting_one_stops_the_other_and_says_which(timing, monkeypatch):
	rows = [{
		"name": "TIME-00001", "task": "TASK-1", "project": "P",
		"person": "somebody@example.com", "starts_at": "2026-01-01 09:00:00",
		"note": "", "ends_at": None,
	}]
	clock(timing, monkeypatch, rows)
	found = timing.start("TASK-2")
	assert found["task"] == "TASK-2"
	assert found["stopped"] == "TIME-00001"
	# Stopped on disk, not merely reported.
	assert rows[0]["ends_at"]


def test_stopping_twice_is_not_an_error(timing, monkeypatch):
	"""A second press, a stale tab and a reload all mean "make sure nothing is
	running", and answering empty is the truthful way to say it already was
	not."""
	clock(timing, monkeypatch, [])
	assert timing.stop() == {}


def test_the_button_hands_over_a_record_and_the_clock_ignores_it(timing, monkeypatch):
	"""The action runner passes the record a button was pressed on, and `stop`
	takes a note in that position — so a bare `stop` wired to a button would
	have filed the task's id as the note on every stretch anybody timed."""
	rows = [{
		"name": "TIME-00001", "task": "TASK-1", "project": "P",
		"person": "somebody@example.com", "starts_at": "2026-01-01 09:00:00",
		"note": "", "ends_at": None,
	}]
	clock(timing, monkeypatch, rows)
	timing.stop_for("TASK-1")
	assert rows[0]["ends_at"]
	assert rows[0]["note"] == ""


def test_a_task_that_is_not_there_is_refused(timing, monkeypatch):
	clock(timing, monkeypatch, [])
	monkeypatch.setattr(timing.frappe.db, "exists", lambda *a, **k: False)
	with pytest.raises(Exception):
		timing.start("TASK-9")


# --------------------------------------------------------------------------- #
# How long a stretch is
# --------------------------------------------------------------------------- #

@pytest.fixture
def entry(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onetask"):
			del sys.modules[name]
	return importlib.import_module(
		"oneapp.onetask.doctype.one_time_entry.one_time_entry"
	)


def test_a_stretch_is_the_minutes_between_its_ends(entry):
	assert entry._length("2026-01-01 09:00:00", "2026-01-01 11:30:00") == 150


def test_a_running_stretch_has_no_length_yet(entry):
	assert entry._length("2026-01-01 09:00:00", None) == 0
	assert entry._length(None, None) == 0


def test_a_part_minute_rounds_down(entry):
	"""Ninety seconds is one minute. Rounding up would make a day of
	twenty-second interruptions add up to more time than the day had."""
	assert entry._length("2026-01-01 09:00:00", "2026-01-01 09:01:30") == 1
