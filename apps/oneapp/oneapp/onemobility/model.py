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
    rollup={
        "into": "serviceHour",
        "group": ["line", "hour", "dow"],
        "measures": {
            "readings": ("count", "*"),
            "delay_avg": ("avg", "delay_s"),
            "delay_max": ("max", "delay_s"),
            "occupancy_avg": ("avg", "occupancy"),
        },
    },
)


#: The tier that stays. Small enough that a year of it is a rounding error
#: beside a day of the one above, and it is what answers every long-range
#: question anybody actually asks.
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
        "occupancy_avg": "float",
    },
    keys=(("line", "at"), ("hour", "dow")),
    # Never expires, never freezes. `sweep` skips a table with no hot window,
    # which is how "this is the tier that stays" is said in code.
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
)


def ensure_all():
    """Create every table this module declares. Idempotent, cheap, on demand.

    Called when the space is enabled and again on the first write, rather than
    at install: a workspace that never enables OneMobility should not carry its
    tables, and a workspace that does should not have to be migrated for them.
    """
    for fact in (OBSERVATION, SERVICE_HOUR, TRIP):
        facts.ensure(fact)


def drop_all():
    """Remove them. Called when the space is disabled — see `lifecycle.py`."""
    import frappe

    for fact in (OBSERVATION, SERVICE_HOUR, TRIP):
        frappe.db.sql_ddl(f"DROP TABLE IF EXISTS `{fact.table}`")
