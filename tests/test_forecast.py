"""The arithmetic behind every forward-looking number, and the three rules.

`forecast.py` is deliberately statistics rather than a model, which makes it
testable in the way a model is not: every answer here is a function of numbers
we already hold, so the whole of it can be exercised without a database, a
fitted anything, or a fixture that takes a minute to build.

What is actually being defended is not the arithmetic — a weighted mean is hard
to get wrong — but the three rules the module exists to keep. Nothing is
answered without saying what it rests on. Nothing is answered without its
spread. Nothing is offered beyond the horizon a timetable survives. Each of
those is one line of code and each of them is the difference between a forecast
somebody can act on and one that quietly misleads.
"""

import sys

import pytest


@pytest.fixture
def forecast(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import forecast as module

	return module


def hour(readings, p50, p85, p95, avg=None):
	"""One row as the aggregate tier hands it over."""
	return {
		"readings": readings,
		"delay_p50": p50,
		"delay_p85": p85,
		"delay_p95": p95,
		"delay_avg": avg if avg is not None else p50,
	}


def test_a_distribution_says_how_much_it_rests_on(forecast):
	one = forecast._reading([hour(400, 60, 200, 400)], "delay")
	assert one["basis"] == 400
	assert not one["learning"]
	assert (one["p50"], one["p85"], one["p95"]) == (60, 200, 400)


def test_too_little_history_is_still_answered_and_marked(forecast):
	"""Refusing to answer is its own kind of unhelpful, and a workspace switched
	on this morning is exactly the one most likely to be looking. So the number
	comes back with `learning` on it and every surface draws that differently."""
	one = forecast._reading([hour(4, 60, 90, 120)], "delay")
	assert one["basis"] == 4
	assert one["learning"]
	assert one["p50"] == 60


def test_nothing_at_all_is_a_distribution_with_no_numbers_in_it(forecast):
	"""Not a zero. A line nobody has observed is not a line that runs on time,
	and the two must not be drawn the same way."""
	for rows in ([], [{}], [hour(0, None, None, None)]):
		one = forecast._reading(rows, "delay")
		assert one["basis"] == 0 and one["learning"]
		assert one["p50"] is None


def test_a_busy_line_and_a_quiet_one_do_not_get_an_equal_say(forecast):
	"""Weighted by readings, not averaged flat. A flat mean is how a line
	somebody observed four times comes to dominate a network's headline."""
	rows = [hour(1000, 60, 100, 140), hour(10, 600, 700, 800)]
	one = forecast._reading(rows, "delay")
	assert one["basis"] == 1010
	# Flat would be 330. Weighted lands near the line that was actually running.
	assert 60 < one["p50"] < 70


def test_a_row_with_no_number_does_not_drag_the_answer_to_zero(forecast):
	"""A null percentile is a measure that was not recorded, not a measure that
	was nought — and averaging it in as nought is the classic way an aggregate
	comes out confidently wrong."""
	rows = [hour(100, 120, 200, 300), hour(100, None, None, None)]
	assert forecast._reading(rows, "delay")["p50"] == 120


def test_the_spread_becomes_a_probability(forecast):
	"""p50 and p95 are two points on a distribution; a chance of being late is
	what an operator acts on. Half the runs are over the median by definition,
	and the p95 is exceeded by one in twenty."""
	one = forecast._reading([hour(500, 300, 500, 700)], "delay")
	assert forecast._chance_over(one, 300) == pytest.approx(50, abs=0.5)
	assert forecast._chance_over(one, 700) == pytest.approx(5, abs=0.5)
	# And further out than anything observed is unlikely rather than impossible.
	assert 0 < forecast._chance_over(one, 900) < 5


def test_a_distribution_with_no_spread_yields_no_probability(forecast):
	"""Rather than a hundred percent. Every reading landing on the same number
	means too little data far more often than it means certainty, and this is
	the case that would otherwise print "100% late" from four observations."""
	flat = forecast._reading([hour(500, 300, 300, 300)], "delay")
	assert forecast._sigma(flat) is None
	assert forecast._chance_over(flat, 100) is None


def test_it_will_not_speak_about_a_month_from_now(forecast, stub_frappe):
	"""What changes over a fortnight is the timetable, and no amount of history
	sees that coming. Refused rather than extrapolated."""
	from datetime import datetime, timedelta

	soon = datetime.now() + timedelta(days=3)
	forecast._horizon(soon)  # does not throw

	with pytest.raises(stub_frappe.ValidationError):
		forecast._horizon(datetime.now() + timedelta(days=60))


def test_the_past_is_never_out_of_horizon(forecast):
	"""Because it is not a forecast at all — it is what happened, and the same
	lookup answers it. `outlook` is one read whether the Tuesday has been yet."""
	from datetime import datetime, timedelta

	forecast._horizon(datetime.now() - timedelta(days=200))


def test_the_history_window_cannot_be_talked_into_anything(forecast):
	"""A caller-supplied number reaching a query is how a screen ends up asking
	for four years of a table it should read ninety days of."""
	for asked, expected in ((0, 90), (1, 7), (99999, 400), ("30", 30)):
		start, end = forecast._history(asked)
		assert (end - start).days == expected


def test_every_endpoint_is_a_read_and_says_so(forecast):
	"""A whitelisted method that writes on GET is a CSRF away from being a
	problem, and the five here are all lookups."""
	import inspect

	source = inspect.getsource(forecast)
	assert source.count('@frappe.whitelist(methods=["GET"])') == 5
	assert "methods=[\"POST\"]" not in source


def test_it_refuses_a_reader_who_cannot_see_a_line(forecast, stub_frappe):
	"""The permission is on the doctype rather than on the fact table, because
	a fact table has none — see README §3."""
	stub_frappe.has_permission = lambda *a, **k: False
	with pytest.raises(stub_frappe.PermissionError):
		forecast._guard()


# --------------------------------------------------------------------------- #
# The three that were missing
# --------------------------------------------------------------------------- #

def test_how_full_becomes_a_decision_rather_than_a_number(forecast):
	"""§7a point 4, and the reason the occupancy percentiles now exist. "Half
	full on average" is a number; "full on three journeys in ten at this hour"
	is a decision about whether to put another vehicle out."""
	one = forecast._reading(
		[{"readings": 500, "occupancy_p50": 60, "occupancy_p85": 85,
		  "occupancy_p95": 95, "occupancy_avg": 62}],
		"occupancy",
	)
	assert one["p50"] == 60
	# A median of sixty with a p95 of ninety-five: about one journey in six is
	# over eighty, which is a sentence somebody can act on.
	assert forecast._chance_over(one, forecast.FULL_PCT) == pytest.approx(17, abs=3)


def test_full_is_not_a_hundred_percent(forecast):
	"""A vehicle at eighty percent of capacity is one people are already
	choosing not to board. An operator acts on crowding before the doors stop
	closing, not after."""
	assert 70 <= forecast.FULL_PCT <= 85


def test_a_collapsing_gap_is_read_off_the_low_tail(forecast):
	"""§7a point 3, and the forward half of `network.bunching` — that one
	answers "which vehicles have caught each other now", this one answers
	"where does this keep happening", which is the question a timetable can be
	fixed from."""
	gap = forecast._headway({"visits": 400, "headway_p50": 600, "headway_p85": 900})
	# Half the median is well inside the low tail of a gap that spreads from
	# ten minutes to fifteen.
	assert forecast._chance_under(gap, 300) == pytest.approx(15, abs=5)
	assert forecast._chance_under(gap, 600) == pytest.approx(50, abs=1)


def test_bunching_is_measured_against_the_lines_own_headway(forecast):
	"""Four minutes is a disaster on a ninety second metro and unremarkable on
	an hourly rural bus, so the threshold is a share of the median rather than
	a number of seconds."""
	assert 0 < forecast.BUNCHED_SHARE < 1


def test_a_gap_with_no_spread_yields_no_chance_of_collapsing(forecast):
	"""The same refusal `_sigma` makes: every gap landing on one number means
	too little data far more often than it means a perfect timetable."""
	flat = forecast._headway({"visits": 400, "headway_p50": 600, "headway_p85": 600})
	assert forecast._chance_under(flat, 300) is None


def test_the_low_tail_is_its_own_arithmetic_and_not_one_minus_the_high_one(forecast):
	"""Read as `100 - _chance_over` this is right only while the distribution
	is symmetric, and the moment somebody changes the approximation it becomes
	a silent bug in whichever of the two nobody was looking at."""
	import ast
	import inspect

	body = ast.parse(inspect.getsource(forecast._chance_under).lstrip())
	called = {
		ast.unparse(node.func) for node in ast.walk(body) if isinstance(node, ast.Call)
	}
	assert "_chance_over" not in called, called


def test_a_dwell_is_a_distribution_like_everything_else(forecast):
	"""§7a point 6, and what makes point 1 accurate rather than merely present:
	an arrival is when the doors open, and a stop where a vehicle usually
	stands thirty seconds and sometimes two minutes is the difference between
	catching a connection and missing it."""
	one = forecast._reading(
		[{"visits": 200, "dwell_p50": 30, "dwell_p85": 120, "dwell_avg": 45}],
		"dwell",
	)
	assert (one["p50"], one["p85"]) == (30, 120)
	assert not one["learning"]
