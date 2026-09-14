"""Columns a screen says are words rather than records.

A Link is a foreign key and the engine draws one as a record — a face, a title,
an id underneath. That is right for a Link to a *record* and wrong for the ones
that are really categories, which is most of the Links on a doctype somebody
else designed: a Designation is a Link because ERPNext keeps a table of them,
not because anybody wants to open one.

Declared rather than guessed. Whether a Link is a category is a judgement about
the product, and a rule like "no title field means a category" is a guess that
is wrong on the first exception.
"""

import pytest

from test_screens import spaceview  # noqa: F401


def _resolved(columns):
	rows = [dict(one) for one in columns]
	return {"columns": rows, "all_columns": [dict(one) for one in rows]}


LINKED = [
	{"fieldname": "designation", "cell": "link"},
	{"fieldname": "employee_name", "cell": "text"},
	{"fieldname": "status", "cell": "badge"},
	{"fieldname": "ctc", "cell": "currency"},
	{"fieldname": "joined", "cell": "date"},
]


def _cells(resolved):
	return {c["fieldname"]: c["cell"] for c in resolved["columns"]}


def test_a_declared_column_becomes_a_tag(spaceview):  # noqa: F811
	resolved = _resolved(LINKED)
	spaceview._as_tags(resolved, ["designation", "employee_name", "status"])

	cells = _cells(resolved)
	assert cells["designation"] == "tag"
	assert cells["employee_name"] == "tag"
	assert cells["status"] == "tag"
	# And on both lists, because the record form reads the wider one and a
	# field drawn two ways on one screen is the bug this replaced.
	assert {c["fieldname"] for c in resolved["all_columns"] if c["cell"] == "tag"} == {
		"designation", "employee_name", "status",
	}


def test_a_column_nothing_can_tag_is_left_alone(spaceview):  # noqa: F811
	"""A currency drawn as a coloured pill is a number somebody has to decode,
	and a date is not a category however few of them there are."""
	resolved = _resolved(LINKED)
	spaceview._as_tags(resolved, ["ctc", "joined"])

	cells = _cells(resolved)
	assert cells["ctc"] == "currency"
	assert cells["joined"] == "date"


def test_a_fieldname_the_screen_does_not_carry_is_dropped(spaceview):  # noqa: F811
	"""The rule every shaper here follows: a settings blob somebody mistyped
	costs the drawing it describes and not the screen."""
	resolved = _resolved(LINKED)
	spaceview._as_tags(resolved, ["designtaion", "", None, 7])
	assert _cells(resolved) == {c["fieldname"]: c["cell"] for c in LINKED}


def test_nothing_at_all_is_not_an_error(spaceview):  # noqa: F811
	resolved = _resolved(LINKED)
	for asked in (None, "", {}, "designation", []):
		spaceview._as_tags(resolved, asked)
	assert _cells(resolved) == {c["fieldname"]: c["cell"] for c in LINKED}


def test_a_row_of_tags_is_capped(spaceview):  # noqa: F811
	"""Past a handful a row of badges is a row of noise, and the point of the
	colour is telling a few things apart."""
	columns = [{"fieldname": f"f{at}", "cell": "link"} for at in range(20)]
	resolved = _resolved(columns)
	spaceview._as_tags(resolved, [one["fieldname"] for one in columns])

	tagged = [c for c in resolved["columns"] if c["cell"] == "tag"]
	assert len(tagged) == spaceview.MOST_TAGS


def test_the_declaration_survives_the_view_settings_shaper(spaceview):  # noqa: F811
	"""`tags` is not a view type, so `_shaped` drops the block — which is right,
	because it is applied to the *columns* rather than carried for the browser
	to interpret. This is the guard that the dropping happens after the
	applying."""
	resolved = _resolved(LINKED)
	kept = spaceview._view_settings(resolved, {"tags": ["designation"]})

	assert "tags" not in kept, "a tags block reaching the browser is a second opinion"
	assert _cells(resolved)["designation"] == "tag"


def test_onehr_draws_its_categories_as_tags():
	"""The screen this was built for. `reports_to` is deliberately *not* in the
	list: it is a Link to a record somebody genuinely wants to open, and drawing
	it as a word would lose the face and the way through."""
	import importlib.util
	import json
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent
	path = root / "apps/oneapp_control/oneapp_control/spaces/onehr.py"
	spec = importlib.util.spec_from_file_location("tags_onehr", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)

	screen = next(one for one in module.SCREENS if one["screen"] == "people")
	settings = json.loads(screen["view_settings"])

	assert settings["tags"] == ["designation", "department", "branch"]
	assert "reports_to" not in settings["tags"]
