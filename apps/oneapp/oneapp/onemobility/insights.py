"""The aggregate tier, read forwards.

Every number on the Insights screen comes out of `serviceHour` — the tier the
nightly roll-up writes and nothing ever deletes. No model is fitted and nothing
is predicted in the machine-learning sense: what a Tuesday at eight looks like
*is* every Tuesday at eight that has already happened, and saying so is both
more useful to a scheduler and more defensible to a regulator than a number a
model produced. See `README.md` §7a.

One shaping, on the server, for the same reason `onespace/dashboard.py` shapes
its widgets there: the same aggregate feeds a headline figure and a plot, and
two shapings of one answer is how a dashboard comes to disagree with itself.

The one number that is not from the aggregate tier is punctuality, because
"within five minutes" is a threshold and an average of averages cannot answer
it. That one reads `observation` over the hot window, and says so.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from ..shared import facts
from . import model

#: Late enough to be late, and early enough to be early. The European
#: convention a transport authority already reports against: a minute early or
#: five minutes late is on time, and either side of that is not.
EARLY_S = -60
LATE_S = 300

#: Monday first, because a service week does — and because `live.record` stores
#: `dow` as Python's `date.weekday()`, which is Monday zero. Indexed by that
#: number directly, so the two must not drift apart.
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _window(days_back) -> tuple:
	end = getdate() + timedelta(days=1)
	return end - timedelta(days=max(1, min(cint(days_back) or 30, 400))), end


def _guard():
	if not frappe.has_permission("Transit Line", "read"):
		frappe.throw(_("You cannot read this."), frappe.PermissionError)


@frappe.whitelist(methods=["GET"])
def rhythm(line: str = "", days_back: int = 30) -> dict:
	"""What this network does over a day and over a week.

	Four series and four headline figures, all from the same query, because
	asking four times would be four chances for them to disagree about which
	rows they counted.
	"""
	_guard()
	start, end = _window(days_back)
	empty = {
		"headline": [],
		"by_hour": [],
		"load_by_hour": [],
		"week": [],
		"by_line": [],
		"from": str(start),
		"to": str(end),
		"lines": _lines(),
	}
	if not facts.exists(model.SERVICE_HOUR):
		return empty

	where = {"line": line} if line else None
	hours = facts.aggregate(
		model.SERVICE_HOUR,
		start=start, end=end,
		group=["hour", "dow"],
		measures={
			"readings": ("sum", "readings"),
			"delay_avg": ("avg", "delay_avg"),
			"delay_max": ("max", "delay_max"),
			"occupancy_avg": ("avg", "occupancy_avg"),
		},
		where=where,
	)
	if not hours:
		return empty

	return {
		"headline": _headline(hours, line, start, end),
		"by_hour": _fold(hours, "delay_avg"),
		"load_by_hour": _fold(hours, "occupancy_avg"),
		"week": _week(hours),
		"by_line": _by_line(start, end),
		"from": str(start),
		"to": str(end),
		"lines": _lines(),
	}


def _lines() -> list[dict]:
	"""Which lines there are to choose between. Cheap, and the screen needs it."""
	return frappe.get_all(
		"Transit Line",
		filters={"status": ("!=", "Retired")},
		fields=["name", "short_name", "line_name"],
		order_by="short_name asc",
		limit_page_length=0,
	)


def _label(hour) -> str:
	return f"{cint(hour):02d}:00"


def _fold(rows: list[dict], measure: str) -> list[dict]:
	"""One value per hour of the day, weighted by how much was seen in it.

	Weighted and not a plain mean, because an hour with four readings and an
	hour with four thousand are not the same evidence and a straight average
	lets the quiet one shout as loudly as the busy one.
	"""
	totals: dict[int, list] = {}
	for row in rows:
		hour = cint(row.get("hour"))
		weight = flt(row.get("readings")) or 1
		value = flt(row.get(measure))
		carried = totals.setdefault(hour, [0.0, 0.0])
		carried[0] += value * weight
		carried[1] += weight

	return [
		{"label": _label(hour), "value": round(carried[0] / carried[1], 1) if carried[1] else 0}
		for hour, carried in sorted(totals.items())
	]


def _week(rows: list[dict]) -> list[dict]:
	"""Hour against weekday, which is the shape of a heatmap and of a timetable.

	The most quietly useful plot in the product: a Saturday afternoon peak that
	no weekday has is a bus nobody scheduled, and it is visible here in a
	second and nowhere else at all.
	"""
	cells: dict[tuple, list] = {}
	for row in rows:
		key = (cint(row.get("dow")), cint(row.get("hour")))
		weight = flt(row.get("readings")) or 1
		carried = cells.setdefault(key, [0.0, 0.0])
		carried[0] += flt(row.get("occupancy_avg")) * weight
		carried[1] += weight

	out = []
	for (dow, hour), carried in sorted(cells.items()):
		if not 0 <= dow < len(WEEKDAYS):
			continue
		out.append(
			{
				"label": _label(hour),
				"series": _(WEEKDAYS[dow]),
				"value": round(carried[0] / carried[1], 1) if carried[1] else 0,
			}
		)
	return out


def _by_line(start, end) -> list[dict]:
	"""Average lateness per line, worst first. Always every line, never one.

	Deliberately not filtered by the screen's line selector: this is the plot
	somebody looks at to decide *which* line to select, and one bar is not a
	comparison.
	"""
	rows = facts.aggregate(
		model.SERVICE_HOUR,
		start=start, end=end,
		group=["line"],
		measures={"delay_avg": ("avg", "delay_avg"), "readings": ("sum", "readings")},
	)
	named = {
		one["name"]: one["short_name"] or one["name"]
		for one in frappe.get_all("Transit Line", fields=["name", "short_name"], limit_page_length=0)
	}
	out = [
		{
			"label": named.get(row.get("line"), row.get("line") or ""),
			"value": round(flt(row.get("delay_avg")) / 60, 1),
		}
		for row in rows
		if row.get("line")
	]
	out.sort(key=lambda one: one["value"], reverse=True)
	return out[:20]


def _headline(hours: list[dict], line: str, start, end) -> list[dict]:
	"""The four figures across the top, in the order somebody reads them."""
	readings = sum(cint(row.get("readings")) for row in hours)
	weighted = sum(flt(row.get("delay_avg")) * (flt(row.get("readings")) or 1) for row in hours)
	weight = sum(flt(row.get("readings")) or 1 for row in hours)

	busiest = max(hours, key=lambda row: flt(row.get("occupancy_avg") or 0), default=None)

	return [
		{"label": _("Readings"), "value": readings},
		{
			"label": _("Average delay"),
			"value": round((weighted / weight) / 60, 1) if weight else 0,
			"suffix": _(" min"),
		},
		{"label": _("On time"), "value": _punctual(line, start, end), "suffix": "%"},
		{
			"label": _("Busiest hour"),
			"value": _label(busiest.get("hour")) if busiest else "—",
		},
	]


def _punctual(line: str, start, end) -> float:
	"""The share of readings inside the on-time window.

	A threshold, so it cannot come from the aggregate tier: an average delay of
	zero is equally a service that is always punctual and one that is five
	minutes early half the time and five late the other half, and those are not
	the same railway. This reads the observations, and therefore only reaches
	as far back as the hot window does — which is said on the screen.
	"""
	if not facts.exists(model.OBSERVATION):
		return 0

	clauses = ["`at` >= %s", "`at` < %s", "`delay_s` IS NOT NULL"]
	values = [start, end]
	if line:
		clauses.append("`line` = %s")
		values.append(line)

	row = frappe.db.sql(
		f"""SELECT COUNT(*) AS seen,
		           SUM(CASE WHEN `delay_s` BETWEEN %s AND %s THEN 1 ELSE 0 END) AS punctual
		    FROM `{model.OBSERVATION.table}` WHERE {' AND '.join(clauses)}""",
		(EARLY_S, LATE_S, *values),
		as_dict=True,
	)
	seen = cint(row and row[0].get("seen"))
	return round(100.0 * cint(row[0].get("punctual")) / seen, 1) if seen else 0
