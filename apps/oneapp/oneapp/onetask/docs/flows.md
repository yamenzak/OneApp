# Flows

## Saving a task — `task.ProjectTask`

`override_doctype_class` on ERPNext's `Task`, and the order inside `validate`
is load-bearing:

1. **`status` is written from `custom_state`**, through `states.STATUS_OF`,
   **before** `super().validate()`. Their validation reads `status` — for the
   dependency check, for `completed_on`, for the project rollup — so writing it
   after would be writing it too late. One direction, one path, and the two
   vocabularies cannot disagree.
2. **`Task Depends On.project` is filled in.** One line, and it fixes something
   of theirs: `reschedule_dependent_tasks` looks its dependants up by
   `{"task": self.name, "project": self.project}` and *nothing in ERPNext ever
   writes that row's `project`* — not the controller, not `populate_depends_on`,
   not the desk form. So their slip found nothing and silently never ran.
3. `super().validate()` does the rest, including the plan and the recursion
   check, which are theirs.

## Naming — `REEM-14`

`Task.autoname` is overridden to use `Project.custom_key` as the prefix. Frappe
runs `autoname` before the doctype's own `naming_series` rule, so a project
with no key falls straight through to ERPNext's series with nothing to
configure. The counter is per prefix, which makes it per project for free.

A project that changes its key leaves its existing tasks named after the old
one, which is right: a task's id is what somebody wrote on a whiteboard.

## Ranking — `ranking.py`

Dragging one card to the top of a column of two hundred rewrites **one** row.
A fractional rank the way LexoRank publishes it, base-36, so a new value can
always be found between two existing ones. On the record rather than in the
reader's own arrangement: a project's order is the team's, and one person
moving a task to the top of Backlog is telling everybody it is next.

## The clock — `timing.py`

* `start(task)` writes a `Timesheet Detail` with a `from_time` and no
  `to_time`. **What is running is a row with no `to_time`** — not a flag, not a
  cache, not a key in Redis. A browser that closed, a session that expired and
  a server that restarted all leave the same truth on disk.
* One per person. `start` on a second task stops the first and says which.
* `stop` fills the `to_time`.
* `running()` is the query for the blank one.
* `spent` counts drafts as well as submitted sheets, and says so. ERPNext rolls
  `actual_time` onto the task from *submitted* sheets only, which is not a gap
  to work around — it is what a timesheet is.

Start and Stop are declared verbs in `spaceview/actions.py`, so they are
offered on the open record and in the selection bar alike and cost a line of
manifest rather than a control.

## Assignment — `assignment.py`, in both directions

An assignment is Frappe's `ToDo`. A ToDo cannot be a column — a board groups by
a field, a list sorts by one, and `_assign` is a JSON blob nothing can group by
— so `Task.custom_assigned_to` mirrors it.

* `follow_todo` is hooked on `ToDo` after insert, on update and on trash.
* `follow_field` is hooked on `Task` on update, because somebody edits the
  field on a form: it is a field on a form.

Frappe's two ways of ending an assignment earn their difference here.
`close_all_assignments` writes **Closed**, which is what ERPNext's
`Task.unassign_todo` does the moment a task is Completed; `_remove` writes
**Cancelled**, which is a person taken off it. So a finished task keeps the
name on its card and an unassigned one loses it, from one query.

## The service — `service.py`

A 400px dock window over the same rows. Every verb in it is something a person
could have done by going to OneProject; what it is for is the cost of going
there.

* `now()` — **one read** answers the whole window. A 380px window that reflows
  three times as three requests land is worse than one that waits.
* `capture(subject)` — a text box that is always there rather than a New
  button, because the whole claim is that a thought costs one keystroke. The
  task lands with no project, which is the Inbox.
* `tick(name)` — writes `custom_state`, never `status`.

Pressing a row takes the **page** to that record in OneProject and leaves the
window where it was. `/one/tasks` is the maximised case, for the same reason
OneCloud keeps `/files`: a window has no address and a pasted link should land
somewhere.
