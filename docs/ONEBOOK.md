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
| 2 | Opening and closing | not started |
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
leaves, and nothing in OneBook takes it. A workspace reaching the end of a year
has to move its profit to retained earnings and stop people posting into the
year it just closed.

Both exist in ERPNext — `Journal Entry.is_opening`, the
`Opening Invoice Creation Tool`, `Period Closing Voucher`, and the
`Accounting Period` screen OneBook already has — and neither has a door.

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
