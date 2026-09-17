# Integrations

## ERPNext

Everything. The space owns no doctypes and every screen is over
`erpnext/accounts`, with `Supplier` from `erpnext/buying`. `requires_apps` on
the manifest is `erpnext`, so `entitlements/apps.py` refuses the grant with the
app named rather than succeeding into a space of empty lists.

The one behaviour added to an ERPNext document is `custom_origin` on four of
them — `flows.md` §1.

`Sales Invoice` also carries `onespace/retention.py`'s `validate` handler, which
is the engine's and predates this space. Both run, in the order `hooks.py` lists
them.

## HRMS

Read, in three doctypes and one direction. `Salary Slip`, `Payroll Entry` and
`Expense Claim` are granted at `Read` to the Manager seat and shown under the
**Raised elsewhere** heading. Nothing here writes any of them.

The Payroll screen draws with `record: payslip`, which is OnePeople's record
view from `docs/CLEANUP.md` stage 6. It is the second screen in the product to
use it, and that is the stage-6 argument landing: a payslip is a payslip
whichever rail it was opened from.

## OnePeople

Not an integration so much as the other end of one. OnePeople **drafts** money
documents and does not post them — `docs/ERP-SPACES.md`, "The line that moved,
and what moved it" — so a `Payment Entry` or `Journal Entry` raised there
arrives here as a draft for the bookkeeper to submit. `custom_origin` reads
`onehr` on it, which is how it is told apart from one raised here.

## OneProject

The mirror image. OneProject grants `Sales Invoice` at `Read` with `hide_new`
on its Invoices screen: a project reads what it has been billed and does not
bill. The invoice is raised here and carries the project, which is what
`custom_origin` reads as `oneproject`.

## OneCRM

Owns the customer, which this space reads and never writes. The other half —
recognising an invoice that came down the Quotation chain — is **not built**;
the README §2 says why and what it would cost.

## The engine

`OneSpace Saved View` at `Write`/`if_owner` and `OneSpace Word` at `Read` for
everybody, `Write` for the Manager seat. The same two every space grants, for
the same two reasons.

## Nothing else

This module reaches no microservice. It sends no mail, writes no file and makes
no AI call. A bill's attachment is a `File`, which is OneCloud's and reached
through the record's own Files tab with no code here.
