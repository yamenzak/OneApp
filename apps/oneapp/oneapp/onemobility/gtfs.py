"""GTFS static, read into the model.

GTFS before VDV, and GTFS *as* the model, for the reason in README §1: build on
VDV's entities and you have a German product that needs rewriting the first
time somebody in Vienna asks. Every other format — VDV 452, NeTEx — becomes a
normaliser onto what is read here, never a second model.

A feed is a zip of CSVs. The ones that matter:

    agency.txt    who runs it
    routes.txt    what a rider calls the 12
    stops.txt     where the poles are
    trips.txt     one run of one route on one service pattern
    stop_times.txt when each trip is due at each stop
    shapes.txt    the drawn line, which is what a map needs

Idempotent by natural key. A second load of the same feed updates what the
first made rather than doubling it, which is what makes a nightly fetch safe
and is the same promise `onespace/importer.py` makes for a whole workspace.
"""

import csv
import io
import json
import zipfile
from datetime import datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, flt, now_datetime

from ..shared import facts
from . import conflicts
from . import model

#: How many rows of one CSV are held in memory at once. A big-city
#: `stop_times.txt` is hundreds of megabytes, so it is streamed and committed
#: in batches rather than read whole — the same reason `facts.write` batches.
CHUNK = 5000


def _text(archive: zipfile.ZipFile, name: str):
    """One CSV out of the zip, as dicts, or nothing if it is absent.

    Absent is normal: `shapes.txt` is optional in the specification and half
    the feeds in the wild omit it, and a loader that fails on a legal feed is a
    loader nobody can use.
    """
    if name not in archive.namelist():
        return
    with archive.open(name) as handle:
        # utf-8-sig: a feed exported from a Windows tool carries a BOM, and a
        # BOM on the first header makes `agency_id` a column nobody can find.
        text = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
        yield from csv.DictReader(text)


def _seconds(value: str) -> int:
    """GTFS time, which is not a clock time.

    `25:10:00` is a real and common value: it means ten past one in the
    morning *on the service day that began yesterday*, which is how a night bus
    is expressed without inventing a date. `datetime.strptime` refuses it, so
    the value is kept as seconds from midnight of the service day and turned
    into a real moment only when the day is known.
    """
    parts = (value or "").strip().split(":")
    if len(parts) != 3:
        return 0
    try:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    except ValueError:
        return 0


def _upsert(doctype: str, key_field: str, key: str, values: dict,
            source: str = "", feed: str = "") -> str:
    """One reference record, by natural key. The idempotence lives here.

    Through `conflicts.record` rather than a bare save, so what this delivery
    claims is written down beside what every other source claims for the same
    key. Where this is the only source saying anything, that is one extra row
    and the record is what it always was — see `conflicts.py` for why the
    alternative, quietly overwriting, is the thing customers stop trusting.
    """
    return conflicts.record(doctype, key, values, source=source, feed=feed)


def load(feed_name: str, content: bytes) -> dict:
    """Read one GTFS zip into the model. Returns what it found.

    Everything is attributed to the feed, so a wrong number is answerable: the
    record says which delivery it came from, and the delivery says which source
    and when.
    """
    feed = frappe.get_doc("Transit Feed", feed_name)
    model.ensure_all()

    archive = zipfile.ZipFile(io.BytesIO(content))
    counts = {"agencies": 0, "lines": 0, "stops": 0, "trips": 0, "stop_times": 0}

    agencies = {}
    for row in _text(archive, "agency.txt") or ():
        key = (row.get("agency_id") or row.get("agency_name") or "").strip()
        if not key:
            continue
        agencies[key] = _upsert(
            "Transit Agency", "agency_key", key,
            {
                "agency_name": row.get("agency_name") or key,
                "timezone": row.get("agency_timezone") or "Europe/Berlin",
                "url": row.get("agency_url") or "",
                "feed": feed.name,
            },
            source=feed.source, feed=feed.name,
        )
        counts["agencies"] += 1

    # Shapes first, because a line wants one and a shape is read whole. Held in
    # memory: a shape file is coordinates, and even a large network's is a few
    # megabytes — unlike stop_times, which is not.
    shapes: dict[str, list] = {}
    for row in _text(archive, "shapes.txt") or ():
        shapes.setdefault(row.get("shape_id") or "", []).append(
            (
                cint(row.get("shape_pt_sequence")),
                flt(row.get("shape_pt_lon")),
                flt(row.get("shape_pt_lat")),
            )
        )

    lines = {}
    line_shape = {}
    for row in _text(archive, "routes.txt") or ():
        key = (row.get("route_id") or "").strip()
        if not key:
            continue
        colour = (row.get("route_color") or "").strip()
        lines[key] = _upsert(
            "Transit Line", "line_key", key,
            {
                "short_name": row.get("route_short_name") or key,
                "line_name": row.get("route_long_name") or row.get("route_short_name") or key,
                "agency": agencies.get((row.get("agency_id") or "").strip(), ""),
                "mode": MODES.get((row.get("route_type") or "").strip(), "Other"),
                "colour": f"#{colour}" if colour else "",
                "feed": feed.name,
            },
            source=feed.source, feed=feed.name,
        )
        counts["lines"] += 1

    stops = {}
    for row in _text(archive, "stops.txt") or ():
        key = (row.get("stop_id") or "").strip()
        if not key:
            continue
        stops[key] = _upsert(
            "Transit Stop", "stop_key", key,
            {
                "stop_name": row.get("stop_name") or key,
                "stop_code": row.get("stop_code") or "",
                "latitude": flt(row.get("stop_lat")),
                "longitude": flt(row.get("stop_lon")),
                "zone": row.get("zone_id") or "",
                "status": "Served",
                "feed": feed.name,
            },
            source=feed.source, feed=feed.name,
        )
        counts["stops"] += 1

    # Which days each service pattern runs. `calendar.txt` is seven booleans
    # per service id, which is exactly the bitmask the timetable stores — see
    # `timetable.py`. `calendar_dates.txt`, which is the exceptions to it, is
    # deliberately not read: a public holiday timetable is a different service
    # on a named date and belongs to a Service Day record nobody has asked for
    # yet, and folding it into the weekly pattern would say the wrong thing
    # about every other week.
    services = {}
    for row in _text(archive, "calendar.txt") or ():
        key = (row.get("service_id") or "").strip()
        if not key:
            continue
        services[key] = sum(
            1 << at for at, name in enumerate(WEEKDAYS)
            if (row.get(name) or "").strip() == "1"
        )

    # Trips, and the shape each one draws, so a line can be given the geometry
    # of the pattern most of its trips actually run.
    trips = {}
    for row in _text(archive, "trips.txt") or ():
        key = (row.get("trip_id") or "").strip()
        route = (row.get("route_id") or "").strip()
        if not key or route not in lines:
            continue
        trips[key] = {
            "line": lines[route],
            "headsign": (row.get("trip_headsign") or "")[:64],
            "shape": (row.get("shape_id") or "").strip(),
            # 127 for a feed with no calendar at all, which is legal and
            # common: every day beats no day, because a trip that runs on no
            # day is one no screen can ever show and nobody can debug.
            "days": services.get((row.get("service_id") or "").strip(), 127),
        }
        if trips[key]["shape"]:
            line_shape.setdefault(lines[route], trips[key]["shape"])
        counts["trips"] += 1

    for line, shape_id in line_shape.items():
        points = sorted(shapes.get(shape_id) or [])
        if len(points) < 2:
            continue
        frappe.db.set_value(
            "Transit Line", line, "shape",
            json.dumps({"type": "LineString", "coordinates": [[x, y] for _, x, y in points]}),
            update_modified=False,
        )

    counts["trip_rows"] = _load_trips(feed, trips)
    counts["stop_times"] = _load_stop_times(archive, feed, trips, stops)

    feed.db_set("lines_seen", counts["lines"], update_modified=False)
    feed.db_set("stops_seen", counts["stops"], update_modified=False)
    feed.db_set("trips_seen", counts["trips"], update_modified=False)
    feed.db_set("status", "Loaded", update_modified=False)
    feed.db_set(
        "notes",
        ", ".join(f"{value} {key}" for key, value in counts.items() if value),
        update_modified=False,
    )
    frappe.db.commit()
    return counts


#: `calendar.txt`'s seven columns, in the order the bitmask numbers them —
#: Monday is bit 0, which is `date.weekday()`'s own numbering and therefore the
#: one place this file does not have to convert anything.
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday")


def _load_stop_times(archive, feed, trips: dict, stops: dict) -> int:
    """The timetable: when each trip is due at each stop.

    The one file here that does not fit in memory. A big-city `stop_times.txt`
    is hundreds of megabytes and tens of millions of rows, so it is read as a
    stream and written in batches of `CHUNK` — and it is written through
    `timetable.replace`, which swaps this source's whole plan rather than
    merging it into whatever was there before. A timetable half from March and
    half from April is one nobody ever published.

    Times are kept as seconds from midnight of the service day rather than as
    times, which is `_seconds` above and README's night-bus argument: 25:10:00
    is ten past one on the day that began yesterday.
    """
    def calls():
        for row in _text(archive, "stop_times.txt") or ():
            trip = trips.get((row.get("trip_id") or "").strip())
            stop = stops.get((row.get("stop_id") or "").strip())
            if not (trip and stop):
                continue
            arrives = _seconds(row.get("arrival_time") or row.get("departure_time"))
            yield {
                "trip_key": (row.get("trip_id") or "").strip(),
                "line": trip["line"],
                "stop": stop,
                "seq": cint(row.get("stop_sequence")),
                "arrives_s": arrives,
                "departs_s": _seconds(row.get("departure_time")) or arrives,
                "days": trip["days"],
                "headsign": trip["headsign"],
            }

    from . import timetable

    return timetable.replace(feed.source, calls())


def _load_trips(feed, trips: dict) -> int:
    """Write the trip facts.

    Separate from the timetable above and kept: this is one row per *run*,
    which the network screen counts and the roll-up uses as a denominator,
    where the timetable is one row per run per stop.
    """
    if not trips:
        return 0

    day = frappe.utils.getdate()
    rows = []
    for key, trip in trips.items():
        started = datetime.combine(day, datetime.min.time()) + timedelta(hours=6)
        rows.append(
            {
                "started": started,
                "trip_key": key[:64],
                "line": trip["line"],
                "vehicle": "",
                "headsign": trip["headsign"],
                "planned_end": started + timedelta(hours=1),
                "hour": started.hour,
                "dow": started.weekday(),
            }
        )

    facts.ensure(model.TRIP)
    return facts.write(model.TRIP, rows)


#: GTFS route types, as the words this product uses. Only the ones a European
#: feed actually carries; anything else is Other rather than a guess.
MODES = {
    "0": "Tram",
    "1": "Metro",
    "2": "Rail",
    "3": "Bus",
    "4": "Ferry",
    "5": "Cable",
    "6": "Cable",
    "7": "Cable",
    "11": "Bus",
    "12": "Rail",
}


@frappe.whitelist(methods=["POST"])
def load_feed(source: str, file_url: str = "", label: str = "") -> dict:
    """Take a delivery from an upload and read it.

    The Upload door of the four in README §5, and the one a manager tries
    first. The others — SFTP, HTTP, socket — fetch differently and then arrive
    at the same `sources.deliver`, so there is one place a feed is recorded and
    one place it is normalised.
    """
    if not frappe.has_permission("Transit Feed", "create"):
        frappe.throw(_("You cannot load a feed."), frappe.PermissionError)

    from .sources import deliver

    return deliver(source, _bytes_of(file_url) or b"", label=label, file_url=file_url)


def _bytes_of(file_url: str) -> bytes | None:
    if not file_url:
        return None
    name = frappe.db.get_value("File", {"file_url": file_url}, "name")
    if not name:
        return None
    return frappe.get_doc("File", name).get_content()
