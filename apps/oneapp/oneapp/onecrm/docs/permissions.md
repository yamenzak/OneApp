# Permissions

OneCRM is a **space**, so it has the four seats every space has — `CRM-User`,
`CRM-Manager`, `CRM-Audit`, `CRM-Admin` — declared in
`oneapp_control/spaces/roles.py` and granted in
`oneapp_control/spaces/onecrm.py`.

## The rule this space is most emphatic about

**A rep may read a stage and may not write one.**

    One Deal Stage    Read for CRM-User, Write for CRM-Manager

A rep who can invent a stage can move a deal into one, and the forecast quietly
stops meaning anything to everybody else. `tests/test_four_seats.py` runs the
real manifest through the real ladder and asserts exactly this.

The same split covers everything a pipeline is *measured* by: Sales Stage,
Opportunity Type, Opportunity Lost Reason, the UTM tables, Campaign, Territory,
Customer Group, Market Segment — and `One Response Target` with its three child
tables, for the same reason one step along: **a rep who can lengthen their own
target is a rep who is never late.**

## What a User does have

Manage on the four records selling is actually made of — `Lead`,
`Opportunity`, `Prospect`, `Quotation` — and **not `if_owner`**. A desk where a
rep cannot see the deal a colleague is covering for them is a desk that loses a
deal every time somebody takes a week off.

`One Call` is Manage too, and also not `if_owner`: a call log whose rows a rep
cannot correct is a call log they stop writing, and a desk where you cannot see
that a colleague already rang this person rings them twice.

`Customer` is **Write, not Manage** — converting a deal creates one, and
deleting a customer is an accounting decision made in an accounting space.

## What nobody writes

**`One Stage Change`** is Read for every seat. A log somebody can edit is not a
log, and the controller is the only writer.

## The Manager, and the Admin

`CRM-Manager` runs the desk: the stages, the sources, the territories, the lost
reasons, the response targets and the contracts underneath a won deal.

`CRM-Admin` inherits all of it through the ladder and adds nothing of its own
in this space — which is honest rather than a gap: OneCRM has no confidential
lane the way OneHR has pay.

## The Audit seat

Read on all forty-two doctypes the space reaches, derived by
`registry.laddered` rather than declared, so it cannot drift from what the
other three seats can see and cannot be handed a Write by a manifest row.

## The child tables are granted, and that is not an oversight

`One Working Day`, `One Response Level` and `One Response Rule` each appear in
the manifest. **A grid whose doctype the reader cannot see is a grid that draws
nothing**, so the target's record would show an empty week and no promise.
