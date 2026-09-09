"""What the feed plans, and the one piece of arithmetic that hides a bug.

Every other module here records what happened. This one records what was
*supposed* to, which makes it the denominator for the two features built on it —
the ghosts on the forward scrubber and the plan against what ran.

Almost all of the risk is in one place: the service day. A trip leaving at 00:40
belongs to yesterday's pattern, every feed in this market says so, and getting it
wrong does not throw — it silently loses every night bus, which is the service an
operator is most often asked to account for. So most of what is below is that.
"""

import sys
import types
from datetime import date, datetime, timedelta

import pytest


@pytest.fixture
def timetable(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import timetable as module

	return module


class Rows:
	"""The schedule table, as `_calls` reads it: one SQL shape, answered here."""

	def __init__(self, stub_frappe, rows):
		self.rows = rows
		self.asked = []
		stub_frappe.db.sql = self.sql

	def sql(self, query, values=None, as_dict=False, **kw):
		values = values or {}
		if "DELETE" in query or "COUNT" in query:
			return [[len(self.rows)]]
		self.asked.append(values)
		found = [
			one for one in self.rows
			if one["days"] & values["bit"]
			and values["low"] <= one["arrives_s"] < values["high"]
			and all(one.get(key) == value for key, value in values.items()
			        if key.startswith("w"))
		]
		return sorted(found, key=lambda one: one["arrives_s"])


def call(arrives_s, trip="t-1", seq=1, days=127, stop="alx", line="u6"):
	return {
		"trip_key": trip, "line": line, "stop": stop, "seq": seq,
		"arrives_s": arrives_s, "departs_s": arrives_s + 30,
		"headsign": "Zoo", "source": "gtfs", "days": days,
	}


@pytest.fixture
def table(timetable, stub_frappe, monkeypatch):
	from oneapp.shared import facts

	monkeypatch.setattr(facts, "exists", lambda fact: True)
	# Every read narrows by a facet the table carries, so the resolver has to
	# answer rather than be stubbed out — it is what decides `stop` is a column
	# here and `vehicle` is not.
	return lambda rows: Rows(stub_frappe, rows)


# --------------------------------------------------------------------------- #
# The service day
# --------------------------------------------------------------------------- #

def test_a_pattern_is_stored_as_weekdays_not_as_dates(timetable):
	"""Monday is bit nought, which is `date.weekday()`'s own numbering — so a
	trip running Monday to Friday is 31 and nothing has to convert anything."""
	assert timetable.bit(date(2026, 9, 7)) == 1
	assert timetable.bit(date(2026, 9, 13)) == 64
	weekdays = sum(timetable.bit(date(2026, 9, 7) + timedelta(days=one)) for one in range(5))
	assert weekdays == 31


def test_a_query_asks_yesterdays_pattern_too(timetable, table):
	"""The night bus, and the whole reason this file exists. A trip at 25:10
	is on the pattern of the day that began yesterday, so a window at half past
	midnight has to look there — and a window that only looks at today finds
	nothing and reports an empty network."""
	shop = table([call(25 * 3600 + 600, trip="night")])
	found = timetable._calls(
		datetime(2026, 9, 9, 1, 0), datetime(2026, 9, 9, 1, 30), {}, 50,
	)
	assert [one["trip_key"] for one in found] == ["night"]
	# And it is reported at the real moment, not at 25:10 of a day that has no
	# such hour.
	assert found[0]["due"] == datetime(2026, 9, 9, 1, 10)
	assert len(shop.asked) == 2


def test_a_window_asks_each_day_for_its_own_seconds(timetable, table):
	"""Yesterday's pattern is asked about the second day of its service, which
	is what the shift is. Asking both days the same range is the bug that
	double-counts every morning trip."""
	shop = table([])
	timetable._calls(datetime(2026, 9, 9, 1, 0), datetime(2026, 9, 9, 1, 30), {}, 50)
	ranges = sorted((one["low"], one["high"]) for one in shop.asked)
	assert ranges == [(3600, 5400), (90000, 91800)]


def test_the_ordinary_case_is_the_ordinary_case(timetable, table):
	table([call(8 * 3600, trip="morning")])
	found = timetable._calls(
		datetime(2026, 9, 9, 7, 30), datetime(2026, 9, 9, 8, 30), {}, 50,
	)
	assert found[0]["due"] == datetime(2026, 9, 9, 8, 0)


def test_a_trip_that_does_not_run_today_is_not_due_today(timetable, table):
	"""A Sunday-only service on a Wednesday. The bitmask is the whole of it, and
	a timetable that ignores it shows a network nobody is running."""
	table([call(8 * 3600, days=64)])
	assert timetable._calls(
		datetime(2026, 9, 9, 7, 0), datetime(2026, 9, 9, 9, 0), {}, 50,
	) == []


# --------------------------------------------------------------------------- #
# Ghosts
# --------------------------------------------------------------------------- #

def running(timetable, table, when, stops):
	# The datetime rather than its string: the stub's `get_datetime` is the
	# identity, so a string here would test the stub rather than the module.
	table(stops)
	return timetable.expected(when=when)


def test_a_ghost_is_two_stops_and_a_fraction(timetable, table, stub_frappe):
	"""Not a position. The browser holds the line's drawn shape and projects
	onto it — sending coordinates would mean a second geometry implementation
	that can disagree with the first about where the route goes."""
	out = running(timetable, table, datetime(2026, 9, 9, 8, 5), [
		call(8 * 3600, seq=1, stop="alx"),
		call(8 * 3600 + 600, seq=2, stop="zoo"),
	])
	ghost = out["ghosts"][0]
	assert (ghost["from_stop"], ghost["to_stop"]) == ("alx", "zoo")
	# Five minutes into a ten-minute leg that began thirty seconds after the
	# first call.
	assert 0.45 < ghost["t"] < 0.55


def test_a_trip_that_has_not_started_is_not_on_the_map(timetable, table):
	"""Rather than parked on its first stop for half an hour beforehand, which
	is what a bracket that falls back to the nearest call would draw."""
	out = running(timetable, table, datetime(2026, 9, 9, 7, 50), [
		call(8 * 3600, seq=1, stop="alx"),
		call(8 * 3600 + 600, seq=2, stop="zoo"),
	])
	assert out["ghosts"] == []


def test_a_trip_that_has_finished_is_not_on_the_map(timetable, table):
	out = running(timetable, table, datetime(2026, 9, 9, 8, 20), [
		call(8 * 3600, seq=1, stop="alx"),
		call(8 * 3600 + 600, seq=2, stop="zoo"),
	])
	assert out["ghosts"] == []


def test_two_trips_of_one_line_are_two_ghosts(timetable, table):
	out = running(timetable, table, datetime(2026, 9, 9, 8, 5), [
		call(8 * 3600, seq=1, stop="alx", trip="a"),
		call(8 * 3600 + 600, seq=2, stop="zoo", trip="a"),
		call(8 * 3600 - 300, seq=1, stop="alx", trip="b"),
		call(8 * 3600 + 420, seq=2, stop="zoo", trip="b"),
	])
	assert {one["trip_key"] for one in out["ghosts"]} == {"a", "b"}


# --------------------------------------------------------------------------- #
# The plan against what ran
# --------------------------------------------------------------------------- #

def compare(timetable, stub_frappe, table, planned, visits, day="2026-09-09"):
	table(planned)
	from oneapp.shared import facts

	facts.rows_between = lambda fact, start, end, where=None: visits
	return timetable.deviation(day=day)


def seen(at, line="u6", stop="alx"):
	return {"at": at, "line": line, "stop": stop}


def test_planned_0738_against_observed_0744(timetable, table, stub_frappe):
	"""§6's own sentence, one level below the record conflict `conflicts.py`
	resolves: that module decides which record two sources describe, this one
	compares two statements about the same event. Nothing resolves it — the gap
	is the product."""
	out = compare(
		timetable, stub_frappe, table,
		[call(7 * 3600 + 38 * 60)],
		[seen(datetime(2026, 9, 9, 7, 44))],
	)
	assert out["matched"] == 1 and out["missed"] == 0
	assert out["calls"][0]["gap_s"] == 360
	assert out["median_s"] == 360


def test_a_call_nothing_came_to_is_missed_and_not_matched_to_the_next_hour(
	timetable, table, stub_frappe
):
	"""The failure that would make a cancelled trip look like a very late one,
	and it is the one an operator will check first."""
	out = compare(
		timetable, stub_frappe, table,
		[call(7 * 3600)],
		[seen(datetime(2026, 9, 9, 9, 0))],
	)
	assert out["missed"] == 1 and out["matched"] == 0
	assert out["calls"][0]["gap_s"] is None


def test_one_vehicle_does_not_answer_for_two_calls(timetable, table, stub_frappe):
	"""A frequent line's calls are minutes apart, and a single visit matched to
	every nearby one would report a working service where half of it never
	ran."""
	out = compare(
		timetable, stub_frappe, table,
		[call(7 * 3600, trip="a"), call(7 * 3600 + 120, trip="b")],
		[seen(datetime(2026, 9, 9, 7, 1))],
	)
	assert out["matched"] == 1 and out["missed"] == 1


def test_a_visit_no_timetable_planned_is_its_own_finding(timetable, table, stub_frappe):
	"""Not silence. A vehicle serving a stop the plan does not mention is
	either an unpublished working or a stop mapped to the wrong pole, and both
	are things somebody wants to be told."""
	out = compare(timetable, stub_frappe, table, [], [seen(datetime(2026, 9, 9, 7, 0))])
	assert out["unplanned"] == 1 and out["planned"] == 0


def test_the_worst_calls_are_shown_first(timetable, table, stub_frappe):
	"""This is a list somebody reads the top of, and a page of on-time calls is
	not why they opened it."""
	out = compare(
		timetable, stub_frappe, table,
		[call(7 * 3600, trip="a", stop="alx"), call(8 * 3600, trip="b", stop="zoo")],
		[seen(datetime(2026, 9, 9, 7, 0, 30), stop="alx"),
		 seen(datetime(2026, 9, 9, 8, 20), stop="zoo")],
	)
	assert [one["gap_s"] for one in out["calls"]] == [1200, 30]


# --------------------------------------------------------------------------- #
# The shape of the module
# --------------------------------------------------------------------------- #

def test_a_timetable_belongs_to_a_source(timetable, stub_frappe):
	"""Scoped, so replacing one feed's plan does not take another's with it —
	the same rule `conflicts.py` keeps one level up."""
	with pytest.raises(stub_frappe.ValidationError):
		timetable.replace("", [call(0)])


def test_a_delivery_restates_the_plan_rather_than_amending_it(timetable):
	"""Delete then write. A timetable half from March and half from April is
	one nobody ever published."""
	import inspect

	source = inspect.getsource(timetable.replace)
	assert "DELETE" in source and "`source` = %s" in source


def test_every_endpoint_is_a_read_and_says_so(timetable):
	import inspect

	source = inspect.getsource(timetable)
	assert source.count('@frappe.whitelist(methods=["GET"])') == 3
	assert 'methods=["POST"]' not in source


def test_it_refuses_a_reader_who_cannot_see_a_line(timetable, stub_frappe):
	stub_frappe.has_permission = lambda *a, **k: False
	with pytest.raises(stub_frappe.PermissionError):
		timetable._guard()
