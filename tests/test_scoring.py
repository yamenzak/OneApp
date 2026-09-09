"""A forecast nobody scores is a decoration.

The thing worth defending here is not the arithmetic, which is a mean and a
median. It is the shape: a prediction is written down *before* the answer
exists, and the pass that checks it never recomputes it. The tempting design —
a nightly job that recomputes yesterday's forecast and compares it against
yesterday — needs no table and is worthless, because the history it would
forecast from contains the day being judged. It asks a model whether it agrees
with itself and it always does.

So one of these tests reads the source. That is unusual and it is the right tool
for this one property: the failure it prevents is not a wrong number, it is a
number that is right for the wrong reason and looks excellent for ever.
"""

import ast
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import where

ROOT = Path(where.__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/onemobility/scoring.py"
HOOKS = ROOT / "apps/oneapp/oneapp/hooks.py"


@pytest.fixture
def scoring(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import scoring as module

	return module


def claim(about, error, inside, line="U6"):
	"""One settled row, as `accuracy` reads it back."""
	return {
		"about": about,
		"line": line,
		"error_s": error,
		"inside": inside,
		"scored_at": datetime.now(),
	}


def settled(scoring, rows):
	"""Answer `accuracy` off a fixed set of rows, with no database."""
	from oneapp.shared import facts

	facts.exists = lambda fact: True
	facts.rows_between = lambda fact, start, end, where=None: rows
	return scoring.accuracy()


def test_the_headline_is_the_band_and_not_the_error(scoring, stub_frappe):
	"""Whether what happened landed inside the range that was offered. A
	forecast that is confidently wrong and one that is uncertain and right have
	similar errors and are not the same product."""
	day = datetime.now() - timedelta(days=2)
	out = settled(scoring, [
		claim(day, 30, 1), claim(day, 900, 0), claim(day, 10, 1), claim(day, 20, 1),
	])
	assert out["scored"] == 4
	assert out["inside_pct"] == 75.0


def test_the_typical_error_is_a_median(scoring, stub_frappe):
	"""One line that was catastrophically wrong on one hour is a finding, not a
	reason to describe every other hour as worse than it was. A mean here would
	let a single outlier decide the number a customer reads."""
	day = datetime.now() - timedelta(days=2)
	out = settled(scoring, [
		claim(day, 10, 1), claim(day, 20, 1), claim(day, 30, 1), claim(day, 9000, 0),
	])
	assert out["typical_error_s"] == 30


def test_an_error_is_scored_on_its_size_either_way(scoring, stub_frappe):
	"""Early and late are opposite failures and both are wrong. Signed errors
	averaged together cancel, and a forecaster that is ten minutes out in both
	directions scores perfectly."""
	day = datetime.now() - timedelta(days=2)
	out = settled(scoring, [claim(day, -600, 0), claim(day, 600, 0)])
	assert out["typical_error_s"] == 600


def test_nothing_scored_yet_is_not_a_score_of_zero(scoring, stub_frappe):
	"""A workspace switched on this week has claims and no answers. Reporting
	nought percent would say the forecast is bad; it is saying nothing yet."""
	day = datetime.now() - timedelta(days=2)
	unscored = {**claim(day, None, None), "scored_at": None}
	for rows in ([], [unscored]):
		out = settled(scoring, rows)
		assert out["scored"] == 0
		assert out["inside_pct"] is None
		assert out["typical_error_s"] is None


def test_the_worst_lines_come_first_and_carry_their_count(scoring, stub_frappe):
	"""Ranked by how often the band held, ascending — this is a list somebody
	reads the top of. And with the count beside it, because "nought percent of
	two" is not the same finding as "nought percent of four hundred"."""
	day = datetime.now() - timedelta(days=2)
	out = settled(scoring, [
		claim(day, 10, 1, "U1"), claim(day, 10, 1, "U1"),
		claim(day, 900, 0, "U6"), claim(day, 10, 1, "U6"),
	])
	assert [one["label"] for one in out["worst"]] == ["U6", "U1"]
	assert out["worst"][0]["value"] == 50.0
	assert out["worst"][0]["scored"] == 2


def test_the_history_is_kept_by_day(scoring, stub_frappe):
	"""One figure cannot show the day a line was rerouted and this stopped
	working, which is the whole reason to keep a record rather than a score."""
	first = datetime.now() - timedelta(days=3)
	second = datetime.now() - timedelta(days=2)
	out = settled(scoring, [
		claim(first, 10, 1), claim(first, 10, 1),
		claim(second, 900, 0), claim(second, 10, 1),
	])
	assert [one["value"] for one in out["by_day"]] == [100.0, 50.0]


def test_settling_never_recomputes_the_forecast(scoring):
	"""The property this module exists for, read off the source.

	`settle` may touch the prediction table and the roll-up and nothing else. If
	it ever calls `forecast`, it is comparing a claim against a claim made with
	the answer in hand, and the score becomes a measure of nothing that will
	look excellent for ever.
	"""
	tree = ast.parse(SOURCE.read_text())
	body = next(
		node for node in ast.walk(tree)
		if isinstance(node, ast.FunctionDef) and node.name == "settle"
	)
	called = {
		ast.unparse(node.func) for node in ast.walk(body) if isinstance(node, ast.Call)
	}
	assert not [one for one in called if one.startswith("forecast.")], called


def test_a_claim_is_made_from_history_that_stops_before_the_day(scoring):
	"""`claim` is allowed to use the forecast — that is what it is recording —
	but it must run for a day that has not happened. The nightly order settles
	first and claims second, and the comment in `nightly` says why."""
	tree = ast.parse(SOURCE.read_text())
	body = next(
		node for node in ast.walk(tree)
		if isinstance(node, ast.FunctionDef) and node.name == "nightly"
	)
	order = [
		ast.unparse(node.value.func)
		for node in ast.walk(body)
		if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)
	]
	assert order.index("settle") < order.index("claim")


def test_it_runs_after_the_roll_up_that_writes_what_it_scores(scoring):
	"""Registered last of the three, and the order is the whole of it: settling
	reads the aggregate row for yesterday, which `facts.sweep` writes."""
	nightly = [
		node for node in ast.walk(ast.parse(HOOKS.read_text()))
		if isinstance(node, ast.Assign)
		and any(getattr(t, "id", None) == "scheduler_events" for t in node.targets)
	]
	events = ast.literal_eval(nightly[0].value)["daily"]
	assert events.index("oneapp.shared.facts.sweep") < events.index(
		"oneapp.onemobility.scoring.nightly"
	)


def test_a_claim_nobody_could_have_made_is_not_recorded(scoring):
	"""Below the same floor `forecast` marks as learning. A claim resting on
	four readings, scored against reality, measures how little data there was."""
	from oneapp.onemobility import forecast

	assert scoring.ENOUGH == forecast.ENOUGH


def test_it_refuses_a_reader_who_cannot_see_a_line(scoring, stub_frappe):
	stub_frappe.has_permission = lambda *a, **k: False
	with pytest.raises(stub_frappe.PermissionError):
		scoring.accuracy()
