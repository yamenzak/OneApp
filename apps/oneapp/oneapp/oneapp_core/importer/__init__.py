"""Bringing another Frappe site's records onto this one.

The layers, in import order. A module may use the ones above it, never below:

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
