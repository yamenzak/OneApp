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
| `RUA Payment` (Pay / Receive / Petty Cash) | **Payment Entry** | This is the change that buys them a ledger: today a payment is a row with an amount and nothing behind it. Petty cash is not a fourth kind of transaction — all eleven of them pay a supplier — so it is a Pay with `Cash` as the mode of payment, not a Journal Entry. |
| `RUA Employee` | **Employee** (HRMS) | `basic` + `allowance` become a **Salary Structure**. |
| `RUA Attendance` (one row per *day*, a JSON blob keyed by employee) | **Attendance**, one row per employee per day | 307 blobs become 20,229 rows. The blob is why nothing can report on it. |
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

Not a script. `oneapp_core/importer.py` is an engine, and it is not
RUA-specific: a plan is data — steps, field maps, value maps — so the next
workspace arriving off its own Frappe site is a plan and no code at all.

Five properties are what make it worth calling one:

* **Idempotent.** Every source row's target is remembered in `Import Identity`,
  so a second run updates the record the first made rather than making another.
  That table is also link resolution: an invoice's `party` becomes the Customer
  an earlier step made out of the same source row.
* **Incremental.** Each step keeps a watermark — the newest `modified` it has
  taken across — and asks the source only for rows at or after it. Rehearse a
  month out, run it again the morning of the switch, and the second run carries
  the night's work. That is the whole of "up to the last second".
* **Resumable.** The watermark advances per committed batch, not per run.
* **Answerable.** A row that will not save is kept whole — what the source said,
  what we made of it, what refused it — so a bad import is a list to work
  through rather than a log to read.
* **Rehearsable.** A dry run fetches, maps, resolves and validates, and commits
  nothing.

It writes through `get_doc().save()`, never a direct SQL write: an imported
Sales Invoice that skipped its own controller is a row in a table rather than a
document, and the ledger behind it does not exist. It also runs as whoever
pressed the button, so an import cannot create what its operator could not.

The customer's half is one panel in workspace settings: their old site's
address and API key, **Rehearse**, and then **Bring everything across** — which
becomes **Bring across what has changed** once it has been over once.

**The plan is checked before it is run.** A fourteen-step field map is a
document nobody can read for correctness, and every mistake in one is quiet: a
source field renamed since somebody wrote the map drops a column, a target field
that does not exist on this site's version drops another, a value map that
covers four of the five values in a column lets the fifth through untouched, and
a link resolved against a later step files an issue per row. `importer.check`
reads both schemas — the source's over the wire, this site's locally — and
reports all four. It touches nothing, so it is free to press.

The plan itself is `oneapp_core/plans/rua.py`: eleven steps, declared as data.
Checked against the live source, every step reads clean —

| Step | Rows | |
| --- | --- | --- |
| `RUA Party` → **Customer** | 75 | clients and consultants |
| `RUA Party` → **Supplier** | 22 | the same table, filtered the other way |
| `RUA Project` → **Project** | 82 | |
| `RUA Employee` → **Employee** | 71 | HRMS |
| `RUA Quotation` → **Quotation** | 5 | 89 lines, priced by area |
| `RUA LPO` → **Purchase Order** | 21 | 105 lines, with the supplier's part numbers |
| `RUA Invoice` → **Sales Invoice** | 45 | final tax invoices only |
| `RUA Payment` → **Payment Entry** | 152 | submitted; petty cash included, drafts not |
| `RUA Attendance` → **Attendance** | 307 → **20,229** | see below |
| `RUA Document` → **Compliance Document** | 408 | |
| `RUA Letter` → **Correspondence** | 51 | |

**Attendance is the interesting one.** They keep a month of it as one row per
*day* holding a JSON object keyed by employee, which is what a system with no
reporting looks like from the inside: nobody can ask how many days somebody
worked in March, because the answer is inside thirty-one blobs. So the engine
grew a `fan_out` — one source row becoming several records, each with its own
identity — and those 307 rows become 20,229 Attendance rows, which is the shape
every report HRMS ships already expects.

Three booleans (`present`, `late`, `absent`) become one `status` plus a
`late_entry` flag, through a `when` rule: the answer is in none of them
individually, and late is not a status in ERPNext — it is a flag on a day that
was worked, which is what it means here too.

**The lines are the other half.** A quotation without them is not a quotation,
and Frappe's list endpoint does not answer a child table — `fields=["*"]` over
five quotations returns all five with not one line on any of them. So a step
whose map reads child rows reads each of its rows twice: the list for the page
and the watermark, then the document for what is inside it. One request per
row, which is why it happens only where a map says `rows`: it is the difference
between five quotations and twenty thousand attendance records.

Two things about their lines are worth knowing before reading the map.

`amount` on a RUA quotation line is the price of *one piece* and `total` is the
line — the opposite of what both words mean in ERPNext, where `rate` is per
piece and `amount` is the line. Read the wrong way round it multiplies every
quotation by its own quantities, and forty-five of the eighty-nine lines have a
quantity above one.

And their widths and heights are prose: `"200.0 cm"`, because the old form had
one box and no unit. A system that keeps a measurement as a string cannot add
two of them, so a rule may say `"number": true` and the leading number is what
crosses — or nothing, where somebody typed "as drawn". Never zero: a width of
zero is a real width and everything downstream would believe it.

Neither quotation codes (`CW01`) nor LPO part numbers (`M70032-G3`) become
Items. Their quotation codes are per-project labels and their part numbers are
suppliers' own; an Item master built out of either is a catalogue nobody agreed
to maintain. Two non-stock Items carry every line — `RUA-FAB` for fabrication
and installation, `RUA-MAT` for material bought in — and the real code and
description sit on the line, where a person reads them. A proper item master is
a decision for later, and the data to build one from will still be there.

**A rehearsal is the real run inside a transaction that is thrown away.** The
first version validated each document in isolation and called that a rehearsal,
which cannot answer the question that decides a migration: does this link point
at something? Nothing an earlier step would have made exists to point at, so
every step after the first reported failures only the rehearsal had. Now the
dry run inserts exactly as the real one does — links resolve, controllers run,
the ledger posts — and at the end it is rolled back, with the counts and the
refused rows written again afterwards because the rollback would take those too.

Two consequences worth knowing. A row that will not save is undone to its own
savepoint rather than by rolling back the connection, which is what the code
used to do — and that quietly discarded up to a hundred and ninety-nine records
already counted as created. And a rehearsal cannot undo what happens outside
the database: a controller that enqueues a background job or writes a file has
done it, and the job will look for rows that no longer exist.

**The plan makes what it assumes.** Nine of its maps name a `custom_` field and
one names an Item, and a plan naming a field nothing creates is a plan that
cannot run — `check` says so, which beats silence and still leaves somebody
making nine fields by hand before the button does anything. So the module
declares `FIELDS` and `SEEDS` beside the maps that use them, and installing the
plan creates them. Where the target doctype is absent the field is skipped
rather than fatal: this app installs on benches without ERPNext, and a plan
that cannot be installed there is worse than one that cannot be run there.

**What the first rehearsal against a real ERPNext found.** Eleven steps, and
every one of them wrong in a way no amount of reading would have shown:

* Two steps read one source doctype, and `execute` paired the run's rows with
  the plan's *by name* — so the Customer step never ran at all. Seventy-five
  customers, reported Done.
* Every party's emirate went into `territory`, and Abu Dhabi is not a Territory
  on a new site. Every designation, gender and branch the same. They are small
  closed vocabularies — fourteen job titles, two emirates, three branches — so
  a rule may now say `"into": "Designation"` and the record is made where it is
  missing. Deliberately per-rule: the same mechanism pointed at a quotation's
  line codes would invent an item master out of a year of typing.
* Company setup makes one Fiscal Year and their books start in 2023, so every
  document outside the current year was refused — most of them.
* ERPNext's Quotation has no `project`. A Sales Order has one, a Sales Invoice
  has one, and a quotation is meant to reach one through the other; every
  quotation these people write is against a project, so it gets a field.
* Their invoice has no lines at all — a progress invoice is one number against
  a contract — and ERPNext will not post one without them. A `rows` rule may
  now say `__self` and build one line out of the header.
* `taxes_and_charges` fills the tax table in the browser and not on the server,
  so an invoice imported with only the template named carries no VAT. The 5%
  row is a constant on the step.
* A Payment Entry needs the two accounts it moves between, and the old system
  records none — only an amount. They are the company's own defaults, which is
  an assumption stated in the plan rather than a fact from the source, and the
  one an accountant reclassifies from.

What is left is four purchase orders with no lines on them in the source. An
order with nothing on it is not an order, and ERPNext is right to refuse it.

A Proforma does not cross: it is not a receivable, and posting one is how a set
of books stops reconciling.

Order is the plan author's to get right; the check refuses a link that resolves
against a step running later, rather than letting the run discover it one row at
a time.

Two things to decide before the first row moves: what an opening balance looks
like (63 invoices and 155 payments with no ledger behind them have to land as
something), and whether history moves at all or only open work does.
