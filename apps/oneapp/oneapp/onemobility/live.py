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
from frappe.utils import cint, get_datetime, now_datetime

from ..shared import facts
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
def at(when: str = "", line: str = "") -> dict:
    """Every vehicle's position at a moment. `when` empty means now.

    One row per vehicle: its newest observation at or before the moment asked
    for. Written as a correlated maximum rather than a window function because
    the same query has to run on the MariaDB a bench actually has.
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
    if line:
        conditions.append("`line` = %(line)s")
        values["line"] = line

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

    return {"moment": str(moment), "vehicles": rows, "capped": len(rows) >= MAX_VEHICLES}


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
