"""Where the vehicles are, now and at any moment we kept.

One screen, two clocks. `now` reads the last observation per vehicle; a past
moment reads the same table at that time. The browser does the rest — see
`README.md` §7a, "Moving the vehicle between pings": a feed reports every
fifteen to thirty seconds and a marker that jumps every twenty seconds reads as
broken, so the position between reports is dead-reckoned along the line's own
shape rather than sent from here at 60fps.

Which is the design worth protecting: the server answers "where was everything
at time T", and one renderer draws it whether T is now or a Tuesday in March.
Two endpoints would become two screens, and two screens become two products.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime

from ..shared import facts
from . import facets as facetlib
from . import model

#: How far back to look for a vehicle's last report before calling it silent.
#: Two minutes is four missed reports on a thirty-second feed — long enough not
#: to flicker on one dropped packet, short enough that a screen never shows a
#: bus that stopped reporting at breakfast as though it were moving.
STALE_AFTER = 120

#: The most vehicles one frame will carry. A network larger than this is a
#: network that wants a bounding box, and drawing four thousand markers is
#: slower than the honest refusal.
MAX_VEHICLES = 1500


@frappe.whitelist(methods=["GET"])
def at(when: str = "", facets: str = "") -> dict:
    """Every vehicle's position at a moment. `when` empty means now.

    One row per vehicle: its newest observation at or before the moment asked
    for. Written as a correlated maximum rather than a window function because
    the same query has to run on the MariaDB a bench actually has.

    `facets` is the shared vocabulary — see `facets.py`. It used to be a bare
    `line`, which meant the map could be narrowed one way and Insights another
    and the two were separate code.
    """
    if not frappe.has_permission("Transit Vehicle", "read"):
        frappe.throw(_("You cannot read this."), frappe.PermissionError)

    moment = get_datetime(when) if when else now_datetime()
    since = moment - timedelta(seconds=STALE_AFTER * 4)

    # Unqualified, because these go in the *inner* query where the outer
    # alias does not exist — which is the kind of thing that only fails once
    # somebody opens the screen.
    conditions = ["`at` <= %(moment)s", "`at` >= %(since)s"]
    values = {"moment": moment, "since": since}

    narrow, unavailable = facetlib.resolve(model.OBSERVATION, facets)
    for at_index, (column, value) in enumerate(sorted(narrow.items())):
        # The column names come out of the closed table in `facets.py` and are
        # checked there against this fact's own columns, so they can be
        # interpolated; every value is still a parameter.
        if isinstance(value, list):
            if not value:
                conditions.append("1 = 0")
                continue
            marks = []
            for one_index, one in enumerate(value):
                key = f"f{at_index}_{one_index}"
                values[key] = one
                marks.append(f"%({key})s")
            conditions.append(f"`{column}` IN ({', '.join(marks)})")
        else:
            values[f"f{at_index}"] = value
            conditions.append(f"`{column}` = %(f{at_index})s")

    table = model.OBSERVATION.table
    rows = frappe.db.sql(
        f"""
        SELECT o.`vehicle`, o.`line`, o.`trip_key`, o.`lat`, o.`lon`,
               o.`occupancy`, o.`delay_s`, o.`at`
        FROM `{table}` o
        JOIN (
            SELECT `vehicle`, MAX(`at`) AS `newest`
            FROM `{table}`
            WHERE {' AND '.join(conditions)}
            GROUP BY `vehicle`
            LIMIT {int(MAX_VEHICLES)}
        ) last ON last.`vehicle` = o.`vehicle` AND last.`newest` = o.`at`
        """,
        values,
        as_dict=True,
    )

    for row in rows:
        age = (moment - get_datetime(row["at"])).total_seconds()
        # Stale is drawn differently and never as live. A position carried
        # forward past this is a guess, and a guess drawn as a fact is the one
        # thing that makes an operator stop trusting the screen.
        row["stale"] = age > STALE_AFTER
        row["age_s"] = int(age)
        row["at"] = str(row["at"])

    return {
        "moment": str(moment),
        "vehicles": rows,
        "capped": len(rows) >= MAX_VEHICLES,
        "unavailable": unavailable,
        # An empty frame has two meanings and the screen cannot tell them
        # apart: nothing was running, or the day has aged out of the database
        # and is sitting in the bucket. Only the second one has something to
        # offer, so it is answered here rather than left to be inferred.
        "frozen": bool(not rows and _is_frozen(moment.date())),
    }


def _is_frozen(day) -> bool:
    """Whether this day is out of the hot window and in the bucket.

    Two questions and the cheap one first: a day inside the window is not
    frozen whatever the bucket holds, and asking the bucket about today would
    be a network call on every frame the map draws.
    """
    if day > (now_datetime().date() - timedelta(days=facts.hot_days(model.OBSERVATION))):
        return False
    return any(one["day"] == str(day) for one in facts.frozen_index(model.OBSERVATION))


@frappe.whitelist(methods=["POST"])
def thaw(day: str) -> dict:
    """Bring one frozen day back into the database, on request.

    Enqueued: a day of a large fleet is millions of rows out of a gzipped
    object, which outlives the request that asked for it — and a map that hangs
    for four minutes reads as broken rather than as busy.

    The day is then held for a week, so the sweep that runs tonight does not
    quietly undo what somebody asked for this afternoon. See
    `shared/facts.THAW_HOLD_DAYS`.
    """
    if not frappe.has_permission("Transit Vehicle", "read"):
        frappe.throw(_("You cannot read this."), frappe.PermissionError)

    when = getdate(day)
    if not when:
        frappe.throw(_("That is not a day."))
    if not any(one["day"] == str(when) for one in facts.frozen_index(model.OBSERVATION)):
        frappe.throw(_("There is no stored copy of {0}.").format(day))

    frappe.enqueue(
        "oneapp.onemobility.live.thaw_day",
        queue="long",
        timeout=3600,
        job_id=f"oneapp-thaw-{frappe.local.site}-{when}",
        deduplicate=True,
        day=str(when),
    )
    return {"ok": True, "day": str(when), "queued": True}


def thaw_day(day: str) -> dict:
    """The job behind `thaw`. Every raw tier for that day, not just positions.

    A person asking for the 12th of March back wants the map *and* the stop
    calls, and hydrating one of the two would produce a day that half exists —
    which is worse than one that does not.
    """
    when = getdate(day)
    brought = {}
    for fact in (model.OBSERVATION, model.STOP_EVENT, model.TRIP):
        brought[fact.name] = facts.thaw(fact, when)
    frappe.db.commit()
    return {"ok": True, "day": str(when), "rows": brought}


@frappe.whitelist(methods=["GET"])
def track(vehicle: str, day: str) -> dict:
    """One vehicle's whole day, for the scrubber to run through.

    The playback format of README §4, computed on request rather than rolled
    nightly — which is the honest state of it: the nightly roll into one object
    per vehicle per day is what makes this instant at scale, and until a
    workspace has that scale, a query over one day of one vehicle is already
    fast. The shape returned is the same either way, so the roll-up can be
    added underneath without a screen changing.
    """
    if not frappe.has_permission("Transit Vehicle", "read"):
        frappe.throw(_("You cannot read this."), frappe.PermissionError)

    start = get_datetime(f"{day} 00:00:00")
    rows = facts.rows_between(
        model.OBSERVATION, start, start + timedelta(days=1), {"vehicle": vehicle}
    )

    # Delta-encoded: time as seconds from the start of the day, position as
    # micro-degrees. A day of one vehicle is a few thousand points, and sending
    # them as objects with six keys each is four times the bytes for nothing.
    return {
        "vehicle": vehicle,
        "day": day,
        "t": [int((get_datetime(r["at"]) - start).total_seconds()) for r in rows],
        "lat": [round(r["lat"] or 0, 6) for r in rows],
        "lon": [round(r["lon"] or 0, 6) for r in rows],
        "occupancy": [cint(r["occupancy"]) for r in rows],
        "delay": [cint(r["delay_s"]) for r in rows],
    }


def record(rows: list[dict]) -> int:
    """Take observations in. The shape every live source normalises onto.

    `hour` and `dow` are filled here rather than asked of the caller: they are
    derivable, and a source that got them wrong would poison every roll-up
    silently. See `model.py` for why they are stored at all.
    """
    model.ensure_all()

    prepared = []
    for row in rows:
        when = get_datetime(row["at"])
        prepared.append(
            {
                "at": when,
                "vehicle": (row.get("vehicle") or "")[:140],
                "line": (row.get("line") or "")[:140],
                "trip_key": (row.get("trip_key") or "")[:64],
                "lat": row.get("lat"),
                "lon": row.get("lon"),
                # -1 rather than 0 for "not reported": an empty bus and a bus
                # with no counter are different facts and must not be one
                # colour on a map.
                "occupancy": cint(row.get("occupancy", -1)) if row.get("occupancy") is not None else -1,
                "delay_s": cint(row.get("delay_s") or 0),
                "hour": when.hour,
                "dow": when.weekday(),
            }
        )

    return facts.write(model.OBSERVATION, prepared)


def happened(vehicle: str, reported: list[dict], seen: dict | None = None) -> int:
	"""What one vehicle said about itself, written as edges.

	The sibling of `record` above and deliberately a second function rather
	than a flag on it: a position is a sample and an event is a change, so
	they are stored differently, kept for different lengths, and one of them
	is dropped when it repeats. Sharing a writer would mean a branch at the
	top of every line of it.

	`vdv301.read` is what decides which of the reported states are news.
	"""
	from . import vdv301

	rows = vdv301.read(vehicle, reported, seen=seen)
	if not rows:
		return 0

	model.ensure_all()
	return facts.write(model.VEHICLE_EVENT, rows)


@frappe.whitelist(methods=["POST"])
def relay(vehicle: str, events: str | list) -> dict:
	"""The push door for IBIS-IP: a bridge on a vehicle hands us what it heard.

	Separate from `report` because the two are not the same claim. `report`
	says where vehicles are and takes a list that may span a fleet; this says
	what *one* vehicle did, and naming the vehicle once is what lets the
	reader hold a per-vehicle state and drop a repeat. A bridge relays for the
	vehicle it is bolted to.

	The same permission as `report`, for the same reason: this is a write
	about the fleet. A bridge is a machine, so it holds an API key against a
	user that has it, and nothing here is reachable by a person who could not
	already write a vehicle.
	"""
	if not frappe.has_permission("Transit Vehicle", "create"):
		frappe.throw(_("You cannot report for a vehicle."), frappe.PermissionError)

	rows = frappe.parse_json(events) if isinstance(events, str) else events
	if not isinstance(rows, list):
		frappe.throw(_("Events must be a list."))
	if len(rows) > 5000:
		frappe.throw(_("That is too many events for one call."))

	# The last state per (kind, part) for this vehicle, so a relay arriving
	# five minutes after the last one does not re-write a door that has not
	# moved. Read once here rather than per event.
	written = happened(vehicle, rows, seen=_last_seen(vehicle))
	frappe.db.commit()
	return {"written": written}


def _last_seen(vehicle: str) -> dict:
	"""The most recent value per `(kind, part)` for one vehicle.

	One query and a small answer: a vehicle has a handful of doors and a
	handful of devices, so this is tens of rows however long it has been
	running. The alternative — no memory between calls — writes a duplicate
	row on the first event of every relay, which is a fact table with a
	heartbeat in it.
	"""
	table = model.VEHICLE_EVENT.table
	rows = frappe.db.sql(
		f"""
		select e.kind, e.part, e.value, e.at
		from `{table}` e
		join (
			select kind, part, max(at) as at
			from `{table}`
			where vehicle = %(vehicle)s
			group by kind, part
		) last on last.kind = e.kind and last.part = e.part and last.at = e.at
		where e.vehicle = %(vehicle)s
		""",
		{"vehicle": vehicle},
		as_dict=True,
	)
	return {(one.kind, one.part): {"value": one.value, "at": one.at} for one in rows}


@frappe.whitelist(methods=["POST"])
def report(observations: str | list) -> dict:
    """The push door: a live source hands us positions.

    Whitelisted because a socket bridge and a webhook both arrive this way. The
    permission is `create` on Transit Vehicle — writing where a fleet is, is a
    write about the fleet.
    """
    if not frappe.has_permission("Transit Vehicle", "create"):
        frappe.throw(_("You cannot report positions."), frappe.PermissionError)

    rows = frappe.parse_json(observations) if isinstance(observations, str) else observations
    if not isinstance(rows, list):
        frappe.throw(_("Observations must be a list."))
    if len(rows) > 5000:
        frappe.throw(_("That is too many observations for one call."))

    written = record(rows)
    frappe.db.commit()
    return {"written": written}
