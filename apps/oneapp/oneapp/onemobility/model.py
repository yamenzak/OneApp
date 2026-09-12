"""The fact tables — the half of OneMobility that is not documents.

`scripts/doctypes/mobility.py` holds the reference nouns: lines, stops,
vehicles, the things a person opens and comments on. This holds the data, and
the reason the two are separate is arithmetic rather than taste. See
`README.md` §3.

Two tiers, declared here and swept by `shared/facts.py`:

    observation   where a vehicle was, how full, how late — hot for a month
    serviceHour   the same day rolled up per line, per hour, per weekday, and
                  kept for ever, because that is what every chart reads
    vehicleEvent  what the vehicle said about itself — a door, a trip state,
                  a broken counter. Edges rather than samples, which is what
                  keeps it a tenth of `observation`

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
        # How many got on and off, and **only where a counter said so**. The
        # paragraph above rules out a boarding inferred from two occupancy
        # readings, and that still stands: what changed is that VDV 457-3
        # exists, and an automatic counter's in/out per door is a measurement
        # rather than a difference between two estimates. `-1` for "nobody
        # counted this visit", which is the distinction `occupancy` already
        # keeps and for the same reason — averaged in as nought, an uncounted
        # stop makes a busy one look quiet.
        "boarded": "smallint",
        "alighted": "smallint",
        # How long it stayed inside the radius. Two readings a minute apart is
        # a coarse ruler, so this is honest to the feed's own resolution and no
        # finer — a dwell of nought means "seen once", not "did not stop".
        # A counted visit overwrites it with the door timings, which are the
        # dwell rather than a sample of it.
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
            # Summed, where every other measure here is a distribution: a
            # boarding is a thing that happened rather than a reading, and
            # the question a planner asks of a stop-hour is how many people
            # used it, not how many used it on average.
            "boarded": ("sum", "boarded"),
            "alighted": ("sum", "alighted"),
            # How much of the hour was actually counted. Without it a stop
            # where one vehicle in ten carries a counter reads as a tenth as
            # busy as it is, and nothing on the screen says why.
            "counted": ("count", "boarded"),
        },
    },
    settings=SETTINGS,
)


#: What a counter measured at a stop, before anything is concluded from it.
#:
#: `stopEvent` is derived and rebuilt: `arrivals.build` deletes a day and writes
#: it again from positions, which is what makes a second run free of
#: consequence. A boarding cannot live only there, because the rebuild would
#: erase it — the counts are an *input* to that pass, not an output of it, and
#: this is where they wait.
#:
#: So a 457-3 delivery lands here as it arrived, keyed the way the feed keys it,
#: and `arrivals.build` joins it onto the visit it inferred for the same vehicle
#: at the same stop. A visit with no counter is `-1` and says so; a count with
#: no visit is kept here, because the counter is the better witness and a
#: positions feed that missed the stop is not evidence the bus did not call.
STOP_COUNT = facts.declare(
    "stopCount",
    module="OneMobility",
    when="at",
    columns={
        "at": "datetime",
        "stop": "key",
        "vehicle": "key",
        "trip_key": "char",
        "boarded": "smallint",
        "alighted": "smallint",
        # From the door timings the counter itself reports — when the first
        # door opened to when the last one closed — rather than from how long
        # a vehicle sat inside a radius.
        "dwell_s": "smallint",
        # Whether `at` is the counter's own stamp for this stop, or the
        # journey's departure standing in for it. 457-3's corrected form
        # carries neither a per-stop time nor a door timing — the operator's
        # clearing pass drops both — so a cleared visit knows its journey and
        # its stop and not its minute. The join reads this: an exact stamp is
        # matched inside a few minutes, an inexact one only by stop and day.
        "exact": "smallint",
        "hour": "smallint",
        "dow": "smallint",
    },
    keys=(("stop", "at"), ("vehicle", "at"), ("trip_key",)),
    hot_days=30,
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


#: What a vehicle said about itself: a door opened, a trip ended, a counter
#: broke. The tier the IBIS-IP family lands in — see `vdv301.py` for the
#: vocabulary and README §7e for why it is one table rather than one per
#: service.
#:
#: **Edges, not samples**, and the whole size argument rests on it. A door
#: state service will answer "closed" every second for eight hours; a row is
#: written only where the state *changed*, so a three-door bus calling at
#: sixty stops writes a few hundred rows a day rather than a quarter of a
#: million. Five hundred of them is under two hundred thousand rows a day —
#: a tenth of what `observation` takes at the same fleet size, which is why
#: this can be kept twice as long.
#:
#: Generic on purpose. `kind`/`part`/`value` rather than a column per service
#: is what makes "support the next VDV service" a row in a table instead of a
#: migration, and IBIS-IP alone has twenty-three services in its own
#: `ServiceNameEnumeration`. The cost is that a value is a string; the check
#: that it is a *known* string is `vdv301.KNOWN`, applied where it is drawn
#: rather than where it is stored, because a vehicle reporting something we
#: have never seen is news rather than an error.
VEHICLE_EVENT = facts.declare(
    "vehicleEvent",
    module="OneMobility",
    when="at",
    columns={
        "at": "datetime",
        "vehicle": "key",
        # Empty from a 301 device, which is bolted to a vehicle and knows
        # nothing about the service it is running — the same asymmetry
        # `stopCount` already has, and `arrivals.py` fills both in.
        "line": "key",
        "trip_key": "char",
        "stop": "key",
        "kind": "char",
        # Which door, which device. A `DoorID` is an `IBIS-IP.NMTOKEN` and
        # means nothing outside the vehicle, so it is kept as the vehicle
        # spelled it rather than resolved against anything.
        "part": "char",
        "value": "char",
        # Whatever number the event carries, if it carries one: a count, a
        # span. Nought where it does not, which is safe here in a way it is
        # not on `occupancy` — nobody averages this column across kinds.
        "number": "int",
        # Whether this value is one somebody should look at. Denormalised
        # from `vdv301.TROUBLE` for the same reason `hour` is denormalised
        # from `at`: the attention list is a filter on a column, not a scan
        # with an IN list of pairs.
        "trouble": "smallint",
        "hour": "smallint",
        "dow": "smallint",
    },
    keys=(
        ("vehicle", "at"),
        ("kind", "at"),
        ("line", "at"),
        ("trouble", "at"),
    ),
    # Twice `observation`'s window, and affordable because the table is a
    # tenth the size. "Has that door been sticking all quarter" is the
    # question this tier exists for and a month cannot answer it.
    hot_days=60,
    settings=SETTINGS,
    rollup=[
        {
            "into": "eventHour",
            "group": ["kind", "value", "line", "hour", "dow"],
            "measures": {
                "events": ("count", "*"),
                "trouble": ("sum", "trouble"),
                # The span a state lasted, where the reader worked one out.
                # A distribution rather than a mean for the reason every
                # other tier here keeps one: "the doors are usually open
                # twenty seconds and sometimes two minutes" is the sentence,
                # and a mean of forty says neither half of it.
                "seconds_p50": ("p50", "number"),
                "seconds_p85": ("p85", "number"),
                "seconds_max": ("max", "number"),
            },
        },
    ],
)

#: The distribution the event charts read. Never expires, like every other
#: `*Hour` tier here, because "is that door sticking more than it was in
#: spring" is a question about a year.
EVENT_HOUR = facts.declare(
    "eventHour",
    module="OneMobility",
    when="at",
    columns={
        "at": "datetime",
        "kind": "char",
        "value": "char",
        "line": "key",
        "hour": "smallint",
        "dow": "smallint",
        "events": "int",
        "trouble": "int",
        "seconds_p50": "float",
        "seconds_p85": "float",
        "seconds_max": "int",
    },
    keys=(("kind", "at"), ("line", "at"), ("hour", "dow")),
    hot_days=0,
    freeze=False,
)


#: The same events per vehicle per day, which is the shape the fleet list
#: reads. A second aggregate rather than a grain on the first, for the reason
#: `VEHICLE_DAY` is: a vehicle is a document somebody opens and "how did this
#: bus behave" is a row, where `eventHour` is a network-wide distribution.
EVENT_DAY = facts.declare(
    "eventDay",
    module="OneMobility",
    when="day",
    columns={
        "day": "date",
        "vehicle": "key",
        "kind": "char",
        "events": "int",
        "trouble": "int",
        "seconds_total": "int",
        "seconds_max": "int",
    },
    keys=(("vehicle", "day"), ("kind", "day")),
    hot_days=0,
    freeze=False,
)


#: Every table this module declares, in the order they are created. Written
#: once so `ensure_all` and `drop_all` cannot drift apart — a table created on
#: enable and not dropped on disable is a tenant paying for a fleet they
#: removed.
ALL = (OBSERVATION, SERVICE_HOUR, VEHICLE_DAY, STOP_COUNT, STOP_EVENT, STOP_HOUR,
       VEHICLE_EVENT, EVENT_HOUR, EVENT_DAY,
       SCHEDULE,
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
