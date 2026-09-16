# OneTask

Everything there is to do, on a board, in a list or on a day. For one person's
own list, for a team's queue, and for the work inside a project — which are the
same thing with and without a project on it.

`docs/WORK.md` is the study this was built from; this is what it became.

---

## 1. The one decision everything follows from

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

---

## 4. What is not built

In the order it blocks.

1. **Dependencies and the plan** — `docs/WORK.md` stage 5. `One Task Link`,
   blocking drawn on a Gantt, and milestones that mean something.
2. **Time** — stage 6. `One Time Entry` with a start and a stop, and the bridge
   that posts approved time to an ERPNext Timesheet where a workspace bills
   through ERPNext.
3. **Per-project columns.** The set is data already; the order is not. See §3.
4. **Recurring tasks and cycles** — stage 6.
5. **Automations** — stage 7. Frappe already ships Notification, Assignment
   Rule and Workflow; the work is a face on them, not a second engine.
