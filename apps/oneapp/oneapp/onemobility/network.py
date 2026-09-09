"""What the network screen draws before anything moves.

Lines with their shapes, stops with their positions, and the numbers under
both. One call, because the screen needs all of it before its first frame and
four round trips is four chances to draw half a map.
"""

from datetime import timedelta

import frappe
from frappe import _
from frappe.utils import cint, getdate, now_datetime

from ..shared import facts
from . import markers, model


@frappe.whitelist(methods=["GET"])
def shape() -> dict:
    """The drawn network: every line's geometry, every stop's position.

    Sent whole rather than by bounding box. A city's network is a few hundred
    lines and a few thousand stops — under a megabyte of coordinates, cached by
    the browser for the session — and paging it would mean redrawing the map on
    every pan, which is the thing that makes a web map feel like a web page.
    """
    if not frappe.has_permission("Transit Line", "read"):
        frappe.throw(_("You cannot read this."), frappe.PermissionError)

    lines = frappe.get_all(
        "Transit Line",
        filters={"status": ("!=", "Retired")},
        fields=["name", "short_name", "line_name", "mode", "colour", "shape", "status",
                "marker_shape", "emoji"],
        order_by="short_name asc",
        limit_page_length=0,
    )
    for line in lines:
        line["shape"] = frappe.parse_json(line.get("shape") or "null")
    # Already resolved, so the browser is handed a line that knows what it looks
    # like rather than a mapping table it would have to apply itself.
    markers.resolve(lines)

    stops = frappe.get_all(
        "Transit Stop",
        filters={"status": ("!=", "Closed")},
        fields=["name", "stop_name", "stop_code", "latitude", "longitude", "status", "emoji"],
        order_by="stop_name asc",
        limit_page_length=0,
    )
    interchange = _served()
    for stop in stops:
        stop["served"] = interchange.get(stop["name"], 0)

    return {"lines": lines, "stops": stops}


def _served() -> dict:
    """How many lines have actually been seen at each stop.

    Every transit map ever printed draws an interchange larger than a plain
    stop, and it is not decoration — it is the thing a person navigating is
    looking for. Until `arrivals.py` there was nothing here to draw it from:
    this model has no stop-to-line relation, and GTFS's own lives on a trip
    rather than a line.

    So the number is *observed* rather than declared: how many distinct lines
    have had a vehicle stand at this stop. Which is better than a timetable
    would be, and worth saying plainly — a stop the timetable claims is an
    interchange but where the second line has not run for a month is not one,
    and this draws it the way it actually is.
    """
    if not facts.exists(model.STOP_HOUR):
        return {}

    rows = frappe.db.sql(
        f"""SELECT `stop`, COUNT(DISTINCT `line`) AS `lines_seen`
            FROM `{model.STOP_HOUR.table}` GROUP BY `stop`""",
        as_dict=True,
    )
    return {row["stop"]: cint(row["lines_seen"]) for row in rows if row.get("stop")}


@frappe.whitelist(methods=["GET"])
def days() -> dict:
    """Which days there is anything to play back.

    The scrubber needs to know where its track ends, and "the last thirty days"
    is a lie on a workspace that connected a source yesterday. Read off the
    partitions rather than by counting rows: the answer is in the table's own
    metadata and costs nothing.
    """
    if not frappe.has_permission("Transit Vehicle", "read"):
        frappe.throw(_("You cannot read this."), frappe.PermissionError)

    rows = frappe.db.sql(
        f"""SELECT DATE(`at`) AS day, COUNT(*) AS readings
            FROM `{model.OBSERVATION.table}`
            GROUP BY DATE(`at`) ORDER BY day DESC LIMIT 60"""
    ) if facts.exists(model.OBSERVATION) else []

    return {
        "days": [{"day": str(day), "readings": cint(readings)} for day, readings in rows],
        "now": str(now_datetime()),
    }


@frappe.whitelist(methods=["GET"])
def punctuality(line: str = "", days_back: int = 30) -> dict:
    """How late this line runs, by hour and by weekday.

    The aggregate tier read forwards, which is the whole of README §7a: no
    model, no fitted anything — the numbers the roll-up already computed,
    grouped the way a scheduler reads them.
    """
    if not frappe.has_permission("Transit Line", "read"):
        frappe.throw(_("You cannot read this."), frappe.PermissionError)

    end = getdate() + timedelta(days=1)
    start = end - timedelta(days=max(1, min(cint(days_back) or 30, 400)))

    if not facts.exists(model.SERVICE_HOUR):
        return {"hours": [], "from": str(start), "to": str(end)}

    rows = facts.aggregate(
        model.SERVICE_HOUR,
        start=start,
        end=end,
        group=["hour", "dow"],
        measures={
            "readings": ("sum", "readings"),
            "delay_avg": ("avg", "delay_avg"),
            "delay_max": ("max", "delay_max"),
            "occupancy_avg": ("avg", "occupancy_avg"),
        },
        where={"line": line} if line else None,
    )
    return {"hours": rows, "from": str(start), "to": str(end)}


@frappe.whitelist(methods=["GET"])
def bunching(line: str = "", gap_m: int = 300) -> dict:
    """Vehicles on one line that have caught each other.

    The highest ratio of value to effort in the whole product, and no model at
    all: two positions, one distance. An operator can act on this — hold one,
    turn the other — which is more than can be said for most of what a
    dashboard shows them.

    Equirectangular rather than haversine. At the distances that matter here —
    under a kilometre — the error is centimetres, and it is three operations
    rather than eight on every pair.
    """
    from . import live

    frame = live.at(line=line)
    vehicles = [v for v in frame["vehicles"] if not v["stale"] and v.get("lat")]

    by_line: dict[str, list] = {}
    for one in vehicles:
        by_line.setdefault(one["line"], []).append(one)

    pairs = []
    limit = max(50, cint(gap_m) or 300)
    for on_line, group in by_line.items():
        for at, first in enumerate(group):
            for second in group[at + 1:]:
                metres = _metres(first["lat"], first["lon"], second["lat"], second["lon"])
                if metres <= limit:
                    pairs.append(
                        {
                            "line": on_line,
                            "vehicles": [first["vehicle"], second["vehicle"]],
                            "metres": int(metres),
                            "lat": (first["lat"] + second["lat"]) / 2,
                            "lon": (first["lon"] + second["lon"]) / 2,
                        }
                    )

    pairs.sort(key=lambda p: p["metres"])
    return {"pairs": pairs[:100], "moment": frame["moment"]}


def _metres(lat1, lon1, lat2, lon2) -> float:
    import math

    mean = math.radians((lat1 + lat2) / 2)
    x = math.radians(lon2 - lon1) * math.cos(mean)
    y = math.radians(lat2 - lat1)
    return math.hypot(x, y) * 6371000
