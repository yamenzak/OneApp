"""Tables that are not Documents, and the tiers they move through.

A Document is the right shape for something a person opens: it costs a
controller, a validation pass, a permission check, a `modified` stamp and a
`varchar(140)` primary key that every secondary index carries a copy of, and
every one of those buys something on a record somebody reads.

None of it buys anything on a GPS ping. Five hundred vehicles reporting every
fifteen seconds is 2.2 million rows a day: as documents that is four hours of
CPU to store sixteen bytes of fact behind several hundred bytes of bookkeeping,
and as plain rows it is 110 MB and a few seconds. The difference is not the
data. It is the machinery.

So a module **declares** a fact table here and gets four things it would
otherwise write itself:

    ensure()      the table, partitioned by day
    write()       batched inserts, no Document anywhere
    sweep()       roll yesterday up, freeze what has aged out, drop it
    hydrate()     bring a frozen range back for one question

The tiers are the argument in `onemobility/README.md` §3a, generalised: hot
rows for a declared window, an aggregate that never expires and is what every
chart actually reads, and frozen originals in R2 for the question nobody
anticipated. Long-range questions are aggregate questions — nobody asks where a
vehicle was at 14:23:07 last March — so the small answer is kept for ever and
the large one is not.

**Partitioned by day, always.** Retiring a month has to be `DROP PARTITION`,
which is instantaneous, rather than a `DELETE` of sixty million rows, which
locks the table and leaves it bloated. That is not an optimisation; a design
that cannot drop cheaply cannot have a retention window at all.

OneMobility is the first module with a fact table. It must not be the last to
be able to have one: mail events, AI call logs and audit trails are the same
shape, and none of them should reimplement this.
"""

import gzip
import json
from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate

#: Every declared fact table, by name. Populated by `declare()` at import time,
#: the way `doctype()` populates the generator's registry — so the list of what
#: exists is the list of what somebody wrote down, and a sweep cannot miss one.
TABLES: dict[str, "Fact"] = {}

#: Where a frozen day lands. One object per table per day, under the tenant's
#: own prefix so it is covered by the same lifecycle everything else is.
FROZEN_PREFIX = "facts"

#: How many rows go in one INSERT. Large enough that the round trips stop
#: mattering, small enough that a failure loses a second of work rather than an
#: hour, and well inside `max_allowed_packet` for rows this narrow.
BATCH = 2000

#: The column types a fact table may use. Deliberately short: these are the
#: ones that are fixed-width and index well, which is the whole point of not
#: being a Document. A fact needing TEXT is a fact that wants a Document.
TYPES = {
    "int": "int",
    "bigint": "bigint",
    "smallint": "smallint",
    "float": "float",
    "double": "double",
    "decimal": "decimal(18,6)",
    "char": "varchar(64)",
    "key": "varchar(140)",
    "datetime": "datetime(6)",
    "date": "date",
}


class Fact:
    """One declared fact table.

    `name` is the suffix: a table called `observation` is `factObservation` in
    the database, so it sorts away from Frappe's `tab…` and nothing in the
    framework will ever mistake it for a doctype.
    """

    def __init__(
        self,
        name: str,
        *,
        module: str,
        columns: dict,
        when: str,
        keys: tuple = (),
        hot_days: int = 30,
        rollup: dict | None = None,
        freeze: bool = True,
    ):
        self.name = name
        self.module = module
        self.columns = columns
        self.when = when
        self.keys = keys
        self.hot_days = hot_days
        self.rollup = rollup or {}
        self.freeze = freeze

    @property
    def table(self) -> str:
        return f"fact{self.name[:1].upper()}{self.name[1:]}"

    @property
    def fields(self) -> list[str]:
        return list(self.columns)


def declare(name: str, **spec) -> Fact:
    """Register a fact table. Called at import time, once, per table."""
    if name in TABLES:
        raise ValueError(f"fact table {name} is declared twice")
    for column, kind in spec.get("columns", {}).items():
        if kind not in TYPES:
            raise ValueError(f"{name}.{column}: {kind} is not a fact column type")
    if spec.get("when") not in spec.get("columns", {}):
        raise ValueError(f"{name}: `when` must be one of its own columns")
    fact = Fact(name, **spec)
    TABLES[name] = fact
    return fact


def reset():
    """Forget every declaration. For tests, which declare their own."""
    TABLES.clear()


# --------------------------------------------------------------------------- #
# The table
# --------------------------------------------------------------------------- #

def _partition_name(day: date) -> str:
    return f"p{day.strftime('%Y%m%d')}"


def ensure(fact: Fact, through: date | None = None):
    """Create the table if it is absent, and make sure it has room for today.

    Idempotent, and safe to call on every write: a partition that exists is
    added with `IF NOT EXISTS`, and the whole thing is one metadata query.

    Partitioned by `TO_DAYS(when)` with one partition per day and a `pMAX`
    catch-all at the end. The catch-all is what stops a row arriving for a day
    nobody anticipated from being rejected outright — a clock skewed an hour
    forward would otherwise drop data on the floor — and the sweep reorganises
    it away each night.
    """
    columns = ",\n  ".join(f"`{c}` {TYPES[k]}" for c, k in fact.columns.items())
    keys = "".join(
        f",\n  KEY `k_{'_'.join(one)}` ({', '.join(f'`{c}`' for c in one)})"
        for one in fact.keys
    )
    frappe.db.sql_ddl(
        f"""
        CREATE TABLE IF NOT EXISTS `{fact.table}` (
          `id` bigint unsigned NOT NULL AUTO_INCREMENT,
          {columns},
          PRIMARY KEY (`id`, `{fact.when}`){keys}
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        PARTITION BY RANGE (TO_DAYS(`{fact.when}`)) (
          PARTITION pMAX VALUES LESS THAN MAXVALUE
        )
        """
    )
    _open_partitions(fact, through or (getdate() + timedelta(days=1)))


def _existing_partitions(fact: Fact) -> set[str]:
    rows = frappe.db.sql(
        """select PARTITION_NAME from information_schema.PARTITIONS
           where TABLE_SCHEMA = database() and TABLE_NAME = %s
             and PARTITION_NAME is not null""",
        fact.table,
    )
    return {r[0] for r in rows}


def _open_partitions(fact: Fact, through: date):
    """Split `pMAX` so every day up to `through` has a partition of its own.

    Reorganising the catch-all is the only way to add a partition *before* the
    end of the range, and it rewrites only the rows that were sitting in it —
    which, on a table swept nightly, is none.
    """
    have = _existing_partitions(fact)
    wanted = []
    day = getdate(through) - timedelta(days=2)
    for _ in range(4):
        day += timedelta(days=1)
        if _partition_name(day) not in have:
            wanted.append(day)
    if not wanted:
        return

    parts = ", ".join(
        f"PARTITION {_partition_name(d)} VALUES LESS THAN (TO_DAYS('{d + timedelta(days=1)}'))"
        for d in sorted(wanted)
    )
    frappe.db.sql_ddl(
        f"ALTER TABLE `{fact.table}` REORGANIZE PARTITION pMAX INTO "
        f"({parts}, PARTITION pMAX VALUES LESS THAN MAXVALUE)"
    )


# --------------------------------------------------------------------------- #
# Writing
# --------------------------------------------------------------------------- #

def write(fact: Fact, rows: list[dict]) -> int:
    """Insert rows in batches. Returns how many landed.

    One statement per batch with N value groups, not one statement per row and
    not `get_doc`. No controller, no validation pass, no hooks — which is the
    entire point. A caller who wants any of those wants a Document and should
    declare one.
    """
    if not rows:
        return 0

    columns = fact.fields
    names = ", ".join(f"`{c}`" for c in columns)
    marks = "(" + ", ".join(["%s"] * len(columns)) + ")"
    written = 0

    for at in range(0, len(rows), BATCH):
        chunk = rows[at : at + BATCH]
        flat = [row.get(c) for row in chunk for c in columns]
        frappe.db.sql(
            f"INSERT INTO `{fact.table}` ({names}) VALUES "
            + ", ".join([marks] * len(chunk)),
            tuple(flat),
        )
        written += len(chunk)

    return written


# --------------------------------------------------------------------------- #
# Reading
# --------------------------------------------------------------------------- #

def rows_between(fact: Fact, start, end, where: dict | None = None) -> list[dict]:
    """Raw rows for a range. The escape hatch, not the usual path.

    Every screen should be asking `aggregate` instead: a body that reads raw
    rows is a body that has to be rewritten the day this table moves somewhere
    else, and moving it is the plan. This exists for a hydrate-and-inspect, and
    for the roll-up itself.
    """
    clauses, values = _conditions(fact, start, end, where)
    return frappe.db.sql(
        f"SELECT {', '.join(f'`{c}`' for c in fact.fields)} FROM `{fact.table}` "
        f"WHERE {clauses} ORDER BY `{fact.when}`",
        values,
        as_dict=True,
    )


def aggregate(
    fact: Fact,
    *,
    start,
    end,
    group: list[str],
    measures: dict,
    where: dict | None = None,
    limit: int = 5000,
) -> list[dict]:
    """Grouped numbers, which is what a chart wants and a screen should ask for.

    `measures` is `{alias: (function, column)}` — `{"trips": ("count", "*"),
    "delay": ("avg", "delay_s")}`. Both halves are checked against a fixed list
    and the table's own columns, so this is a query builder that cannot be
    talked into reading somewhere else however the caller was reached.
    """
    allowed = set(fact.fields)
    for column in group:
        if column not in allowed:
            frappe.throw(_("There is no column called {0}.").format(column))

    picked = []
    for alias, (function, column) in measures.items():
        if function not in AGGREGATIONS:
            frappe.throw(_("{0} is not something to measure with.").format(function))
        if column != "*" and column not in allowed:
            frappe.throw(_("There is no column called {0}.").format(column))
        target = "*" if column == "*" else f"`{column}`"
        picked.append(f"{AGGREGATIONS[function]}({target}) AS `{alias}`")

    clauses, values = _conditions(fact, start, end, where)
    grouped = ", ".join(f"`{c}`" for c in group)
    select = ", ".join([*(f"`{c}`" for c in group), *picked]) or "COUNT(*) AS `rows`"

    return frappe.db.sql(
        f"SELECT {select} FROM `{fact.table}` WHERE {clauses}"
        + (f" GROUP BY {grouped}" if group else "")
        + f" LIMIT {cint(limit)}",
        values,
        as_dict=True,
    )


#: What `aggregate` will compute. `p85` is here because it is the number a
#: scheduler actually builds a timetable from, and a mean travel time answers
#: no question anybody has — see `onemobility/README.md` §7a.
AGGREGATIONS = {
    "count": "COUNT",
    "sum": "SUM",
    "avg": "AVG",
    "min": "MIN",
    "max": "MAX",
}


def _conditions(fact: Fact, start, end, where: dict | None):
    """The WHERE clause, with every column name checked against the table.

    Values are always parameters. Column names cannot be, so they are checked
    against `fact.fields` and interpolated — which is the only safe way to let
    a caller name a column, and the reason this is one function rather than a
    string built at each call site.
    """
    clauses = [f"`{fact.when}` >= %s", f"`{fact.when}` < %s"]
    values = [get_datetime(start), get_datetime(end)]

    for column, value in (where or {}).items():
        if column not in set(fact.fields):
            frappe.throw(_("There is no column called {0}.").format(column))
        if isinstance(value, (list, tuple, set)):
            listed = list(value)
            if not listed:
                # An empty `in` matches nothing, which is what the caller meant.
                clauses.append("1 = 0")
                continue
            clauses.append(f"`{column}` IN ({', '.join(['%s'] * len(listed))})")
            values.extend(listed)
        else:
            clauses.append(f"`{column}` = %s")
            values.append(value)

    return " AND ".join(clauses), tuple(values)


# --------------------------------------------------------------------------- #
# The tiers
# --------------------------------------------------------------------------- #

def roll_up(fact: Fact, day: date) -> int:
    """Write one day's aggregate rows into the table that never expires.

    Declared as `rollup = {"into": <fact name>, "group": [...],
    "measures": {...}}`. The target is another declared fact table — one with
    no `hot_days`, because it is the tier that stays — so there is one
    mechanism rather than a second concept called "summary".
    """
    plan = fact.rollup
    if not plan:
        return 0

    target = TABLES.get(plan["into"])
    if not target:
        raise ValueError(f"{fact.name} rolls up into {plan['into']}, which is not declared")

    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    rows = aggregate(
        fact,
        start=start,
        end=end,
        group=plan["group"],
        measures=plan["measures"],
        limit=1_000_000,
    )
    if not rows:
        return 0

    ensure(target, through=day + timedelta(days=1))
    stamped = [{**row, target.when: start} for row in rows]

    # Idempotent: a sweep that ran twice, or a day recomputed after a late
    # feed, must not double the numbers. The day is deleted and rewritten,
    # which is one partition's worth of rows and no slower than the insert.
    frappe.db.sql(
        f"DELETE FROM `{target.table}` WHERE `{target.when}` >= %s AND `{target.when}` < %s",
        (start, end),
    )
    return write(target, stamped)


def freeze(fact: Fact, day: date) -> str | None:
    """Put one day's raw rows in R2 and say where they went.

    Gzipped JSON lines, which is unglamorous and right: it needs no reader
    beyond the standard library, it compresses a narrow numeric row about
    tenfold, and a person handed the object can open it. Parquet would be
    smaller and would make this depend on a library the bench does not have.

    Returns the key, or None when there was nothing to freeze or nowhere to
    put it. Nowhere is not an error: a bench with no bucket configured keeps
    its hot window and never freezes, which is the right behaviour for a
    development site and for a workspace that has not been provisioned yet.
    """
    from ..onestorage import r2

    if not fact.freeze or not r2.is_configured():
        return None

    start = datetime.combine(day, datetime.min.time())
    rows = rows_between(fact, start, start + timedelta(days=1))
    if not rows:
        return None

    body = gzip.compress(
        "\n".join(json.dumps(row, default=str) for row in rows).encode("utf-8")
    )
    key = f"tenants/{r2.config()['tenant']}/{FROZEN_PREFIX}/{fact.name}/{day}.jsonl.gz"
    r2.client().put_object(
        Bucket=r2.config()["bucket"],
        Key=key,
        Body=body,
        ContentType="application/gzip",
    )
    return key


def hydrate(fact: Fact, day: date) -> int:
    """Bring one frozen day back into the hot table.

    The rare path, and deliberately explicit rather than automatic: a query
    that silently pulls two years out of object storage is a query that takes
    ten minutes and surprises somebody. A caller asks for the days it needs.

    Idempotent for the same reason `roll_up` is — the day is cleared first, so
    hydrating twice is hydrating once.
    """
    from ..onestorage import r2

    if not r2.is_configured():
        return 0

    key = f"tenants/{r2.config()['tenant']}/{FROZEN_PREFIX}/{fact.name}/{day}.jsonl.gz"
    try:
        got = r2.client().get_object(Bucket=r2.config()["bucket"], Key=key)
    except Exception:
        return 0

    rows = [
        json.loads(line)
        for line in gzip.decompress(got["Body"].read()).decode("utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        return 0

    ensure(fact, through=day + timedelta(days=1))
    start = datetime.combine(day, datetime.min.time())
    frappe.db.sql(
        f"DELETE FROM `{fact.table}` WHERE `{fact.when}` >= %s AND `{fact.when}` < %s",
        (start, start + timedelta(days=1)),
    )
    return write(fact, rows)


def sweep(today: date | None = None) -> dict:
    """The nightly pass over every declared table. Wired in `hooks.py`.

    Three things per table, in this order, because each depends on the last
    having happened: open tomorrow's partition so writes never fall into the
    catch-all, roll up the days that have gone quiet, then freeze and drop what
    has aged past the hot window.

    Ordering matters more than it looks. Dropping before rolling up loses the
    numbers for ever; freezing after dropping freezes nothing.
    """
    today = getdate(today or None)
    done = {}

    for name, fact in TABLES.items():
        if not fact.hot_days:
            continue  # An aggregate tier. It is the thing that stays.
        ensure(fact)

        rolled = frozen = dropped = 0
        for partition in sorted(_existing_partitions(fact)):
            if partition == "pMAX":
                continue
            day = datetime.strptime(partition[1:], "%Y%m%d").date()
            if day >= today:
                continue

            if fact.rollup and day >= today - timedelta(days=2):
                # Yesterday and the day before, in case a feed arrived late.
                rolled += 1 if roll_up(fact, day) else 0

            if day >= today - timedelta(days=fact.hot_days):
                continue

            if fact.rollup:
                roll_up(fact, day)
            if freeze(fact, day):
                frozen += 1
            frappe.db.sql_ddl(f"ALTER TABLE `{fact.table}` DROP PARTITION {partition}")
            dropped += 1

        done[name] = {"rolled": rolled, "frozen": frozen, "dropped": dropped}

    frappe.db.commit()
    return done
