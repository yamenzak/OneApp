"""What the feed *plans*, and what the plan is worth.

Everything else in this module is a record of what happened. This is the other
half — README §2 lists Stop Time as a noun and §6 opens on the sentence this
table exists to answer: *the planned timetable says 07:38 and the vehicle says
07:44*. Until there was somewhere to keep 07:38, that disagreement could not be
drawn, the scrubber could not run a ghost forward, and "is this line reliable"
had no denominator.

**A timetable is a pattern, and it is stored as one.** Flattening it over the
dates it runs is the obvious version and multiplies the table by the length of
the horizon — tens of millions of rows a fortnight, rewritten nightly, to say
what the pattern already said, and then a nightly job to keep extending it. A
pattern is one row per trip per stop with the weekdays it runs on, and "what is
due at Alexanderplatz at 08:15 next Tuesday" is a bitmask test and a range.

**Which makes the service day the awkward part, and it is unavoidable.** A trip
leaving at 00:40 belongs to *yesterday's* service day, and every feed says so
the same way: GTFS writes `25:10:00`, VDV 452 gives an offset from the trip's
start. So a query for a calendar day is two queries — this day's pattern and
yesterday's, the second shifted by a day — and `_windows` is that and nothing
else. Getting it wrong loses every night bus, which is the service an operator
is most often asked about.

The reads here are raw SQL rather than `facts.aggregate`, which is a deliberate
exception to §3a's rule. The aggregate tier filters on the partition column, and
this table's partition column is the day a version became valid — a fact about
the *delivery*, not about the row. Nothing here asks a question shaped like the
one that helper answers.
"""

from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime

from . import facets as facetlib
from . import model
from ..shared import facts

#: A day, in seconds. Named because it appears as an offset rather than as a
#: duration and `86400` in a WHERE clause reads as a magic number.
DAY_S = 86400

#: How many service days back a query looks for a trip still running. Two,
#: because a service day may legally reach into the next one and no timetable
#: in this market runs a single trip for more than a day.
BACK_DAYS = 2

#: The most ghosts one frame carries, for the reason `live.MAX_VEHICLES` has
#: one: a network larger than this wants a bounding box, and a thousand markers
#: is slower than the honest refusal.
MAX_GHOSTS = 1500

#: How far either side of a moment to read the timetable when placing ghosts. A
#: trip is between two stops, and on a rural line those are twenty minutes
#: apart; thirty is enough to bracket every service anybody runs.
BRACKET_S = 30 * 60

#: How far from a planned call an observed visit may be and still be that call.
#: Wider than any delay a screen draws, because the point of the comparison is
#: to *measure* the delay — and narrow enough that a vehicle an hour late is
#: reported as a missed call rather than as an early one for the next hour.
MATCH_S = 45 * 60


def _guard():
	if not frappe.has_permission("Transit Line", "read"):
		frappe.throw(_("You cannot read this."), frappe.PermissionError)


def bit(when: date) -> int:
	"""The weekday bit for a date. Monday is 1, Sunday is 64."""
	return 1 << when.weekday()


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

#: How many calls are held in memory before they are written. The same reason
#: `gtfs.CHUNK` exists: a big-city `stop_times.txt` is tens of millions of rows
#: and a list of them is not a thing a worker survives.
BATCH = 5000


def replace(source: str, rows, valid_from: date | None = None) -> int:
	"""This source's whole timetable, swapped for a new one.

	Delete then write, scoped to the source: a delivery restates the plan
	rather than amending it, and merging two versions of a timetable produces a
	third that neither the operator nor the feed has ever seen. Scoped so a
	second source's plan survives — which is the same rule `conflicts.py` keeps
	one level up.

	`rows` may be a generator, and for a real feed it is: the caller reads a
	CSV stream and this writes it in batches without either of them holding the
	whole timetable.
	"""
	if not source:
		frappe.throw(_("A timetable belongs to a source."))

	facts.ensure(model.SCHEDULE)
	frappe.db.sql(
		f"DELETE FROM `{model.SCHEDULE.table}` WHERE `source` = %s", (source,)
	)

	from_day = valid_from or getdate()
	stamp = datetime.combine(from_day, datetime.min.time())
	written, batch = 0, []
	for row in rows:
		arrives = cint(row.get("arrives_s"))
		batch.append({
			"valid_from": stamp,
			"valid_to": get_datetime(row["valid_to"]) if row.get("valid_to") else None,
			"trip_key": (row.get("trip_key") or "")[:64],
			"line": (row.get("line") or "")[:140],
			"stop": (row.get("stop") or "")[:140],
			"seq": cint(row.get("seq")),
			"arrives_s": arrives,
			"departs_s": cint(row.get("departs_s") or arrives),
			# A trip that runs no day at all is a trip nobody can be shown, and
			# a feed with an empty calendar is commoner than it should be. Every
			# day rather than no day: visible and wrong beats invisible.
			"days": cint(row.get("days")) or 127,
			"headsign": (row.get("headsign") or "")[:64],
			"source": source[:140],
			# The hour of the service day it falls in, so a screen narrowing to
			# the morning peak does not scan the whole pattern.
			"hour": (arrives // 3600) % 24,
		})
		if len(batch) >= BATCH:
			written += facts.write(model.SCHEDULE, batch)
			batch = []
	if batch:
		written += facts.write(model.SCHEDULE, batch)
	return written


def kept(source: str = "") -> int:
	"""How many calls the timetable holds. The fixture and the tests read it."""
	if not facts.exists(model.SCHEDULE):
		return 0
	where = " WHERE `source` = %s" if source else ""
	return cint(frappe.db.sql(
		f"SELECT COUNT(*) FROM `{model.SCHEDULE.table}`{where}",
		(source,) if source else (),
	)[0][0])


# --------------------------------------------------------------------------- #
# Reading a pattern back as real moments
# --------------------------------------------------------------------------- #

def _windows(start: datetime, end: datetime) -> list[tuple]:
	"""The service days that can put a call inside a real-time window.

	Today's pattern, and yesterday's shifted forward — which is the whole of
	the night-bus problem. Returns `(midnight, bit, low, high)` per day, where
	low and high are seconds from that day's midnight.
	"""
	out = []
	for back in range(BACK_DAYS):
		day = getdate(start) - timedelta(days=back)
		midnight = datetime.combine(day, datetime.min.time())
		low = (start - midnight).total_seconds()
		high = (end - midnight).total_seconds()
		if high <= 0 or low >= BACK_DAYS * DAY_S:
			continue
		out.append((midnight, bit(day), max(0, int(low)), int(high)))
	return out


def _calls(start: datetime, end: datetime, where: dict, limit: int) -> list[dict]:
	"""Every planned call inside a real-time window, as real moments."""
	if not facts.exists(model.SCHEDULE):
		return []

	table = model.SCHEDULE.table
	found = []
	for midnight, day_bit, low, high in _windows(start, end):
		clauses = ["`days` & %(bit)s", "`arrives_s` >= %(low)s", "`arrives_s` < %(high)s"]
		values = {"bit": day_bit, "low": low, "high": high}
		# The column names come out of the closed table below and are checked
		# against the fact's own columns; every value is still a parameter.
		for at, (column, value) in enumerate(sorted(where.items())):
			values[f"w{at}"] = value
			clauses.append(f"`{column}` = %(w{at})s")

		for row in frappe.db.sql(
			f"""SELECT `trip_key`, `line`, `stop`, `seq`, `arrives_s`, `departs_s`,
			           `headsign`, `source`
			    FROM `{table}` WHERE {' AND '.join(clauses)}
			    ORDER BY `arrives_s` LIMIT {int(limit)}""",
			values, as_dict=True,
		):
			row["due"] = midnight + timedelta(seconds=cint(row["arrives_s"]))
			row["leaves"] = midnight + timedelta(seconds=cint(row["departs_s"]))
			found.append(row)
	found.sort(key=lambda one: one["due"])
	return found[:limit]


def _narrow(facets: str) -> tuple[dict, list]:
	"""The shared facet vocabulary, kept to the columns this table carries."""
	where, unavailable = facetlib.resolve(model.SCHEDULE, facets)
	# A list-valued facet is an `IN`, which `_calls` deliberately does not
	# build: this table is read for one line or one stop at a time and a screen
	# asking for six is asking six questions.
	flat = {key: value for key, value in where.items() if not isinstance(value, list)}
	for key, value in where.items():
		if isinstance(value, list) and len(value) == 1:
			flat[key] = value[0]
	return flat, unavailable


@frappe.whitelist(methods=["GET"])
def due(when: str = "", stop: str = "", line: str = "", minutes: int = 60,
        limit: int = 200) -> dict:
	"""What is planned in the next hour. A departure board, off the pattern.

	The plainest possible use of this table, and the one that proves it is
	right: if the night bus is missing from a query at half past midnight, the
	service-day arithmetic above is wrong and every other answer here is too.
	"""
	_guard()
	moment = get_datetime(when) if when else now_datetime()
	span = max(5, min(cint(minutes) or 60, 24 * 60))

	where = {}
	if stop:
		where["stop"] = stop
	if line:
		where["line"] = line

	calls = _calls(moment, moment + timedelta(minutes=span), where,
	               max(10, min(cint(limit) or 200, 1000)))
	return {
		"moment": str(moment),
		"until": str(moment + timedelta(minutes=span)),
		"calls": [{**one, "due": str(one["due"]), "leaves": str(one["leaves"])}
		          for one in calls],
		"kept": kept(),
	}


# --------------------------------------------------------------------------- #
# Ghosts: where a trip should be, when nothing has reported
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def expected(when: str = "", facets: str = "") -> dict:
	"""Where every running trip is *due* to be at a moment.

	Answered as a pair of stops and a fraction between them rather than as a
	position, which is the split README §7a already made for live vehicles: the
	browser holds the line's drawn shape and `motion.js` projects onto it, so
	sending coordinates would mean a second geometry implementation that can
	disagree with the first about where a route goes.

	Fraction of *time*, not of distance. A vehicle does not cover the gap
	between two stops at a constant speed, and pretending it does is a smaller
	lie than pretending we know its speed profile — the timetable only ever
	claimed the two endpoints.
	"""
	_guard()
	moment = get_datetime(when) if when else now_datetime()
	where, unavailable = _narrow(facets)

	calls = _calls(
		moment - timedelta(seconds=BRACKET_S),
		moment + timedelta(seconds=BRACKET_S),
		where, MAX_GHOSTS * 6,
	)

	runs: dict[str, list] = {}
	for one in calls:
		runs.setdefault(one["trip_key"], []).append(one)

	ghosts = []
	for trip_key, stops in runs.items():
		stops.sort(key=lambda one: cint(one["seq"]))
		behind = [one for one in stops if one["leaves"] <= moment]
		ahead = [one for one in stops if one["due"] > moment]
		if not (behind and ahead):
			# Before its first call or after its last: not running, rather than
			# parked on top of a terminus for half an hour either side.
			continue

		leaving, arriving = behind[-1], ahead[0]
		span = (arriving["due"] - leaving["leaves"]).total_seconds()
		ghosts.append({
			"trip_key": trip_key,
			"line": leaving["line"],
			"headsign": leaving["headsign"] or arriving["headsign"],
			"from_stop": leaving["stop"],
			"to_stop": arriving["stop"],
			"t": round((moment - leaving["leaves"]).total_seconds() / span, 4)
			if span > 0 else 0.0,
			"due": str(arriving["due"]),
		})
		if len(ghosts) >= MAX_GHOSTS:
			break

	return {
		"moment": str(moment),
		"ghosts": ghosts,
		"capped": len(ghosts) >= MAX_GHOSTS,
		"unavailable": unavailable,
		"kept": kept(),
	}


# --------------------------------------------------------------------------- #
# The plan against what happened
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def deviation(day: str = "", facets: str = "", limit: int = 200) -> dict:
	"""Planned 07:38 against observed 07:44, call by call.

	The conflict README §6 says is often the interesting part, one level below
	the one `conflicts.py` resolves: that module decides which *record* two
	sources are describing, and this one compares two statements about the same
	*event*. Nothing resolves it, deliberately — the gap is the product.

	Matched on line, stop and nearest time rather than on a trip key, because a
	live feed's journey reference and a timetable's trip id agree in about half
	the deliveries in this market and a comparison that only works for the
	tidy half is a comparison nobody can rely on. A planned call with nothing
	within `MATCH_S` is reported as missed rather than matched to the next
	hour's vehicle, which is the failure that would make a cancelled trip look
	like a very late one.
	"""
	_guard()
	on = getdate(day) if day else getdate() - timedelta(days=1)
	midnight = datetime.combine(on, datetime.min.time())
	where, unavailable = _narrow(facets)

	empty = {
		"day": str(on),
		"planned": 0, "observed": 0, "matched": 0, "missed": 0, "unplanned": 0,
		"median_s": None,
		"calls": [],
		"unavailable": unavailable,
		"kept": kept(),
	}
	if not (facts.exists(model.SCHEDULE) and facts.exists(model.STOP_EVENT)):
		return empty

	planned = _calls(midnight, midnight + timedelta(days=1), where, 20000)
	visits = facts.rows_between(
		model.STOP_EVENT, midnight, midnight + timedelta(days=1),
		{key: value for key, value in where.items() if key in model.STOP_EVENT.columns},
	)
	if not planned:
		return {**empty, "observed": len(visits), "unplanned": len(visits)}

	seen: dict[tuple, list] = {}
	for one in visits:
		seen.setdefault((one["line"], one["stop"]), []).append(get_datetime(one["at"]))
	for times in seen.values():
		times.sort()

	taken: set = set()
	matched = []
	for call in planned:
		times = seen.get((call["line"], call["stop"])) or []
		best, gap = None, None
		for at, moment in enumerate(times):
			if (call["line"], call["stop"], at) in taken:
				continue
			apart = (moment - call["due"]).total_seconds()
			if abs(apart) > MATCH_S:
				continue
			if gap is None or abs(apart) < abs(gap):
				best, gap = at, apart
		if best is None:
			matched.append({**call, "seen": None, "gap_s": None})
			continue
		taken.add((call["line"], call["stop"], best))
		matched.append({**call, "seen": times[best], "gap_s": int(gap)})

	gaps = sorted(one["gap_s"] for one in matched if one["gap_s"] is not None)
	shown = sorted(
		matched,
		key=lambda one: (one["gap_s"] is not None, -abs(one["gap_s"] or 0)),
	)[: max(10, min(cint(limit) or 200, 1000))]

	return {
		**empty,
		"planned": len(planned),
		"observed": len(visits),
		"matched": len(gaps),
		"missed": len(matched) - len(gaps),
		"unplanned": max(0, len(visits) - len(gaps)),
		"median_s": gaps[len(gaps) // 2] if gaps else None,
		"calls": [{
			"line": one["line"], "stop": one["stop"], "trip_key": one["trip_key"],
			"due": str(one["due"]),
			"seen": str(one["seen"]) if one["seen"] else None,
			"gap_s": one["gap_s"],
		} for one in shown],
	}
