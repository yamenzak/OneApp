# OneTask

A door onto the work, from wherever you are standing. Not a space, not a task
table, and no project of its own: a dock window over ERPNext's `Task` — the
same rows OneProject's board draws — where you can put a thought down, tick
something off and start the clock without leaving the page you were on.

`docs/WORK.md` is the study this was built from and §12 is the correction that
made it this. The short version of that correction is below, because it is the
thing everything in this directory follows from.

---

## 1. The one decision everything follows from

**The task table is ERPNext's.** Stages 1 to 7 of the arc built a `One Task`,
a `One Project` and a plan of our own, on one premise: that a workspace which
bought nothing using ERPNext does not carry ERPNext. **Every site in this
product has ERPNext.** The premise was never checked against the fleet and it
is not true here.

With it gone the argument inverts. A second task table and a second project
table are not "ours rather than theirs" — they are a second costing chain, a
second billing path, a second accounting dimension, a second Gantt, a second
project-template system, and a standing tax on every ERPNext release we would
otherwise inherit for free.

So the rule is OnePeople's, exactly: **OnePeople is Frappe HR with better
views and the four things HRMS lacks**, and it owns no employee table.
**OneProject is ERPNext's Projects module on the same terms**, and OneTask is
a door onto it.

    OneProject   the space. ERPNext `Project` is the record, ERPNext `Task`
                 is the unit of work, ERPNext `Timesheet` is the time.
                 Ours: the views, and the five things their Task lacks.

    OneTask      this directory. The five things, the behaviour that writes
                 them, and a service. It owns no table of work.

**And it is not the assignment system.** An assignment is a pointer at a record
that already exists — Frappe's `ToDo` — and a task is the record. The two meet
in exactly one place and it is the framework's own: assigning a task goes
through `assign_to.add` like every other record, so it lands in that person's
work list beside everything else they have been asked to look at.

---

## 2. The model

Four small tables, and every one of them is a column on somebody else's
doctype:

    One Task State  what a board's columns are — `Task.custom_state`
    One Label       a tag with a colour
    One Task Label  which labels are on a task — `Task.custom_labels`
    One Task Step   a checklist inside one task — `Task.custom_steps`
    One Cycle       a sprint a team pulls work into — `Task.custom_cycle`

and three fields with no table behind them: `Task.custom_rank`,
`Task.custom_assigned_to`, and `Project.custom_key`. They are declared in
`oneapp_control/spaces/oneproject.py`, because a custom field belongs to the
space that renders it.

**A task with no project is the inbox.** Not a second store and not a flag:
ERPNext's Task has an optional project, so a task nobody has placed *is*
unplaced and the Inbox is one filter. This is the thing that makes the service's
capture box cost nothing.

---

## 3. The decisions that cost something

### The columns are data, and the status is derived from them

ERPNext's `Task.status` is seven fixed words and three of them are machinery:
`Overdue` is computed from a date, `Template` marks a task that is not work,
and `Pending Review` is a word no category means. A team that wants a Design
review column cannot have one.

So `custom_state` is a **Link** to `One Task State` — a row, which is the whole
of "each board has its own columns", and a workspace may rename, recolour and
add to the set. Each state carries a `category`, and `states.STATUS_OF` maps
the four categories onto ERPNext's own words. `task.py` writes `status` from
the state on every save, before `super().validate()`, because their validation
reads it: for the dependency check, for `completed_on`, for the project
rollup. One direction, one path, and the two vocabularies cannot disagree.

The order a board draws them in is declared in the manifest, because a board
over a Link field has no order of its own. Per-project columns wait for the
board to learn to read that order from data.

### The rank is a string, and it is on the record

Dragging one card to the top of a column of two hundred should rewrite one row
and not two hundred — two hundred `modified` bumps, two hundred version rows,
two hundred websocket messages. `ranking.py` mints a fractional rank the way
LexoRank publishes it: base-36, and a new value can always be found *between*
two existing ones.

On the record rather than in the reader's own arrangement, unlike the generic
board's card order. A project's order is the team's: one person moving a task
to the top of Backlog is telling everybody it is next.

### A task is named after its project

`REEM-14` is what people say to each other and `TASK-2026-00042` is not. That
needs `Task.autoname` to change, which means `override_doctype_class` on
somebody else's doctype — the supported hook, and one this repository already
uses four times. Frappe runs `autoname` before the doctype's own
`naming_series` rule, so a project with no key falls straight through to
ERPNext's series with nothing to configure.

The counter is per prefix, which makes it per project for free. A project that
changes its key leaves its existing tasks named after the old one, which is
right: a task's id is what somebody wrote on a whiteboard.

### A checklist is not sub-tasks

Three lines and a tick are not three things that each need an owner, a date and
a place on a board. Making people create sub-tasks for them is how a backlog
fills with noise nobody can filter out. Sub-tasks are ERPNext's `parent_task`,
which is a real nested set; a checklist is `One Task Step`.

### The plan is ERPNext's, and one line of theirs was broken

They already store what a task waits for — a `Task Depends On` row per edge,
one direction, the same shape stage 5 wrote — and they already do both halves
of what `sequence.py` did: `reschedule_dependent_tasks` pushes a plan forward
when a date moves, keeping each dependant's own duration, and `check_recursion`
refuses a loop with one recursive CTE per direction. So `sequence.py` was
deleted rather than ported.

One thing of theirs was broken rather than missing. `reschedule_dependent_tasks`
looks its dependants up by `{"task": self.name, "project": self.project}` on
`Task Depends On`, and **nothing in ERPNext ever writes that row's `project`**
— not the controller, not `populate_depends_on`, not the desk form. So the slip
found nothing and silently never ran. `task.py` fills it in one line, and their
own code works. It is the one place this module fixes something of theirs
rather than adding something of ours, and it is a candidate to upstream.

Two of their rules differ from what stage 5 wrote and both are defensible: they
push only within one project, and only tasks still `Open`.

A **milestone** is `is_milestone`, theirs, and on their Task it is a box
somebody ticks on an ordinary task that still has a real span. Collapsing that
to a point belongs in the **view** rather than the data — `GanttBody` draws the
diamond at the end date — because rewriting the row would be changing what a
team said to suit a chart.

### Time is a Timesheet row, and there is no bridge

A `Timesheet Detail` is a person, a task, a from and a to, which is exactly
what a clock produces and exactly what a Sales Invoice reads. So `timing.py`
writes one directly; `One Time Entry` and the bridge that posted its rows into
theirs are deleted rather than ported. Billable time reaches an invoice by
*being* what an invoice reads, and fixed-price work is a Sales Order against
the same Project, which is an accounting dimension.

**What is running is a row with no `to_time` on it.** Not a flag, not a cache,
not a key in Redis: the thing that is running *is* the timesheet row, so a
browser that closed, a session that expired and a server that restarted all
leave the same truth on disk. ERPNext is already happy with one — `hours` is
zero, so `set_to_time` leaves the blank alone and `calculate_hours` skips it —
and the only thing that refuses an unfinished row is submitting the sheet,
which is exactly when somebody should be made to look at it. One per person:
starting a second stops the first and says which.

**A day is a sheet**, and submitting it is the person saying it is right.
ERPNext rolls `actual_time` and the costing onto the task from *submitted*
sheets only, which is not a gap to work around — it is what a timesheet is.
Until then `timing.spent` counts the drafts too, and says so.

Start and Stop are declared verbs — `spaceview/actions.py` — so they are
offered on the open record and in the selection bar alike, and cost a line of
manifest rather than a control.

### The assignment is a ToDo, mirrored into a column

A ToDo cannot be a column: a board groups by a field, a list sorts by one, a
dashboard counts by one, and `_assign` is a JSON blob nothing can group by. So
`Task.custom_assigned_to` is a mirror of it — written from the assignment,
never instead of it — and `assignment.py` keeps the two in step in both
directions, because both happen: a rule assigns, and somebody edits the field
on a form because it is a field on a form.

Frappe's two ways of ending an assignment finally earn their difference here.
`close_all_assignments` writes **Closed**, which is what ERPNext's
`Task.unassign_todo` does the moment a task reaches Completed; `_remove` writes
**Cancelled**, which is a person being taken off it. So a finished task keeps
the name on its card and an unassigned one loses it, from one query.

### A cycle is a window, and recurrence is Frappe's

A `One Cycle` is a sprint: a window of time a team pulls work into. It holds no
tasks — one container, and it is the project — so its work is the tasks that
name it, which is a declared tab like any other.

Repeating tasks are **Frappe's Auto Repeat**. The framework already ships the
form, the schedule and the machinery to stop; what we would have written is a
`recurrence` field and a nightly job, which is that feature with fewer of its
parts.

### An automation is a face on Frappe's

"When a task reaches In review, hand it to the reviewers" is Frappe's own
`Assignment Rule` wearing the sentence somebody would say —
`onespace/routing.py`, beside the alerts panel it shares a gate and a
vocabulary with. The condition is compiled from three controls rather than
typed, because `assign_condition` is evaluated on every save of every record of
that kind. Unassigning is deliberately not offered: work vanishing from
somebody's list weeks later, with nothing on the record to say why, is a
footgun with a delay on it.

### The service is a door, and it owns nothing

`service.py`, and `frontend/src/modules/onetask`. A 400px window over the same
rows, and every verb in it is something a person could have done by going to
OneProject. What it is for is the cost of going there: catching a thought
without leaving the document you are writing, ticking something off without
losing the quotation you were in the middle of.

Three controls and two lists, and the restraint is the design. **Capture** is a
text box that is always there rather than a New button, because the whole claim
is that a thought costs one keystroke. **Mine** is `_assign`. **Inbox** is the
tasks with no project. A **tick** writes `custom_state` and never `status`.
The clock is `timing.py`'s, the same one the space's verb presses.

Pressing a row takes the **page** to that record, in OneProject, and leaves the
window where it was. One read answers all of it — `service.now()` — because a
380px window that reflows three times as three requests land is worse than one
that waits. The tile is live exactly when this workspace has a space over those
tasks, and dark with a reason when it has not.

`/one/tasks` is the maximised case, for the same reason OneCloud keeps
`/files`: a window has no address, and a pasted link should land somewhere.

---

## 4. What is not built

In the order it blocks.

1. **Per-project columns.** The set is data already; the order is not, because
   a board over a Link field has no order of its own. One change in one view
   type.
2. **A critical path.** The edges are ERPNext's and the slip is theirs; what is
   not there is the longest path through them, which is only worth drawing once
   estimates are worth trusting.
3. **An approval step on time.** A stretch on a customer's project is billable
   until somebody unticks it; a workspace that wants a lead to sign the week
   off before it can be invoiced has ERPNext's submit and no screen of ours for
   it yet.
4. **The service on a phone.** It is a dock window and the dock is desktop only
   — `docs/DESKTOP.md` stage 7 is where a phone gets one.
5. **Workflow.** Frappe ships one and it is the third automation; what is here
   is alerts and handovers. A state machine with approvals is worth a face of
   its own and nobody has asked for one.
