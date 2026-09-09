"""VDV 452, read into the same model GTFS is.

README §1 is the whole argument for this file existing in the shape it does:
the internal model is GTFS's, and every format is an importer into it. Model on
VDV's entities and we have built a German product that needs rewriting the
first time somebody in Vienna asks. So nothing here introduces a noun — a
`REC_ORT` becomes a Transit Stop, a `LINIE` becomes a Transit Line, a `REC_FRT`
becomes a trip, and `SEL_FZT_FELD` becomes rows in the timetable.

**The format.** A delivery is one or more ASCII files, usually `.x10`, usually
inside a zip, and each is a sequence of tables written as declaration and rows:

    mod; 09.09.2026; 12:00:00; free
    tbl; REC_ORT
    atr; ORT_NR; ORT_NAME; ORT_POS_LAENGE; ORT_POS_BREITE
    frm; num[9.0]; char[40]; num[9.0]; num[9.0]
    rec; 1000; "Hauptbahnhof"; 13400000; 52500000
    end; REC_ORT

`atr` names the columns and every `rec` after it is positional against that
list — which is the one thing a reader must not get wrong, because a delivery
that reorders its columns between versions is legal and produces a stop called
`52500000` rather than an error.

**What is dropped, deliberately.** VDV 452 carries planning concepts GTFS has no
word for: vehicle duties (`REC_UMLAUF`), driver rosters, block numbers, depot
allocations. Nothing this product draws reads them, and modelling them would be
building the second model §1 exists to refuse. They are skipped rather than
stored-and-ignored, so nobody later mistakes an empty table for a missing
feature.

**What is guessed, and why it is said out loud.** Coordinates. VDV 452 states
them as integers whose scale is declared per delivery — WGS84 in millionths of a
degree in most exports, tenths of an arc-second in some — and a great many
deliveries in the wild carry no declaration at all. `_degrees` picks by
magnitude, which is unambiguous for any coordinate on Earth and is still a
guess. It is the one place here that could be quietly wrong, so it has a test
with both scales in it.

Derived from no Frappe code; the format is the VDV specification's. Written
from a working understanding of it rather than from the document itself — read
the spec before trusting an edge case, and correct this file where it disagrees.
"""

import io
import json
import zipfile
from datetime import date, datetime

import frappe
from frappe import _
from frappe.utils import cint, flt

from . import conflicts
from . import model
from . import timetable as timetablelib
from ..shared import facts

#: The tables this reads. Everything else in a delivery is skipped — see the
#: docstring on what is dropped and why it is not stored-and-ignored.
WANTED = {
    "MENGE_UNTERNEHMEN",
    "REC_ORT",
    "REC_HP",
    "LINIE",
    "REC_LID",
    "LID_VERLAUF",
    "REC_FRT",
    "SEL_FZT_FELD",
    "ORT_HZTF",
    "FIRMENKALENDER",
    "MENGE_FZG",
}

#: What a delivery is written in. `ISO8859-1` is what the specification says and
#: what nearly every export uses; a `chs` line may say otherwise and is obeyed.
DEFAULT_CHARSET = "iso-8859-1"

CHARSETS = {
    "ISO8859-1": "iso-8859-1",
    "ISO-8859-1": "iso-8859-1",
    "UTF8": "utf-8",
    "UTF-8": "utf-8",
}

#: Above this, a coordinate is in tenths of an arc-second rather than in
#: millionths of a degree. 180° is 1.8e8 in the first scale and 6.48e9 in the
#: second, so nothing on Earth is ambiguous — see `_degrees`.
DEGREE_SCALE = 1_000_000
ARCSECOND_TENTHS = 36_000_000  # tenths of an arc-second in one degree


def _charset(text: bytes) -> str:
    """What the delivery says it is written in, if it says.

    Read off the raw bytes because it has to be: the answer decides how to
    decode them, so decoding first to find out is circular. `chs` is ASCII in
    every charset a delivery can legally use.
    """
    for line in text[:4096].split(b"\n"):
        if line.lower().startswith(b"chs"):
            named = line.decode("ascii", "ignore").split(";")[-1].strip().strip('"')
            return CHARSETS.get(named.upper(), DEFAULT_CHARSET)
    return DEFAULT_CHARSET


def _split(line: str) -> list[str]:
    """One record's fields. Semicolons, trimmed, and quotes are not data."""
    return [one.strip().strip('"').strip() for one in line.split(";")]


def tables(text: str) -> dict[str, list[dict]]:
    """Every table in one file, as lists of dicts keyed by their `atr` names.

    Positional against the *current* `atr` line and nothing else. A delivery
    that reorders its columns between two versions is legal, and a reader that
    remembered the first order would name a stop after its longitude.
    """
    found: dict[str, list[dict]] = {}
    table, columns = "", []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line[0] in "#*":
            continue
        kind, _sep, rest = line.partition(";")
        kind = kind.strip().lower()

        if kind == "tbl":
            table = rest.strip().strip('"').upper()
            columns = []
        elif kind == "atr":
            columns = [one.upper() for one in _split(rest)]
        elif kind == "end":
            table, columns = "", []
        elif kind == "rec" and table in WANTED and columns:
            values = _split(rest)
            found.setdefault(table, []).append(
                dict(zip(columns, values, strict=False))
            )
    return found


def _degrees(value) -> float:
    """One VDV coordinate as degrees.

    Two scales are in use and a delivery may declare neither, so this picks by
    magnitude: 13.4° is 13,400,000 in millionths of a degree and 482,400,000 in
    tenths of an arc-second, and no coordinate on Earth falls in both ranges.
    A guess, and the one thing in this file that could be quietly wrong — a
    stop at the wrong scale lands in the Atlantic rather than throwing.
    """
    try:
        # Its own parse rather than `flt`, because an empty or dashed
        # coordinate is a real thing a delivery contains and "no position" is
        # an answer here, not an error to propagate out of an import.
        number = float(str(value or "").strip() or 0)
    except ValueError:
        return 0.0
    if not number:
        return 0.0
    if abs(number) > 180 * DEGREE_SCALE:
        return number / ARCSECOND_TENTHS
    return number / DEGREE_SCALE


def _seconds(value) -> int:
    """A VDV time. Seconds from midnight of the service day, which is already
    what the timetable stores — see `timetable.py` on why that is not a time."""
    return cint(value)


def load(feed_name: str, content: bytes) -> dict:
    """Read one VDV 452 delivery into the model. Returns what it found.

    Same contract as `gtfs.load`, which is the point: `sources.deliver` does not
    know which of them it called, and every screen above this reads the model
    rather than a format.
    """
    feed = frappe.get_doc("Transit Feed", feed_name)
    model.ensure_all()

    merged: dict[str, list[dict]] = {}
    for text in _files(content):
        for name, rows in tables(text).items():
            merged.setdefault(name, []).extend(rows)

    counts = {"agencies": 0, "lines": 0, "stops": 0, "trips": 0, "stop_times": 0}

    agency = _agency(feed, merged, counts)
    stops = _stops(feed, merged, counts)
    lines = _lines(feed, merged, agency, counts)
    patterns = _patterns(merged)
    _shapes(lines, patterns, stops, merged)
    counts["stop_times"] = _timetable(feed, merged, lines, stops, patterns, counts)

    feed.db_set("lines_seen", counts["lines"], update_modified=False)
    feed.db_set("stops_seen", counts["stops"], update_modified=False)
    feed.db_set("trips_seen", counts["trips"], update_modified=False)
    feed.db_set("status", "Loaded", update_modified=False)
    feed.db_set(
        "notes",
        ", ".join(f"{value} {key}" for key, value in counts.items() if value)
        or _("The delivery held no table this can read."),
        update_modified=False,
    )
    frappe.db.commit()
    return counts


def _files(content: bytes):
    """The delivery's text, however it was packed.

    A zip of `.x10` files is the common shape and a single bare file is legal,
    so both are read rather than one being refused for not being the other.
    """
    if content[:2] == b"PK":
        archive = zipfile.ZipFile(io.BytesIO(content))
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            raw = archive.read(name)
            yield raw.decode(_charset(raw), "replace")
        return
    yield content.decode(_charset(content), "replace")


# --------------------------------------------------------------------------- #
# The nouns
# --------------------------------------------------------------------------- #

def _agency(feed, merged, counts) -> str:
    rows = merged.get("MENGE_UNTERNEHMEN") or []
    if not rows:
        return ""
    row = rows[0]
    key = (row.get("UNTERNEHMEN") or "vdv").strip()
    counts["agencies"] = len(rows)
    return conflicts.record(
        "Transit Agency", key,
        {
            "agency_name": row.get("UN_NAME") or row.get("UNTERNEHMEN_ABK") or key,
            "timezone": "Europe/Berlin",
            "feed": feed.name,
        },
        source=feed.source, feed=feed.name,
    )


def _stops(feed, merged, counts) -> dict:
    """`REC_ORT`, or `REC_HP` where a delivery uses that instead.

    Keyed on `ORT_NR`, which is the number the operator's own systems use and
    is therefore the natural key §6 compares two sources on.
    """
    stops = {}
    for row in (merged.get("REC_ORT") or []) + (merged.get("REC_HP") or []):
        key = (row.get("ORT_NR") or "").strip()
        if not key or key in stops:
            continue
        stops[key] = conflicts.record(
            "Transit Stop", key,
            {
                "stop_name": row.get("ORT_NAME") or row.get("ORT_REF_ORT_NAME") or key,
                "stop_code": key,
                "latitude": _degrees(row.get("ORT_POS_BREITE")),
                "longitude": _degrees(row.get("ORT_POS_LAENGE")),
                "status": "Served",
                "feed": feed.name,
            },
            source=feed.source, feed=feed.name,
        )
    counts["stops"] = len(stops)
    return stops


#: VDV's `VERKEHRSMITTEL`, as the words this product uses. Only the ones a
#: German delivery actually carries; anything else is Other rather than a guess.
MODES = {
    "0": "Bus", "1": "Bus", "2": "Tram", "3": "Metro", "4": "Rail",
    "5": "Ferry", "6": "Cable",
}


def _lines(feed, merged, agency, counts) -> dict:
    lines = {}
    for row in merged.get("LINIE") or []:
        key = (row.get("LI_NR") or "").strip()
        if not key or key in lines:
            continue
        short = row.get("LI_KUERZEL") or row.get("LI_KURZNAME") or key
        lines[key] = conflicts.record(
            "Transit Line", key,
            {
                "short_name": short,
                "line_name": row.get("LIDNAME") or row.get("LI_KURZNAME") or short,
                "agency": agency,
                "mode": MODES.get((row.get("VERKEHRSMITTEL") or "").strip(), "Bus"),
                "feed": feed.name,
            },
            source=feed.source, feed=feed.name,
        )
    counts["lines"] = len(lines)
    return lines


def _patterns(merged) -> dict:
    """`LID_VERLAUF`: which stops a route variant calls at, in order.

    Keyed `(line, variant)`, because a line has several and a trip names one.
    This is the piece GTFS puts in `stop_times` per trip and VDV puts once per
    pattern — which is the more compact statement and is why the timetable here
    is assembled rather than read.
    """
    patterns: dict[tuple, list] = {}
    for row in merged.get("LID_VERLAUF") or []:
        key = ((row.get("LI_NR") or "").strip(), (row.get("STR_LI_VAR") or "").strip())
        patterns.setdefault(key, []).append(
            (cint(row.get("LI_LFD_NR")), (row.get("ORT_NR") or "").strip())
        )
    for key in patterns:
        patterns[key].sort()
    return patterns


def _shapes(lines, patterns, stops, merged):
    """A drawn line, from the stops its longest variant calls at.

    VDV 452 carries no geometry between stops — that is `REC_SEL`'s
    `SEL_LAENGE`, a distance and not a shape — so the drawn route is the stop
    positions joined up. Honest and coarse: a map drawn this way follows the
    stops rather than the road, which is visibly true rather than invented.
    """
    longest: dict[str, list] = {}
    for (line_key, _variant), calls in patterns.items():
        if line_key not in lines:
            continue
        if len(calls) > len(longest.get(line_key) or []):
            longest[line_key] = calls

    for line_key, calls in longest.items():
        points = []
        for _order, stop_key in calls:
            name = stops.get(stop_key)
            if not name:
                continue
            row = frappe.db.get_value(
                "Transit Stop", name, ["longitude", "latitude"], as_dict=True
            )
            if row and (row.longitude or row.latitude):
                points.append([flt(row.longitude), flt(row.latitude)])
        if len(points) < 2:
            continue
        frappe.db.set_value(
            "Transit Line", lines[line_key], "shape",
            json.dumps({"type": "LineString", "coordinates": points}),
            update_modified=False,
        )


# --------------------------------------------------------------------------- #
# The timetable
# --------------------------------------------------------------------------- #

def _calendar(merged) -> dict:
    """`FIRMENKALENDER`: which dates each day-type runs, as a weekday bitmask.

    Derived from the dates rather than declared, because VDV states the
    calendar as dates and this product's timetable is a weekly pattern — see
    `timetable.py`. A day-type that only ever falls on a Sunday comes out as
    Sunday, which is what it is.
    """
    days: dict[str, int] = {}
    for row in merged.get("FIRMENKALENDER") or []:
        kind = (row.get("TAGESART_NR") or "").strip()
        when = _date(row.get("BETRIEBSTAG"))
        if not (kind and when):
            continue
        days[kind] = days.get(kind, 0) | (1 << when.weekday())
    return days


def _date(value) -> date | None:
    """VDV writes a date as `YYYYMMDD`, and some exports as `DD.MM.YYYY`."""
    text = str(value or "").strip().strip('"')
    for shape in ("%Y%m%d", "%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, shape).date()
        except ValueError:
            continue
    return None


def _legs(merged) -> dict:
    """`SEL_FZT_FELD`: how long it takes to get from one stop to the next."""
    legs: dict[tuple, int] = {}
    for row in merged.get("SEL_FZT_FELD") or []:
        legs[(
            (row.get("ORT_NR") or "").strip(),
            (row.get("SEL_ZIEL") or "").strip(),
        )] = _seconds(row.get("SEL_FZT"))
    return legs


def _dwells(merged) -> dict:
    """`ORT_HZTF`: how long it waits there. Zero where a delivery omits it,
    which is most of them — a dwell nobody stated is not a dwell of nought and
    is drawn as one either way."""
    return {
        (row.get("ORT_NR") or "").strip(): _seconds(row.get("HP_HZT"))
        for row in merged.get("ORT_HZTF") or []
    }


def _timetable(feed, merged, lines, stops, patterns, counts) -> int:
    """Assemble the plan: every trip, every call, as seconds from midnight.

    A VDV trip states where it starts and when, and the travel times are stated
    once per segment rather than once per trip. So a call time is the trip's
    start plus the legs and dwells before it — which is the whole of what this
    does, and is why VDV deliveries are a fraction of the size of the GTFS
    export of the same network.
    """
    calendar = _calendar(merged)
    legs = _legs(merged)
    dwells = _dwells(merged)

    trips = merged.get("REC_FRT") or []
    counts["trips"] = len(trips)
    timetablelib.runs(feed, {
        (trip.get("FRT_FID") or "").strip(): {
            "line": lines[(trip.get("LI_NR") or "").strip()],
            "headsign": trip.get("FRT_TEXT") or "",
        }
        for trip in trips
        if (trip.get("FRT_FID") or "").strip()
        and (trip.get("LI_NR") or "").strip() in lines
    })

    def calls():
        for trip in trips:
            key = (trip.get("FRT_FID") or "").strip()
            line_key = (trip.get("LI_NR") or "").strip()
            pattern = patterns.get((line_key, (trip.get("STR_LI_VAR") or "").strip()))
            if not (key and pattern and line_key in lines):
                continue

            clock = _seconds(trip.get("FRT_START"))
            previous = ""
            days = calendar.get((trip.get("TAGESART_NR") or "").strip(), 127)
            for seq, (_order, stop_key) in enumerate(pattern, start=1):
                if previous:
                    clock += legs.get((previous, stop_key), 0)
                stop = stops.get(stop_key)
                if stop:
                    yield {
                        "trip_key": key,
                        "line": lines[line_key],
                        "stop": stop,
                        "seq": seq,
                        "arrives_s": clock,
                        "departs_s": clock + dwells.get(stop_key, 0),
                        "days": days,
                        "headsign": trip.get("FRT_TEXT") or "",
                    }
                clock += dwells.get(stop_key, 0)
                previous = stop_key

    return timetablelib.replace(feed.source, calls())
