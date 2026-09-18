# Permissions

The engine is where the product's permission model is *implemented*, and its
own answer is short: **it does not decide anything.**

## The two rules

**The manifest is the allowlist, twice over.** A screen can only be reached
through a space the workspace is entitled to, and can only name a doctype that
space's permission manifest already granted. A screen is not a way to read
something the entitlement did not include.

**Permission is Frappe's.** Every read and write goes through the ordinary
DocPerms `sync_permissions` writes from that manifest. The engine reports what
a person may do so the UI can hide what it must.

## The four seats, on this side of the wire

`seats.py`: `SEATS = ("User", "Manager", "Audit", "Admin")` and
`role(prefix, seat)` giving `<prefix>-<Seat>`. Restated here rather than
imported because a tenant site does not carry `oneapp_control`, and the sync
payload carries the prefix and never the child table of seats.
`tests/test_shipped_roles.py` reads the two lists against each other.

`resolve._space_roles` derives a space's four from its prefix, plus the bare
prefix first — for the two spaces the **control plane** runs over itself, which
have one job each and one role rather than four.

## Who sees a space

`resolve.visible`: a space with no `role_name` is open to everybody, and
otherwise **any of its four seats** opens it. Not one named role — a reader
holding only the audit seat is a reader who may look.

## Who sees a screen

`resolve.navigable` narrows a space's screens to what this reader can reach,
and two things stay in the rail on purpose:

* A screen naming **no doctype** — a component screen — has no grant to
  consult. Hiding it on a technicality would make an escape hatch unreachable
  for every seat but one.
* A screen whose doctype **no seat grants** is a manifest that does not add up,
  and hiding it would turn a mistake somebody can see into one nobody can.

## What the finder may find

`finding.py` fans a query out over a hundred-odd tables at once, which is the
kind of thing that gets permission wrong quietly. It decides nothing of its
own and inherits three rules from the list:

* **Its targets are `navigable`**, so a screen a seat cannot open is not a
  screen its records can be found through. It never reads the manifest's grants
  directly and never asks about a space `visible` did not return.
* **Every query is `get_list`** under the reader's own permissions — nothing
  there passes `ignore_permissions`, and `tests/test_finding.py` reads that off
  the syntax tree rather than grepping for it.
* **A screen's own filters apply**, `@me` resolved through `mine.resolve`, and
  **only the fields that screen shows are searched**. The second is
  `filters.py`'s rule and the reason for it is the same here: watching which
  rows come back is a way of reading a column you were never given.

So the worst a bad query can do is return rows the reader could have reached by
opening the screen and typing the same thing into its own box.

## The two refusals, which are not the same sentence

`_refuse_ungranted`, and the distinction matters:

* **"X is not part of this space."** The manifest does not add up.
* **"X is part of this space, and not of your role in it."** The permission
  model working.

Saying the first about a screen sitting in the rail in front of somebody is the
kind of message that costs an afternoon.

## What no manifest may grant, however it asks

`registry.NEVER_GRANTED` on the control plane, subtracted in
`permission_manifest`. Not a list of dangerous doctypes — a list of the ones
that grant power over **the permission system itself** (`User`, `Role`,
`Custom DocPerm`), over **the schema** (`DocType`, `Custom Field`,
`Property Setter`), over **code that runs as us** (`Server Script`,
`Client Script`), and over the platform's own tenancy records.

It applies to the shipped manifest too, not only to what a customer may build:
a space naming one is a bug in the space, and the honest behaviour is for the
grant to do nothing rather than to work.

It used to be an allowlist *by absence* — those doctypes were unreachable
because no manifest named them. Absence is true until somebody writes a
manifest row, and the dev fixture already had it: `zzmock` declared `Role` at
Manage, so the workspace role builder offered it in a dropdown.

## The engine's own doctypes

`OneSpace Saved View` is `if_owner` — a reader's own filters — until they share
it. `OneSpace Hidden View` is a row saying "not for me", which is why
dismissing a shared view does not delete somebody else's work.

`OneSpace Site State` is a Single nobody but the sync writes.

## Field levels

`sync_field_levels` reconciles them rather than seeding once, because **a
permlevel is a security control** and a workspace lowering one back has not
expressed a preference. `_level_roles` composes the Frappe role from a label,
and a label that is not one of the four seats resolves to **nothing** — it used
to fall back to the base role, which is how a typo granted the level to
everybody in the space.
