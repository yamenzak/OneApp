"""Bringing a customer's data with them, from a Frappe site that is still in use.

Every workspace that replaces something arrives with years of it, and the naive
answer — a script somebody runs once — gets it wrong twice. It runs once, and
the system it read from keeps moving, so the cutover becomes a night nobody
works and a morning of typing in whatever changed.

So this is an engine, and five properties are what make it one:

**Idempotent.** Every source row's target is remembered in `Import Identity`, so
a second run updates the record the first one made rather than making another.
That single table is also what lets a link resolve: an invoice's `party` becomes
the Customer an earlier step created out of the same source row.

**Incremental.** Each step keeps a watermark — the newest `modified` it has
taken across — and asks the source only for rows at or after it. Run it a month
before the cutover to rehearse, run it again at midnight, and the second run
carries only the delta. That is the "up to the last second" part, and it is
three lines rather than a feature.

**Resumable.** The watermark advances per committed batch, not per run. A step
that dies in the middle of two thousand rows resumes near where it stopped.

**Answerable.** A row that will not save is kept whole — what the source said,
what we made of it, and what refused it — as an `Import Issue`. A migration is
then a list to work through rather than a log to read.

**Rehearsable.** A dry run fetches, maps, resolves and validates, and commits
nothing. It is the only honest way to learn what a migration will do before it
does it, and the counts it reports are real.

Nothing here is about any one customer. A plan is data — steps, field maps,
value maps — so the next workspace arriving off its own Frappe site is a plan
and no code.

## The field map

Keyed by *target* fieldname, because what is being built is the target: read it
top to bottom and it is the record you end up with. Each value is one of:

    {"from": "party"}                                    copy a field across
    {"from": "type", "values": {...}, "default": "..."}  copy through a map
    {"from": "project", "link": "RUA Project"}           resolve to what an
                                                         earlier step made of
                                                         that source row
    {"const": "RUA Contracting"}                         the same on every row
    {"when": [["absent", "Absent"]], "default": "Present"}
                                                         the first of these
                                                         fields that is true
                                                         gives its value

A `link` that resolves to nothing is an issue on that row rather than a blank
saved quietly, because a link that silently did not arrive is the failure people
find months later in a report that is missing a third of its rows.

## One row over there, many rows here

The second most common shape a migration takes, after one-to-one. RUA keeps
attendance as one row per *day* holding a JSON object keyed by employee — 307
rows that have to become about twenty thousand — and a system that could only
map one row to one row would leave it behind, which is exactly why nothing in
that system can report on attendance.

A step says so with `fan_out`:

    {"from": "attendance_log", "shape": "map"}    an object: each key is a row
    {"from": "items", "shape": "list"}            an array: each item is a row

Each piece becomes its own target record, built from the parent's fields with
the piece's own merged over them and `__key` holding the key it came in under —
so the employee is `{"from": "__key", "link": "RUA Employee"}` and the day is
still `{"from": "date"}` off the parent.

Identity is `parent:key`, which keeps every promise the engine makes: a second
run updates the twenty thousand rather than making twenty thousand more, and a
day edited on the old system re-crosses only its own employees.

## The layers

In import order. A module may use the ones above it, never below:. A module may use the ones above it, never below:

    source      reaching the other site, and reading rows off it
    mapping     one site's row as this one's, and what could not be resolved
    writing     writing a mapped row, its files, and where it came from
    running     the run: steps, batches, progress
    checking    what a plan would do, before it does any of it
    screen      the import screen

`checking` is deliberately below `running` rather than beside it: a check is a
dry run, and it reads the same mapping and the same fan-out the real run would,
so that "what it says it will do" and "what it does" cannot drift apart.
"""

from .source import (
	ALL_FIELDS,
	BATCH,
	TIMEOUT,
	_endpoint,
	_get,
	attachments,
	download,
	fetch,
	preview,
	verify,
	whole,
)
from .mapping import (
	SELF,
	Unresolved,
	_lines,
	_number,
	_pick,
	build,
	explode,
	maps_children,
	resolve,
	vocabulary,
)
from .writing import _attach, _issue, _mark, _point_at_ours, _remember, _write, carry
from .running import _step, execute, progress, start
from .checking import (
	LOOK,
	SAMPLE,
	_check_fan_out,
	_check_step,
	_one_with_lines,
	_our_fields,
	_their_fields,
	check,
)
from .screen import console, install_plan, issues, save_source

__all__ = [
	"ALL_FIELDS",
	"BATCH",
	"LOOK",
	"SAMPLE",
	"SELF",
	"TIMEOUT",
	"Unresolved",
	"_attach",
	"_check_fan_out",
	"_check_step",
	"_endpoint",
	"_get",
	"_issue",
	"_lines",
	"_mark",
	"_number",
	"_one_with_lines",
	"_our_fields",
	"_pick",
	"_point_at_ours",
	"_remember",
	"_step",
	"_their_fields",
	"_write",
	"attachments",
	"build",
	"carry",
	"check",
	"console",
	"download",
	"execute",
	"explode",
	"fetch",
	"install_plan",
	"issues",
	"maps_children",
	"preview",
	"progress",
	"resolve",
	"save_source",
	"start",
	"verify",
	"vocabulary",
	"whole",
]
