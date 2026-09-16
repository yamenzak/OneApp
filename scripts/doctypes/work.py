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
# The task, the project and the plan are not here any more
#
# `docs/WORK.md` §12. `One Task`, `One Project` and `One Task Link` were a
# second task table, a second project table and a second dependency table
# beside ERPNext's — which is to say a second costing chain, a second billing
# path and a second accounting dimension. Every site in this product has
# ERPNext, so the premise they were built on was never true here.
#
# What replaced them is not a port: **their** `Task` is the unit of work,
# **their** `Project` is the container and **their** `Task Depends On` is the
# plan, and OneProject adds the five things their Task cannot say — which is
# what the four tables below still are. `onetask/task.py` is the whole of the
# behaviour, and `onetask/sequence.py` went with the edges because ERPNext
# already slips a plan forward and already refuses a loop.
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# A stretch of somebody's time is not here any more
#
# `docs/WORK.md` §12. `One Time Entry` was a second time store, and the moment
# the clock was pointed at ERPNext's own `Timesheet Detail` — which is the row
# a Sales Invoice reads — there was nothing for it to hold and no screen over
# it. So it is gone, along with `onetask/billing.py`, the bridge that posted
# its rows to a ledger we already had.
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# A cycle — a sprint, for the teams that work in them
#
# Not a second container. `docs/WORK.md` §4 is clear that a project is the one
# thing that holds work; a cycle is a *window of time* a team pulls work into,
# and a task carries at most one. Which is why it has no tasks of its own: the
# tasks say which cycle they are in, exactly as they say which project.
# --------------------------------------------------------------------------- #
doctype(
    "One Cycle",
    autoname="field:cycle_name",
    title_field="cycle_name",
    search_fields="starts_on,ends_on",
    track_changes=1,
    **TENANT,
    fields=[
        f("cycle_name", "Data", "Name", reqd=1, unique=1, in_list_view=1,
          description="What the team calls it — Sprint 14, October, Week 3."),
        f("status", "Select", reqd=1, default="Planned", in_list_view=1,
          options="Planned\nRunning\nDone",
          description="Where it is in its own life. Not derived from the "
                      "dates: a team that has not started a sprint on Monday "
                      "has not started it."),
        column("cb_cycle_when"),
        f("starts_on", "Date", "Starts", reqd=1, in_list_view=1),
        f("ends_on", "Date", "Ends", reqd=1, in_list_view=1),
        section("sec_cycle_what"),
        f("goal", "Small Text", "Goal",
          description="The one sentence the team agreed this window is for."),
    ],
)
