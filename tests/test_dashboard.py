"""The dashboard view: what a manifest may declare, and what it computes to.

Two things are worth pinning and they are different in kind. The vocabulary is
closed, so a manifest that names a chart nobody built, an aggregate nobody
implements or a field the screen does not offer has to be *dropped* rather than
passed through to a browser that will draw an empty box. And the shaping is one
answer for nine charts, so a bug in it is a bug in all of them at once.

What is not tested here is the SQL. Every widget is one `frappe.get_list` with
the screen's own filters, as the person asking — there is no query of ours to
be wrong, which is the point of computing it that way.
"""

import pathlib
import re

import pytest
import components


@pytest.fixture
def dashboard(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]

	from oneapp.oneapp_core import dashboard as module

	return module


OFFERED = {"status", "priority", "date", "amount", "owner"}


# --- the vocabulary --------------------------------------------------------


def test_a_widget_naming_a_chart_nobody_built_is_dropped(dashboard):
	assert dashboard.shape([{"kind": "treemap", "label": "x"}], OFFERED) == []
	assert dashboard.shape([{"kind": "", "label": "x"}], OFFERED) == []
	assert dashboard.shape("not a list", OFFERED) == []


def test_a_widget_naming_a_field_the_screen_does_not_offer_is_dropped(dashboard):
	"""Dropped whole, not narrowed.

	Every fieldname here reaches a `GROUP BY`. Keeping the parts that happened
	to be valid would draw a chart of something nobody asked for, which is
	worse than drawing nothing — a reader cannot tell the difference.
	"""
	assert dashboard.shape(
		[{"kind": "bar", "label": "x", "group_by": "secret"}], OFFERED
	) == []
	# And the same for the measure.
	assert dashboard.shape(
		[{"kind": "number", "label": "x", "aggregate": "sum", "field": "secret"}],
		OFFERED,
	) == []


def test_an_aggregate_that_measures_something_needs_something_to_measure(dashboard):
	"""`count` counts rows. The other four are meaningless without a field, and
	a manifest that omits one has declared a widget that would draw nothing."""
	for aggregate in dashboard.NEEDS_FIELD:
		assert dashboard.shape(
			[{"kind": "number", "label": "x", "aggregate": aggregate}], OFFERED
		) == [], aggregate

	# And a field alongside `count` is dropped rather than obeyed: somebody
	# expecting "count of distinct" is asking a different question.
	found = dashboard.shape(
		[{"kind": "number", "label": "x", "aggregate": "count", "field": "status"}],
		OFFERED,
	)
	assert found[0]["field"] == ""


def test_every_kind_declares_what_it_cannot_be_drawn_without(dashboard):
	"""A heatmap with one grouping is a bar chart with extra steps, and a
	scatter needs two measures rather than a category. Each kind names its own
	required keys, and a widget missing one is dropped."""
	assert dashboard.shape(
		[{"kind": "heatmap", "label": "x", "group_by": "status"}], OFFERED
	) == []
	assert dashboard.shape(
		[{"kind": "scatter", "label": "x", "x_field": "amount"}], OFFERED
	) == []
	assert len(dashboard.shape(
		[{"kind": "scatter", "label": "x", "x_field": "amount", "y_field": "amount"}],
		OFFERED,
	)) == 1


def test_a_widget_filter_may_only_name_a_field_the_screen_offers(dashboard):
	found = dashboard.shape(
		[{
			"kind": "number", "label": "Open", "aggregate": "count",
			"filters": {"status": "Open", "secret": "yes"},
		}],
		OFFERED,
	)
	assert found[0]["filters"] == {"status": "Open"}


def test_a_width_outside_the_grid_falls_back_rather_than_breaking_it(dashboard):
	"""The browser lays these out on twelve columns with written-out classes —
	Tailwind emits no CSS for a class it cannot see — so a width of 7 has no
	span to be and would silently be full width."""
	found = dashboard.shape(
		[{"kind": "number", "label": "x", "width": 7},
		 {"kind": "number", "label": "y", "width": 4}],
		OFFERED,
	)
	assert [one["width"] for one in found] == [dashboard.DEFAULT_WIDTH, 4]


def test_a_dashboard_stops_somewhere(dashboard):
	"""Each widget is a query. A screen that wants thirty wants a report."""
	asked = [{"kind": "number", "label": f"n{i}"} for i in range(40)]
	assert len(dashboard.shape(asked, OFFERED)) == dashboard.WIDGETS


# --- the shaping -----------------------------------------------------------


def test_a_count_is_a_whole_number(dashboard):
	"""MySQL returns COUNT as a float, and a card that should say 41 said
	"41.0". Whole numbers stay whole; the rounding is for a SUM of currency,
	which prints eleven decimal places in binary floating point."""
	assert dashboard._number(41.0) == 41
	assert dashboard._number(41) == 41
	assert dashboard._number(1 / 3) == 0.333333
	assert dashboard._number(None) == 0
	# A date, which MIN and MAX return and no chart can plot.
	assert dashboard._number("2026-01-01") == "2026-01-01"


def test_a_row_with_no_grouping_value_is_a_bucket_and_not_a_gap(dashboard):
	"""Rows with no status are still rows. Dropping them makes the totals
	disagree with the list beside them, which is the one thing a dashboard
	must not do."""
	assert dashboard._label(None) == "None"
	assert dashboard._label("") == "None"
	assert dashboard._label(" Open ") == "Open"


@pytest.mark.parametrize(
	"grain,expected",
	[("day", "2026-03-09"), ("week", "2026-W11"), ("month", "2026-03"), ("year", "2026")],
)
def test_time_is_bucketed_in_python_because_sql_will_not(dashboard, grain, expected):
	"""Frappe refuses a SQL function in `group_by` — `DATE(creation)` comes
	back as "Unsupported function or operator" — so a grained widget fetches
	the column and buckets here. ISO weeks, so a week is the same seven days
	whoever is reading it."""
	assert dashboard._bucket("2026-03-09", grain) == expected
	assert dashboard._bucket(None, grain) is None


@pytest.mark.parametrize(
	"aggregate,expected",
	[("count", 3), ("sum", 12), ("avg", 4), ("min", 2), ("max", 6)],
)
def test_a_bucket_folds_the_same_five_ways_sql_would(dashboard, aggregate, expected):
	assert dashboard._fold([2, 4, 6], aggregate) == expected
	# An empty bucket is zero rather than an error: a month with no rows in it
	# is a real answer.
	assert dashboard._fold([], aggregate) == 0


def test_a_widget_filter_narrows_and_never_widens(dashboard):
	"""The screen's filters are what make it that screen. A widget's own are
	rows *on top of* them, so a widget cannot count what the screen excludes."""
	assert dashboard._own({"filters": {"status": "Open"}}) == [["status", "=", "Open"]]
	assert dashboard._own({}) == []


def test_the_measure_is_a_dict_because_frappe_refuses_the_string(dashboard):
	"""`count(name) as value` is rejected — "SQL functions are not allowed as
	strings in SELECT" — and building the string ourselves would be building
	SQL out of a manifest."""
	assert dashboard._measure({"aggregate": "count", "field": ""}) == {
		"COUNT": "name", "as": "value",
	}
	assert dashboard._measure({"aggregate": "sum", "field": "amount"}) == {
		"SUM": "amount", "as": "value",
	}


# --- the two halves agree --------------------------------------------------


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPA = ROOT / "apps/oneapp/frontend/src"


def test_every_kind_names_a_chart_frappe_ui_actually_exports():
	"""The server names the component and the browser looks it up. A name that
	is not in frappe-ui's own charts entry point is a widget that renders as
	the "not built" card for ever, with nothing failing."""
	charts = (
		ROOT
		/ "apps/oneapp/frontend/node_modules/frappe-ui/src/charts/index.ts"
	)
	if not charts.is_file():
		pytest.skip("frappe-ui not installed")

	exported = set(re.findall(r"export \{ default as (\w+)", charts.read_text()))
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/dashboard.py").read_text()
	named = set(re.findall(r'"component": "(\w+)"', source))

	assert named, "the KINDS reader matched nothing"
	assert not named - exported, (
		f"the dashboard names charts frappe-ui does not export: "
		f"{sorted(named - exported)}"
	)


def test_the_browser_can_draw_every_kind_the_server_offers():
	"""The other half of the same rule: a component frappe-ui exports and our
	widget does not import is one the server will happily name."""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/dashboard.py").read_text()
	named = set(re.findall(r'"component": "(\w+)"', source))
	widget = components.source("DashboardWidget.vue")
	lookup = widget.split("const COMPONENTS = {")[1].split("}")[0]
	known = set(re.findall(r"^\s*(\w+),", lookup, re.M))

	assert not named - known, (
		f"DashboardWidget cannot draw {sorted(named - known)}"
	)


def test_every_width_the_server_allows_has_a_class_the_browser_emits():
	"""Tailwind only emits CSS for class names it can see written out, so
	`md:col-span-${n}` compiles to nothing and every widget sits full width
	with no error anywhere."""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/dashboard.py").read_text()
	widths = re.search(r"WIDTHS = \(([\d, ]+)\)", source).group(1)
	allowed = {int(one) for one in widths.replace(" ", "").strip(",").split(",")}

	body = components.source("DashboardBody.vue")
	written = {int(one) for one in re.findall(r"^\s*(\d+): 'md:col-span-\d+',", body, re.M)}

	assert allowed == written, (
		f"the server allows {sorted(allowed)} and the grid draws {sorted(written)}"
	)
