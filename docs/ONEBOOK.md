# Finishing the books

`docs/CLEANUP.md` stage 7 built OneBook: twenty-one screens over ERPNext's
accounts, four seats, and `custom_origin` saying which space raised a row. The
retrospective after stage 13 asked whether it was a complete accounting
solution and the answer was no, with a list. This is the arc that closes the
list.

**The long-term shape this serves**, and the reason it is worth doing properly
rather than adding three reports: every doctype Frappe, ERPNext and HRMS ship
should end up reachable through the One Suite, split across spaces and
microservices rather than presented as one desk of two thousand tables. OneBook
is the test of whether that can be done for a whole functional area, because
accounting is the area with the most doctypes, the least room for approximation
and the clearest definition of finished — a set of books either produces a
balance sheet that balances or it does not.

---

## 0. Where we are

| # | Stage | State |
| --- | --- | --- |
| 1 | The statements | **done** — three screens over ERPNext's own reports; found revenue booked to Exchange Gain |
| 2 | Opening and closing | **done** — four doors, and a Single became a screen the engine draws |
| 3 | Reconciliation | **done** — a two-pane screen for the bank, a verb for the party; found the fixture banking into Cash |
| 4 | What is owed, aged | **done** — two sides, one component; the roll-up sorts by what is late rather than by what is large |
| 5 | The order, and what is deliberately out | **done** — the order is not a goods question, and the out-list is a guard |
| 6 | Docs, guards and the matrix | **done** — seven documents rewritten, and the five specs this space never had |

Same rules as the cleanup arc: one stage, one commit, pushed; `pytest`,
`vitest` and `vite build` green before each; nothing kept for compatibility.

---

## 1. Call their reports, do not copy them

The decision the whole arc rests on.

ERPNext ships `trial_balance`, `profit_and_loss_statement` and `balance_sheet`
as reports with an `execute(filters)` that returns `(columns, data)`. Each
carries things that are easy to get wrong and expensive to get wrong twice: the
sign convention per root type, the chart's tree order and indent, period
columns built from a fiscal year and a periodicity, accumulated values,
presentation currency, and the closing-entry handling that decides whether an
opening balance is an opening balance.

**We call them.** Measured on the dev site, all three return the same row shape
— `account`, `account_name`, `indent`, `currency`, and one or more `Currency`
columns for the periods — so one normaliser serves all three and the seam is a
single entry per report in `oneapp/adapters/erpnext.py`.

The alternative was writing the queries ourselves, and it is worth naming why
not. It is not effort: a trial balance is a grouped sum and half a day. It is
that a second implementation of a financial statement is a second answer to
"what did we earn", and the day the two disagree is the day somebody has to
decide which of them the auditor was shown.

**A statement is not a list**, so these are `component` screens rather than a
view type. The view types are alternate renderings of the rows a screen has
already narrowed to; a trial balance is a different aggregation with its own
filters, over rows no screen lists. `spaceview/actions.py`'s escape hatch is
for exactly this — "a dashboard, a wizard, anything a list cannot be".

## 2. Opening and closing

A workspace arriving from another system has a trial balance on the day it
leaves, and nothing in OneBook took it. A workspace reaching the end of a year
has to move its profit to retained earnings and stop people posting into the
year it just closed. All four documents existed in ERPNext and none had a door.

Four now, under one heading of their own rather than under Setup, because none
of these is a setting: each is a thing somebody does once, on a date, and which
every number on every statement is downstream of.

**Opening balances** is the Journals screen narrowed to `is_opening = Yes`,
with a New button that starts a record the screen will actually show —
`view_settings.create` fills in `is_opening` and `Opening Entry`, and those two
values are checked against the screen's own columns on the way in.

**Opening invoices** is ERPNext's `Opening Invoice Creation Tool`, and it is
where the stage turned out to be about the engine rather than about OneBook.
It is a **Single** — a doctype with exactly one document — and Frappe's list
engine has nothing to say about one: no list, no record id, no New button. So
every screen mechanism in this product passed straight over it.

OnePeople had already answered that once, for six HRMS Singles, in
`onehr/tools.py`. Copying that file into OneBook would have been two sets of
rules about what such a page may write, so the form half moved to the engine
instead — `onespace/singles.py`, a third component screen any space may name,
beside `home` and `configuration`. A space says

    {"screen": "opening-invoices", "component": "single",
     "document_type": "Opening Invoice Creation Tool",
     "fields": "company,invoice_type,create_missing_party,invoices"}

and gets the doctype's own form, drawn by the component a record page uses —
including the child table, which is what an opening invoice list is. OnePeople
kept the half that is actually about people: find the people these filters
describe, then do it to the ones that were ticked.

Two things are named on this side and not in the manifest, and both because a
screen key arrives from a browser. The **writable fields** are the screen's
`fields`, which is where every other allowlist in this product lives. And a
**verb beyond Save** is `VERBS`, keyed by doctype and holding the whole dotted
path — module, class, method — checked against the document before it is
called. A manifest that could name a method would be a manifest that can call
anything; a bare method name would survive an upgrade that moved the class and
call whatever else answered to it.

**Year end** is `Period Closing Voucher`, submittable, which is what makes
closing a year early recoverable: ERPNext posts the closing entries on submit
and reverses them on cancel. `gle_processing_status` is a column because the
posting is enqueued on a large chart and "Completed" is the only word that says
the year is actually closed.

**Accounting periods** moved here from Setup. `closed_documents` — the child
table that is the actual lock — was already on the record's own form, because a
record page is handed every field of its doctype and only the *list* is
narrowed to what the manifest names.

Both new grants are Admin, which is the same argument the statements made in
reverse: taking an opening balance twice doubles the books, and closing a
period stops everybody else posting.

## 3. Reconciliation

The bank feed was a list. What it could not say is which document in these
books each of its lines is — which is the whole of what a bank account is *for*
in a set of books, and the thing an auditor asks about first.

**Their matcher, called rather than copied**, on the same argument as §1 and
more so. ERPNext's `get_linked_payments` runs one query per document type and
each computes a **rank** from how many of four things agree: the amount to the
penny, the reference number, the party, and the unallocated amount. It has a
sign convention per direction — a deposit looks at `paid_to` and may match a
Sales Invoice, a withdrawal looks at `paid_from` and may match a Purchase
Invoice — and `subtract_allocations` on top, which takes off what a voucher has
already been reconciled against somewhere else. That ranking is the product. A
second opinion about which payment a bank line is would be the worst thing in
this space to own twice.

So `onebook/reconcile.py` does the four things their tool does not: asks the
caller's own permission, holds the allowlist of what may be matched against,
shapes the answer into rows, and gives it an address that is not the desk.

**Two lists side by side**, which is why this is a component screen and not a
view type — more clearly than the statements were. A view type is an alternate
rendering of the rows a screen has already narrowed to; here the right-hand
list is a function of the row selected in the left-hand one.

**The window nothing said out loud.** Their queries end in `posting_date
BETWEEN from AND to`, so passing no dates is `BETWEEN NULL AND NULL` and
matches nothing at all — a screen that silently finds no candidate for any
line. Measured, not reasoned about. `LOOK_BACK` and `LOOK_AHEAD` are a year
behind and a month ahead, and they are deliberately not symmetrical: a payment
is *entered* after the money moves and sometimes long after, while one entered
a year before it moved is somebody's mistake rather than this line.

### The party side is a verb, not a screen

`Payment Reconciliation` is the same question about a receipt rather than a
bank line, and putting its form in the rail would have been a worse version of
it: three grids of things the tool *found* rather than things anybody types, a
Link to `DocType` whose picker is empty in this product, and three buttons
pressed in order against a document that is never saved — its own `db_update`
is a no-op, which is Frappe's way of saying it is a question rather than a
record.

What a bookkeeper does with it nine times in ten is one sentence: *this receipt
pays the oldest invoices that are open.* That is a verb on the payment, so it
is one button on the Payments screen — `spaceview/actions.py`, driving their
tool in memory rather than drawing it. It still has to go through their tool,
and that is the part worth knowing: a **submitted** Payment Entry's references
cannot simply be edited, so allocating one after the fact is ledger surgery and
`reconcile_allocations` is where it lives.

Splitting a receipt across invoices out of order is the tenth time, and it is
in §5's list of what is deliberately out.

### What it found

The fixture was banking into a **Cash** account, and had been since the space
was built. It posted, it looked right on every screen, and it could not be
reconciled at all: ERPNext finds a voucher's bank leg with `account_type =
"Bank"`, so money in a Cash account has — as far as a reconciliation is
concerned — never touched the bank. Nothing says so until the day somebody ties
a statement to it.

That is the same shape as the revenue-in-Exchange-Gain that §1 turned up, and
the same lesson: a books space is only as honest as the screen that would have
to disagree with it. The seeder now opens a Bank-type leaf, sets it as the
company's default, and takes its own receipts off whatever they landed in
before.

## 4. What is owed, aged

The Invoices screen carries an `outstanding_amount` column and totals it, which
answers *how much*. An invoice for two thousand that went out last week and one
for two thousand that went out in March are the same number and completely
different problems, and no list in this space could tell them apart.

**Their report, called rather than copied**, on the same argument as §1 and §3.
What looks like "subtract two dates" is a set of decisions: whether a document
ages from its due date or its posting date, what a credit note against an
earlier month does to it, how a part payment is apportioned across the buckets,
and which ledger a partly settled advance belongs in. All of it is
`ReceivablePayableReport`, it runs off the Payment Ledger rather than off the
invoices, and a second version of it is a second answer to "are we owed this".

**One shape for both sides**, measured: `accounts_receivable` and
`accounts_payable` return the same row — party, voucher, due date, outstanding,
an age and six buckets — differing only in columns neither screen draws. So
`Owing.vue` draws either, and which side it is arrives as the screen it is
mounted as.

**Two screens rather than one with a switch**, because in OneBook the two sides
sit on opposite rungs: being owed money is everybody's business and owing it is
the bookkeeper's. Each names its invoice doctype, which is both what the screen
is about and the grant refused at the door.

### What this module does add

The roll-up by party, and it is a smaller claim than it sounds. ERPNext also
ships `accounts_receivable_summary`, which is the same report grouped — calling
it would be a second query over the same ledger for sums already in hand.
Adding a column of numbers their report has decided is arithmetic rather than
an opinion, and the detail rows travel in the same payload so the two can be
checked against each other on screen.

Two small decisions in it are the whole point of the screen. **The worst is
first, and that is not the biggest**: parties sort by what is *late*, because
the largest balance on the page is usually somebody's largest customer paying
normally and the row worth a Monday morning is the smaller one sitting in the
last two buckets. And **`range0` is kept** — everything not yet due, which on a
healthy ledger is most of the money and is the difference between "we are owed
four hundred thousand" and "we are owed four hundred thousand and none of it is
late".

The bucket headings are read off their columns rather than composed from the
boundaries here, so a boundary moved in one place cannot leave the headings
saying the old one.

## 5. The order, and what is deliberately out

This section's first draft said the missing middle was "won, not yet
delivered", which is a goods question, and that a services business runs
quotation → project → invoice instead. Measuring it said otherwise, and the
measurement is the whole of stage 5.

**ERPNext's `Project` already computes four numbers.** `total_billed_amount`
from its invoices, `total_costing_amount` from its timesheets,
`total_purchase_cost` from its bills, and a gross margin from those. The fifth
is `total_sales_amount`, and it is filled **from a Sales Order and from nothing
else**. So a workspace without orders has a project that knows what it has
billed and what it has cost and not what it was *worth* — which is the
denominator of every question a services firm asks about a contract, and has
nothing to do with goods.

On the fixture that reads: **zzHarbour Point fit-out, agreed 400,000, billed
240,000**. Before this stage the first number was nought.

So the order is granted, and by **both** spaces that touch it and at the same
rung. Accepting a quote is a selling act — ERPNext puts the Sales Order in
Selling for the same reason — and billing one is a books act. What the two read
it *for* differs, and that is what the two screens say: a rep's list is what
they have won, a bookkeeper's carries `per_billed`, which is the only number in
this product that answers "how much of this contract is left".

**Two verbs, both of them their mappers.** `make_sales_order` on a quotation
and `make_sales_invoice` on an order are `get_mapped_doc` definitions — a field
map per doctype, a per-row condition that skips what is already fulfilled, and
a postprocess that reprices and recalculates the taxes. The second is why a
part-billed order opens an invoice for the remainder rather than for the whole
thing again.

Both **only ever make a draft**. Converting is clerical and submitting is a
ledger act, and the second is a decision somebody makes while looking at the
document. Neither passes `ignore_permissions`, so a seat that may not raise an
invoice cannot reach one through an order.

**And one setting.** ERPNext defers the project roll-up to a scheduled job
unless `Selling Settings.sales_update_frequency` is `Each Transaction`, which
on a site with a hundred thousand orders is the right default and on a
workspace with a few hundred is not: it defers exactly the number this stage
exists for. A margin that is a month stale is a margin nobody reads, so
`onespace/books.py` sets it at setup.

### What stays out

Each of these is absent on purpose, and `tests/test_book_scope.py` holds the
list so that adding one means writing its case in the same commit. None is a
judgement about ERPNext; each is a judgement about *this* space, because a
books space that grows a module nobody asked for is a books space that takes
twice as long to learn.

* **Fixed assets** — `Asset`, `Asset Category`. A depreciation schedule is its
  own product: a life, a method, a salvage value and a disposal, none of which
  the rest of this space would ever read.
* **Budgets** — a control nobody has asked for, and one that is only worth
  having where somebody enforces it.
* **Dunning** — a letter, and OneWriter is where a letter belongs.
* **Exchange rate revaluation** — one company and one currency until a
  customer says otherwise.
* **Accounting dimensions** — a second cost centre with more words.
* **The goods half of the chain** — `Delivery Note`, `Stock Entry`,
  `Material Request`. This is where the order deliberately stops: it says what
  was agreed and the invoice says what was billed, and what was *delivered* is
  a stock question. A workspace that wanted it would want a warehouse first,
  and that is a space rather than a screen.

## 6. Docs, guards and the matrix

Every stage added screens and grants, so the matrix was regenerated as it went
and the documents were rewritten once at the end rather than six times.

**Seven documents.** `onebook/README.md` gained a section per module — the
argument for each, and what building it *found*, because two of the five found
something the tests could not have. The six reference files under `docs/` gained
the new doctypes, the five ERPNext reports (which are not collections, because a
report is not a doctype and nothing here stores its answer), the two mappers,
the one Selling Settings change, and the two grants that sit where a reader
might expect the other ones.

**And the specs this space never had.** Five stages of screens shipped without a
browser test, which was the one honest debt the arc carried the whole way. It is
paid now — `e2e/onebook.spec.js`, five tests, twenty seconds — and the reason it
had to be paid is that none of these screens fails the way a list does:

> A list that goes wrong renders thinner. A statement, a reconciliation and an
> ageing all render as an **empty panel**, which is exactly what a workspace
> with no data looks like — so a server change that quietly stops answering is
> invisible from the browser and from `check_screens.py` alike.

So the assertions are the things that would still be true of an empty screen if
they were not checked: that a balance sheet **balances**, read off the rendered
cells rather than the payload, because a sign convention applied on the server
and dropped in the component is the failure this exists for. That a profit and
loss offers a periodicity and a trial balance does not. That a bank line's
candidates are a function of the row selected and arrive ranked. That an ageing
puts the late before the large and keeps the not-yet-due bucket. That an order
says how much of itself is still to bill, and that the number is a *fraction*,
which is the only state proving it is ERPNext's rather than a default.

The spec names the five endpoints it drives in a comment, which is not decoration:
`scripts/affected.py` attributes a Python change by the whitelisted dotted names
in it, so a spec that reached an endpoint only through a route would be a spec it
could not see the change reaching.

---

## What the arc did not do

Written down here rather than left to be rediscovered.

**`custom_origin` still does not read the CRM lane.** An invoice made from an
order made from a quotation reads as raised in OneBook. Stage 5 shortened the
chain from three hops to two without closing it; the honest fix is a nightly
pass rather than three joins on every save, and it does not exist.

**Nothing here is scheduled.** The ageing is a screen somebody opens, not a
Monday email. `notifications.md` says why that is the last mile rather than the
whole road.

**No AI.** `ai.md` names the two things worth building — reading a bill, and
suggesting the account from how the same supplier was coded before — and the
rule either would keep: OneAI proposes and a seat decides.
