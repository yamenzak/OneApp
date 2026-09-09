"""Reading the aggregate tier forward.

**Prediction is not a subsystem here, it is a second reader of the roll-up.**
`serviceHour` and `stopHour` already hold what happened, per line, per stop, per
hour, per weekday — and that table *is* the model for everything in README §7a
worth predicting. Which is why this module is arithmetic and no more: a
percentile lookup, a normal tail, a z-score, a straight-line extrapolation.

That is not a limitation accepted reluctantly. Every number here is explainable
to a customer who does not trust software, costs nothing to compute, is correct
on a workspace with no AI credits, and cannot go subtly and unaccountably wrong
the way a fitted model can. For these questions it is simply the better
engineering, and the day it stops being enough will announce itself in the
scores rather than in a complaint.

Four things it answers, in the order they earn their place:

    expect      when a vehicle reaches a stop, as a range rather than a time
    outlook     what a future date looks like, hour by hour, with its spread
    risk        the same distribution stated as a probability, which is what an
                operator acts on
    unusual     what today is doing that its own history does not

Three rules hold across all four, and they are the difference between this being
useful and being a liability.

**Nothing is answered without saying what it rests on.** Every reading carries
`basis` — the number of observations behind it — and `learning` when that is too
few. A workspace switched on this morning has no distribution, so an ETA is the
timetable plus the current delay and the screen says exactly that. Software that
pretends to know is worse than software that says it is still learning.

**Nothing is answered without its spread.** There is no endpoint here that
returns a bare number. A confident wrong ETA costs more trust than no ETA, and
the way to not be confidently wrong is to be visibly uncertain.

**Nothing invents a dimension we do not measure.** There is no boarding forecast,
because §3b explains why there is no boarding figure. There is no what-if — "add
a bus at 07:00 and what happens to load" — because that needs a network model
rather than a history, and answering it from this data would be a guess wearing
a chart's clothes.
"""

from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from . import facets as facetlib
from . import model
from . import network as networklib
from ..shared import facts

#: How many readings a distribution needs before it is offered as one.
#:
#: Below this the answer is still given — refusing to answer is its own kind of
#: unhelpful — but it is marked `learning`, and every surface draws that
#: differently. Thirty is the conventional floor for treating a sample as one,
#: and it is about two days of one line in one hour on a feed that reports every
#: twenty seconds.
ENOUGH = 30

#: How far ahead this will look. Beyond a fortnight the honest answer is that a
#: timetable will have changed, and a forecast that ignores that is a forecast
#: about a network that will not exist.
HORIZON_DAYS = 14

#: What counts as late, matching `insights.py` so one screen cannot report a
#: punctuality the other contradicts.
LATE_S = 300

#: The spread between p50 and p95 of a normal distribution, in standard
#: deviations. Used to turn the two percentiles we store back into a sigma,
#: which is what a probability needs.
#:
#: Delay is not normally distributed — it has a long right tail and a hard-ish
#: floor, because a bus can be an hour late and not twenty minutes early — so
#: this is an approximation and is named as one. It is the right approximation
#: anyway: it is only ever used to turn a stored spread into a probability, the
#: answer is rounded to a percentage before anybody sees it, and the alternative
#: is keeping the whole histogram to gain a point of accuracy nobody can act on.
P95_SIGMAS = 1.6449


def _guard():
	if not frappe.has_permission("Transit Line", "read"):
		frappe.throw(_("You cannot read this."), frappe.PermissionError)


def _history(days_back: int = 90) -> tuple:
	"""How far back a distribution is built from.

	Ninety days rather than everything: a network is re-timetabled, a road is
	dug up, and a year-old distribution for a line that was rerouted in spring
	is not a weaker claim about today — it is a claim about a different line.
	"""
	end = getdate() + timedelta(days=1)
	return end - timedelta(days=max(7, min(cint(days_back) or 90, 400))), end


def _when(at: str = "") -> datetime:
	"""The moment being asked about. Empty means now."""
	if not at:
		return datetime.now()
	parsed = frappe.utils.get_datetime(at)
	if not parsed:
		frappe.throw(_("That is not a moment."))
	return parsed


def _horizon(when: datetime):
	"""Refuse a date this cannot honestly speak about.

	Past is fine and is not a forecast — it is what happened, and every screen
	here can draw it. The far future is refused rather than extrapolated,
	because the thing that changes over a fortnight is the timetable, and no
	amount of history sees that coming."""
	ahead = (getdate(when) - getdate()).days
	if ahead > HORIZON_DAYS:
		frappe.throw(
			_("This looks {0} days ahead at most — beyond that the timetable "
			  "itself will have changed.").format(HORIZON_DAYS)
		)


def _reading(rows: list[dict], measure: str) -> dict:
	"""One distribution, from however many rows matched.

	Rows are per line and per hour, so a question about a whole network in one
	hour gets several. They are combined by weight rather than averaged flat: a
	line with four thousand readings and one with forty do not have an equal say
	in what the network does, and a flat mean is how a rarely-observed line
	comes to dominate a headline figure.
	"""
	basis = sum(cint(row.get("readings") or row.get("visits") or 0) for row in rows)
	if not rows or not basis:
		return {"basis": 0, "learning": True, "p50": None, "p85": None, "p95": None}

	def weighted(field):
		total = 0.0
		weight = 0
		for row in rows:
			value = row.get(field)
			count = cint(row.get("readings") or row.get("visits") or 0)
			if value is None or not count:
				continue
			total += flt(value) * count
			weight += count
		return round(total / weight, 1) if weight else None

	return {
		"basis": basis,
		"learning": basis < ENOUGH,
		"p50": weighted(f"{measure}_p50"),
		"p85": weighted(f"{measure}_p85"),
		"p95": weighted(f"{measure}_p95"),
		"avg": weighted(f"{measure}_avg"),
	}


def _sigma(reading: dict) -> float | None:
	"""Turn a stored spread back into a standard deviation. See `P95_SIGMAS`."""
	if reading.get("p95") is None or reading.get("p50") is None:
		return None
	spread = flt(reading["p95"]) - flt(reading["p50"])
	return spread / P95_SIGMAS if spread > 0 else None


def _chance_over(reading: dict, threshold: float) -> float | None:
	"""The probability of exceeding a value, from a median and a spread.

	`math.erf` rather than a table or a dependency: the normal CDF is one line
	of the standard library, and a probability drawn to the nearest percent does
	not need more than that.
	"""
	import math

	sigma = _sigma(reading)
	if sigma is None or reading.get("p50") is None:
		return None
	z = (threshold - flt(reading["p50"])) / sigma
	return round((1 - 0.5 * (1 + math.erf(z / math.sqrt(2)))) * 100, 1)


@frappe.whitelist(methods=["GET"])
def outlook(facets: str = "", when: str = "", days_back: int = 90) -> dict:
	"""What a day looks like, hour by hour, with the spread it rests on.

	The same read whether the date is next Tuesday or last Tuesday, which is the
	honest shape: this is not a forecaster and a reporter bolted together, it is
	one lookup of "what does this network do on a Tuesday at nine", and whether
	that Tuesday has happened yet changes nothing about the arithmetic. What it
	changes is the label, and `ahead` says which it is.
	"""
	_guard()
	moment = _when(when)
	_horizon(moment)
	day = getdate(moment)
	start, end = _history(days_back)
	where, unavailable = facetlib.resolve(model.SERVICE_HOUR, facets)

	empty = {
		"hours": [],
		"day": str(day),
		"weekday": day.weekday(),
		"ahead": (day - getdate()).days,
		"from": str(start),
		"to": str(end),
		"unavailable": unavailable,
		"learning": True,
	}
	if not facts.exists(model.SERVICE_HOUR):
		return empty

	rows = facts.aggregate(
		model.SERVICE_HOUR,
		start=start, end=end,
		group=["hour", "line"],
		measures={
			"readings": ("sum", "readings"),
			"delay_avg": ("avg", "delay_avg"),
			"delay_p50": ("avg", "delay_p50"),
			"delay_p85": ("avg", "delay_p85"),
			"delay_p95": ("avg", "delay_p95"),
			"occupancy_avg": ("avg", "occupancy_avg"),
			"occupancy_p85": ("avg", "occupancy_p85"),
		},
		# The weekday is the whole point: a Tuesday is forecast from Tuesdays.
		# Reading a Saturday's demand off a week that is five sixths weekday is
		# the single most common way this kind of chart lies.
		where={**where, "dow": day.weekday()},
	)
	if not rows:
		return empty

	by_hour: dict[int, list] = {}
	for row in rows:
		by_hour.setdefault(cint(row["hour"]), []).append(row)

	hours = []
	for hour in sorted(by_hour):
		delay = _reading(by_hour[hour], "delay")
		load = _reading(by_hour[hour], "occupancy")
		hours.append({
			"hour": hour,
			"label": f"{hour:02d}:00",
			"delay": delay,
			"occupancy": load,
			"late_chance": _chance_over(delay, LATE_S),
			"basis": delay["basis"],
			"learning": delay["learning"],
		})

	return {
		**empty,
		"hours": hours,
		"learning": all(one["learning"] for one in hours),
	}


@frappe.whitelist(methods=["GET"])
def expect(stop: str, line: str = "", when: str = "", delay_s: int = 0,
           days_back: int = 90) -> dict:
	"""When a vehicle reaches this stop, as a range rather than a time.

	The honest first version, and it beats most fitted models: look up what the
	delay at *this stop* at *this hour* on *this weekday* has actually been, and
	offset it by the delay the vehicle is carrying right now. A vehicle already
	eight minutes down does not arrive at its historical median.

	It is a range because it is a distribution. `early` is the median, `likely`
	the p85, and the surface draws both — a scheduler plans against the second
	and a rider is told the first.
	"""
	_guard()
	if not stop:
		frappe.throw(_("Which stop?"))
	moment = _when(when)
	_horizon(moment)
	start, end = _history(days_back)

	empty = {
		"stop": stop,
		"line": line,
		"at": moment.isoformat(timespec="minutes"),
		"basis": 0,
		"learning": True,
		"scheduled_only": True,
		"carried_s": cint(delay_s),
	}
	if not facts.exists(model.STOP_HOUR):
		return empty

	where = {"stop": stop, "hour": moment.hour, "dow": getdate(moment).weekday()}
	if line:
		where["line"] = line

	rows = facts.aggregate(
		model.STOP_HOUR,
		start=start, end=end,
		group=["stop"],
		measures={
			"visits": ("sum", "visits"),
			"delay_avg": ("avg", "delay_avg"),
			"delay_p50": ("avg", "delay_p50"),
			"delay_p85": ("avg", "delay_p85"),
			"headway_avg": ("avg", "headway_avg"),
			"headway_p85": ("avg", "headway_p85"),
			"dwell_avg": ("avg", "dwell_avg"),
		},
		where=where,
	)
	reading = _reading(rows, "delay")
	if not reading["basis"]:
		return empty

	# The delay it is carrying now, plus what this stop does to a vehicle at
	# this hour. Added rather than replaced: the history says what the stop
	# costs, the live figure says where this one already is.
	carried = cint(delay_s)
	row = rows[0]
	return {
		**empty,
		"basis": reading["basis"],
		"learning": reading["learning"],
		"scheduled_only": False,
		"delay": reading,
		"early_s": None if reading["p50"] is None else round(carried + reading["p50"]),
		"likely_s": None if reading["p85"] is None else round(carried + reading["p85"]),
		"headway_avg_s": row.get("headway_avg"),
		"headway_p85_s": row.get("headway_p85"),
		"dwell_avg_s": row.get("dwell_avg"),
	}


@frappe.whitelist(methods=["GET"])
def risk(facets: str = "", when: str = "", late_s: int = LATE_S,
         days_back: int = 90) -> dict:
	"""The same distribution, per line, stated as a probability.

	An operator does not act on "four minutes late on average". They act on
	"line 12 misses five minutes on seven runs in ten at this hour", because the
	first is a number and the second is a decision. Which is the whole argument
	for storing percentiles: a mean cannot be turned into this and a median with
	a spread can.
	"""
	_guard()
	moment = _when(when)
	_horizon(moment)
	start, end = _history(days_back)
	where, unavailable = facetlib.resolve(model.SERVICE_HOUR, facets)
	threshold = max(60, cint(late_s) or LATE_S)

	empty = {
		"lines": [],
		"at": moment.isoformat(timespec="minutes"),
		"hour": moment.hour,
		"weekday": getdate(moment).weekday(),
		"late_s": threshold,
		"unavailable": unavailable,
	}
	if not facts.exists(model.SERVICE_HOUR):
		return empty

	rows = facts.aggregate(
		model.SERVICE_HOUR,
		start=start, end=end,
		group=["line"],
		measures={
			"readings": ("sum", "readings"),
			"delay_avg": ("avg", "delay_avg"),
			"delay_p50": ("avg", "delay_p50"),
			"delay_p85": ("avg", "delay_p85"),
			"delay_p95": ("avg", "delay_p95"),
			"occupancy_p85": ("avg", "occupancy_p85"),
		},
		where={**where, "hour": moment.hour, "dow": getdate(moment).weekday()},
	)

	# By the name somebody calls it. A fact table stores the doctype's id, which
	# is a hash, and a bar chart of hashes is a chart nobody can act on.
	named = networklib.line_names()

	lines = []
	for row in rows:
		reading = _reading([row], "delay")
		if not reading["basis"]:
			continue
		lines.append({
			# Both, and they are not the same thing: a chart labels a bar with
			# the name and the map colours a *geometry* with the id, and a
			# forecast drawn on the network needs the second.
			"id": row["line"],
			"line": named.get(row["line"], row["line"]),
			"chance": _chance_over(reading, threshold),
			"delay": reading,
			"occupancy_p85": row.get("occupancy_p85"),
			"basis": reading["basis"],
			"learning": reading["learning"],
		})

	# Worst first: this is a list somebody reads the top of and acts on, and
	# ordering it by line name would bury the one that needs attention.
	lines.sort(key=lambda one: (one["chance"] is None, -(one["chance"] or 0)))
	return {**empty, "lines": lines}


@frappe.whitelist(methods=["GET"])
def unusual(facets: str = "", days_back: int = 90, on: str = "") -> dict:
	"""What today is doing that its own history does not.

	A z-score against the same table, per line and hour, which catches an
	incident without anybody having to define what an incident is — and that is
	the only way this feature ever works. A rule that says "alert over ten
	minutes late" fires all day on a line that is always ten minutes late and
	never fires on the one that has never been late until this morning.

	The comparison is like for like: this hour on this weekday against the same
	hour on the same weekday. A Monday morning compared against a Sunday
	afternoon is not an anomaly, it is a calendar.
	"""
	_guard()
	day = getdate(on) if on else getdate()
	start, end = _history(days_back)
	where, unavailable = facetlib.resolve(model.SERVICE_HOUR, facets)

	empty = {"findings": [], "day": str(day), "unavailable": unavailable}
	if not facts.exists(model.SERVICE_HOUR):
		return empty

	today = facts.aggregate(
		model.SERVICE_HOUR,
		start=datetime.combine(day, datetime.min.time()),
		end=datetime.combine(day + timedelta(days=1), datetime.min.time()),
		group=["line", "hour"],
		measures={
			"readings": ("sum", "readings"),
			"delay_avg": ("avg", "delay_avg"),
			"delay_p85": ("avg", "delay_p85"),
		},
		where=where,
	)
	if not today:
		return empty

	# The history excludes the day being judged, which is not pedantry: with
	# one day of history a day is compared against itself and nothing is ever
	# unusual, and that is exactly the workspace most likely to be looking.
	before = facts.aggregate(
		model.SERVICE_HOUR,
		start=start, end=datetime.combine(day, datetime.min.time()),
		group=["line", "hour"],
		measures={
			"readings": ("sum", "readings"),
			"delay_p50": ("avg", "delay_p50"),
			"delay_p95": ("avg", "delay_p95"),
		},
		where={**where, "dow": day.weekday()},
	)
	usual = {(row["line"], cint(row["hour"])): row for row in before}
	named = networklib.line_names()

	findings = []
	for row in today:
		key = (row["line"], cint(row["hour"]))
		reading = _reading([usual.get(key, {})], "delay")
		sigma = _sigma(reading)
		if not reading["basis"] or reading["learning"] or not sigma:
			continue
		score = (flt(row.get("delay_avg") or 0) - flt(reading["p50"])) / sigma
		if abs(score) < 2:
			continue
		findings.append({
			"line": named.get(row["line"], row["line"]),
			"hour": cint(row["hour"]),
			"label": f"{cint(row['hour']):02d}:00",
			"score": round(score, 1),
			"delay_avg": round(flt(row.get("delay_avg") or 0)),
			"usual_p50": reading["p50"],
			"basis": reading["basis"],
			"worse": score > 0,
		})

	findings.sort(key=lambda one: -abs(one["score"]))
	return {**empty, "findings": findings[:40]}
