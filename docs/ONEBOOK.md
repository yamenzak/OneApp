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
| 3 | Reconciliation | not started |
| 4 | What is owed, aged | not started |
| 5 | The order, and what is deliberately out | not started |
| 6 | Docs, guards and the matrix | not started |

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

The bank feed is a list. `Bank Reconciliation Tool` is what turns it into a
reconciliation, and `Payment Reconciliation` is the same question on the party
side: which receipt settles which invoice.

## 4. What is owed, aged

"What are we owed" is on the Invoices screen as a column and a total, which
answers it for today. What it does not answer is *how late*, and an ageing is
the one report every business with customers opens weekly. ERPNext's
`accounts_receivable` and `accounts_payable` are reports of the same shape as
the statements, so they arrive through the same door.

## 5. The order, and what is deliberately out

`Sales Order` is granted by nobody, so the quote → order → invoice chain has no
middle. The narrow version of that hole: ERPNext lets a Quotation become a
Sales Invoice directly, and for a services business the real chain is quotation
→ project → invoice, which OneProject already carries. What is missing is
"won, not yet delivered", which is a goods question.

What stays out until somebody asks, and the reason each: fixed assets
(a depreciation schedule is its own product), budgets (a control nobody has
asked for), dunning (a letter, and OneWriter is where a letter belongs),
exchange rate revaluation (one company, one currency, until a customer says
otherwise), accounting dimensions (a second cost centre with more words).

## 6. Docs, guards and the matrix

Every stage adds screens and grants, so `seat_matrix.json` is regenerated and
the module docs are rewritten at the end rather than six times.
