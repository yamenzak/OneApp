# Integrations

## ERPNext

Everything. The space owns no doctypes and every screen is over
`erpnext/accounts`, with `Supplier` from `erpnext/buying`. `requires_apps` on
the manifest is `erpnext`, so `entitlements/apps.py` refuses the grant with the
app named rather than succeeding into a space of empty lists.

The one behaviour added to an ERPNext document is `custom_origin` on four of
them — `flows.md` §1.

**And nine of their functions are called rather than reimplemented**, each
declared in `oneapp/adapters/erpnext.py` with the reason:

| What | Why not ours |
| --- | --- |
| `trial_balance`, `profit_and_loss_statement`, `balance_sheet` | a second implementation of a financial statement is a second answer to "what did we earn" |
| `accounts_receivable`, `accounts_payable` | the bucketing — due date against posting date, credit notes, part payments, advances — runs off the Payment Ledger and is the whole of the report |
| `get_bank_transactions`, `get_account_balance`, `get_linked_payments`, `reconcile_vouchers` | the ranking is the product, and allocation is ledger surgery |
| `quotation.mapper.make_sales_order`, `sales_order.mapper.make_sales_invoice` | what carries forward from a quote to an order has twenty answers in it and no interesting ones |
| `OpeningInvoiceCreationTool.make_invoices` | temporary accounts, party types, savepoints per row, and enqueueing past fifty |
| `party.get_party_account` | the one filter `Payment Reconciliation` cannot work out for itself |

**One setting is changed at setup.** `Selling Settings.sales_update_frequency`
becomes `Each Transaction` — `onespace/books.py`. ERPNext defers the project
roll-up to a scheduled job by default, which is right on a site with a hundred
thousand orders and wrong on a workspace with a few hundred: it defers exactly
the number the Orders screen exists for, and a margin that is a month stale is a
margin nobody reads.

`Sales Invoice` also carries `onespace/retention.py`'s `validate` handler, which
is the engine's and predates this space. Both run, in the order `hooks.py` lists
them.

## HRMS

Read, in three doctypes and one direction. `Salary Slip`, `Payroll Entry` and
`Expense Claim` are granted at `Read` to the Manager seat and shown under the
**Raised elsewhere** heading. Nothing here writes any of them.

The Payroll screen draws with `record: payslip`, which is OneHR's record
view from `docs/CLEANUP.md` stage 6. It is the second screen in the product to
use it, and that is the stage-6 argument landing: a payslip is a payslip
whichever rail it was opened from.

## OneHR

Not an integration so much as the other end of one. OneHR **drafts** money
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

Owns the customer, which this space reads and never writes.

**And shares the Sales Order**, at the same rung in both manifests. Accepting a
quotation is a selling act — ERPNext puts the Sales Order in Selling for the
same reason — and billing one is a books act, so both spaces grant it and each
draws it for a different question: OneCRM's screen is what a rep has won,
OneBook's carries `per_billed`. The verb that makes one is declared here, in
`onebook/orders.py`, and offered on *OneCRM's* quotations screen: a verb belongs
to whoever owns the target.

Recognising an invoice that came down that chain in `custom_origin` is still
**not built**; the README §2 says why and what it would cost, and notes that the
order shortened the chain from three hops to two.

## The engine

`OneSpace Saved View` at `Write`/`if_owner` and `OneSpace Word` at `Read` for
everybody, `Write` for the Manager seat. The same two every space grants, for
the same two reasons.

## The engine's Single page

`onespace/singles.py`, which this space is half the reason for. An Opening
Invoice Creation Tool is a Frappe Single, so the list engine had nothing to say
about it and every screen mechanism passed over it. OneHR had already
solved that for six HRMS Singles; rather than copy `onehr/tools.py`, the form
half moved into the engine and both spaces name it. OneBook declares one screen
against it — `"component": "single"` with a doctype and a field list — and
writes no page code at all.

## Nothing else

This module reaches no microservice. It sends no mail, writes no file and makes
no AI call. A bill's attachment is a `File`, which is OneCloud's and reached
through the record's own Files tab with no code here.
