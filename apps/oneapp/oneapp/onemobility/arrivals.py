"""Turning positions into visits, which is the only way a stop gets a number.

Every other fact table here records something a feed said. This one records a
conclusion: a feed reports "vehicle 41 is at 52.5219, 13.4132" and never
"vehicle 41 is serving Alexanderplatz", and without that second sentence a stop
has no history at all — no dwell, no headway, no answer to what it does on a
Saturday. GTFS has `stop_times`, but that is a *timetable*: it says where a bus
was meant to be, and the whole product is the difference between that and where
it was.

So the visit is inferred, spatially, from the positions we already have:

    a vehicle is *at* a stop while it is within `RADIUS` metres of it, and one
    unbroken run of readings inside that circle is one visit

which is deliberately the weakest claim that is still useful. It needs no
stop-to-line relation — this model has none, and GTFS's own is a property of a
trip rather than a line — and it finds a bus serving a stop it was never
scheduled for, which is a thing operators do and timetables do not record.

What it will not do is count boardings. Occupancy is a percentage of capacity
with a counter's error either side of it, and the difference between two of
them is that error twice over; a boarding figure derived that way is a guess,
and this product does not draw a guess as a fact. See `README.md` §7a.

The cost is one pass per vehicle per day over rows an index already orders, and
a grid so a reading is compared against the stops near it rather than all of
them. Naively it is observations times stops — for a mid-size operator, four
billion distance calculations a night — and the grid makes it about one.
"""

from datetime import datetime, timedelta
from math import cos, radians

import frappe
from frappe.utils import cint, flt, get_datetime, getdate

from ..shared import facts
from . import model

#: How close is *at* the stop. Fifty metres is the figure GTFS-RT consumers
#: settle on, and it is a compromise in both directions: tighter and a reading
#: taken while the doors are open across a wide forecourt misses; looser and
#: two stops on opposite sides of a junction become one. A vehicle inside two
#: circles is credited to the nearer.
RADIUS = 50.0

#: Metres per degree of latitude. Longitude is this times the cosine of the
#: latitude, which is why the grid is built around a network's own latitude
#: rather than assuming a square degree.
METRES_PER_DEGREE = 111_320.0

#: A gap longer than this ends a visit even if the vehicle never left the
#: circle. A bus that sits at a terminus for twenty minutes between runs has
#: made two visits and not one long one, and the layover in the middle is not
#: dwell.
BREAK_S = 300

#: How far apart a counted stop and an inferred visit may be and still be the
#: same call. Two clocks, not one: a counter stamps the moment its doors opened
#: and a visit is stamped when the vehicle was first seen inside the radius, so
#: the gap is the approach. Five minutes is longer than any approach and
#: shorter than a headway on the lines a counter is fitted to; wider than this
#: and a busy stop starts matching the lap before.
COUNT_WINDOW_S = 300

#: The most vehicles one day's pass will walk. A fleet larger than this wants
#: the pass sharded across workers rather than a longer timeout, and answering
#: with what we have beats a job that never finishes.
MAX_VEHICLES = 5000


def _index(stops: list[dict]) -> tuple[dict, float, float]:
    """Stops in a grid whose cell is one radius across.

    A reading then looks at nine cells rather than every stop in the network,
    and nine is the whole of the optimisation: the cell is exactly the radius,
    so a stop within range is always in one of the neighbours.
    """
    if not stops:
        return {}, 0.0, 0.0

    middle = sum(flt(one["latitude"]) for one in stops) / len(stops)
    lat_size = RADIUS / METRES_PER_DEGREE
    lon_size = RADIUS / (METRES_PER_DEGREE * max(0.1, cos(radians(middle))))

    grid: dict[tuple, list] = {}
    for one in stops:
        cell = (int(flt(one["latitude"]) // lat_size), int(flt(one["longitude"]) // lon_size))
        grid.setdefault(cell, []).append(one)
    return grid, lat_size, lon_size


def _nearest(grid, lat_size, lon_size, lat, lon) -> dict | None:
    """The stop this reading is inside, or nothing. Nearest wins a tie."""
    if not grid:
        return None

    home = (int(lat // lat_size), int(lon // lon_size))
    scale = METRES_PER_DEGREE * max(0.1, cos(radians(lat)))

    best = None
    closest = RADIUS
    for down in (-1, 0, 1):
        for across in (-1, 0, 1):
            for one in grid.get((home[0] + down, home[1] + across), ()):
                north = (flt(one["latitude"]) - lat) * METRES_PER_DEGREE
                east = (flt(one["longitude"]) - lon) * scale
                away = (north * north + east * east) ** 0.5
                if away <= closest:
                    best, closest = one, away
    return best


def _visits(rows: list[dict], grid, lat_size, lon_size) -> list[dict]:
    """One vehicle's day, as the stops it was at.

    A visit opens when a reading falls inside a circle and closes when one
    falls outside it, when the stop changes, or when the feed goes quiet for
    longer than `BREAK_S`. The arrival's own delay and occupancy are kept and
    not the visit's average: what a rider met is the bus that pulled in.
    """
    out = []
    open_at = None

    def close():
        if open_at:
            out.append(open_at)

    for row in rows:
        lat, lon = row.get("lat"), row.get("lon")
        if lat is None or lon is None:
            continue
        when = get_datetime(row["at"])
        near = _nearest(grid, lat_size, lon_size, flt(lat), flt(lon))

        if not near:
            close()
            open_at = None
            continue

        gone = open_at and (when - open_at["_last"]).total_seconds() > BREAK_S
        if open_at and (open_at["stop"] != near["name"] or gone):
            close()
            open_at = None

        if not open_at:
            open_at = {
                "at": when,
                "stop": near["name"],
                "line": row.get("line") or "",
                "vehicle": row.get("vehicle") or "",
                "trip_key": row.get("trip_key") or "",
                "delay_s": cint(row.get("delay_s")),
                "occupancy": cint(row.get("occupancy", -1)),
                "dwell_s": 0,
                # Not nought: nought is a bus arriving on the heels of another,
                # and this is a bus with nothing in front of it. `_headways`
                # fills it in where there is an answer and leaves it NULL where
                # there is not, which is what keeps it out of the average
                # instead of dragging the average down.
                "headway_s": None,
                "hour": when.hour,
                "dow": when.weekday(),
                "_last": when,
            }
        else:
            open_at["_last"] = when
            open_at["dwell_s"] = min(32000, int((when - open_at["at"]).total_seconds()))

    close()
    return out


def _headways(visits: list[dict]) -> None:
    """How long since the last one, per stop and per line. Written in place.

    Only the visits that have a previous one are given a number; the first of
    each day at each stop keeps its NULL, so it is skipped by the average
    rather than counted as a headway of nought. The day boundary does cost a
    real headway either side of midnight — the alternative is reading the
    previous day back on every run, for one row per stop per line on a service
    that is mostly not running at the time.
    """
    ordered: dict[tuple, list] = {}
    for one in visits:
        ordered.setdefault((one["stop"], one["line"]), []).append(one)

    for series in ordered.values():
        series.sort(key=lambda one: one["at"])
        for before, after in zip(series, series[1:]):
            after["headway_s"] = int((after["at"] - before["at"]).total_seconds())


def _counted(visits: list[dict], start, end) -> None:
    """Put the measured boardings onto the visits they belong to. In place.

    Every visit arrives here with `boarded` and `alighted` unset, and leaves
    with them either filled in from a counter or set to `-1`. There is no third
    answer and there is deliberately no inferred one: `model.STOP_EVENT` says
    why, and VDV 457-3 is the interface that made the measured kind possible
    — `vdv457.py`.

    The counts are an input to this pass rather than an output of it, which is
    the whole reason they live in their own table. `build` deletes and rewrites
    a day; anything written straight into `stopEvent` would not survive the
    next sweep.

    Where a vehicle called at one stop more than once in a day, the nearest
    count in time wins and is then spent, so two laps get their own counts
    rather than the same one twice. The clocks differ by design — a counter
    stamps the moment its doors opened, a visit is stamped when the vehicle was
    first seen nearby — so nearness is the only honest match and the window is
    generous.
    """
    from . import vdv457

    for one in visits:
        one["boarded"] = -1
        one["alighted"] = -1

    found = vdv457.since(start, end)
    if not found:
        return

    for one in visits:
        candidates = found.get((one["vehicle"], one["stop"]))
        if not candidates:
            continue
        nearest = min(
            candidates,
            key=lambda row: abs((get_datetime(row["at"]) - one["at"]).total_seconds()),
        )
        # The window applies only to a stamp the counter made. 457-3's
        # corrected form carries no per-stop time, so those rows are stamped
        # from the journey's departure and can be minutes out by the end of
        # the route — see `exact` on `model.STOP_COUNT`. For them the stop and
        # the day are the match, and the nearest visit is the one.
        if cint(nearest.get("exact", 1)) and abs(
            (get_datetime(nearest["at"]) - one["at"]).total_seconds()
        ) > COUNT_WINDOW_S:
            continue
        candidates.remove(nearest)
        one["boarded"] = cint(nearest["boarded"])
        one["alighted"] = cint(nearest["alighted"])
        # The counter's dwell is the doors, not a sample of how long a vehicle
        # sat inside a radius. Where it has one, it is the better number.
        if cint(nearest["dwell_s"]):
            one["dwell_s"] = min(32000, cint(nearest["dwell_s"]))


def build(day=None) -> int:
    """Write one day's visits. Idempotent — the day is replaced, not added to.

    Called by the nightly sweep through `hooks.py`, and by hand after a feed
    arrives late. Rewriting rather than appending is what makes a second run
    free of consequence, which is the only way a derived table stays
    trustworthy.
    """
    day = getdate(day or (getdate() - timedelta(days=1)))
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)

    # Asked before the doctype is touched, because this runs from the nightly
    # scheduler on every site — including the ones that never enabled
    # OneMobility, where `Transit Stop` does not exist to be queried.
    if not facts.exists(model.OBSERVATION):
        return 0

    stops = frappe.get_all(
        "Transit Stop",
        filters={"latitude": ("is", "set"), "longitude": ("is", "set")},
        fields=["name", "latitude", "longitude"],
        limit_page_length=0,
    )
    grid, lat_size, lon_size = _index(stops)
    if not grid:
        return 0

    model.ensure_all()
    table = model.OBSERVATION.table
    fleet = [
        row["vehicle"]
        for row in frappe.db.sql(
            f"SELECT DISTINCT `vehicle` FROM `{table}` "
            f"WHERE `at` >= %s AND `at` < %s LIMIT {int(MAX_VEHICLES)}",
            (start, end),
            as_dict=True,
        )
        if row.get("vehicle")
    ]

    visits = []
    for vehicle in fleet:
        # One vehicle at a time, on the `(vehicle, at)` index: bounded memory
        # and a sorted read, rather than pulling a fleet-day into a list and
        # sorting it in Python.
        rows = frappe.db.sql(
            f"SELECT `at`, `line`, `vehicle`, `trip_key`, `lat`, `lon`, `occupancy`, `delay_s` "
            f"FROM `{table}` WHERE `vehicle` = %s AND `at` >= %s AND `at` < %s ORDER BY `at`",
            (vehicle, start, end),
            as_dict=True,
        )
        visits.extend(_visits(rows, grid, lat_size, lon_size))

    _headways(visits)
    _counted(visits, start, end)
    for one in visits:
        one.pop("_last", None)

    frappe.db.sql(
        f"DELETE FROM `{model.STOP_EVENT.table}` WHERE `at` >= %s AND `at` < %s", (start, end)
    )
    written = facts.write(model.STOP_EVENT, visits) if visits else 0
    facts.roll_up(model.STOP_EVENT, day)
    frappe.db.commit()
    return written

