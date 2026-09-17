# Permissions

OnePeople is a **space**, so it has the four seats: `HR-User`, `HR-Manager`,
`HR-Audit`, `HR-Admin`.

## The map

| Seat | What it is |
| --- | --- |
| `HR-User` | Self-service. Ask for leave, correct your own attendance, claim expenses, keep your goals. Sees the directory and nobody else's records. |
| `HR-Manager` | Administers the people — attendance, leave, hiring, onboarding, appraisals and the tables behind them. Deliberately not pay. |
| `HR-Admin` | Everything the Manager has, plus **pay**: structures, payroll cycles, payslips and advances. The one seat that can see what anybody earns. |
| `HR-Audit` | Reads every record in the space and writes nothing. |

## Pay belongs to the Admin seat

Every HR department in the world keeps salary away from the people who
administer leave, and ERPNext's answer is a role list you assemble by hand.
Here the Manager runs the people and the Admin runs the pay, so a workspace
that entitles OnePeople gets the separation **without having thought about it**,
and merging the two is a decision somebody makes rather than one they inherit.

## `if_owner` is the User seat

Every self-service door — leave applications, attendance requests, shift
requests, expense claims, travel requests, grievances, goals — is granted
`if_owner`. You file your own and cannot read the person next to you's. One
manifest, two lists, decided by the grant rather than by a filter somebody has
to remember to apply.

## Where the split stops, and where it now does not

A grant is per doctype, so the seats divide the **screens** and not the fields.
ERPNext keeps `ctc`, the bank account and the IBAN on `Employee` at permission
level zero — so the same grant that makes the directory openable by a colleague
handed everybody everybody else's pay.

`FIELD_LEVELS` is the answer and it is in the manifest. **Two levels, not one**,
and that took a second pass: the first version put the whole personnel file at
level one and granted it to both administering seats, which closed the hole
against the User and left it wide open between the other two.

* **level 1** — date of birth, passport, health, emergency contact, the
  resignation and relieving dates. Manager **and** Admin, because an exit is a
  date somebody types and an emergency contact is a number somebody rings.
* **level 2** — `ctc`, salary mode and currency, bank account, IBAN. **Admin
  alone.**

Frappe's levels are a ladder rather than a set, so each row names exactly the
seats that should have it.

**What it costs is one real thing**, worth naming rather than discovering: a
Manager can no longer set somebody's salary on the person's own record. That is
the point. Pay is set from a Salary Structure Assignment, which is the Admin's
screen, and `ctc` on Employee was only ever a second place to say it.

`FIELD_LEVELS` is the one fixture **reconciled** rather than seeded once: a
permlevel is a security control, so a workspace lowering `ctc` back has not
expressed a preference — it has opened the payroll to everybody who can open
the directory.

## The reader's own — `own.py`

`may_read` is what every endpoint in `me`, `presence` and `history` goes
through. A person reads their own record, and their manager's, peers' and
reports' **presence** — not their records. That is what let the home page exist
without widening a single grant.

## The rail is the seat, not the space

Thirty screens is a readable rail for somebody who runs HR and a wall for
somebody who files leave twice a year. `api.visible_spaces` narrows it: a User
gets twelve entries, a Manager twenty-five.

Two things stay in the rail on purpose. A screen naming no doctype has no grant
to consult. And a screen whose doctype **no** seat grants is a manifest that
does not add up, and hiding it would turn a mistake somebody can see into one
nobody can.

## What is a permission and what is not

`tools.py`'s §12 in the README draws the line: opening HR Settings is a
permission, and *running* the Leave Control Panel is a bulk write that has to
check the doctype it is writing, not the tool it was pressed from.
