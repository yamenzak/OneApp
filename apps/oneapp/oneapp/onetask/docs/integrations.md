# Integrations

## ERPNext — the deep one

This module is mostly a set of decisions about ERPNext's Projects module.

**`Task`** is subclassed through `override_doctype_class`, the supported hook,
which this repository already uses four times. The subclass writes `status`
from `custom_state` and fills `Task Depends On.project`.

**The plan is theirs and `sequence.py` was deleted rather than ported.** They
already store an edge per row, one direction, in the shape stage 5 wrote; they
already push a plan forward when a date moves (`reschedule_dependent_tasks`,
keeping each dependant's own duration) and already refuse a loop
(`check_recursion`, one recursive CTE per direction).

Two of their rules differ from what stage 5 wrote and both are defensible: they
push only within one project, and only tasks still `Open`.

**One line of theirs was broken**, and this is the one place the module fixes
something of theirs rather than adding something of ours: nothing in ERPNext
ever writes `Task Depends On.project`, so their own slip found nothing. A
candidate to upstream.

**A milestone is `is_milestone`, theirs**, and on their Task it is a box
somebody ticks on an ordinary task that still has a real span. Collapsing that
to a point belongs in the **view** — `GanttBody` draws the diamond at the end
date — because rewriting the row would be changing what a team said to suit a
chart.

**`Timesheet` is the clock and there is no bridge.** A `Timesheet Detail` is a
person, a task, a from and a to, which is exactly what a clock produces and
exactly what a Sales Invoice reads. `One Time Entry` and the bridge that posted
its rows into theirs were deleted. Billable time reaches an invoice by *being*
what an invoice reads; fixed-price work is a Sales Order against the same
Project, which is an accounting dimension.

## Frappe

**`ToDo`** is the assignment, and assigning goes through `assign_to.add` like
every other record, so a task lands in that person's work list beside
everything else they have been asked to look at. This module is **not** the
assignment system: an assignment is a pointer at a record that already exists,
and a task is the record.

**`Auto Repeat`** is recurrence. The framework ships the form, the schedule and
the machinery to stop; what we would have written is a `recurrence` field and a
nightly job, which is that feature with fewer of its parts.

**`Assignment Rule`** is the automation. "When a task reaches In review, hand
it to the reviewers" is that rule wearing the sentence somebody would say.

## OneProject

The space. Its manifest declares every custom field this module writes, because
a custom field belongs to the space that renders it — so `Task.custom_state` is
declared in `oneapp_control/spaces/oneproject.py` and read here.

The service's tile is live exactly when this workspace has a space over those
tasks, and dark with a reason when it has not.

## The engine (`onespace`)

* **`spaceview/actions.py`** — Start and Stop are declared verbs.
* **`routing.py`** — the automation's face, beside the alerts panel it shares a
  gate and a vocabulary with. The condition is compiled from three controls
  rather than typed, because `assign_condition` is evaluated on every save of
  every record of that kind.
* **The desk** — the service is a dock window. `docs/DESKTOP.md`.

## OneCalendar

A task with a date is on somebody's diary because OneProject's manifest
declares a calendar over `Task`, not because either module knows about the
other. `docs/WORK.md` §6 is the argument that a calendar is one question rather
than three.

## OneLegal

Nothing. This module registers no clause: it adds no subprocessor, sends
nothing outside and stores nothing a person would not expect a task tracker to.

## OneAI

See `ai.md`.
