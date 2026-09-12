"""The event tiers, read.

`vdv301.py` writes what a vehicle said about itself; this is the half a person
looks at. Four reads, and they are four different questions rather than four
cuts of one:

    attention   what is wrong *now* — a door on emergency release, a counter
                reporting sabotage, a vehicle off route
    behaviour   what this fleet does over a day and a week, per kind
    doors       how long the doors are open, as a distribution
    story       one vehicle's day, as spans rather than edges

The first is the one that earns the tier. Everything else in OneMobility
answers "what happened"; `attention` answers "what is happening, and has it
been happening for forty minutes" — which is the question that gets somebody
out of a chair.

## Two rules shared with `insights.py`, for the same reasons

**One shaping, on the server.** The same aggregate feeds a headline figure and
a plot, and two shapings of one answer is how a dashboard comes to disagree
with itself.

**Distributions, not means.** `eventHour` stores `seconds_p50`, `p85` and
`max` because "the doors are usually twenty seconds and sometimes two minutes"
is the sentence somebody needs, and a mean of forty says neither half of it.

## And one that is only here

**A state has no end until the next one.** The tier stores edges, so a reader
asking "how long has door 3 been jammed" is asking about a row with nothing
after it. `attention` computes that against *now* and says so; `story` leaves
the last span of a day open rather than closing it at midnight, because a
vehicle whose doors were open when the window ended did not shut them.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, now_datetime

from . import facets as facetlib
from . import model
from . import vdv301

#: How far back `attention` looks for a state that is still in force. A door
#: jammed at six this morning is worth showing at nine; one jammed last
#: Tuesday is a maintenance record, not an alert, and putting it in the same
#: list is how a list stops being read.
ATTENTION_H = 24

#: The most rows any of these will draw. A fleet of five hundred with a bad
#: morning can have thousands of trouble rows, and a list nobody can scroll
#: is the same as no list.
MOST = 200


def _guard():
	if not frappe.has_permission("Transit Vehicle", "read"):
		frappe.throw(_("You cannot read this."), frappe.PermissionError)


def _window(days_back) -> tuple:
	end = getdate() + timedelta(days=1)
	return end - timedelta(days=max(1, min(cint(days_back) or 30, 400))), end


@frappe.whitelist(methods=["GET"])
def attention(hours: int = ATTENTION_H) -> dict:
	"""What is wrong, and how long it has been wrong.

	The tier's reason for existing. Every row here is a state a vehicle
	reported and has not reported its way out of — `vdv301.TROUBLE` decides
	which states those are, and the flag is on the row so this is an indexed
	filter rather than a scan with a list of pairs.

	"Still in force" is the whole subtlety. Edges mean the absence of a later
	row *is* the state continuing, so this takes the newest row per
	`(vehicle, kind, part)` and keeps it only where that newest row is a
	troubled one. A door that jammed and then unjammed has a later row and
	drops out on its own, without anything having to resolve it.
	"""
	_guard()
	model.ensure_all()

	table = model.VEHICLE_EVENT.table
	since = now_datetime() - timedelta(hours=max(1, min(cint(hours) or ATTENTION_H, 720)))

	rows = frappe.db.sql(
		f"""
		SELECT e.vehicle, e.kind, e.part, e.value, e.line, e.stop, e.at
		FROM `{table}` e
		JOIN (
			SELECT vehicle, kind, part, MAX(at) AS at
			FROM `{table}`
			WHERE at >= %(since)s
			GROUP BY vehicle, kind, part
		) newest
		  ON newest.vehicle = e.vehicle AND newest.kind = e.kind
		 AND newest.part = e.part AND newest.at = e.at
		WHERE e.at >= %(since)s AND e.trouble = 1
		ORDER BY e.at ASC
		LIMIT {MOST}
		""",
		{"since": since},
		as_dict=True,
	)

	now = now_datetime()
	out = []
	for one in rows:
		out.append({
			"vehicle": one.vehicle,
			"kind": one.kind,
			"part": one.part,
			"value": one.value,
			"line": one.line or "",
			"stop": one.stop or "",
			"since": one.at,
			# Against now, not against a later row — there is no later row,
			# which is what makes it still true.
			"minutes": int((now - one.at).total_seconds() // 60),
			"part_of": vdv301.KINDS.get(one.kind, ""),
		})

	# Oldest first: a door that has been jammed for two hours outranks one
	# that jammed a minute ago, and sorting by recency puts the worst case at
	# the bottom of the list.
	out.sort(key=lambda one: -one["minutes"])
	return {
		"since": since,
		"rows": out,
		"vehicles": len({one["vehicle"] for one in out}),
		"truncated": len(rows) >= MOST,
	}


@frappe.whitelist(methods=["GET"])
def behaviour(facets: str = "", days_back: int = 30) -> dict:
	"""What this fleet does over a day and over a week, per kind.

	Off `eventHour`, which is the tier that never expires — so this answers
	for a year where `attention` answers for a day.
	"""
	_guard()
	model.ensure_all()

	start, end = _window(days_back)
	where, unavailable = facetlib.resolve(model.EVENT_HOUR, facets)

	clauses = ["`at` >= %s", "`at` < %s"]
	values = [start, end]
	facetlib.narrow(clauses, values, where)

	rows = frappe.db.sql(
		f"""
		SELECT kind, value, hour, dow,
		       SUM(events) AS events, SUM(trouble) AS trouble,
		       AVG(seconds_p50) AS seconds_p50, MAX(seconds_max) AS seconds_max
		FROM `{model.EVENT_HOUR.table}`
		WHERE {' AND '.join(clauses)}
		GROUP BY kind, value, hour, dow
		""",
		values,
		as_dict=True,
	)

	kinds: dict = {}
	byhour: dict = {}
	for one in rows:
		held = kinds.setdefault(one.kind, {"kind": one.kind, "events": 0,
		                                   "trouble": 0, "values": {}})
		held["events"] += cint(one.events)
		held["trouble"] += cint(one.trouble)
		held["values"][one.value] = held["values"].get(one.value, 0) + cint(one.events)
		byhour.setdefault(one.hour, {}).setdefault(one.kind, 0)
		byhour[one.hour][one.kind] += cint(one.events)

	shaped = []
	for held in kinds.values():
		# Values ordered by the specification's own order where we know it, so
		# a legend reads `DoorsOpen, AllDoorsClosed, …` rather than by
		# whichever happened to be commonest this month.
		known = vdv301.KNOWN.get(held["kind"]) or ()
		order = {value: index for index, value in enumerate(known)}
		held["values"] = sorted(
			({"value": value, "events": count} for value, count in held["values"].items()),
			key=lambda one: (order.get(one["value"], len(order)), one["value"]),
		)
		held["part_of"] = vdv301.KINDS.get(held["kind"], "")
		shaped.append(held)
	shaped.sort(key=lambda one: -one["events"])

	return {
		"from": start,
		"to": end,
		"kinds": shaped,
		"hours": [
			{"hour": hour, **{kind: count for kind, count in held.items()}}
			for hour, held in sorted(byhour.items())
		],
		"unavailable": unavailable,
	}


@frappe.whitelist(methods=["GET"])
def doors(facets: str = "", days_back: int = 30) -> dict:
	"""How long the doors are open, as a distribution.

	The measured dwell, and the number this whole arc was worth building for.
	`stopEvent.dwell_s` is inferred from positions — the time a vehicle spent
	inside a stop's radius, honest to the feed's resolution and no finer — and
	VDV 301-2-15 exists because a door release signal does not say which door
	opened. So where a fleet reports door states, this is the real answer and
	that one is the estimate.

	Both are returned, side by side and labelled, rather than one silently
	replacing the other: a workspace with door data on half its fleet should
	be able to see which half.
	"""
	_guard()
	model.ensure_all()

	start, end = _window(days_back)
	where, unavailable = facetlib.resolve(model.EVENT_HOUR, facets)

	clauses = ["`at` >= %s", "`at` < %s", "`kind` = %s"]
	values = [start, end, vdv301.DOOR]
	facetlib.narrow(clauses, values, where)

	# On `was`, not on `value`. The duration a row carries is how long the
	# state it *ended* had lasted, so "how long were the doors open" is the
	# distribution on rows whose previous state was open — see `vdv301`.
	measured = frappe.db.sql(
		f"""
		SELECT hour,
		       AVG(seconds_p50) AS p50, AVG(seconds_p85) AS p85,
		       MAX(seconds_max) AS worst, SUM(events) AS events
		FROM `{model.EVENT_HOUR.table}`
		WHERE {' AND '.join(clauses)} AND `was` IN (%s, %s)
		GROUP BY hour ORDER BY hour
		""",
		[*values, "DoorsOpen", "SingleDoorOpen"],
		as_dict=True,
	)

	# And the inferred one beside it, from the tier that has always had it.
	inferred_where, _unused = facetlib.resolve(model.STOP_HOUR, facets)
	clauses = ["`at` >= %s", "`at` < %s"]
	values = [start, end]
	facetlib.narrow(clauses, values, inferred_where)
	inferred = frappe.db.sql(
		f"""
		SELECT hour, AVG(dwell_p50) AS p50, AVG(dwell_p85) AS p85,
		       SUM(visits) AS visits
		FROM `{model.STOP_HOUR.table}`
		WHERE {' AND '.join(clauses)}
		GROUP BY hour ORDER BY hour
		""",
		values,
		as_dict=True,
	)

	return {
		"from": start,
		"to": end,
		"measured": [
			{"hour": one.hour, "p50": flt(one.p50, 1), "p85": flt(one.p85, 1),
			 "worst": cint(one.worst), "events": cint(one.events)}
			for one in measured
		],
		"inferred": [
			{"hour": one.hour, "p50": flt(one.p50, 1), "p85": flt(one.p85, 1),
			 "visits": cint(one.visits)}
			for one in inferred
		],
		"measured_from": "VDV 301-2-15",
		"unavailable": unavailable,
	}


@frappe.whitelist(methods=["GET"])
def story(vehicle: str, day: str = "") -> dict:
	"""One vehicle's day, as spans rather than edges.

	What a record surface draws, and what a scrubber would read. The edges are
	turned back into durations by `vdv301.spans`, per kind — "door 3 was open
	from 07:12:04 for fourteen seconds" is not a row in the table, it is the
	gap between two of them.

	The last span of the day is left open rather than closed at midnight. A
	vehicle whose doors were open when the window ended did not shut them, and
	inventing the close would put a number on a screen that nothing measured.
	"""
	_guard()
	if not vehicle:
		frappe.throw(_("Which vehicle?"))
	if not frappe.has_permission("Transit Vehicle", "read", doc=vehicle):
		frappe.throw(_("You cannot read that vehicle."), frappe.PermissionError)

	model.ensure_all()
	when = getdate(day) if day else getdate()

	rows = frappe.db.sql(
		f"""
		SELECT at, kind, part, value, number, trouble, line, stop
		FROM `{model.VEHICLE_EVENT.table}`
		WHERE vehicle = %s AND at >= %s AND at < %s
		ORDER BY at
		LIMIT 5000
		""",
		(vehicle, when, when + timedelta(days=1)),
		as_dict=True,
	)

	held = [dict(one) for one in rows]
	return {
		"vehicle": vehicle,
		"day": when,
		"kinds": sorted({one["kind"] for one in held}),
		"spans": {
			kind: vdv301.spans(held, kind)
			for kind in sorted({one["kind"] for one in held})
		},
		"dwell_s": vdv301.dwell(held),
		"trouble": [one for one in held if one["trouble"]],
		"events": len(held),
	}


# --------------------------------------------------------------------------- #
# The nightly summary
# --------------------------------------------------------------------------- #

def summarise(day=None) -> int:
	"""Yesterday's events per vehicle per kind, into `eventDay`.

	`eventHour` is a declared rollup and `facts.roll_up` writes it; this one
	is not, because its grain is a *day* and the rollup machinery groups
	within one. Written the same way `arrivals.build` is: the day is deleted
	and written again, so re-running it is free of consequence.

	`seconds_total` is the sum of the spans rather than of the `number`
	column, because a span is the gap between two rows and no single row
	knows it.
	"""
	when = getdate(day) if day else getdate() - timedelta(days=1)
	model.ensure_all()

	frappe.db.sql(
		f"DELETE FROM `{model.EVENT_DAY.table}` WHERE `day` = %s", (when,)
	)

	rows = frappe.db.sql(
		f"""
		SELECT vehicle, kind, at, part, value, trouble
		FROM `{model.VEHICLE_EVENT.table}`
		WHERE at >= %s AND at < %s
		ORDER BY vehicle, kind, part, at
		""",
		(when, when + timedelta(days=1)),
		as_dict=True,
	)
	if not rows:
		return 0

	byvehicle: dict = {}
	for one in rows:
		byvehicle.setdefault((one.vehicle, one.kind), []).append(dict(one))

	written = []
	for (vehicle, kind), held in byvehicle.items():
		spans = vdv301.spans(held, kind)
		seconds = [one["seconds"] for one in spans if one["seconds"]]
		written.append({
			"day": when,
			"vehicle": vehicle,
			"kind": kind,
			"events": len(held),
			"trouble": sum(1 for one in held if one["trouble"]),
			"seconds_total": sum(seconds),
			"seconds_max": max(seconds) if seconds else 0,
		})

	from ..shared import facts

	return facts.write(model.EVENT_DAY, written)


def nightly():
	"""Scheduled. Yesterday, and the day before in case a relay arrived late."""
	today = getdate()
	for back in (1, 2):
		try:
			summarise(today - timedelta(days=back))
		except Exception:
			frappe.log_error(title="Event summary failed",
			                 message=frappe.get_traceback())
	frappe.db.commit()
