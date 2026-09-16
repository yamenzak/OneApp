# OneTask

Everything there is to do, on a board, in a list or on a day. For one person's
own list, for a team's queue, and for the work inside a project — which are the
same thing with and without a project on it.

`docs/WORK.md` is the study this was built from; this is what it became.

> **Reversed in `docs/WORK.md` §12, and being unwound.** Section 1 below rests
> on a premise that is not true of this product: every site here has ERPNext,
> so a task table of our own is a second costing chain, a second billing path
> and a second accounting dimension beside one we already had. **OneProject is
> now ERPNext's Projects module the way OnePeople is Frappe HR** — their
> `Project`, their `Task`, their `Timesheet`, and ours are the views and the
> five fields their Task cannot express. **OneTask becomes a dock applet over
> the same tasks and owns no table.**
>
> Stages 8 to 10 have landed: the custom fields, the class override, the space,
> the clock and the assignment mirror. Stages 11 and 12 are the applet and the
> deletion, and this file is rewritten when the doctypes below go. Where a
> section is already untrue it says so rather than being quietly left.

---

## 1. The one decision everything follows from

> Reversed. Read the note above: the premise here was never checked against the
> fleet, and it is false.

**The task table is ours.** A site installs the union of what its granted
spaces need — `docs/APPS-AND-SPACES.md` §4 — so a workspace that bought nothing
using ERPNext does not carry ERPNext, and this is the general answer for any
business at all. Building it on ERPNext's `Task` would have undone the one thing
that document bought, and would have brought forty fields, a fixed six-word
status, dependencies in a `Code` field, no order and no labels with it.

So `One Task` is the only task table in the product. A task in a project and a
task in somebody's own list are one row, which is what makes "put this on the
Al Reem project" a link rather than a migration.

**And it is not the assignment system.** An assignment is a pointer at a record
that already exists — Frappe's `ToDo` — and a task is the record. A quotation
assigned to somebody is the quotation with their name on it, not a task called
"quotation". The two meet in exactly one place, and it is the framework's own:
assigning a task goes through `assign_to.add` like every other record, so it
lands in that person's work list beside everything else they have been asked to
look at. Nothing here copies a ToDo and nothing here is one.

---

## 2. The model

    One Task        the unit of work
    One Project     the container, which is also the board
    One Task State  what a board's columns are
    One Label       a tag with a colour
    One Task Step   a checklist inside one task
    One Task Label  which labels are on one

**A board is a project.** One container, drawn as a board or a list or a
calendar. Every competitor with both spends its documentation explaining the
difference and every customer still asks.

**A task with no project is the inbox.** Not a second store and not a flag: a
task nobody has placed *is* unplaced, so the Inbox screen is one filter.

---

## 3. The decisions that cost something

### The columns are data, and the order is not

`docs/WORK.md` §5: Monday's model is that a board's columns are data, and
writing a `Custom Field` when somebody adds one is a migration per click. So
`state` is a **Link** to a row a workspace can rename, recolour and add to.

What that costs is the engine's status machinery, which is Select-shaped: the
badge, the filters and "is it finished" all want a word from a fixed list. So
the state carries a `category` — Backlog, Started, Done, Cancelled — and the
task carries a `status` copied down from it on save. Derived, on one path, from
one place. A project may call its last column Shipped or Signed off and a
progress bar still knows which one is finished.

**The honest bound today** is the order. A board over a Link field has no order
of its own, so the order its columns open in is declared in the manifest and the
set is workspace-wide. Per-project columns wait for the board view to learn to
read that order from data, which is one change in one view type rather than a
second table here.

### The rank is a string, and it is on the record

Where a card sits in its column is a fractional rank — `a0`, `a0V`, `a1` — so
dragging one card rewrites one row rather than two hundred. `ranking.py` has the
alphabet and the argument.

On the record rather than in the reader's own arrangement, unlike the generic
board's card order: a project's order is the team's. One person moving a task
to the top of Backlog is telling everybody it is next, which is the whole point
of a shared board.

### A checklist is not sub-tasks

Three lines and a tick are not three things that each need an owner, a date and
a place on a board. Making people create sub-tasks for them is how a backlog
fills with noise nobody can filter out afterwards. `One Task Step` is the
checklist; `parent_task` is the sub-task.

### The counts are rolled up

A portfolio of forty projects is one query rather than forty, so `open_tasks`
and `done_tasks` are written on the project when a task moves. Including the
project a task *left*, which is the half a rollup forgets.

### The project is a place, not a second engine

A project record is the work, the files, the documents and the mail about it —
and not one line of any of them is written here. Tasks are a declared showcase
tab, filtered by `project`; the Calendar tab is the project's own month, which
`docs/WORK.md` §6(c) gets for free from the tabs it already has; Files is the
door onto OneCloud at that record's own room, where a document written there is
a `File` attached to the project like every upload beside it; Mail is the record
shell's, as it is on every record in the product.

Two things had to be fixed for that to read as one thing rather than seven.

**One way into a doctype.** Three screens here are over `One Task` and all three
point back through `project`, so a project drew three tabs of the same rows —
one of them ("the tasks on no project") empty by construction. A screen carrying
its own filters is a lens on the *space*, and narrowing a lens to one record asks
a question nobody asked: `spaceview/connections.py` now keeps the plain screen
where there is one and falls back to a narrowed screen only where it is the only
way in.

**A tab is a table, and a project is looked at as a board.** So the tab does not
grow a board — it opens the real screen, narrowed, through the `narrow`
parameter the mobility space has carried since §C4 and in the same grammar:
`?screen=tasks&type=board&narrow=project:REEM`. What arrives is an ordinary
filter, seeded into the panel where the reader can see it and take it off, with
a control in the header saying what it is. Every related tab in every space gains
the same door, which is the test of whether it was the right place to put it.

### The plan is one direction stored, and one rule about time

> Superseded, and the code is deleted rather than ported. ERPNext already
> stores what a task waits for — a `Task Depends On` row per edge, the same one
> direction — and already does both halves of what `sequence.py` did:
> `reschedule_dependent_tasks` pushes a plan forward keeping each dependant's
> duration, and `check_recursion` refuses a loop. One thing of theirs was
> broken rather than missing: nothing in ERPNext ever fills that row's
> `project`, which is what their own lookup keys on, so the slip never ran.
> `onetask/task.py` fills it in one line. Two of their rules differ from ours
> and both are defensible — they push only within one project and only tasks
> still `Open`.

A `One Task Link` row hangs off the task that is **waiting** and names what it
waits for. "Blocks" is that same edge read backwards — a query in
`sequence.py`, and a tab on the record through the engine's own child-table
filter (`links.task`, narrowed to `kind = Blocked by`) — because two rows for
one fact is two rows that disagree by Thursday. `Relates to` lives in the same
table and is not a sequence: it is a pointer somebody left for somebody, and a
chart that drew an arrow for it would push dates around for a note.

A loop is refused before the row is saved, with the path named, rather than
discovered by a chart that renders nothing.

And **a plan slips forward and never backwards.** Moving a task's due date
later moves everything waiting on it that would now start too early, each
keeping its own duration, breadth-first with a seen set so a diamond moves its
far end once. The other direction is deliberately not symmetric: finishing
early is not permission to promise somebody else's week, so nothing is ever
pulled earlier. The cascade is bounded at 200 tasks and says so rather than
running.

A **milestone** is a date the project is measured by rather than work in it, so
it has no duration — whichever end it is given becomes both — and the plan
draws it as the diamond every chart of one draws. On ERPNext's Task that
collapse belongs to the *view* rather than the data: `is_milestone` is a box
somebody ticks on an ordinary task that still has a real span, so `GanttBody`
draws the diamond at the end date and leaves the row alone.

### Time is a Timesheet row, and there is no bridge

`docs/WORK.md` §12. A `Timesheet Detail` is a person, a task, a from and a to —
which is exactly what a clock produces, and it is the row a Sales Invoice
reads. So the clock writes one directly, `One Time Entry` is deleted rather
than ported, and `billing.py` — the bridge that posted our hours into theirs —
is deleted with it. Billable time reaches an invoice by *being* what an invoice
reads.

**What is running is a row with no `to_time` on it.** Not a flag, not a cache,
not a key in Redis: the thing that is running *is* the timesheet row, so a
browser that closed, a session that expired and a server that restarted all
leave the same truth on disk. ERPNext is already happy with it — `hours` is
zero, so `set_to_time` leaves the blank alone — and the only thing that refuses
an unfinished row is submitting the sheet, which is exactly when somebody
should be made to look at it. One per person: starting a second stops the first
and says which. Start and Stop are declared verbs — `spaceview/actions.py` — so
they are offered on the open record and in the selection bar alike, and cost a
line of declaration rather than a control.

**A day is a sheet**, and submitting it is the person saying it is right.
ERPNext rolls `actual_time` and the costing onto the task from *submitted*
sheets only, which is not a gap to work around — it is what a timesheet is.
Until then the hours are readable where the clock is: `timing.spent` counts the
drafts too, and says so.

### A cycle is a window, and recurrence is Frappe's

A `One Cycle` is a sprint: a window of time a team pulls work into. It holds no
tasks — one container, and it is the project (§ `docs/WORK.md` §4) — so its
work is the tasks that name it, which is a declared tab like any other.

Repeating tasks are **Frappe's Auto Repeat**, switched on for `One Task` with
one line of declaration. The framework already ships the form, the schedule and
the machinery to stop; what we would have written is a `recurrence` field and a
nightly job, which is that feature with fewer of its parts.

### An automation is a face on Frappe's, and the assignment is still a ToDo

"When a task reaches In review, hand it to the reviewers" is Frappe's own
`Assignment Rule`, wearing the sentence somebody would say —
`onespace/routing.py`, beside the alerts panel it shares a gate and a
vocabulary with. The condition is compiled from three controls rather than
typed, because `assign_condition` is evaluated on every save of every record of
that kind. Unassigning is deliberately not offered: work vanishing from
somebody's list weeks later, with nothing on the record to say why, is a
footgun with a delay on it.

The rule assigns through `assign_to.add`, so what it writes is a **ToDo** —
one assignment store, §2, and the task lands in that person's own work list
beside everything else. `One Task.assigned_to` is a *mirror* of it, written by
`onetask/assignment.py` in both directions: a ToDo cannot be a board column,
and a field that somebody edits on a form must not leave the task on nobody's
list while a column says otherwise.

---

## 4. What is not built

In the order it blocks.

1. **Per-project columns.** The set is data already; the order is not. See §3.
2. **A critical path.** The edges are stored and the slip is honest; what is
   not there is the longest path through them, which is only worth drawing
   once estimates are worth trusting.
3. **An approval step on time.** Every stretch is billable until somebody says
   otherwise, and the bridge posts what it is given; a workspace that wants a
   lead to sign the week off first has no screen for it yet.
4. **Workflow.** Frappe ships one and it is the third automation; what is here
   is alerts and handovers. A state machine with approvals is worth a face of
   its own and nobody has asked for one yet.
