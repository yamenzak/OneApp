# Permissions

Four seats, the same four as every space — `oneapp_control/spaces/roles.py` —
and this is the space they were designed for. Frappe roles are
`Books-User`, `Books-Manager`, `Books-Audit` and `Books-Admin`.

## Who may do what

| Seat | May |
| --- | --- |
| **User** | Raise, amend and cancel a `Sales Invoice`. Read the chart, the cost centres, the ledger, the fiscal years and the periods. Read the customers, items and currencies an invoice resolves against. |
| **Manager** | Everything above, plus `Payment Entry`, `Journal Entry`, `Purchase Invoice` and `Bank Transaction` at Manage, the supplier at Manage, and read on what OnePeople raised: `Salary Slip`, `Payroll Entry`, `Expense Claim`, `Employee`, `Project`. |
| **Admin** | Everything above, plus the shape of the books: `Account`, `Cost Center`, `Fiscal Year`, `Accounting Period` and the four templates, all at Manage. |
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
