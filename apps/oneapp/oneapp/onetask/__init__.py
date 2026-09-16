"""OneTask — the work, on somebody else's table.

`docs/WORK.md` §12 is the argument and it reverses the one this module was
built on. Every site in this product has ERPNext, so a task table of our own
was never "ours rather than theirs" — it was a second costing chain, a second
billing path and a second accounting dimension beside ones we already had. So
**ERPNext's `Task` is the unit of work**, the way Frappe HR's Employee is
OnePeople's, and what lives here is the handful of things their Task cannot
express: the column a team named, the rank a card sits at, the labels, the
checklist and the cycle.

The three modules that run on save are `task.py` (the class override, which
names a task after its project and writes their status from our state),
`states.py` (what a column means) and `ranking.py` (where a card sits).
`timing.py` is the clock and writes a `Timesheet Detail`, because that is the
row an invoice reads. `assignment.py` mirrors Frappe's own assignment into a
column, because a board cannot group by a JSON blob.

What it is not is the assignment system. Frappe's ToDo stays exactly what it
is — a pointer at a record that already exists — and the two meet where a task
is assigned, through the framework's own path.

Four small tables are all that is left of ours: `One Task State`, `One Label`
with `One Task Label`, `One Task Step` and `One Cycle`. Every one of them is a
column on ERPNext's Task and nothing else.
"""
