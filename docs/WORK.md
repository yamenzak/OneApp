# Work: projects, tasks, and the calendar over them

Three things were queued as three arcs — OneCalendar's sources, OneProject, and
OneTask — and they are one document because they are one question asked three
ways: **what is there to do, who is doing it, and when.** Designing them apart
is how a product ends up with a task in a project, a to-do in a list, an
assignment on a record and an event in a diary, none of which know about each
other and all of which a person has to check separately every morning.

This is the study and the plan. Nothing here is built yet.

---

## 1. What is already true, measured

Worth writing down first, because three of the four hard parts are done and the
plan is smaller than it looks.

**The record engine.** A space declares screens over doctypes; every screen can
open as a list, a board, a Gantt, a calendar, a tree, a matrix or a dashboard,
with saved views, quick filters, bulk actions, printing, record tabs and the
assistant over all of it. `docs/ERP-SPACES.md` is the argument. A board drags
cards between columns — the drop writes the column's field — and remembers the
order *within* a column in the arrangement rather than on the record
(`BoardBody.vue`). So a Trello board, a Linear list and a Monday group are all
already drawable; what is missing is not the view, it is what they draw.

**The reader, resolved.** `onespace/mine.py` gives a manifest `@me` and
`@me:employee` — the session's user, or whoever that user is in some app's own
terms, through a registry an app adds itself to. It resolves once in
`resolve.py`, before the list, the board, the calendar, the dashboard and the
count read the filters, so every view of a screen narrows the same way. An
unresolvable subject narrows to *nothing*, deliberately.

**The diary merges.** `onecalendar/diary.py` is a merge first and a store
second: every screen that declares `calendar: {start_field, end_field, diary:
true}` contributes its rows, read through that screen's own resolution and
permissions; the reader's own `Event` rows are the only thing it stores. Six
screens opt in today — a CRM next step, a call, leave, an interview, a training
event, a project milestone. Entries are deduped by `(doctype, record)`, so the
same meeting reached by two screens is one entry.

**Assignment is Frappe's, and is understood.** `spaceview/assign.py`: the ToDo
is the truth and `_assign` is a cache of it; assigning goes through
`frappe.desk.form.assign_to` so the record gets a face *and* the person gets a
row in their own list. Read permission is enough to assign, deliberately.

**And there is already a hole where a task goes.** `ai/kinds.py` has a `Task`
kind whose docstring says it: *"this product has no tasks screen yet, so there
is no path to route through"*, and it inserts a bare `ToDo` instead, with a
note that the handler should go through the screen when one exists.

**What OneProject is today.** A space over ERPNext's Projects module — Project,
Task, Timesheet, Task Type, Project Type — with six screens and no doctype of
its own. It requires `erpnext` and says so.

---

## 2. The four nouns, and why three of them are not tasks

Most of the confusion in this area is one word doing four jobs.

**A task** is a unit of work with its own life: a title, a state it moves
through, somebody doing it, an estimate, a place in an order, a history. It
exists whether or not anybody has been asked to do it yet.

**An assignment** is a pointer: *you, on this thing*. It has no life of its own
— it is a claim on somebody's attention about a record that already exists.
Frappe's ToDo. A quotation assigned to Hala is not a task called "quotation";
it is the quotation, with Hala's name on it.

**An event** is a commitment of *time*: it occupies an hour whether or not any
work comes out of it. Frappe's `Event`.

**A record with a date** is everything else: a leave application from the 3rd
to the 7th, an interview at 10, an invoice due Friday. It is not a task and
never becomes one; it is a row on some screen that also happens to be on a
calendar.

**The rule this whole document rests on:** these are four kinds of thing and
they stay four. What they share is not a table, it is a *question* — "what is
on my plate" — and the answer to that question is a **view over all four**, not
a fifth table that copies them.

This is the same rule the repository already keeps elsewhere. There is no
second file store: a document, a workbook and an attachment are all `File`
rows. There is no second editor. And there will be **no second task store**, and
no task store that is secretly the assignment store.

---

## 3. Decision 1 — one task doctype, and it is ours

The question the arc turns on: does a task in OneProject stay ERPNext's `Task`,
and does OneTask reuse it?

**It cannot.** `docs/APPS-AND-SPACES.md` §4: a site installs the union of what
its granted spaces need, so *a workspace that bought nothing using ERPNext does
not carry ERPNext* — no fifteen hundred doctypes, no tables, no patches on
every migrate. OneTask is "the general task management solution for any
business or user within a business", which means it has to work on a site whose
apps are `frappe` and `oneapp`. Requiring ERPNext for a to-do list would undo
the one thing that document bought.

So: **`One Task` is ours, in `oneapp`, and it is the only task doctype in the
product.** OneProject's tasks are One Tasks with a project on them. OneTask's
are One Tasks without one. There is one board, one Gantt, one "assigned to me",
one AI action, one print format, one shape of notification.

**What that costs, said plainly.** ERPNext's Task carries a costing chain:
Timesheet logs against a Task, the Task rolls into a Project, and the Project
reports budget, billed and gross margin. Replacing Task breaks that chain. The
answer is not to keep both tables — it is to keep the *chain* where it is
earned: a workspace that bills through ERPNext gets a **posting bridge**, where
approved time on a One Task writes an ERPNext Timesheet against the ERPNext
Project the One Project names. One direction, one seam, only where `erpnext` is
installed, and nothing in OneTask knows it exists. That is one bridge instead of
two schemas.

**And ERPNext's Task is not a loss to mourn.** Forty fields, `lft`/`rgt` tree
bookkeeping, a `Select` status with six fixed words, `is_template`,
`template_task`, `depends_on_tasks` as a `Code` field, and no notion of order
within a column, of a label, of a watcher, or of a cycle. It is a work
breakdown structure for a projects module, and the products the plan is
measured against — Linear, Monday, Trello, Asana, Notion — are not that.

**Migration.** OneProject ships `Restricted` and is granted per workspace, so
this is a small number of tenants or none. Whoever has it gets a one-time
import: Project → One Project, Task → One Task, and the ERPNext rows stay where
they are for the accounting to keep reading. Written once, run once, tested
against a copy of a real tenant, never run again.

---

## 4. Decision 2 — a board *is* a project

Trello has boards. Monday has boards. Linear has teams, projects and cycles.
Asana has projects and portfolios. Notion has databases. Every one of them has
exactly one container that holds work, plus a way to group the containers.

So: **one container, called a project.** A "board" is a project drawn as a
board; the word is a view type and not a noun. A personal list is a project of
your own, or no project at all — the tasks with nothing above them, which is the
inbox.

This is the single highest-leverage cut in the plan. Every competitor that has
both a "board" and a "project" spends its documentation explaining the
difference, and every customer asks.

**Above projects**: a space is the portfolio. OneProject's Projects screen with
a board by status *is* the portfolio view, and it exists today.

---

## 5. Decision 3 — how far the board defines its own fields

This is the real Monday question and the one place where the honest answer is a
recommendation rather than a certainty.

Monday's model is that a board's **columns are data**: a person adds a "Risk"
dropdown to one board and not another. Notion is the same. Linear ships with a
fixed schema and no custom fields at all, and is loved for it. Trello has
one-off "custom fields" bolted on and mostly ignored.

Three ways to do it here:

**A. Schema per board.** A `Custom Field` written when somebody adds a column.
No. A user action that writes DDL is a migration per click, a doctype that
drifts per tenant, and a permission surface nobody can reason about.

**B. Values as data (EAV).** A `One Field` definition per project and a value
row per task per field. Fully flexible; filtering, sorting and grouping all
become joins the record engine does not currently speak, and every screen in the
product would have to learn them.

**C. A fixed spine, with the two things people actually add.** Ship an
opinionated schema, and make *states* and *labels* per-project data rather than
fixed lists. Almost every real "custom column" in the wild is one of those two
in disguise.

**Recommended: C now, B later and only if asked for.** Ship the spine plus
per-project states and labels; measure what people ask for next. The escape
hatch already exists and is honest: a workspace that genuinely needs a typed
column can have one as a real custom field through the space manifest, which is
how every other schema extension in this product is done — see
`docs/APPS-AND-SPACES.md` §B.

The part of B worth building early is not the storage, it is the *grouping*: a
board that groups by any field, which the engine nearly has already.

---

## 6. Decision 4 — a calendar is a question, not a container

The three questions asked at the top of this document:

> Does each user have their own calendar, and is there one for everybody? Does
> each project have one? Is there an all-in-one for the person and the company?

**Yes to all of them, and none of them is a new object.** A calendar in this
product is a *lens over one merge*, and the merge already exists. What is
missing is three small things.

**(a) A source says whose an entry is.** Today `calendar: {start_field,
end_field, diary: true}`. It gains one optional key:

    "calendar": {"start_field": "from_date", "end_field": "to_date",
                 "diary": True, "about": "employee"}

`about` names the field that says which *person* the row concerns, resolved
through the same subject registry `@me:employee` uses. With that, the diary can
answer "mine" without a second screen and without a second query path.

**(b) The diary grows a lens, which is two buttons and no new data.**

* **Mine** — every merged row whose `about` resolves to me, plus my own Events,
  plus the tasks assigned to me, plus my open assignments that carry a date.
  This is the personal calendar, and it is the default: a calendar opened on a
  Tuesday morning is a question about your Tuesday.
* **Everyone** — the whole merge, permission-scoped exactly as it is today.
  Who is off, which interviews are booked, which milestones land this month.
  This is the company calendar, and for a manager it is what the diary already
  shows; the difference is that it will say so.

A source with no `about` is workspace-wide by nature — a milestone, a public
holiday, an office closure — and belongs to **Everyone** only.

**(c) A record's calendar is the calendar of what is related to it.** The
record shell already declares `related` — screen plus the field that points
back (`{"screen": "tasks", "field": "project"}` on a project, today). A
project's calendar is that declaration read as a calendar: every related
screen's dated rows, narrowed to this record. **No new manifest key at all**,
and it generalises for free: an employee record gets a calendar of their leave
and their interviews, a client gets one of their deliveries, because both
already declare `related`.

**What each app "creating its own calendars" means, then:** it declares
`calendar` on a screen. That is all, and it is already true. The rest is lenses.

**One thing it does not answer, and should later:** several *named* personal
calendars — the Google "Work / Family / Gym" split. That is a `One Calendar`
row with a colour and an owner, and an `Event` pointing at it. It is worth
having and it is not worth blocking on: the rail already toggles sources, so the
machinery lands into a place that is ready for it.

---

## 7. OneTask and OneProject are one engine and two doors

    OneTask      the door for work that is nobody's project
                 your list, a team's queue, a workspace's intake
    OneProject   the door for work that has a shape
                 a client project, a build, a launch — with a plan and a budget

Same `One Task` table underneath, same board, same Gantt, same "assigned to
me". A task moved into a project does not change table, and that is the point:
"put this on the Al Reem project" is a link, not a migration.

**What OneTask ships that OneProject does not care about:** an inbox (tasks
with no project), a personal list, quick capture from anywhere, and recurring
tasks.

**What OneProject ships that OneTask does not:** the project record itself,
milestones, dependencies drawn as a Gantt, a budget, time posted to billing, and
a portfolio over many projects.

---

## 8. What gets built — the doctypes

All in `oneapp`, module OneTask, so a site with no ERPNext carries them.

    One Task           the unit of work
    One Project        the container: a board, a plan, a budget
    One Task State     per project: name, category, colour, order
    One Label          a tag with a colour, per space
    One Task Link      typed dependency: blocks / blocked by / relates to
    One Time Entry     a stretch of somebody's time against a task
    One Cycle          a sprint, where a team works in them (stage 6)

`One Task`'s spine, and nothing beyond it in the first pass:

    title, description, state, priority, project, parent, order,
    starts_on, due_on, estimate, spent, labels, watchers, steps,
    completed_on, completed_by, recurrence

Three notes on that list.

**`order` is a rank string, not an integer.** Dragging one card must not
rewrite the whole column. A fractional rank (`a0`, `a0V`, `a1`) is what every
product that does this well uses, and it is why order lives on the *record*
here rather than in the arrangement the way the generic board does it — a
project's order is the team's, not each reader's.

**`state` is a Link, not a Select.** That is the whole of "custom columns per
board": a project's states are its own rows, with their own colours and their
own order, and a `category` (backlog, started, done, cancelled) so that
"is it finished" has an answer the engine can ask without reading the word.

**`steps` is a child table**, not sub-tasks. A checklist inside one task —
three lines and a tick — is not the same as a task that needs its own owner and
date, and making people create sub-tasks for it is how backlogs fill with
noise. Sub-tasks are `parent`.

---

## 9. The questions, answered directly

**Are a project's tasks the same as ERPNext's Task doctype?** Today, yes,
literally. After this plan, no: they are `One Task`, and ERPNext's Task stays
only where a workspace bills through ERPNext, reached by the posting bridge in
§3.

**Are they the same as document assignments?** No, and the distinction is load
bearing (§2). An assignment points at a record that already exists; a task *is*
the record. **They meet in exactly one place:** assigning a One Task to somebody
goes through `assign_to.add` like every other record, so it lands in their work
list beside everything else they have been asked to look at. One list, two kinds
of row, no copying.

**Does OneTask intersect Frappe's ToDo?** Yes, as above: ToDo stays the
assignment store and never becomes the task store. The one change is that
`ai/kinds.py`'s `Task` kind stops inserting a bare ToDo and starts making a real
One Task — the comment in that file has been waiting for this.

**Does it intersect ERPNext's Projects module?** Only at billing, and only
through the bridge.

**Does each project get its own calendars?** Yes, and free: §6(c).

**Is there an all-in-one calendar for the person and for the company?** Yes,
and it is the same merge with two lenses: §6(b).

---

## 10. The stages

Each is a commit, each leaves the product working, each has a checkpoint that
is a screenshot rather than a test count.

**1. The calendar answers whose it is.** `about` on a calendar declaration; the
Mine / Everyone lens on the diary; the six screens that opt in today declare it.
*Checkpoint: a manager's diary opens on their own week and one press shows the
company's.*

**2. A record's calendar.** The `related` declaration read as a calendar, and a
Calendar tab on the project, the employee and the client records that already
declare one. *Checkpoint: a project's own month, with its milestones and its
team's leave on it, opened from the project.*

**3. The task, and OneTask.** `One Task`, `One Task State`, `One Label`, the
rank, the steps; the OneTask space with an inbox, a list, a board and a
calendar; the assistant's `Task` kind rewired. *Checkpoint: capture a task from
the assistant, see it on your board, drag it to Done.*

**4. The project.** `One Project`, the portfolio board, the record shell with
its tasks, its files (OneCloud already gives a record a folder), its documents
and its correspondence. *Checkpoint: a project record where the work, the
files, the documents and the mail about it are four tabs of one thing.*

**5. The plan.** `One Task Link` and dependencies drawn on the Gantt,
milestones, a critical path that is honest about what it does not know.
*Checkpoint: move one task and watch what it blocks move with it.*

**6. Time, cycles and recurrence.** `One Time Entry` with a start/stop, the
billing bridge where ERPNext is installed, `One Cycle` for teams that sprint,
and repeating tasks. *Checkpoint: a week of somebody's time, and an invoice
that agrees with it.*

**7. Automations.** Frappe already ships Notification, Assignment Rule and
Workflow; the work is a face on them that says "when a task moves to Review,
assign the reviewer", not a new engine. Last, because it is the one people
demonstrate and the one they use least.

---

## 11. What this deliberately does not do

* **No second task store, and no task that is secretly an assignment.**
* **No schema written by a user action.** Per-board columns are states and
  labels, which are rows; a genuinely new typed field is a manifest change like
  every other schema change in this product.
* **No second calendar merge.** Everything dated reaches the diary by declaring
  a calendar on a screen, and nothing gets a private path to it.
* **No portfolio object.** A space is the portfolio and a project is the
  container; a third level is what every competitor adds in year three and
  nobody can explain.
* **No client seat here.** Somebody outside the workspace looking at a project
  is a share link and a read-only surface, which is `docs/DRIVE.md`'s problem
  and not this one.
