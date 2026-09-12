"""Reading the event tiers, and the three things that are easy to get wrong.

**"Still in force" is the absence of a later row.** A door that jammed and
then unjammed has a later row; a door that is still jammed does not. An
attention list that filtered on `trouble = 1` alone would show every fault
that has ever been resolved, which is a list nobody reads twice.

**A duration belongs to the state it measures.** Rows carry `was` and
`number` — how long the state this row *ended* had lasted — so "how long were
the doors open" filters on `was`, not on `value`. Filtering on `value` reads
naturally and answers a different question.

**A day has no end.** The last span of a window is left open rather than
closed at midnight, because a vehicle whose doors were open when the window
ended did not shut them.
"""

import inspect
import sys

import pytest


@pytest.fixture
def events(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import events as module

	return module


def test_attention_keeps_only_what_is_still_true(events):
	body = inspect.getsource(events.attention)
	# The newest row per (vehicle, kind, part), and troubled only if that
	# newest one is. A resolved fault drops out without anything resolving it.
	assert "MAX(at)" in body
	assert "GROUP BY vehicle, kind, part" in body
	assert "trouble = 1" in body

	# And the duration is measured against now, because there is no later row
	# — which is exactly what makes the state still true.
	assert "now_datetime()" in body
	assert "minutes" in body


def test_attention_puts_the_oldest_first(events):
	"""A door jammed two hours ago outranks one jammed a minute ago, and
	sorting by recency buries the worst case at the bottom."""
	body = inspect.getsource(events.attention)
	assert 'key=lambda one: -one["minutes"]' in body


def test_a_duration_is_read_off_the_state_it_measures(events):
	"""`was`, not `value`. The row that says `SingleDoorClosed` is the one
	carrying how long the door was open."""
	body = inspect.getsource(events.doors)
	assert "`was` IN" in body
	assert "`value` IN" not in body, (
		"the duration belongs to the state that ended, which is `was`"
	)


def test_the_measured_dwell_is_shown_beside_the_inferred_one(events):
	"""A workspace with door data on half its fleet should be able to see
	which half. One silently replacing the other is how a number changes
	meaning without anybody noticing."""
	body = inspect.getsource(events.doors)
	assert "STOP_HOUR" in body and "EVENT_HOUR" in body
	assert "measured_from" in body


def test_a_day_is_not_closed_at_midnight(events):
	body = inspect.getsource(events.story)
	assert "spans" in body
	# `vdv301.spans` leaves the last one open; the read must not invent an end.
	from oneapp.onemobility import vdv301

	assert "until = get_datetime(after" in inspect.getsource(vdv301.spans)


def test_every_read_asks_before_it_answers(events):
	for one in (events.attention, events.behaviour, events.doors, events.story):
		assert "_guard()" in inspect.getsource(one), f"{one.__name__} does not guard"
	assert "has_permission" in inspect.getsource(events._guard)
	# And the one that names a record checks that record, not only the
	# doctype: a vehicle somebody may not read is not answerable by naming it.
	assert 'has_permission("Transit Vehicle", "read", doc=vehicle)' in inspect.getsource(events.story)


def test_the_nightly_summary_can_be_run_twice(events):
	"""`arrivals.build`'s rule, for the same reason: a pass that is not free
	to re-run is a pass nobody dares re-run after a bad night."""
	body = inspect.getsource(events.summarise)
	assert "DELETE FROM" in body and "WHERE `day` = %s" in body

	# And the day before yesterday too, because a relay can arrive late.
	assert "(1, 2)" in inspect.getsource(events.nightly)


def test_the_row_carries_what_it_ended(stub_frappe):
	"""The column that makes a duration aggregate possible at all."""
	from datetime import datetime

	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import model, vdv301

	assert "was" in model.VEHICLE_EVENT.columns
	assert "was" in model.EVENT_HOUR.columns
	# Grouped on, so one tier answers counts per state and durations per state.
	assert "was" in model.VEHICLE_EVENT.rollups[0]["group"]

	rows = vdv301.read("1042", [
		{"kind": "door", "part": "1", "value": "SingleDoorOpen",
		 "at": datetime(2026, 9, 12, 7, 0, 0)},
		{"kind": "door", "part": "1", "value": "SingleDoorClosed",
		 "at": datetime(2026, 9, 12, 7, 0, 14)},
	])
	# The opening row ended nothing and lasted nothing; the closing row says
	# the door had been open fourteen seconds.
	assert rows[0]["was"] == "" and rows[0]["number"] == 0
	assert rows[1]["was"] == "SingleDoorOpen" and rows[1]["number"] == 14


def test_a_caller_supplied_number_is_not_overwritten(stub_frappe):
	"""A count is a number too. Only a state has a span, and stamping a
	duration over a counted boarding would be a made-up figure."""
	from datetime import datetime

	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import vdv301

	seen = {}
	vdv301.read("1042", [{"kind": "counting", "part": "1", "value": "Regular",
	                      "at": datetime(2026, 9, 12, 7, 0, 0)}], seen=seen)
	rows = vdv301.read("1042", [{"kind": "counting", "part": "1", "value": "Defect",
	                             "number": 7, "at": datetime(2026, 9, 12, 7, 5, 0)}],
	                   seen=seen)
	assert rows[0]["number"] == 7
