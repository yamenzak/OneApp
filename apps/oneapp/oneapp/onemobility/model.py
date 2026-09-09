"""The fact tables — the half of OneMobility that is not documents.

`scripts/doctypes/mobility.py` holds the reference nouns: lines, stops,
vehicles, the things a person opens and comments on. This holds the data, and
the reason the two are separate is arithmetic rather than taste. See
`README.md` §3.

Two tiers, declared here and swept by `shared/facts.py`:

    observation   where a vehicle was, how full, how late — hot for a month
    serviceHour   the same day rolled up per line, per hour, per weekday, and
                  kept for ever, because that is what every chart reads

`hour` and `dow` are stored on the observation itself rather than derived in
the query. Four bytes a row against an index MariaDB can actually use: a
`GROUP BY HOUR(at)` cannot use an index on `at`, so the roll-up over a day of
two million rows would be a full scan every night for the rest of the product's
life. Denormalising a number the writer already knows is the cheapest thing
here by an order of magnitude.
"""

from ..shared import facts

#: The Single whose `hot_days` and `frozen_days` a workspace edits in Settings →
#: Transit history, and which beats the numbers declared below. Named here
#: rather than imported from `settings.py`, which imports this module.
SETTINGS = "OneMobility Settings"

#: Where a vehicle was, and how it was doing. The big one.
OBSERVATION = facts.declare(
    "observation",
    module="OneMobility",
    when="at",
    columns={
        "at": "datetime",
        "vehicle": "key",
        "line": "key",
        "trip_key": "char",
        "lat": "double",
        "lon": "double",
        # Percent of the vehicle's own capacity, so a bendy bus and a minibus
        # are comparable. -1 for "not reported", which is not the same as
        # empty and must never be drawn as empty.
        "occupancy": "smallint",
        # Seconds behind the timetable; negative is early, which happens more
        # than a scheduler would like.
        "delay_s": "smallint",
        "hour": "smallint",
        "dow": "smallint",
    },
    keys=(
        ("line", "at"),
        ("vehicle", "at"),
        ("trip_key",),
    ),
    hot_days=30,
    settings=SETTINGS,
    # Two aggregates, not one at two grains — see `VEHICLE_DAY` for why the
    # fleet cannot simply be another column on the first.
    rollup=[
        {
            "into": "serviceHour",
            "group": ["line", "hour", "dow"],
            "measures": {
                "readings": ("count", "*"),
                "delay_avg": ("avg", "delay_s"),
                "delay_max": ("max", "delay_s"),
                # The distribution, which is what makes this tier forecastable
                # rather than merely reportable. See `SERVICE_HOUR`.
                "delay_p50": ("p50", "delay_s"),
                "delay_p85": ("p85", "delay_s"),
                "delay_p95": ("p95", "delay_s"),
                "occupancy_avg": ("avg", "occupancy"),
                # The whole distribution and not two points of it. A median
                # with a spread can be turned into "seven runs in ten"; an
                # average and one percentile cannot, which is the same
                # argument the delay columns beside them settled.
                "occupancy_p50": ("p50", "occupancy"),
                "occupancy_p85": ("p85", "occupancy"),
                "occupancy_p95": ("p95", "occupancy"),
            },
        },
        {
            "into": "vehicleDay",
            "group": ["vehicle", "line"],
            "measures": {
                "readings": ("count", "*"),
                "delay_avg": ("avg", "delay_s"),
                "delay_max": ("max", "delay_s"),
                "delay_p85": ("p85", "delay_s"),
                "occupancy_avg": ("avg", "occupancy"),
                "occupancy_max": ("max", "occupancy"),
            },
        },
    ],
)

#: The second roll-up of the same rows, at a grain the first cannot afford.
#:
#: `serviceHour` is per line and per hour, and putting `vehicle` in it would
#: multiply it by the size of the fleet — four thousand rows a year becomes
#: four million for an operator with five hundred buses, on the tier whose
#: whole justification is that a year of it is a rounding error. Per vehicle
#: and per *day* is a hundred and eighty thousand, which is not, and it is
#: enough to answer every question anybody asks about a vehicle: which ones run
#: late, which one is always full, which one stopped reporting in March.
#:
#: `delay_p85` and not only the mean, because a bus that is on time four days
#: in five and twenty minutes late on the fifth has the same average as one
#: that is four minutes late every day, and they are not the same vehicle.
VEHICLE_DAY = facts.declare(
    "vehicleDay",
    module="OneMobility",
    when="at",
    columns={
        "at": "datetime",
        "vehicle": "key",
        "line": "key",
        "readings": "int",
        "delay_avg": "float",
        "delay_max": "smallint",
        "delay_p85": "float",
        "occupancy_avg": "float",
        "occupancy_max": "smallint",
    },
    keys=(("vehicle", "at"), ("line", "at")),
    hot_days=0,
    freeze=False,
)


#: The tier that stays. Small enough that a year of it is a rounding error
#: beside a day of the one above, and it is what answers every long-range
#: question anybody actually asks — and, now, every forward-looking one.
#:
#: **Three percentiles rather than one mean, and that is the difference between
#: a chart and a product.** A mean delay answers no question anybody has: p50 is
#: what an ETA should say, p85 is what a scheduler builds a timetable from, and
#: the distance between p50 and p95 *is* the uncertainty a forecast has to draw.
#: Without them `forecast.py` could offer a number and no spread, and a
#: confident wrong ETA costs more trust than no ETA at all.
#:
#: Four columns and no extra query: `aggregate` computes percentiles in a
#: second pass it was already capable of, and this tier is thousands of rows a
#: year rather than millions.
SERVICE_HOUR = facts.declare(
    "serviceHour",
    module="OneMobility",
    when="at",
    columns={
        "at": "datetime",
        "line": "key",
        "hour": "smallint",
        "dow": "smallint",
        "readings": "int",
        "delay_avg": "float",
        "delay_max": "smallint",
        "delay_p50": "float",
        "delay_p85": "float",
        "delay_p95": "float",
        "occupancy_avg": "float",
        "occupancy_p50": "float",
        "occupancy_p85": "float",
        "occupancy_p95": "float",
    },
    keys=(("line", "at"), ("hour", "dow")),
    # Never expires, never freezes. `sweep` skips a table with no hot window,
    # which is how "this is the tier that stays" is said in code.
    hot_days=0,
    freeze=False,
)


#: A vehicle at a stop. Derived, not reported — see `arrivals.py`.
#:
#: Nothing else in this module has a stop dimension, and a position is not an
#: arrival: a feed says "bus 41 is here", never "bus 41 is serving Alexanderplatz".
#: So this is inferred by a spatial pass and is the one fact table here that is
#: a conclusion rather than a record, which is why every column it carries is
#: something we measured at the moment of the visit and none of them is a
#: boarding. Occupancy tells us how full the bus was, not how many people got
#: on; the difference between two occupancy readings is an estimate with a
#: counter's error either side of it, and this product does not draw an
#: estimate as a fact.
#:
#: `headway_s` is the gap since the previous vehicle on the same line at the
#: same stop, and it is the one number here a rider feels directly. A ten
#: minute timetable running as a pair four minutes apart and then a sixteen
#: minute hole is on time by every average and unusable, and bunching is
#: invisible in every other table in this module.
STOP_EVENT = facts.declare(
    "stopEvent",
    module="OneMobility",
    when="at",
    columns={
        "at": "datetime",
        "stop": "key",
        "line": "key",
        "vehicle": "key",
        "trip_key": "char",
        "delay_s": "smallint",
        "occupancy": "smallint",
        # How long it stayed inside the radius. Two readings a minute apart is
        # a coarse ruler, so this is honest to the feed's own resolution and no
        # finer — a dwell of nought means "seen once", not "did not stop".
        "dwell_s": "smallint",
        "headway_s": "int",
        "hour": "smallint",
        "dow": "smallint",
    },
    keys=(("stop", "at"), ("line", "at"), ("vehicle", "at")),
    rollup={
        "into": "stopHour",
        "group": ["stop", "line", "hour", "dow"],
        "measures": {
            "visits": ("count", "*"),
            "dwell_avg": ("avg", "dwell_s"),
            # How long it stands there, as a distribution. §7a point 6: dwell
            # is what makes an arrival estimate accurate rather than merely
            # present, and an average dwell cannot say "usually thirty seconds
            # and sometimes two minutes", which is the difference between
            # catching a connection and missing it.
            "dwell_p50": ("p50", "dwell_s"),
            "dwell_p85": ("p85", "dwell_s"),
            "headway_avg": ("avg", "headway_s"),
            # And the gap, as one too. Bunching is the gap collapsing, so
            # predicting it needs the shape of the gap rather than its mean —
            # a ten minute timetable running as a pair and then a sixteen
            # minute hole has a perfectly ordinary average.
            "headway_p50": ("p50", "headway_s"),
            # The number a rider experiences. A mean headway is the timetable;
            # the p85 is the wait the complaint is about.
            "headway_p85": ("p85", "headway_s"),
            "delay_avg": ("avg", "delay_s"),
            # What an arrival is actually predicted from: the delay a vehicle
            # has *at this stop* at this hour, as a distribution rather than as
            # an average of a line's whole route.
            "delay_p50": ("p50", "delay_s"),
            "delay_p85": ("p85", "delay_s"),
            "occupancy_avg": ("avg", "occupancy"),
        },
    },
    settings=SETTINGS,
)


#: The tier that answers every question about a stop, and the largest of the
#: three that stay. Per stop, per line, per hour, per weekday, per day: a three
#: thousand stop network with fourteen hours of service writes something like
#: forty thousand rows a night, fifteen million a year, and each is narrow.
#:
#: That is a real cost and it is worth naming rather than discovering. It is
#: still the right trade: the alternative is keeping `stopEvent` for ever,
#: which is two orders of magnitude worse, or having no answer at all to "what
#: does this stop do on a Saturday", which is the question a scheduler opens
#: the product to ask.
STOP_HOUR = facts.declare(
    "stopHour",
    module="OneMobility",
    when="at",
    columns={
        "at": "datetime",
        "stop": "key",
        "line": "key",
        "hour": "smallint",
        "dow": "smallint",
        "visits": "int",
        "dwell_avg": "float",
        "dwell_p50": "float",
        "dwell_p85": "float",
        "headway_avg": "float",
        "headway_p50": "float",
        "headway_p85": "float",
        "delay_avg": "float",
        "delay_p50": "float",
        "delay_p85": "float",
        "occupancy_avg": "float",
    },
    keys=(("stop", "at"), ("line", "at"), ("hour", "dow")),
    hot_days=0,
    freeze=False,
)


#: The timetable: when each trip is *due* at each stop. What a feed plans,
#: against which everything else in this module is what happened.
#:
#: **Stored as a pattern rather than as calendar days**, which is the decision
#: worth defending. Flattening a timetable over the dates it runs is the
#: obvious version and multiplies the table by the length of the horizon — a
#: three thousand stop network is tens of millions of rows a fortnight, rewritten
#: nightly, to say something the pattern already said. A pattern is one row per
#: trip per stop with the weekdays it runs on, and "what is due at Alexanderplatz
#: at 08:15 next Tuesday" is a bitmask test and a range on `arrives_s`.
#:
#: `arrives_s` and `departs_s` are seconds from midnight of the **service day**
#: and not times, for the reason `gtfs._seconds` gives: `25:10:00` is a real and
#: common value meaning ten past one in the morning on the day that began
#: yesterday, and a night bus expressed as a time is a night bus on the wrong
#: day. VDV 452 says the same thing with `SEL_FZT` offsets from a trip's start.
#:
#: It is a fact table for its size and not for its shape, so `when` is the day
#: the version became valid — which means every row of one delivery lands in one
#: partition and the partition prunes nothing. That is the honest trade: the
#: indexes do the work here, and the alternative is a doctype with ten million
#: rows and a controller on every one of them.
SCHEDULE = facts.declare(
    "schedule",
    module="OneMobility",
    when="valid_from",
    columns={
        "valid_from": "datetime",
        "valid_to": "datetime",
        "trip_key": "char",
        "line": "key",
        "stop": "key",
        "seq": "smallint",
        "arrives_s": "int",
        "departs_s": "int",
        # Monday is bit 0. A trip that runs Monday to Friday is 31; one that
        # runs only on a Sunday is 64. Seven booleans would be seven columns
        # and seven indexes to answer one question.
        "days": "smallint",
        "headsign": "char",
        # Which delivery wrote it, so replacing a feed's timetable is one
        # delete and does not take another source's with it.
        "source": "key",
        "hour": "smallint",
    },
    keys=(("line", "valid_from"), ("stop", "valid_from"), ("trip_key", "seq"),
          ("source",)),
    hot_days=0,
    freeze=False,
)


#: One run of one line on one day. Not as heavy as observations and not light
#: enough to be a Document either: a year of a mid-size operator is millions.
TRIP = facts.declare(
    "trip",
    module="OneMobility",
    when="started",
    columns={
        "started": "datetime",
        "trip_key": "char",
        "line": "key",
        "vehicle": "key",
        "headsign": "char",
        "planned_end": "datetime",
        "hour": "smallint",
        "dow": "smallint",
    },
    keys=(("line", "started"), ("trip_key",)),
    hot_days=400,
    settings=SETTINGS,
)


#: What was claimed, before it was known — and what actually happened.
#:
#: **The one table here written by a *forecast* rather than by a feed**, and the
#: reason it has to exist at all: a scorer that recomputes the forecast today
#: and compares it against today is not scoring anything. It is asking a model
#: whether it agrees with itself, and it always does. A prediction is only a
#: prediction if it was written down before the answer was available.
#:
#: Partitioned by `about` — the moment predicted for, not the moment predicted
#: *at* — so scoring a day is one partition rather than a scan for rows whose
#: subject has since passed. `made_at` keeps the other half, because the gap
#: between the two is itself a finding: a claim made a fortnight out and one
#: made last night are not equally impressive when they are both right.
#:
#: The four columns after `basis` are empty until the night the answer arrives.
#: `inside` is the honest headline: not whether the median was close, but
#: whether what happened landed in the range that was offered — a forecast that
#: is confidently wrong and one that is uncertain and right look identical on
#: an error metric and are not the same product.
PREDICTION = facts.declare(
    "prediction",
    module="OneMobility",
    when="about",
    columns={
        "about": "datetime",
        "made_at": "datetime",
        # What was being claimed. `delay` is the network's, per line and hour;
        # room for an arrival's is left by making this a column rather than a
        # second table nobody would keep in step.
        "kind": "char",
        "line": "key",
        "stop": "key",
        "hour": "smallint",
        "dow": "smallint",
        "p50": "float",
        "p85": "float",
        "p95": "float",
        "basis": "int",
        # Filled in by `scoring.settle`, on the night the day it is about ends.
        "actual": "float",
        "error_s": "float",
        "inside": "smallint",
        "scored_at": "datetime",
    },
    keys=(("kind", "about"), ("line", "about")),
    # Kept long and never frozen: this is the smallest table in the module and
    # the one a customer is most likely to ask a year-old question about —
    # "has this got better since spring" is the question scoring exists for.
    hot_days=0,
    freeze=False,
)


#: Every table this module declares, in the order they are created. Written
#: once so `ensure_all` and `drop_all` cannot drift apart — a table created on
#: enable and not dropped on disable is a tenant paying for a fleet they
#: removed.
ALL = (OBSERVATION, SERVICE_HOUR, VEHICLE_DAY, STOP_EVENT, STOP_HOUR, SCHEDULE,
       TRIP,
       PREDICTION)


def ensure_all():
    """Create every table this module declares. Idempotent, cheap, on demand.

    Called when the space is enabled and again on the first write, rather than
    at install: a workspace that never enables OneMobility should not carry its
    tables, and a workspace that does should not have to be migrated for them.
    """
    for fact in ALL:
        facts.ensure(fact)


def drop_all():
    """Remove them. Called when the space is disabled — see `lifecycle.py`."""
    import frappe

    for fact in ALL:
        frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `{fact.table}`")
