# OneBook

The space is a manifest — `oneapp_control/spaces/onebook.py`, twenty-one screens
over ERPNext's Accounts module, argued in `docs/CLEANUP.md` §5 and §7. This
module is the part of OneBook that is *not* a declaration, and at the moment it
is exactly one thing: `origin.py`.

That ratio is the point rather than an embarrassment. A general ledger is the
most solved problem in business software; a second one is a set of books that
does not agree with the first. Everything a bookkeeper does here is ERPNext
doing it, and what this product adds is **which of one hundred and ninety-three
doctypes a person is ever shown** — which is a manifest, not code.

---

## 1. What it replaced

Until `docs/CLEANUP.md` stage 7 this space was a **reference entitlement**:
eight ERPNext doctypes, no screens, and a docstring saying nobody had decided to
build a books app. It existed so the entitlement pipeline had something running
through it end to end — registry row, sync payload, role created, DocPerms
written, launcher rendering, reconciliation on removal — because with an empty
catalogue every one of those paths is dead code on a fresh control plane.

Four real spaces now run through that pipeline, so the stand-in had nothing left
to stand in for. Its space code was also the last one that disagreed with the
catalogue: `books` where the row in `oneapp/catalogue.py` says `onebook`, which
is the sort of thing stage 3 exists to stop.

---

## 2. `origin` — which space raised this

The only question in this space that no field on any doctype answers, and the
reason is that ERPNext answers it in three different places.

A bookkeeper opening **Invoices** is looking at three kinds of row at once:
invoices they raised, invoices OneProject raised against a job, and — once
there is a subcontractor — bills against that same job. **Journal entries** is
mostly theirs and occasionally a payroll run's. Their first question about any
row is *whose is this*, because the answer decides who they go and ask.

The answer is on the document already:

    Sales Invoice        `project`, or a project on any item row
    Purchase Invoice     the same
    Payment Entry        a reference row naming an Expense Claim or an advance
    Journal Entry        an account row whose `reference_type` is Payroll Entry

Three joins, none of them a column, none of them sortable, every one needing the
record open. So `custom_origin` is a **cache of a join**: written on `validate`,
read-only in every seat, holding a space id from `oneapp/catalogue.py` and
nothing else — so a screen grouping by it groups by the same word the rail uses.

Blank means nobody else raised it, and that is deliberately not spelt
"OneBook": a blank cell reads as *ours* and a filled one reads as *theirs*,
which is the distinction being drawn. Spelling it out would put the most common
value in the largest column and say nothing.

**Rewritten on every save, not set once**, because what it is derived from is
editable until the document is submitted. An invoice given a project on its
second save is a project's invoice from that save on.

**People before projects** where both are true. A payroll bank entry can carry a
cost centre that belongs to a project, and a payment for a job can also clear a
staff advance. The useful answer is the one naming a document somebody else
approved, because that is the one with a person at the end of it.

### What is not built

**The CRM lane.** A Sales Invoice made from a Sales Order made from a Quotation
made from an Opportunity is OneCRM's, and finding that out is three joins up a
chain on every save of every invoice. It would be right and it would be slow.
The honest place for it is a nightly pass that does not exist yet; until then
those invoices read as raised here, which is wrong in a way somebody can see
rather than wrong in a way that costs a page load.

**A trial balance, a P&L and a balance sheet.** ERPNext has all three as desk
reports and this product has no desk. Each is a grouped sum over `GL Entry` that
the Ledger screen's dashboard already draws two thirds of, and the missing third
is the sign convention. It is a stage of its own and not a paragraph of this
one.

---

## 3. Why the supplier lives here

`docs/CLEANUP.md` §7 says entities live once: OneCRM owns parties, OnePeople
owns people, OneCloud owns files. A `Supplier` is a party and OneCRM does not
own it, which looks like a contradiction and is not.

OneCRM owns the *demand* side — a Lead becomes a Prospect becomes a Customer,
and every one of those exists because somebody might buy something. A supplier
exists because you owe them money, and that is the whole of what is known about
one here: a name, a group, a currency and payment terms. Nothing in OneCRM would
ever read it.

When OneInventory is built it will want the same doctype, and it will **read**
it — the way OneProject reads a Sales Invoice.
