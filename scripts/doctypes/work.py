"""The work: a task, the states it moves through, and what it is tagged with.

`docs/WORK.md` is the argument and §3 is the one decision everything here
follows from: **the task doctype has to be ours.** A site installs the union of
what its granted spaces need — `docs/APPS-AND-SPACES.md` §4 — so a workspace
that bought nothing using ERPNext does not carry ERPNext, and OneTask is for
any business at all. Building it on ERPNext's `Task` would have undone the one
thing that document bought.

So this is the only task table in the product. A task in a project and a task
in somebody's own list are one row with and without a project on it, which is
what makes "put this on the Al Reem project" a link rather than a migration.

**What it is not** is the assignment system. §2: an assignment is a pointer at
a record that already exists — Frappe's `ToDo`, unchanged — and a task is the
record. The two meet in exactly one place, and it is the framework's own:
assigning a task goes through `assign_to.add` like every other record, so it
lands in somebody's work list beside everything else they have been asked to
look at. Nothing here copies a ToDo and nothing here is one.
"""

from .spec import MANAGER_PERMS, column, doctype, f, section

MODULE = "OneTask"
TENANT = dict(app="tenant", module=MODULE, perms=MANAGER_PERMS)


# --------------------------------------------------------------------------- #
# A state — which is how a board gets its own columns without a schema change
#
# `docs/WORK.md` §5: Monday's model is that a board's columns are data, and
# writing a `Custom Field` when somebody adds one is a migration per click.
# Almost every real custom column in the wild is a *state* or a *label* in
# disguise, so those two are rows and everything else is the manifest's job.
#
# `category` is what lets the engine ask "is it finished" without reading the
# word: a project may call its last column Shipped, Delivered or Signed off,
# and a progress bar that had to know those three would be a progress bar that
# breaks on the fourth.
# --------------------------------------------------------------------------- #
doctype(
    "One Task State",
    autoname="field:state_name",
    title_field="state_name",
    search_fields="category",
    **TENANT,
    fields=[
        f("state_name", "Data", "Name", reqd=1, unique=1, in_list_view=1,
          description="What this column is called on the board. The id too, so "
                      "a manifest can put them in an order — see the note on "
                      "`category` about what that costs."),
        f("category", "Select", reqd=1, default="Started", in_list_view=1,
          options="Backlog\nStarted\nDone\nCancelled",
          description="What it means, for the code that has to ask. A workspace "
                      "may call its last column Shipped or Signed off; this is "
                      "how a progress bar knows which of them is finished."),
        column("cb_state_look"),
        f("colour", "Select", "Colour", default="gray",
          options="gray\nblue\ngreen\namber\nred\nviolet\ncyan\norange\npink",
          description="The dot beside it, and the tint of its column."),
        f("position", "Int", "Position", default="0", in_list_view=1,
          description="Left to right on the board. Ties break on the name."),
    ],
)


# --------------------------------------------------------------------------- #
# A label — the other half of "a board defines its own fields"
# --------------------------------------------------------------------------- #
doctype(
    "One Label",
    autoname="field:label_name",
    title_field="label_name",
    search_fields="description",
    **TENANT,
    fields=[
        f("label_name", "Data", "Name", reqd=1, unique=1, in_list_view=1),
        f("colour", "Select", "Colour", default="gray",
          options="gray\nblue\ngreen\namber\nred\nviolet\ncyan\norange\npink",
          in_list_view=1),
        f("description", "Small Text",
          description="What it means, for the people who did not invent it."),
    ],
)


doctype(
    "One Task Label",
    istable=1,
    **TENANT,
    fields=[
        f("label", "Link", options="One Label", reqd=1, in_list_view=1),
    ],
)


# --------------------------------------------------------------------------- #
# A step — a checklist inside one task
#
# Not sub-tasks, and the difference is worth writing down: three lines and a
# tick are not three things that each need an owner, a date and a place on a
# board. Making people create sub-tasks for them is how a backlog fills with
# noise nobody can filter out afterwards. Sub-tasks are `parent`.
# --------------------------------------------------------------------------- #
doctype(
    "One Task Step",
    istable=1,
    **TENANT,
    fields=[
        f("done", "Check", "Done", default="0", in_list_view=1),
        f("step", "Data", "Step", reqd=1, in_list_view=1),
    ],
)


# --------------------------------------------------------------------------- #
# The task
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# A dependency — one edge of the plan
#
# `docs/WORK.md` §8. A child table of the task that is *waiting*, and one
# direction stored: "I am blocked by that one". The other direction is the same
# edge read backwards, so `Blocks` is a query rather than a second row — which
# is the only way the two can never disagree.
#
# `Relates to` is stored here too and means nothing to the schedule. It is a
# pointer a person leaves for another person, and a plan that treated it as a
# sequence would push dates around for a note.
# --------------------------------------------------------------------------- #
doctype(
    "One Task Link",
    istable=1,
    **TENANT,
    fields=[
        f("kind", "Select", "Kind", reqd=1, default="Blocked by", in_list_view=1,
          options="Blocked by\nRelates to",
          description="What this edge says. Only `Blocked by` is a sequence: "
                      "`Relates to` is a pointer between two tasks and moves "
                      "nothing."),
        f("task", "Link", "Task", options="One Task", reqd=1, in_list_view=1,
          description="The other end. Always the task this one is *about* — "
                      "the one it waits for, or the one it relates to."),
    ],
)


doctype(
    "One Task",
    autoname="naming_series:",
    title_field="subject",
    search_fields="project,state,assigned_to",
    track_changes=1,
    **TENANT,
    fields=[
        f("naming_series", "Data", "Series", hidden=1, default="TASK-.#####",
          description="A project's own key replaces this where it has one — "
                      "`onetask/task.py`. Linear's ENG-14 is the thing people "
                      "actually say to each other."),
        f("subject", "Data", "Title", reqd=1, in_list_view=1,
          description="What there is to do, in the words somebody would say."),
        f("state", "Link", options="One Task State", in_list_view=1,
          description="Which column it is in. A Link and not a Select, which "
                      "is the whole of "
                      "\"each board has its own columns\"."),
        f("status", "Select", "Status", reqd=1, default="Backlog", in_list_view=1,
          options="Backlog\nStarted\nDone\nCancelled", read_only=1,
          description="The state's own category, copied here on save. Derived "
                      "and not a second truth: the engine's badge, its filters "
                      "and \"is it finished\" all want a Select, and a Link "
                      "cannot be one. `onetask/task.py` keeps it."),
        f("priority", "Select", default="Medium", in_list_view=1,
          options="Low\nMedium\nHigh\nUrgent"),
        column("cb_task_who"),
        f("project", "Link", options="One Project", in_list_view=1,
          description="The board it is on, where it is on one. Empty is the "
                      "inbox: a task nobody has placed yet."),
        f("parent_task", "Link", "Parent", options="One Task",
          description="A task under another. Not a checklist — see "
                      "`One Task Step`."),
        f("assigned_to", "Link", "Owner", options="User",
          description="Who is carrying it. Written from the assignment and "
                      "not instead of it: `assign_to.add` keeps the ToDo that "
                      "puts it in their own list, and this is what a board "
                      "groups and filters by without reading JSON."),
        section("sec_task_when"),
        f("starts_on", "Date", "Starts"),
        f("due_on", "Date", "Due", in_list_view=1),
        f("estimate_minutes", "Int", "Estimate (minutes)", default="0",
          description="How long somebody thinks it will take. Minutes because "
                      "every other unit is a fight about half days."),
        column("cb_task_done"),
        f("completed_on", "Datetime", "Completed", read_only=1),
        f("completed_by", "Link", "Completed by", options="User", read_only=1),
        f("spent_minutes", "Int", "Spent (minutes)", default="0", read_only=1,
          description="Rolled up from the time logged against it."),
        section("sec_task_what"),
        f("description", "Text Editor", "Description"),
        f("steps", "Table", "Checklist", options="One Task Step"),
        f("labels", "Table MultiSelect", "Labels", options="One Task Label"),
        section("sec_task_plan"),
        f("links", "Table", "Depends on", options="One Task Link",
          description="What this task waits for, and what it merely points "
                      "at. One direction is stored and the other is the same "
                      "edge read backwards — `onetask/sequence.py`."),
        section("sec_task_order"),
        f("rank", "Data", "Rank", hidden=1,
          description="Where it sits in its column, as a string that sorts. "
                      "Fractional — `a0`, `a0V`, `a1` — so dragging one card "
                      "rewrites one row rather than the whole column. On the "
                      "record and not in the reader's own arrangement: a "
                      "project's order is the team's."),
        f("is_milestone", "Check", "Milestone", default="0",
          description="A date the project is measured by rather than a piece "
                      "of work. Drawn as a diamond on the plan."),
    ],
)


# --------------------------------------------------------------------------- #
# The project — the container, which is also the board
#
# `docs/WORK.md` §4: one container. Every competitor with both a board and a
# project spends its documentation explaining the difference, and every
# customer asks. A board is a project drawn as a board.
# --------------------------------------------------------------------------- #
doctype(
    "One Project",
    autoname="field:project_name",
    title_field="project_name",
    search_fields="status,lead",
    track_changes=1,
    states=[
        {"title": "Planned", "color": "Gray"},
        {"title": "Active", "color": "Green"},
        {"title": "On hold", "color": "Amber"},
        {"title": "Done", "color": "Blue"},
        {"title": "Cancelled", "color": "Red"},
    ],
    **TENANT,
    fields=[
        f("project_name", "Data", "Name", reqd=1, unique=1, in_list_view=1),
        f("key", "Data", "Key", length=8,
          description="Two to five letters, upper case. A task on this project "
                      "is named after it — ENG-14 — because that is what "
                      "people say to each other and TASK-00042 is not."),
        f("status", "Select", reqd=1, default="Planned", in_list_view=1,
          options="Planned\nActive\nOn hold\nDone\nCancelled"),
        column("cb_project_who"),
        f("lead", "Link", "Lead", options="User", in_list_view=1,
          description="Who answers for it."),
        f("colour", "Select", "Colour", default="blue",
          options="gray\nblue\ngreen\namber\nred\nviolet\ncyan\norange\npink"),
        f("archived", "Check", "Archived", default="0",
          description="Kept and out of the way. Not deleted: a finished "
                      "project is the record of what was done."),
        section("sec_project_when"),
        f("starts_on", "Date", "Starts"),
        f("due_on", "Date", "Due", in_list_view=1),
        column("cb_project_count"),
        f("open_tasks", "Int", "Open", default="0", read_only=1,
          description="Rolled up, so a portfolio of forty projects is one "
                      "query rather than forty."),
        f("done_tasks", "Int", "Done", default="0", read_only=1),
        section("sec_project_what"),
        f("description", "Text Editor", "Description"),
    ],
)
