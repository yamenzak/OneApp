# Permissions

**OneTask has no roles of its own.** It is a service — `docs/CLEANUP.md` §1 —
so it is on for everybody with a seat, and every permission question it raises
is answered by **OneProject's** four seats over ERPNext's `Task`.

That is not a technicality. The service window shows the same rows the space's
board shows, through the same grants: a person who cannot open a project's
tasks in OneProject sees none of them here, and `service.now()` gets an empty
window rather than a refusal, because a dock window that throws is worse than
one that is honestly empty.

## What OneProject grants

`oneapp_control/spaces/oneproject.py`, and the ladder in `spaces/roles.py`:

| Seat | On `Task` | On the small tables |
| --- | --- | --- |
| `Project-User` | Manage — does the work | Read |
| `Project-Manager` | inherits | Write — the states, the labels, the cycles a board is measured by |
| `Project-Admin` | inherits | inherits |
| `Project-Audit` | Read | Read |

The split is the rule the space is most emphatic about: **a person who can
invent a column can move a task into one**, and then the board stops meaning
anything to everybody else. So `One Task State` is Read for a User and Write
for a Manager.

## What the module itself checks

**Nothing by role, and three things by shape.**

`timing.start` enforces **one running entry per person** — starting a second
stops the first and says which. Not a permission, but it is the check that
keeps a timesheet honest.

`service.tick` writes `custom_state` and **never** `status`. The service cannot
reach ERPNext's own vocabulary even for a person who could; one direction, one
path.

`service.capture` makes a task with no project, which lands it in the Inbox.
A person who may make a task may make an unplaced one.

## The one deliberately not offered

**Unassigning, in the automation.** `routing.py` offers handing work to
somebody and does not offer taking it away. Work vanishing from somebody's list
weeks later, with nothing on the record to say why, is a footgun with a delay
on it.
