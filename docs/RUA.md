# RUA — the first space

RUA Contracting is an aluminium, glass and cladding contractor in Abu Dhabi.
They run on `ruabeta.frappe.cloud`: **plain Frappe 16 plus one app**, `rua`
2.1.0, with 26 doctypes and about 1,400 records. No ERPNext, no HRMS, no
accounting — which is the whole reason to rebuild it.

This is what is there, what it becomes, and what OneSpace has to grow to hold
it. Read it before writing any of the space.

## 1. What they actually do

A contract is won, priced as a **Quotation** with a line per opening (width ×
height × quantity, priced by area). Materials are sourced by **RFQ** to
suppliers, ordered on an **LPO**, and booked in on a **Purchase Receipt**
against that LPO. The client is billed in progress **Invoices** — a Proforma
first, then a Tax Invoice — each with UAE VAT at 5% and a **retention**
percentage withheld. **Payments** move both ways, and a project's
invoiced/received/cost figures are reconciled from them.

Alongside that: 71 employees with daily attendance and leave, a register of
expiring documents (visas, trade licences, passports), and a bilingual
English/Arabic **letter and form** register with signatures and its own
numbering.

The numbers, live: 82 projects, 97 parties, 63 invoices, 155 payments, 408
documents, 307 attendance days, 51 letters. Two doctypes have never been used —
`RUA Inventory Item` and `RUA Payslip` are both empty.

## 2. What each doctype becomes

The point of the rebuild is that most of this stops being ours. ERPNext and
HRMS already model it, with a general ledger and a VAT return underneath.

| Today | Becomes | Note |
| --- | --- | --- |
| `RUA Party` (Client / Consultant / Supplier: Glass, Aluminum, Cladding) | **Customer** and **Supplier**, with Customer/Supplier Groups for the sub-types | 51 clients, 24 consultants, 22 suppliers. A consultant is a Customer nobody invoices — a group, not a doctype. |
| `RUA Project` | **Project**, plus custom fields for contract value and emirate | The parent/child pair (`parent1`, `is_child`) is a variation order: ERPNext's own project hierarchy, not a flag. |
| `RUA Quotation` + items | **Quotation** + Quotation Item, priced by area | Width/height/area belong on the item row; `Sq.m` is an ERPNext UOM. The eight Text Editor blocks (scope, exclusions, terms…) become **Terms and Conditions** plus a print format. |
| `RUA RFQ` + items | **Request for Quotation** → **Supplier Quotation** | Two steps in ERPNext where there was one, and the second is where a supplier's price is actually compared. |
| `RUA LPO` + items | **Purchase Order** | `received_quantity` / `pending_quantity` are ERPNext's own `received_qty`. |
| `RUA Purchase Receipt` + items | **Purchase Receipt** | Same shape already. |
| `RUA Invoice` | **Sales Invoice** (Proforma → a draft, or a Sales Order) | See §3: retention is the one thing ERPNext does not model. |
| `RUA Payment` (Pay / Receive / Petty Cash / Salary) | **Payment Entry**, and a **Journal Entry** for petty cash | This is the change that buys them a ledger: today a payment is a row with an amount and nothing behind it. |
| `RUA Employee` | **Employee** (HRMS) | `basic` + `allowance` become a **Salary Structure**. |
| `RUA Attendance` (one row per *day*, a JSON blob keyed by employee) | **Attendance**, one row per employee per day | 307 blobs become ~20,000 rows. The blob is why nothing can report on it. |
| `RUA Leave` | **Leave Application** + Leave Ledger | Gains balances, which they do not have. |
| `RUA Payslip` (empty) | **Salary Slip** | Never used; ships as HRMS payroll. |
| `RUA Inventory Item` (empty) | **Item** + Stock | Never used. Not in scope for v1. |
| `RUA Chat` | Frappe **Comment** on the Project | We already render a timeline. 58 messages migrate as comments. |
| `RUA Todo` | **ToDo** and our assignment | |
| `RUA Company` (single) | **Company** + workspace settings | The Google Sheets keys die with §5. |
| `RUA Issue` / `RUA Remote Issue` / `RUA App Update` | dropped | A developer's own bug tracker and changelog. Not the customer's system. |
| `RUA Document` | **stays ours** | See §4. |
| `RUA Letter` | **stays ours** | See §4. |

## 3. Retention, which is the interesting one

UAE construction withholds a percentage of every progress invoice, released on
completion. ERPNext has no retention concept, and the old app stores it as three
denormalised currency fields per invoice (`amount_after_retention`,
`vat_after_retention`, `grand_total`) computed in the browser.

The honest modelling is a **deduction row in Sales Taxes and Charges** against a
*Retention Receivable* account, so the withheld money is on the balance sheet
where it belongs and the release is an ordinary journal. That is the design to
confirm with an accountant before writing it; everything else in §2 is
mechanical.

Two smaller ones in the same file: `is_vat_inclusive` is ERPNext's inclusive tax
on the item row, and `serial_number` — a per-project sequence for Final tax
invoices — is a custom field, because Frappe's naming series is global.

## 4. What genuinely has no home

Two things ERPNext and HRMS do not model, which the space must ship as its own
doctypes:

* **A document register with expiry.** 408 rows: a visa, a trade licence, a
  passport, attached to any record through a Dynamic Link, each with an issue
  and expiry date. HRMS has an employee-document idea; this is wider, and the
  expiry alert is the whole point of it.
* **A bilingual letter and form register.** 51 letters, English and Arabic side
  by side, with author and signee blocks in both, templates, and `RC-LTR-` /
  `RC-FRM-` numbering. Nothing in Frappe does this.

**And a space cannot ship a doctype today.** A space is a control-plane record —
`OneSpace Space` with screens, roles and doctype grants — over doctypes that
already exist on the tenant. There is no path for "this space brings two
doctypes of its own". That is the first thing to build, and it is the biggest
gap this exercise has found.

## 5. What to delete rather than port

The old app drives quotation pricing and invoice generation through **Google
Sheets** — a service account, a template sheet copied per project, a named range
read back for line items, 582 lines of `google_sheets.py`. It exists because the
app had no usable grid.

We have one. Quotation items are a child table with computed columns; the output
is a print format. Nothing about a spreadsheet survives the port, and saying so
now is what stops it being ported by habit.

Same for `prints.py` (670 lines of hand-built HTML): print formats, built in the
builder.

## 6. What OneSpace is missing, found by trying to hold this

In the order they block:

1. **A space cannot ship doctypes.** §4. Without it the document register and the
   letters have nowhere to live.
2. **No Arabic and no RTL.** Every letter is bilingual. The SPA has never
   rendered right-to-left text, and `dir` is nowhere in it.
3. **Computed child-table columns.** A quotation line is width × height × qty ×
   rate, and a total per row and per document. Our grid edits values; it does not
   derive them.
4. **HRMS is not in the tenant bench.** A shard installs
   `frappe,erpnext,oneapp`. Payroll, leave balances and attendance all need it.
5. **A matrix screen.** Attendance is a month × employee grid — a real screen
   type, not a list, and the first thing that needs the `component` escape hatch.
6. **Expiry alerts.** A document register is worth having because it tells you a
   visa expires in thirty days. That is Notification Rules, which we deferred.

None of these is a reason to stop; they are the order to build in.

## 7. How to migrate

Read-only, over the API, with the key in the scratchpad and never in this repo.
`frappe.client.get_list` reads everything; nothing is written back to the old
site. The order is dictated by the links: Parties → Projects → Employees →
Quotations → RFQs → LPOs → Receipts → Invoices → Payments → Attendance → Leave →
Documents → Letters.

Two things to decide before the first row moves: what an opening balance looks
like (63 invoices and 155 payments with no ledger behind them have to land as
something), and whether history moves at all or only open work does.
