# Permissions

Four seats, the same four as every space — `oneapp_control/spaces/roles.py` —
and this is the space they were designed for. Frappe roles are
`Books-User`, `Books-Manager`, `Books-Audit` and `Books-Admin`.

## Who may do what

| Seat | May |
| --- | --- |
| **User** | Raise, amend and cancel a `Sales Invoice` and the `Sales Order` it is against. Read the chart, the cost centres, the ledger, the fiscal years and the periods. Read the customers, items and currencies an invoice resolves against. |
| **Manager** | Everything above, plus `Payment Entry`, `Journal Entry`, `Purchase Invoice` and `Bank Transaction` at Manage, the supplier at Manage, `Payment Reconciliation` at Write, and read on what OnePeople raised: `Salary Slip`, `Payroll Entry`, `Expense Claim`, `Employee`, `Project`. |
| **Admin** | Everything above, plus the shape of the books: `Account`, `Cost Center`, `Fiscal Year`, `Accounting Period` and the four templates at Manage — and the two ends of a set of books, `Opening Invoice Creation Tool` at Write and `Period Closing Voucher` at Manage. |
| **Audit** | Read on everything any of the three above may reach, and write on nothing. |

The ladder is `registry.laddered`: a grant names the **lowest** seat that may do
it and the seats above inherit. Audit is derived at Read from every grant in the
manifest without the manifest saying a word about it.

## Why Audit matters here more than anywhere

An auditor is a real person who turns up once a year, is handed the books and
must not be able to change one of them. Every other space has an Audit seat
because the four are the same four everywhere; this is the one where somebody
outside the company actually sits in it.

What it gets is exactly the union of the other three seats at `Read` — including
the payroll register, which is the point and not an oversight.

## The payroll grant, said plainly

`Salary Slip` is granted at `Read` to the **Manager** seat, which means the
bookkeeper can read what every employee is paid. That is not a leak, it is the
job: the person writing the cheque knows the amount on it. The User seat — the
one raising sales invoices — does not have it.

In OnePeople the same doctype sits behind the Admin seat and `Employee`'s
salary fields are at permlevel 2. Those are different questions: OnePeople is
deciding who may *set* a salary, and this is deciding who may *pay* one.

## The order is on the User rung, and the closing on Admin

Two decisions worth stating, because they are the only two in the table that a
reader might expect the other way round.

**An order is the invoicer's.** Whoever raises the invoice raises the thing it
is billed against; splitting them would mean a seat that can bill a contract it
cannot see the shape of.

**Opening and closing are Admin's**, and both are once-a-year acts that reach
every number on every screen: taking an opening balance twice doubles the books,
and closing a period stops everybody else posting. That is the profile of a
thing that belongs one rung above the person using it daily — the same argument
the chart of accounts is on that rung for.

## One grant with no screen

`Payment Reconciliation`, deliberately. A doctype whose `db_update` is a no-op
is a question rather than a record, and rendering its form would be a worse
version of it than the button on the Payments screen is — three grids of results
and a Link to `DocType` whose picker is empty in this product. The grant exists
because the space uses the doctype, and a space that uses one and does not say
so is a space whose manifest does not add up.

## What guards check

Nothing in this module. The engine reads `frappe.has_permission` to decide
whether a screen draws New, Save or Submit, so a `Read` grant produces a
read-only screen with no further instruction — which is why the **Raised
elsewhere** screens also carry `hide_new`, to say so before the click rather
than after it.

`tests/test_space_seats.py` checks the ladder, `tests/test_space_screens.py`
checks that every screen shows a doctype its space granted, and
`tests/test_onebook_origin.py` checks that `custom_origin` is read-only on all
four doctypes.

Four more are this arc's: `test_book_statements.py`, `test_bank_reconcile.py`,
`test_book_owing.py` and `test_book_scope.py`. The last is the one worth
knowing about — it holds what the space deliberately does *not* grant, so a
doctype arriving in the manifest without an argument fails there rather than
being noticed a year later.

And `tests/fixtures/seat_matrix.json` is the whole of it, regenerated from a
running site: every screen against every seat, and what each may open, create
and press. `scripts/dev.sh run scripts/seat_matrix.py` writes it and
`test_seat_matrix.py` fails when the manifests and the fixture disagree.
