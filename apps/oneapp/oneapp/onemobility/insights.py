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
from . import facets as facetlib
from . import model
from . import network as networklib

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
def rhythm(facets: str = "", days_back: int = 30) -> dict:
	"""What this network does over a day and over a week.

	Four series and four headline figures, all from the same query, because
	asking four times would be four chances for them to disagree about which
	rows they counted.

	`serviceHour` is per line and per hour, so a vehicle or a stop chosen in
	the facet bar cannot narrow this — that comes back in `unavailable` and the
	screen greys the chip rather than quietly answering a different question.
	`fleet()` and `stops()` are where those two are answerable.
	"""
	_guard()
	start, end = _window(days_back)
	where, unavailable = facetlib.resolve(model.SERVICE_HOUR, facets)
	empty = {
		"headline": [],
		"by_hour": [],
		"load_by_hour": [],
		"service_by_hour": [],
		"week": [],
		"by_line": [],
		"punctuality": [],
		"spread": [],
		"from": str(start),
		"to": str(end),
		"unavailable": unavailable,
	}
	if not facts.exists(model.SERVICE_HOUR):
		return empty

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

	# The observation tier can take every facet this one cannot, so punctuality
	# and the spread are resolved against it separately rather than inheriting
	# a `where` built for a table with different columns.
	hot, _ignored = facetlib.resolve(model.OBSERVATION, facets)
	punctuality = _punctuality(hot, start, end)
	return {
		"headline": _headline(hours, punctuality),
		"punctuality": punctuality["split"],
		# What the average hides. See `_spread`.
		"spread": _spread(hot, start, end),
		"by_hour": _fold(hours, "delay_avg"),
		"load_by_hour": _fold(hours, "occupancy_avg"),
		# How much *service* there is in each hour, which is a different
		# question from how full it was and is the one the scrubber's track
		# draws: an operator dragging through a day should be able to see where
		# the day has something in it before they let go.
		"service_by_hour": _service(hours),
		"week": _week(hours),
		"by_line": _by_line(start, end),
		"from": str(start),
		"to": str(end),
		"unavailable": unavailable,
	}


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


def _service(rows: list[dict]) -> list[dict]:
	"""Readings per hour of the day, summed over every day in the window."""
	totals: dict[int, int] = {}
	for row in rows:
		hour = cint(row.get("hour"))
		totals[hour] = totals.get(hour, 0) + cint(row.get("readings"))
	return [{"label": _label(hour), "hour": hour, "value": total}
	        for hour, total in sorted(totals.items())]


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
	named = networklib.line_names()
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


def _headline(hours: list[dict], punctuality: dict) -> list[dict]:
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
		{"label": _("On time"), "value": punctuality["share"], "suffix": "%"},
		{
			"label": _("Busiest hour"),
			"value": _label(busiest.get("hour")) if busiest else "—",
		},
	]


def _punctuality(where: dict, start, end) -> dict:
	"""How the readings fall either side of the on-time window.

	A threshold, so it cannot come from the aggregate tier: an average delay of
	zero is equally a service that is always punctual and one that is five
	minutes early half the time and five late the other half, and those are not
	the same railway. This reads the observations, and therefore only reaches
	as far back as the hot window does — which is said on the screen.

	Three counts rather than one percentage, because early and late are
	opposite failures with opposite fixes — a bus running early has left a stop
	before people got to it — and a single "on time" figure hides which one a
	network has.
	"""
	empty = {"share": 0, "split": []}
	if not facts.exists(model.OBSERVATION):
		return empty

	clauses = ["`at` >= %s", "`at` < %s", "`delay_s` IS NOT NULL"]
	values = [start, end]
	facetlib.narrow(clauses, values, where)

	row = frappe.db.sql(
		f"""SELECT COUNT(*) AS seen,
		           SUM(CASE WHEN `delay_s` < %s THEN 1 ELSE 0 END) AS early,
		           SUM(CASE WHEN `delay_s` BETWEEN %s AND %s THEN 1 ELSE 0 END) AS punctual,
		           SUM(CASE WHEN `delay_s` > %s THEN 1 ELSE 0 END) AS late
		    FROM `{model.OBSERVATION.table}` WHERE {' AND '.join(clauses)}""",
		(EARLY_S, EARLY_S, LATE_S, LATE_S, *values),
		as_dict=True,
	)
	seen = cint(row and row[0].get("seen"))
	if not seen:
		return empty

	found = row[0]
	return {
		"share": round(100.0 * cint(found.get("punctual")) / seen, 1),
		"split": [
			{"label": _("Early"), "value": cint(found.get("early"))},
			{"label": _("On time"), "value": cint(found.get("punctual"))},
			{"label": _("Late"), "value": cint(found.get("late"))},
		],
	}


# --------------------------------------------------------------------------- #
# What an average hides
# --------------------------------------------------------------------------- #

#: The buckets a delay falls into, as `(floor_seconds, label)`. Read forwards:
#: a reading is in the last bucket whose floor it clears.
#:
#: Uneven on purpose. Lateness is not symmetric — a minute early and a minute
#: late are different failures, and the tail that matters is on one side — so
#: even buckets would spend half their resolution on a range almost nothing
#: falls in and lump every serious failure into one bar at the end.
DELAY_BANDS = (
	(-10_000, lambda: _("More than 5 min early")),
	(-300, lambda: _("1–5 min early")),
	(-60, lambda: _("On the timetable")),
	(300, lambda: _("Up to 5 min late")),
	(600, lambda: _("5–10 min late")),
	(1200, lambda: _("10–20 min late")),
	(1800, lambda: _("More than 20 min late")),
)


def _spread(where: dict, start, end) -> list[dict]:
	"""How the lateness is distributed, not what it averages.

	The one plot on this screen that cannot be derived from any of the others,
	and the reason it is here: an average delay of ninety seconds is equally a
	service that is reliably a minute and a half late — annoying, plannable —
	and one that is on time four times in five and twenty minutes late on the
	fifth, which is the same number and a different railway. Nothing else on
	the screen can tell them apart.

	Bucketed in SQL with a CASE rather than fetched and counted in Python: the
	observation tier is millions of rows over a month and this has to stay one
	pass.
	"""
	if not facts.exists(model.OBSERVATION):
		return []

	clauses = ["`at` >= %s", "`at` < %s", "`delay_s` IS NOT NULL"]
	values = [start, end]
	facetlib.narrow(clauses, values, where)

	picked = []
	for at, (floor, _label) in enumerate(DELAY_BANDS):
		ceiling = DELAY_BANDS[at + 1][0] if at + 1 < len(DELAY_BANDS) else None
		test = f"`delay_s` >= {int(floor)}"
		if ceiling is not None:
			test += f" AND `delay_s` < {int(ceiling)}"
		picked.append(f"SUM(CASE WHEN {test} THEN 1 ELSE 0 END) AS `b{at}`")

	row = frappe.db.sql(
		f"SELECT {', '.join(picked)} FROM `{model.OBSERVATION.table}` "
		f"WHERE {' AND '.join(clauses)}",
		tuple(values),
		as_dict=True,
	)
	if not row:
		return []

	found = row[0]
	return [
		{"label": label(), "value": cint(found.get(f"b{at}"))}
		for at, (_floor, label) in enumerate(DELAY_BANDS)
	]


# --------------------------------------------------------------------------- #
# The fleet, which is a different question from the network
# --------------------------------------------------------------------------- #

#: How many vehicles or stops one ranking draws. Past this a chart is a table
#: drawn badly, and the answer wanted is a list view with a sort on it.
RANK = 20


@frappe.whitelist(methods=["GET"])
def fleet(facets: str = "", days_back: int = 30) -> dict:
	"""Every vehicle, ranked by how it actually ran.

	Off `vehicleDay`, which exists so this question survives the hot window:
	before it, "which of my buses runs late" could only be asked of the last
	thirty days of raw positions, and the answer a depot manager wants is over
	a season.

	Ranked on the 85th percentile of delay and not the mean, because a vehicle
	that is punctual four days in five and twenty minutes late on the fifth
	averages the same as one that is four minutes late every day, and only one
	of them has something wrong with it.
	"""
	_guard()
	start, end = _window(days_back)
	where, unavailable = facetlib.resolve(model.VEHICLE_DAY, facets)
	empty = {"vehicles": [], "reliability": [], "load": [], "unavailable": unavailable,
	         "from": str(start), "to": str(end)}
	if not facts.exists(model.VEHICLE_DAY):
		return empty

	rows = facts.aggregate(
		model.VEHICLE_DAY,
		start=start, end=end,
		group=["vehicle"],
		measures={
			"days": ("count", "*"),
			"readings": ("sum", "readings"),
			"delay_avg": ("avg", "delay_avg"),
			"delay_late": ("avg", "delay_p85"),
			"delay_max": ("max", "delay_max"),
			"occupancy_avg": ("avg", "occupancy_avg"),
			"occupancy_max": ("max", "occupancy_max"),
		},
		where=where,
	)
	if not rows:
		return empty

	named = {
		one["name"]: one["label"] or one["name"]
		for one in frappe.get_all(
			"Transit Vehicle", fields=["name", "label"], limit_page_length=0
		)
	}
	fleet_rows = [
		{
			"vehicle": row.get("vehicle") or "",
			"label": named.get(row.get("vehicle"), row.get("vehicle") or ""),
			"days": cint(row.get("days")),
			"readings": cint(row.get("readings")),
			"delay_avg": round(flt(row.get("delay_avg")) / 60, 1),
			"delay_late": round(flt(row.get("delay_late")) / 60, 1),
			"delay_max": round(flt(row.get("delay_max")) / 60, 1),
			"occupancy_avg": round(flt(row.get("occupancy_avg")), 1),
			"occupancy_max": cint(row.get("occupancy_max")),
		}
		for row in rows
		if row.get("vehicle")
	]
	fleet_rows.sort(key=lambda one: one["delay_late"], reverse=True)

	return {
		"vehicles": fleet_rows[:RANK],
		"reliability": [
			{"label": one["label"], "value": one["delay_late"]} for one in fleet_rows[:RANK]
		],
		# Lateness against load, one point per vehicle. The plot that answers
		# whether a full bus is a late bus — which is the operator's own
		# suspicion and is often wrong, because the cause is usually the road.
		"load": [
			{
				"label": one["label"],
				"x": one["occupancy_avg"],
				"y": one["delay_avg"],
				"value": one["readings"],
			}
			for one in fleet_rows
		],
		"unavailable": unavailable,
		"from": str(start),
		"to": str(end),
	}


# --------------------------------------------------------------------------- #
# The stops, which nothing could answer at all until `arrivals.py`
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def stops(facets: str = "", days_back: int = 30) -> dict:
	"""What each stop actually does: how often, how long, how evenly.

	Off `stopHour`, which is rolled from the visits `arrivals.py` infers — so
	every number here is derived from positions rather than reported by a feed,
	and none of them is a boarding. See that module for why not.

	`bunching` is the number worth the whole table. A ten minute timetable run
	as a pair four minutes apart and then a sixteen minute hole is on time by
	every average on this screen and unusable to the person at the stop; the
	85th percentile headway against the mean is where that becomes visible.
	"""
	_guard()
	start, end = _window(days_back)
	where, unavailable = facetlib.resolve(model.STOP_HOUR, facets)
	empty = {"stops": [], "busiest": [], "bunching": [], "by_hour": [],
	         "unavailable": unavailable, "from": str(start), "to": str(end)}
	if not facts.exists(model.STOP_HOUR):
		return empty

	rows = facts.aggregate(
		model.STOP_HOUR,
		start=start, end=end,
		group=["stop"],
		measures={
			"visits": ("sum", "visits"),
			"dwell_avg": ("avg", "dwell_avg"),
			"headway_avg": ("avg", "headway_avg"),
			"headway_late": ("avg", "headway_p85"),
			"delay_avg": ("avg", "delay_avg"),
			"occupancy_avg": ("avg", "occupancy_avg"),
		},
		where=where,
	)
	if not rows:
		return empty

	named = {
		one["name"]: one["stop_name"] or one["name"]
		for one in frappe.get_all(
			"Transit Stop", fields=["name", "stop_name"], limit_page_length=0
		)
	}
	stop_rows = [
		{
			"stop": row.get("stop") or "",
			"label": named.get(row.get("stop"), row.get("stop") or ""),
			"visits": cint(row.get("visits")),
			"dwell_avg": round(flt(row.get("dwell_avg")), 1),
			"headway_avg": round(flt(row.get("headway_avg")) / 60, 1),
			"headway_late": round(flt(row.get("headway_late")) / 60, 1),
			"delay_avg": round(flt(row.get("delay_avg")) / 60, 1),
			"occupancy_avg": round(flt(row.get("occupancy_avg")), 1),
		}
		for row in rows
		if row.get("stop")
	]

	busiest = sorted(stop_rows, key=lambda one: one["visits"], reverse=True)[:RANK]
	# How much worse the wait is than the timetable implies, in minutes. A stop
	# with no second vehicle has no headway at all and is not bunched — it is
	# unserved, which is a different finding and not this chart's.
	bunched = sorted(
		(one for one in stop_rows if one["headway_avg"] > 0),
		key=lambda one: one["headway_late"] - one["headway_avg"],
		reverse=True,
	)[:RANK]

	hours = facts.aggregate(
		model.STOP_HOUR,
		start=start, end=end,
		group=["hour"],
		measures={"visits": ("sum", "visits"), "occupancy_avg": ("avg", "occupancy_avg")},
		where=where,
	)

	return {
		"stops": stop_rows[:RANK],
		"busiest": [{"label": one["label"], "value": one["visits"]} for one in busiest],
		"bunching": [
			{
				"label": one["label"],
				"value": round(one["headway_late"] - one["headway_avg"], 1),
			}
			for one in bunched
		],
		"by_hour": [
			{"label": _label(row.get("hour")), "value": cint(row.get("visits"))}
			for row in sorted(hours, key=lambda row: cint(row.get("hour")))
		],
		"unavailable": unavailable,
		"from": str(start),
		"to": str(end),
	}
