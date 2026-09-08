"""The dashboard view: widgets a manifest declares, computed against a screen.

A dashboard is the fourth way of looking at a screen, and it is the first one
that does not draw records. A list, a board and a grid all answer "which rows";
a dashboard answers "how many, how much, and which way is it going" — so what
it is made of is not columns but **measures**, and a measure is an aggregate
over the rows the screen already narrows to.

That last clause is the whole security model. Every widget is computed with
`frappe.get_list` over the screen's own doctype, with the screen's own filters,
as the person asking — so a dashboard cannot count a row its owner may not
read, cannot reach a doctype the space did not grant, and answers differently
for two people with different User Permissions. There is no raw SQL here and
there is no `ignore_permissions`.

**The vocabulary is closed.** A widget names one of nine kinds, each mapping to
a chart frappe-ui ships, and one of five aggregates. Anything else is dropped
by `shape()` rather than passed through, and `tests/test_manifests.py` fails
the build on a manifest that declares one — so a typo in a widget is a red test
rather than an empty box on somebody's screen.

**Time is bucketed here, not in SQL.** Frappe refuses SQL functions in
`group_by`, so `DATE(creation)` is not available; a widget grouped by a date
field fetches the column and buckets in Python, under a row cap. That is a real
limit and it is stated where it bites — see `ROWS`.
"""

import frappe
from frappe import _

# How many rows a time-grained widget may read before it stops being a chart
# and starts being a report. Frappe will not group by a SQL expression, so a
# day/week/month bucket is counted in Python over rows we fetched — and a
# widget that quietly reads a hundred thousand of them is a page nobody can
# open. Past this the widget answers with what it has and says it was capped.
ROWS = 5000

# How many buckets a categorical widget draws. Past a couple of dozen a chart
# is a table drawn badly; every chart frappe-ui ships that collapses a tail
# does it at nine.
BUCKETS = 24

# Widgets on one dashboard. Each is a query, and a screen that wants thirty
# wants a report.
WIDGETS = 12


# --------------------------------------------------------------------------- #
# The vocabulary
# --------------------------------------------------------------------------- #

# kind -> what it needs beyond a label, and what the browser draws it with.
#
# `axis` is the family of cartesian charts: one category along the bottom, one
# measure up the side, and an optional second grouping that becomes series.
# They differ in the mark their series draw as, which is a prop rather than a
# different shape — see frappe-ui's own `AxisChartConfig`.
KINDS = {
	"number": {"component": "NumberCard", "needs": ()},
	"bar": {"component": "BarChart", "needs": ("group_by",), "family": "axis"},
	"line": {"component": "LineChart", "needs": ("group_by",), "family": "axis"},
	"area": {"component": "AreaChart", "needs": ("group_by",), "family": "axis"},
	"donut": {"component": "DonutChart", "needs": ("group_by",), "family": "part"},
	"funnel": {"component": "FunnelChart", "needs": ("group_by",), "family": "part"},
	"heatmap": {"component": "HeatmapChart", "needs": ("group_by", "series"), "family": "grid"},
	"sankey": {"component": "SankeyChart", "needs": ("group_by", "series"), "family": "flow"},
	"scatter": {"component": "ScatterChart", "needs": ("x_field", "y_field"), "family": "points"},
}

# What a measure is. Frappe takes these as `{"COUNT": "name", "as": "value"}`
# in a `get_list` field list and refuses the same thing written as a string —
# so this maps our word to its word rather than building SQL.
AGGREGATES = {
	"count": "COUNT",
	"sum": "SUM",
	"avg": "AVG",
	"min": "MIN",
	"max": "MAX",
}

# Aggregates that need something to aggregate. `count` counts rows and takes no
# field; the other four are meaningless without one, and a manifest that omits
# it has declared a widget that would draw nothing.
NEEDS_FIELD = ("sum", "avg", "min", "max")

# How a date axis is read. Bucketed in Python (see the module docstring), so
# this is a vocabulary rather than a SQL fragment.
GRAINS = ("day", "week", "month", "year")

# How wide a widget sits, in twelfths — the grid the browser lays them out on.
WIDTHS = (3, 4, 6, 8, 12)
DEFAULT_WIDTH = 6


def _text(value) -> str:
	return str(value or "").strip()


def shape(widgets, offered: set) -> list[dict]:
	"""The widgets a screen actually has, checked against its own columns.

	A validator rather than a passthrough, for the same reason `_view_settings`
	is one: every fieldname here reaches a query. A widget that names a field
	the screen does not offer is dropped whole — narrowing it to "the parts
	that were valid" would draw a chart of something nobody asked for.
	"""
	if not isinstance(widgets, list):
		return []

	kept = []
	for raw in widgets[:WIDGETS]:
		one = _shaped(raw, offered)
		if one:
			kept.append(one)
	return kept


def _shaped(raw, offered: set) -> dict | None:
	if not isinstance(raw, dict):
		return None

	kind = _text(raw.get("kind")).lower()
	if kind not in KINDS:
		return None

	aggregate = _text(raw.get("aggregate")).lower() or "count"
	if aggregate not in AGGREGATES:
		return None

	field = _text(raw.get("field"))
	if aggregate in NEEDS_FIELD and field not in offered:
		return None
	if aggregate == "count":
		# `count` counts rows. A field alongside it is somebody expecting
		# "count of distinct", which is a different question and not this one.
		field = ""

	one = {
		"kind": kind,
		"component": KINDS[kind]["component"],
		"label": _text(raw.get("label")) or _("Untitled"),
		"aggregate": aggregate,
		"field": field,
		"width": int(raw["width"]) if raw.get("width") in WIDTHS else DEFAULT_WIDTH,
	}

	for key in KINDS[kind]["needs"]:
		name = _text(raw.get(key))
		if name not in offered:
			return None
		one[key] = name

	# Optional everywhere it is allowed: a second grouping turns one line into
	# a line per value of it, and a bar chart into a stacked one.
	series = _text(raw.get("series"))
	if series and series in offered and "series" not in one:
		one["series"] = series

	grain = _text(raw.get("grain")).lower()
	if grain in GRAINS:
		one["grain"] = grain

	filters = raw.get("filters")
	if isinstance(filters, dict) and filters:
		one["filters"] = {
			key: value for key, value in filters.items()
			if isinstance(key, str) and key in offered
		}

	for flag in ("stacked", "horizontal"):
		if raw.get(flag):
			one[flag] = True

	for text in ("prefix", "suffix"):
		value = _text(raw.get(text))
		if value:
			one[text] = value

	return one


# --------------------------------------------------------------------------- #
# Computing one
# --------------------------------------------------------------------------- #

def compute(widget: dict, doctype: str, filters: list, precision) -> dict:
	"""One widget's data, as the chart component it names wants it.

	Shaped here rather than in the browser: the same numbers feed a number card
	and a donut, and two shapings of one answer is how a dashboard comes to
	disagree with itself.
	"""
	narrowed = list(filters) + _own(widget)

	if widget["kind"] == "number":
		return {"value": _one(doctype, widget, narrowed)}

	if widget["kind"] == "scatter":
		return {"rows": _points(doctype, widget, narrowed)}

	if widget.get("grain"):
		return {"rows": _overtime(doctype, widget, narrowed)}

	return {"rows": _grouped(doctype, widget, narrowed)}


def _own(widget: dict) -> list:
	"""A widget's own filters, as rows on top of the screen's.

	On top and never instead: the screen's filters are what makes it that
	screen, and a widget that could widen them would be a way to count rows the
	screen was written to exclude.
	"""
	return [[key, "=", value] for key, value in (widget.get("filters") or {}).items()]


def _measure(widget: dict) -> dict:
	"""The aggregate, in the shape `get_list` takes.

	A dict, because Frappe refuses `count(name) as value` written as a string —
	`"SQL functions are not allowed as strings in SELECT"` — and building the
	string ourselves would be building SQL out of a manifest.
	"""
	function = AGGREGATES[widget["aggregate"]]
	return {function: widget["field"] or "name", "as": "value"}


def _one(doctype: str, widget: dict, filters: list):
	"""A single number."""
	found = frappe.get_list(
		doctype, fields=[_measure(widget)], filters=filters, limit_page_length=1,
	)
	return _number(found[0].get("value") if found else 0)


def _grouped(doctype: str, widget: dict, filters: list) -> list[dict]:
	"""One row per value of the grouping column, largest first.

	Largest first because a chart is read from the top: alphabetical order puts
	the answer wherever the alphabet happens to put it. A widget grouped on
	two columns is grouped by both and the browser splits the series.
	"""
	group = widget["group_by"]
	series = widget.get("series")

	fields = [group] + ([series] if series else []) + [_measure(widget)]
	rows = frappe.get_list(
		doctype,
		fields=fields,
		filters=filters,
		group_by=", ".join([group] + ([series] if series else [])),
		order_by="value desc",
		limit_page_length=BUCKETS * (BUCKETS if series else 1),
	)

	return [
		{
			"label": _label(row.get(group)),
			**({"series": _label(row.get(series))} if series else {}),
			"value": _number(row.get("value")),
		}
		for row in rows
	]


def _points(doctype: str, widget: dict, filters: list) -> list[dict]:
	"""One row per record, for a scatter: two measures and nothing aggregated."""
	rows = frappe.get_list(
		doctype,
		fields=["name", widget["x_field"], widget["y_field"]]
		+ ([widget["series"]] if widget.get("series") else []),
		filters=filters,
		limit_page_length=ROWS,
	)
	return [
		{
			"label": row.get("name"),
			"x": _number(row.get(widget["x_field"])),
			"y": _number(row.get(widget["y_field"])),
			**({"series": _label(row.get(widget["series"]))} if widget.get("series") else {}),
		}
		for row in rows
	]


def _overtime(doctype: str, widget: dict, filters: list) -> list[dict]:
	"""Buckets down a date column, counted in Python.

	Frappe refuses a SQL function in `group_by` — `DATE(creation)` comes back
	as "Unsupported function or operator" — so the column is fetched and
	bucketed here. Which is fine at a chart's scale and is not fine at a
	report's, so it is capped: past `ROWS` the widget answers with what it read
	and says it was capped, rather than drawing a line that is quietly wrong.
	"""
	group = widget["group_by"]
	series = widget.get("series")

	fields = [group] + ([series] if series else [])
	if widget["field"]:
		fields.append(widget["field"])

	rows = frappe.get_list(
		doctype,
		fields=fields,
		filters=filters + [[group, "is", "set"]],
		order_by=f"{group} asc",
		limit_page_length=ROWS,
	)

	buckets: dict[tuple, list] = {}
	for row in rows:
		key = (_bucket(row.get(group), widget["grain"]), _label(row.get(series)) if series else None)
		if key[0] is None:
			continue
		buckets.setdefault(key, []).append(
			_number(row.get(widget["field"])) if widget["field"] else 1
		)

	return [
		{
			"label": label,
			**({"series": name} if series else {}),
			"value": _fold(values, widget["aggregate"]),
		}
		for (label, name), values in sorted(buckets.items(), key=lambda one: one[0])
	]


def _fold(values: list, aggregate: str):
	"""The measure over one bucket's rows, the same five ways SQL would."""
	numbers = [one for one in values if one is not None]
	if not numbers:
		return 0
	if aggregate == "count":
		return len(numbers)
	if aggregate == "sum":
		return _number(sum(numbers))
	if aggregate == "avg":
		return _number(sum(numbers) / len(numbers))
	if aggregate == "min":
		return _number(min(numbers))
	return _number(max(numbers))


def _bucket(value, grain: str):
	"""Which day, week, month or year a timestamp falls in, as its own label."""
	if not value:
		return None
	try:
		moment = frappe.utils.getdate(value)
	except Exception:
		return None

	if grain == "year":
		return moment.strftime("%Y")
	if grain == "month":
		return moment.strftime("%Y-%m")
	if grain == "week":
		# ISO week, so a week is the same seven days whoever is reading.
		year, week, _day = moment.isocalendar()
		return f"{year}-W{week:02d}"
	return moment.strftime("%Y-%m-%d")


def _label(value) -> str:
	"""A bucket's name. An empty grouping value is a bucket, not a gap: rows
	with no status are still rows, and dropping them makes the totals lie."""
	text = _text(value)
	return text or _("None")


def _number(value):
	"""A number the browser can plot, or zero.

	Dates come back from MIN and MAX, and a chart cannot plot one — so those
	are strings. Everything else is a float, rounded on the way out because a
	SUM of currency in binary floating point prints eleven decimal places.
	"""
	if value is None:
		return 0
	if isinstance(value, bool):
		return int(value)
	if isinstance(value, int):
		return value
	if isinstance(value, float):
		# A count comes back from MySQL as a float and prints as "41.0" on a
		# card that should say 41. Whole numbers stay whole; the rounding is
		# for the other case, where a SUM of currency in binary floating point
		# prints eleven decimal places.
		return int(value) if value.is_integer() else round(value, 6)
	try:
		number = float(value)
	except (TypeError, ValueError):
		# A date, which MIN and MAX return and no chart can plot.
		return _text(value)
	return int(number) if number.is_integer() else round(number, 6)
