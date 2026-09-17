# OneBook

The space is a manifest — `oneapp_control/spaces/onebook.py`, thirty-odd screens
over ERPNext's Accounts module, argued in `docs/CLEANUP.md` §5 and §7 and
finished in `docs/ONEBOOK.md`. This module is the part of OneBook that is *not*
a declaration, and it is five files:

    origin.py       which space raised this document
    statements.py   the trial balance, the profit and loss, the balance sheet
    reconcile.py    a bank line against the documents it could be
    owing.py        what is outstanding, aged
    orders.py       the two steps of the selling chain

**Four of the five call ERPNext and none of them computes money.** That ratio is
the point rather than an embarrassment. A general ledger is the most solved
problem in business software; a second one is a set of books that does not agree
with the first. What each of these adds is the same four things: an allowlist of
what may be run, filters filled from the workspace rather than from a form, a
payload a screen can draw, and an address that is not the desk.

The one exception is `origin.py`, which answers a question ERPNext has no field
for. It is the only place in this module where a value is *decided* rather than
read.

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

**The CRM lane.** A Sales Invoice made from an order made from a quotation is
OneCRM's, and finding that out is joins up a chain on every save of every
invoice. It would be right and it would be slow. The honest place for it is a
nightly pass that does not exist yet; until then those invoices read as raised
here, which is wrong in a way somebody can see rather than wrong in a way that
costs a page load.

§7 below shortened that chain without closing it: an invoice made from an order
now carries the order, so the join is two hops rather than three.

---

## 3. `statements` — their reports, called rather than copied

`docs/ONEBOOK.md` §1. A trial balance, a profit and loss and a balance sheet are
what anybody keeps books *for*, and this space shipped without them.

ERPNext has all three, each with an `execute(filters)` returning
`(columns, data)`, and each carries things that are easy to get wrong and
expensive to get wrong twice: the sign convention per root type, the chart's
tree order and indent, period columns built from a year and a periodicity,
accumulated values, presentation currency, and the closing-entry handling that
decides whether an opening balance is an opening balance.

Writing the queries is not hard — a trial balance is a grouped sum. That is not
the objection. **A second implementation of a financial statement is a second
answer to "what did we earn"**, and the day the two disagree is the day somebody
has to decide which of them the auditor was shown.

Measured rather than assumed, all three return the same row shape, so one
normaliser serves them and `Statement.vue` draws any of them. They are
`component` screens rather than a view type: a view type is an alternate
rendering of the rows a screen has already narrowed to, and a statement is a
different aggregation over rows no screen lists.

**What it found.** The fixture's revenue was sitting in *Exchange Gain* — the
first Income leaf in ERPNext's chart, which is what the seeder's old fallback
picked — and its supplier bills in *Exchange Loss* and *Payroll Payable*. A year
of that is invisible, because a list of invoices shows the customer and the
total and never the account. It took a profit and loss to see it, which is the
argument for the whole stage in one sentence.

---

## 4. `reconcile` — a bank line, and what it could be

`docs/ONEBOOK.md` §3. The Bank feed lists what the bank sent. A reconciliation
is the other question: for each line, which document in these books is it — and
the answer is a *ranking* rather than a lookup, because a bank line carries a
date, an amount, a reference string and sometimes a name, and a payment carries
the same four with none of them guaranteed to agree.

ERPNext's `get_linked_payments` runs one query per document type and each
computes a rank from how many of four things agree: the amount to the penny, the
reference number, the party, and the unallocated amount. That ranking is the
product. It is also four queries of forty lines each with a sign convention per
direction, plus `subtract_allocations` on top, which takes off what a voucher
has already been reconciled against elsewhere.

What is ours is the allowlist — `MATCHABLE`, four document types held here and
never taken from the request — the permission, the shaping, and a date window
their queries cannot do without: they end in `posting_date BETWEEN from AND to`,
so passing nothing matches nothing at all. A year behind and a month ahead,
deliberately not symmetrical, because a payment is *entered* after the money
moves and sometimes long after.

**The party side is a verb rather than a screen.** `Payment Reconciliation` is
three grids of results, a Link to `DocType` whose picker is empty in this
product, and three buttons pressed in order against a document that is never
saved. What a bookkeeper does with it nine times in ten is one sentence — *this
receipt pays the oldest invoices that are open* — so it is one button on the
Payments screen, driving their tool in memory rather than drawing it.

**What it found.** The fixture was banking into a **Cash** account, and had been
since the space was built. It posted, it looked right on every screen, and it
could not be reconciled at all: ERPNext finds a voucher's bank leg with
`account_type = "Bank"`, so money in a Cash account has — as far as a
reconciliation is concerned — never touched the bank.

---

## 5. `owing` — how late, not how much

`docs/ONEBOOK.md` §4. The Invoices screen totals `outstanding_amount`, which
answers *how much*. An invoice for two thousand that went out last week and one
for two thousand that went out in March are the same number and completely
different problems.

Their report again, and what is not ours to own twice is the bucketing: whether
a document ages from its due date or its posting date, what a credit note
against an earlier month does to it, how a part payment is apportioned across
the buckets, and which ledger a partly settled advance belongs in.

**The roll-up by party is ours**, and it is a smaller claim than it sounds:
adding a column of numbers their report has already decided is arithmetic rather
than an opinion. Two decisions in it are the whole point of the screen. The
**worst is first, and that is not the biggest** — parties sort by what is late,
because the largest balance on the page is usually somebody's largest customer
paying normally. And **`range0` is kept** — everything not yet due, which on a
healthy ledger is most of the money and is the difference between "we are owed
four hundred thousand" and "and none of it is late".

---

## 6. Opening and closing

`docs/ONEBOOK.md` §2, and it has no module of its own because it needed none.
Four documents ERPNext already ships, none of which had a door: an opening
journal, the `Opening Invoice Creation Tool`, `Accounting Period`, and
`Period Closing Voucher`.

The stage turned out to be about the engine rather than about OneBook. An
`Opening Invoice Creation Tool` is a Frappe **Single** — one document, no list,
no record id, no New button — so every screen mechanism in this product passed
straight over it. OnePeople had already answered that for six HRMS Singles;
copying `onehr/tools.py` here would have been two sets of rules about what such
a page may write, so the form half moved to the engine as
`onespace/singles.py`, a third component screen any space may name beside
`home` and `configuration`.

---

## 7. `orders` — the middle of the selling chain

`docs/ONEBOOK.md` §5. A Quotation and a Sales Invoice with nothing between them,
and the plan's first draft said the missing middle was "won, not yet delivered",
which is a goods question. Measuring it said otherwise.

ERPNext's `Project` computes four numbers already — billed from its invoices,
cost from its timesheets, purchases from its bills, and a gross margin from
those. The fifth is `total_sales_amount`, and it is filled **from a Sales Order
and from nothing else**. So a workspace without orders has a project that knows
what it has billed and what it has cost and not what it was *worth*, which is
the denominator of every question a services firm asks about a contract and has
nothing to do with goods.

Granted by both spaces that touch it and at the same rung: accepting a quote is
a selling act — ERPNext puts the Sales Order in Selling for the same reason —
and billing one is a books act. What the two read it for differs, which is what
the two screens say.

Two verbs, both of them their mappers, and both **only ever making a draft**:
converting is clerical and submitting is a ledger act, and the second is a
decision somebody makes while looking at the document.

### What stays out, and where the list lives

Fixed assets, budgets, dunning, exchange rate revaluation, accounting
dimensions, and the goods half of the chain. Each has a reason and
`tests/test_book_scope.py` holds them, so adding one means writing its case in
the same commit — a paragraph in a document is a paragraph, and a reason nothing
checks is a reason that survives being wrong.

---

## 8. Why the supplier lives here

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
