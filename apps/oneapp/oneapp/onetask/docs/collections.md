# Collections

**OneTask owns no table of work.** The task is ERPNext's `Task`, the project is
ERPNext's `Project`, the time is ERPNext's `Timesheet`. What this module owns
is five small tables, and every one of them is a *column* on somebody else's
doctype.

## Owned

| Doctype | Child of | What it is |
| --- | --- | --- |
| `One Task State` | — | A board's columns. `state_name`, `category`, `colour`, `position`. `Task.custom_state` links to it. |
| `One Label` | — | A tag with a colour. `label_name`, `colour`, `description`. |
| `One Task Label` | `Task.custom_labels` | Which labels are on a task. One `label` field. |
| `One Task Step` | `Task.custom_steps` | A checklist inside one task. `done`, `step`. |
| `One Cycle` | — | A sprint: a window of time a team pulls work into. `cycle_name`, `status`, `starts_on`, `ends_on`, `goal`. `Task.custom_cycle` links to it. |

`category` on a state is the field that matters: `states.STATUS_OF` maps the
four categories onto ERPNext's own seven status words, so a workspace can have
a *Design review* column and ERPNext's validation still reads a word it knows.

A cycle holds no tasks. One container, and it is the project — so a cycle's
work is the tasks that name it, which is a declared tab like any other.

## Borrowed

| Doctype | From | What it is here |
| --- | --- | --- |
| `Task` | ERPNext | The unit of work. Subclassed as `onetask.task.ProjectTask` through `override_doctype_class`. |
| `Project` | ERPNext | The container. `custom_key` is the naming prefix. |
| `Task Depends On` | ERPNext | The plan. One row per edge, one direction. |
| `Timesheet`, `Timesheet Detail` | ERPNext | The clock. A running entry is a detail row with no `to_time`. |
| `ToDo` | Frappe core | The assignment. Mirrored into `Task.custom_assigned_to`. |
| `Auto Repeat` | Frappe core | Repeating tasks. Nothing of ours. |
| `Assignment Rule` | Frappe core | The automation behind "when a task reaches In review, hand it to the reviewers". |

## The custom fields, which live elsewhere

Declared in `oneapp_control/spaces/oneproject.py`, because a custom field
belongs to the space that renders it:

    Task.custom_state         Link to One Task State
    Task.custom_labels        Table of One Task Label
    Task.custom_steps         Table of One Task Step
    Task.custom_cycle         Link to One Cycle
    Task.custom_rank          Data — a fractional rank, base-36
    Task.custom_assigned_to   Link to User — the mirror of _assign
    Project.custom_key        Data — the naming prefix, REEM in REEM-14

## The one that is not a table

**A task with no project is the inbox.** Not a second store and not a flag:
ERPNext's Task has an optional project, so a task nobody has placed *is*
unplaced, and the Inbox is one filter. That is what makes the service's capture
box cost nothing.
