# Integrations

## ERPNext — this module is mostly decisions about it

**`Opportunity` and `Lead` are subclassed** through `override_doctype_class`,
the supported hook. `deal.Deal` and `lead.Lead` add the stage log and the
weighting and call `super().validate()` for everything else.

**`Opportunity.sales_stage` keeps its Link**, and `One Deal Stage` replaces the
list behind it. `category` on a stage maps onto ERPNext's own vocabulary so
their validation reads a word it knows while a workspace reads its own.

**A won deal reaches accounting without a bridge.** Quotation → Sales Order →
Invoice is all theirs. That is the return on not owning the schema, and it is
the same return OneProject and OnePeople take.

**The masters are theirs**: Sales Stage, Opportunity Type, Opportunity Lost
Reason, Territory, Customer Group, Market Segment, Campaign, the three UTM
tables, Contract and Contract Template. Every one is Read for a User and Write
for a Manager, which is the ladder in `permissions.md`.

## Frappe

**`Communication`** is what stops the answering clock —
`answering.on_communication`, hooked on the document event. Sent means
answered; Received means reopened.

**`override_doctype_class`** twice. **`doc_events`** for the answering hooks
and a scheduler entry for `late_now`.

## OneMail

The seam that makes answering real. A reply arrives as a `Communication`, and
`on_communication` reads its direction. Nothing in this module knows how mail
got there.

A message is linked to a deal by `Communication Link`, which is OneMail's, so a
deal's Mail tab is that link read back — through `spaceview/mail.py`'s
`get_list`, because a link is not a grant.

## OneCalendar

A quotation's `valid_till` is on somebody's week because OneCRM's manifest
declares a calendar over it, not because either module knows the other exists.

## OneCloud (`onestorage`)

A deal's attachments are `File` rows with `attached_to_doctype` set. Nothing
here does anything about it.

## The engine (`onespace`)

* **`spaceview/actions.py`** — the `log-a-call` verb, on five screens.
* **The timeline** — `calls.entries` is a source, keyed and timed by `at`.
* **`words.py`** — `OneSpace Word` is the workspace's own word for a screen, so
  a space that calls Deals *Donations* changes what every colleague reads.
  Read for everybody (a tab that draws nothing reads as broken), written by the
  Manager.
* **`mine.py`** — My deals is the same `@me` sentinel every twin screen uses.

## OneAI

`ai.md`. Nothing declared here, and one integration that matters.

## OneLegal

Nothing of its own. A CRM sends no data anywhere this product does not already
say it sends data.
