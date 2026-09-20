# Flows

Almost everything here is ERPNext's own flow drawn on our screens, so this is
short by construction. Two things happen that are ours.

## 1. A document is stamped with where it came from

On every save of a `Sales Invoice`, `Purchase Invoice`, `Payment Entry` or
`Journal Entry`:

1. `hooks.py` calls `oneapp.onebook.origin.stamp` on `validate`.
2. `stamp` asks `doc.meta.has_field("custom_origin")` and returns if not.
   Custom fields are applied by the **tenant seeder** and not by migrate, so
   between installing the app and seeding the space every one of these doctypes
   exists without the column.
3. `_origin_of` reads the document's own links, people first:
   * a `Journal Entry` with an account row whose `reference_type` is one of
     `FROM_PEOPLE` → `onehr`;
   * a `Payment Entry` with a reference row naming one of them → `onehr`,
     otherwise its `project` → `oneproject`;
   * either invoice, its `project` or any item's → `oneproject`;
   * anything else → an empty string, which means somebody raised it here.
4. The value is set on the document. It is rewritten on every save rather than
   set once, because the thing it is derived from is editable until submit.

`origin.restamp(doctype)` does the same over every existing row, for a workspace
that had ERPNext before it had OneBook. It writes with `db_set` and no version
row: this is a cache of something that has not changed, and a hundred Version
rows saying so would be noise on submitted documents.

## 2. A statement, an ageing, a match

Five of the screens here ask ERPNext a question and draw the answer. None of
them stores anything, so there is no flow in the usual sense — but the shape is
the same five steps every time, and it is worth writing down once:

1. the screen names a **kind** (`trial-balance`, `receivable`, …) and the kind
   is looked up in an allowlist held in Python;
2. the reader's permission is checked against the doctype that side of the
   ledger is about — `GL Entry` for a statement, `Sales Invoice` or
   `Purchase Invoice` for an ageing, `Bank Transaction` for a match;
3. the filters are filled from the workspace — the company, the fiscal year,
   today — rather than asked for, because those are facts about the site and a
   form that asks for them is a form that can be answered wrongly;
4. their report or matcher runs;
5. the `(columns, data)` it returns is flattened into one payload shape, so one
   component draws every member of the family.

`statements.py`, `owing.py` and `reconcile.py` are the same five steps three
times. A sixth report of the same shape is a row in a dictionary.

## 3. A bank line is tied to a document, and untied

**Match**: `reconcile.matches` ranks candidates, the reader ticks, and
`reconcile.match` hands the chosen ones to ERPNext's `reconcile_vouchers` —
which adds the rows, refuses a duplicate reference, allocates oldest first up to
the line's amount, sets the clearance date on each voucher and moves the
transaction's status on. How much of the line each voucher takes is theirs to
work out; this module sends two keys per voucher and no amount.

**Unmatch**: `remove_payment_entries`, which does the half that is easy to
forget — taking the clearance date back off every voucher, not just the rows off
the transaction.

## 4. A quotation becomes an order, and an order an invoice

Both through ERPNext's own mappers, and both stopping at a draft:

1. `orders.order` on a submitted quotation runs `make_sales_order`, inserts what
   it returns, and answers `{"open": {"screen": "orders", …}}`;
2. `orders.bill` on a submitted order runs `make_sales_invoice`, which takes off
   what has already been billed row by row, and opens the draft invoice.

Neither submits and neither passes `ignore_permissions`. The reader's own
permission decides what they may create, checked at the insert rather than at a
form they could not have saved.

The verb is declared in `orders.actions()` and reached through
`spaceview/run.py`, which resolves the screen it names against the space the
action was pressed in — so a verb cannot open somebody else's screen.

## 5. The four seats decide what a screen can do

There is no code in this module for it, and that is the interesting part. The
engine reads `frappe.has_permission` to decide whether a screen draws a New
button, a Save or a Submit, so a grant of `Read` on `Salary Slip` produces a
read-only payroll screen with no further instruction. See `permissions.md`.

## What the space does not do

**It does not post anything automatically.** Nothing here watches OneHR or
OneProject and raises a document in response. A payroll run's bank entry is
written by HRMS when somebody presses **Make the bank entry** in OneHR —
`docs/ERP-SPACES.md`, "The line that moved" — and it appears here because it is
a `Journal Entry`, not because this module was told about it.

That is the whole shape of the integration: the other spaces draft and this one
reads, posts and pays. There is no message, no queue and nothing to keep in
step.
