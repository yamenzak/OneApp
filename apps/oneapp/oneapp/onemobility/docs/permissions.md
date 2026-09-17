# Permissions

OneMobility is a **space**, so it has the four seats: `Mobility-User`,
`Mobility-Manager`, `Mobility-Audit`, `Mobility-Admin`.

## The map

| Seat | What it is |
| --- | --- |
| `Mobility-User` | Sees the network, the live map and the history. Saves its own views and changes nothing else. |
| `Mobility-Manager` | Maintains the network: agencies, lines, stops, vehicles and how each mode is drawn. |
| `Mobility-Admin` | Owns where the data comes from — sources, feeds and the order they win in. **The job that can take the map down.** |
| `Mobility-Audit` | Reads all of it, writes none of it. |

## The default seat is the one that can break nothing

That is the point of the split, and it is not theoretical: a transport
authority is mostly people watching a map, and entitling the space must not
hand every one of them the power to re-point a feed at a different server.

**`Transit Source` appears exactly once in the manifest, and behind the Admin
seat.** A source is where the data comes from and its credentials sit on it.

**`Transit Feed` is Read on the User rung and Write for the Admin.** Which feeds
exist is not a secret from the people reading their output; what a feed points
at is.

## A User writes exactly one thing

Everything a `Mobility-User` gets is a grant with no seat on it — the bottom
rung — and that rung contains **exactly one Write**: `OneSpace Saved View`,
restricted to the person who made it. `tests/test_shipped_roles.py` asserts
that, by counting.

## Nobody may edit what a source said

`Transit Claim` is **Read for every seat, including the Admin.** A claim is the
record of what arrived. The answer to "this is wrong" is to change the
precedence or fix the feed; an editable audit trail is not one.

`conflicts.accept_stop` is the sanctioned way to resolve a disagreement, and it
writes a **verdict** rather than editing the claim.

## The facts have no permissions of their own

This is the consequence of `collections.md`'s central decision, and it is worth
being explicit about. An observation row has no `name`, no owner and no
DocPerm. **Permission lives one level up**, on the `Transit Vehicle` and the
`Transit Line` — and it is enforced by the read path being an *aggregate API*:
every endpoint returns rows already grouped, for entities the caller may see,
and there is no query builder to point at the raw table.

Writing screens against raw rows would break that as surely as it would break
the swap to another store.

## The two windows

`hot_days` and `frozen_days` are the workspace's own, on a Single. **Empty means
the declared default**, because an unset Int and a deliberate nought are the
same value in Frappe, and a workspace must not be able to throw its own history
away by clearing a field.

## Forgetting

`lifecycle.forget_everything` is the deliberate, operator-facing end of it. A
customer who wants their positional history gone gets it gone, frozen copies
included — README §9.
