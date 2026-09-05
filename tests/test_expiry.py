"""A document that expires, and the warning before it does.

The rule is four lines and it is the whole point of the register, so it is
pinned here rather than trusted: a status that can be typed eventually says
Valid over a date in 2019, and a warning that goes out every morning is a
warning people filter into a folder.
"""

import pytest


@pytest.fixture
def rule(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core.doctype.compliance_document.compliance_document import standing

	return standing


TODAY = "2026-06-01"


def test_a_date_well_ahead_is_valid(rule):
	assert rule("2026-12-31", 30, TODAY) == "Valid"


def test_a_date_inside_the_window_is_expiring(rule):
	assert rule("2026-06-20", 30, TODAY) == "Expiring"


def test_the_edge_of_the_window_counts_as_expiring(rule):
	"""Thirty days' warning means the thirtieth day, not the twenty-ninth."""
	assert rule("2026-07-01", 30, TODAY) == "Expiring"


def test_the_day_after_the_window_is_still_valid(rule):
	assert rule("2026-07-02", 30, TODAY) == "Valid"


def test_today_is_not_yet_expired(rule):
	"""A licence is good until the end of the day it says."""
	assert rule("2026-06-01", 30, TODAY) == "Expiring"


def test_yesterday_is_expired(rule):
	assert rule("2026-05-31", 30, TODAY) == "Expired"


def test_no_date_is_not_the_same_as_expired(rule):
	"""A deed does not expire. A register that cried wolf over every one of
	them is a register nobody reads the real warnings in."""
	assert rule(None, 30, TODAY) == "No expiry"
	assert rule("", 30, TODAY) == "No expiry"


def test_no_window_still_warns_on_the_day(rule):
	"""Zero days' notice is a choice somebody can make, and it still has to
	report the day it lapses."""
	assert rule("2026-06-01", 0, TODAY) == "Expiring"
	assert rule("2026-06-02", 0, TODAY) == "Valid"


def test_a_missing_window_is_read_as_none_rather_than_raising(rule):
	assert rule("2026-12-31", None, TODAY) == "Valid"


def test_a_negative_window_cannot_reach_backwards(rule):
	"""Otherwise a typo turns the warning into a rule that hides expiries."""
	assert rule("2026-06-01", -90, TODAY) == "Expiring"


def test_the_sweep_only_warns_on_the_way_in(stub_frappe):
	"""The whole design of the daily job: a document is warned about when it
	crosses into Expiring, and again when it actually expires, and never on the
	mornings in between."""
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import expiry

	source = (
		__import__("pathlib").Path("apps/oneapp/oneapp/oneapp_core/expiry.py").read_text()
	)
	# `moved` is the guard, and it is what makes the warning once rather than
	# daily. Read out of the source because the alternative is a fake scheduler.
	assert "if now in (EXPIRING, EXPIRED) and moved:" in source
	assert expiry.LIMIT > 0


def test_the_statuses_sort_into_urgency():
	"""The compliance screen orders by `status`, and that is only right because
	the four words happen to sort that way.

	`expiry_date asc` cannot be used — SQL puts a null before every date, so the
	documents that never expire would head a list whose whole job is to show
	what expires next — and Frappe refuses a null-aware `order_by`. So the
	ordering rides on the names, which makes renaming one a silent change to
	what the register puts in front of somebody. Hence this.
	"""
	import json
	import pathlib

	schema = json.loads(pathlib.Path(
		"apps/oneapp/oneapp/oneapp_core/doctype/compliance_document/"
		"compliance_document.json"
	).read_text())
	options = next(f for f in schema["fields"] if f["fieldname"] == "status")["options"]
	words = options.split("\n")

	assert words == sorted(words), (
		"the compliance screen sorts by status and relies on these sorting into "
		f"urgency order; {words} does not"
	)
	# And the two that matter are the two at the top.
	assert words[:2] == ["Expired", "Expiring"]
