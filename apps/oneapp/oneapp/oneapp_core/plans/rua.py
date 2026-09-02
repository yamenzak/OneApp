"""RUA Contracting, off their own Frappe site and onto ERPNext and HRMS.

An aluminium, glass and cladding contractor in Abu Dhabi, running twenty-six
bespoke doctypes on plain Frappe with no ledger behind any of it. The whole
point of the move is that most of this stops being anybody's custom code: a
party becomes a Customer, an LPO becomes a Purchase Order, and a row with an
amount on it becomes a Payment Entry with double entry underneath.

Read `docs/RUA.md` first — it is the argument. This is the machine-readable
half of it.

## What is deliberately not here

* **`RUA Issue`, `RUA Remote Issue`, `RUA App Update`.** A developer's own bug
  tracker and changelog, not the customer's system.
* **`RUA Inventory Item`, `RUA Payslip`.** Zero rows apiece. Never used, and
  importing an empty table is how a schema nobody wanted arrives anyway.
* **`RUA Chat`.** 58 messages that belong on the project's timeline as
  Comments, which is a different write from a document insert.

## The order

Dependency order, and the engine does not sort it: parties before the projects
that reference them, projects before everything that hangs off one. A link
resolved against a step that runs later finds nothing on every row — which
`importer.check` refuses before the run rather than discovering during it.
"""

PLAN = "RUA — from the old system"
SPACE = "rua"

# UAE VAT, and the company these all belong to. Constants rather than fields
# because the source has one company and one tax rate and says neither.
COMPANY = "RUA Contracting"

# Their party types, onto ERPNext's groups. A consultant is a Customer nobody
# invoices — the architect who approves the work — so it is a group and not a
# doctype, which is the whole reason `type` maps rather than branches.
CUSTOMER_GROUPS = {
	"Client": "Commercial",
	"Consultant": "Commercial",
}

SUPPLIER_GROUPS = {
	"Supplier": "Local",
	"Supplier: Glass": "Local",
	"Supplier: Aluminum": "Local",
	"Supplier: Cladding": "Local",
}

# Their five project states onto ERPNext's three. Tender and Job in Hand are
# both "not started" to a project ledger, and the difference between them is a
# CRM stage rather than a project one — which is why it also travels as a
# custom field rather than being thrown away.
# Their payment types onto ERPNext's two directions. `Pay: Petty Cash` is a
# supplier payment like any other — see `mode_of_payment` on the step — and
# `Salary` never appears on the live site, so it is not invented here.
PAYMENT_TYPES = {
	"Receive": "Receive",
	"Pay": "Pay",
	"Pay: Petty Cash": "Pay",
}

# Which side of the ledger the party sits on, read off the same column.
PAYMENT_PARTIES = {
	"Receive": "Customer",
	"Pay": "Supplier",
	"Pay: Petty Cash": "Supplier",
}

PAYMENT_MODES = {"Pay: Petty Cash": "Cash"}

# The two non-stock Items every line hangs off. Not one Item per line code:
# their quotation codes (`CW01`) are per-project labels and their LPO codes are
# suppliers' part numbers, and an Item master built out of either is a
# catalogue nobody agreed to maintain. The code and the description travel on
# the line, where a person reads them.
FABRICATION = "RUA-FAB"
MATERIAL = "RUA-MAT"

# The accounts, by the names ERPNext's own UAE chart of accounts gives them
# once a company with this abbreviation exists. Named here rather than looked
# up because a field map is data: `books` makes the company, the chart makes
# these, and the plan is checked against a site that has both.
#
# The old system records no account against a payment at all — only an amount —
# so cash is an assumption and not a fact. It is the company's own default and
# the one an accountant reclassifies from; the alternative is refusing every
# payment for want of a field nobody ever filled in.
ABBR = "RUA"
CASH = f"1110 - Cash - {ABBR}"
DEBTORS = f"1310 - Debtors - {ABBR}"
CREDITORS = f"2110 - Creditors - {ABBR}"
VAT = f"VAT 5% - {ABBR}"

# 5% on the net, which is the UAE rate and what every one of their invoices
# already works out by hand. As a constant row rather than a template name:
# `taxes_and_charges` fills the table in the browser and not on the server, so
# an invoice imported with only the template named carries no tax at all.
VAT_ROW = [{
	"charge_type": "On Net Total",
	"account_head": VAT,
	"description": "VAT 5%",
	"rate": 5,
}]

PROJECT_STATUS = {
	"Tender": "Open",
	"Job in Hand": "Open",
	"In Progress": "Open",
	"Completed": "Completed",
	"Cancelled": "Cancelled",
}

# --------------------------------------------------------------------------- #
# What has to exist before the first row can land
#
# Nine of the field maps below name a `custom_` field, and a plan that names a
# field nothing creates is a plan that cannot run: `check` reports it, which is
# better than silence and still leaves somebody to make nine fields by hand.
# So the plan declares them, and installing the plan makes them.
#
# Every one is a real distinction their old system kept and ERPNext has no
# column for — a project's Tender/Job in Hand stage, an invoice's retention
# percentage, their own per-project invoice serial. None is a field ERPNext
# already has under another name; those are mapped rather than added.
# --------------------------------------------------------------------------- #

FIELDS = [
	{"dt": "Project", "fieldname": "custom_stage", "label": "Stage", "fieldtype": "Select",
	 "options": "\n" + "\n".join(PROJECT_STATUS), "insert_after": "status",
	 "description": "Their own five states. Tender and Job in Hand are both "
	                "Open to a project ledger and a real difference to a sales "
	                "team."},
	{"dt": "Project", "fieldname": "custom_location", "label": "Location", "fieldtype": "Data",
	 "insert_after": "custom_stage"},
	{"dt": "Employee", "fieldname": "custom_nationality", "label": "Nationality",
	 "fieldtype": "Data", "insert_after": "date_of_birth"},
	# ERPNext's Quotation has no project — a Sales Order does, a Sales Invoice
	# does, and a quotation is meant to reach one through the other. Every
	# quotation these people write is against a project and they will look for
	# it by that, so it gets one.
	{"dt": "Quotation", "fieldname": "custom_project", "label": "Project",
	 "fieldtype": "Link", "options": "Project", "insert_after": "party_name"},
	{"dt": "Quotation Item", "fieldname": "custom_width_cm", "label": "Width (cm)",
	 "fieldtype": "Float", "insert_after": "qty"},
	{"dt": "Quotation Item", "fieldname": "custom_height_cm", "label": "Height (cm)",
	 "fieldtype": "Float", "insert_after": "custom_width_cm"},
	{"dt": "Purchase Order", "fieldname": "custom_supplier_reference",
	 "label": "Supplier reference", "fieldtype": "Data", "insert_after": "supplier_name",
	 "description": "The number the supplier quotes back at you on the phone."},
	{"dt": "Sales Invoice", "fieldname": "custom_retention_percentage",
	 "label": "Retention %", "fieldtype": "Percent", "insert_after": "project",
	 "description": "Held back until the defects period ends. ERPNext does not "
	                "model retention — see docs/RUA.md §3."},
	{"dt": "Sales Invoice", "fieldname": "custom_legacy_number", "label": "Old number",
	 "fieldtype": "Data", "read_only": 1, "insert_after": "custom_retention_percentage",
	 "description": "What this invoice was called in the system it came from. "
	                "Somebody will look for it by that number for years."},
	{"dt": "Sales Invoice", "fieldname": "custom_project_serial", "label": "Project serial",
	 "fieldtype": "Int", "insert_after": "custom_legacy_number",
	 "description": "Their per-project sequence for final tax invoices. Frappe's "
	                "naming series is global, so this cannot be the id."},
	{"dt": "Attendance", "fieldname": "custom_overtime_hours", "label": "Overtime hours",
	 "fieldtype": "Float", "insert_after": "late_entry"},
]

# Records the plan writes against, made once. The two Items are the whole of
# it: everything else — the Company, the customer and supplier groups, the
# territory — is either already on an ERPNext site or is the company setup this
# workspace does on its own.
SEEDS = [
	# Their books start in 2023 and their newest purchase order is dated 2026.
	# ERPNext refuses to post a document into a year it has no Fiscal Year for,
	# and company setup makes exactly one — so without these, every invoice and
	# every purchase order outside the current year is refused, which is most
	# of them.
	*(
		{"doctype": "Fiscal Year", "year": str(year),
		 "year_start_date": f"{year}-01-01", "year_end_date": f"{year}-12-31"}
		for year in range(2023, 2027)
	),
	{"doctype": "Item", "item_code": FABRICATION,
	 "item_name": "Fabrication and installation", "item_group": "Services",
	 "stock_uom": "Nos", "is_stock_item": 0,
	 "description": "Aluminium, glass and cladding work, priced per the line."},
	{"doctype": "Item", "item_code": MATERIAL,
	 "item_name": "Purchased material", "item_group": "Services",
	 "stock_uom": "Nos", "is_stock_item": 0,
	 "description": "Profiles, glass and hardware bought in. The supplier's own "
	                "part number is on the line."},
]

STEPS = [
	{
		"source": "RUA Party",
		"target": "Customer",
		"why": "Clients and consultants. Suppliers come across in the next step.",
		"filters": [["RUA Party", "type", "in", list(CUSTOMER_GROUPS)]],
		"map": {
			"customer_name": {"from": "party"},
			"customer_type": {"const": "Company"},
			"customer_group": {"from": "type", "values": CUSTOMER_GROUPS,
			                   "default": "All Customer Groups"},
			# The emirates are territories — seven of them, and this company
			# works in two. `into` makes the record where it is missing rather
			# than flattening every customer into "All Territories", which is
			# what a sales report by region needs.
			"territory": {"from": "emirate", "default": "All Territories",
			              "into": "Territory",
			              "with": {"parent_territory": "All Territories", "is_group": 0}},
			# The TRN. ERPNext's own field for a tax registration number, which
			# is what makes a compliant tax invoice possible at all.
			"tax_id": {"from": "trn"},
			"mobile_no": {"from": "phone"},
			"email_id": {"from": "email"},
		},
	},
	{
		"source": "RUA Party",
		"target": "Supplier",
		"why": "The same table again, filtered the other way. Glass, aluminium "
		       "and cladding are supplier groups, not four kinds of party.",
		"filters": [["RUA Party", "type", "in", list(SUPPLIER_GROUPS)]],
		"map": {
			"supplier_name": {"from": "party"},
			"supplier_type": {"const": "Company"},
			"supplier_group": {"from": "type", "values": SUPPLIER_GROUPS,
			                   "default": "All Supplier Groups"},
			"country": {"const": "United Arab Emirates"},
			"tax_id": {"from": "trn"},
			"mobile_no": {"from": "phone"},
			"email_id": {"from": "email"},
		},
	},
	{
		"source": "RUA Project",
		"target": "Project",
		"why": "Contract value and the parent/child pair, which is a variation "
		       "order rather than a flag.",
		"map": {
			"project_name": {"from": "project_name"},
			"company": {"const": COMPANY},
			"status": {"from": "status", "values": PROJECT_STATUS, "default": "Open"},
			"percent_complete_method": {"const": "Manual"},
			"percent_complete": {"from": "completion"},
			"estimated_costing": {"from": "contract_value"},
			"notes": {"from": "description"},
			# Their own five-state word, kept: "Tender" and "Job in Hand" are a
			# real distinction to the people using this and ERPNext has nowhere
			# for it. A custom field on Project, not a second status.
			"custom_stage": {"from": "status"},
			"custom_location": {"from": "location"},
		},
	},
	{
		"source": "RUA Employee",
		"target": "Employee",
		"why": "HRMS. `basic` and `allowance` become a Salary Structure, which "
		       "is a later step and not a field map.",
		"map": {
			"employee_name": {"from": "employee_name"},
			"first_name": {"from": "employee_name"},
			"company": {"const": COMPANY},
			"gender": {"from": "gender", "default": "Prefer not to say", "into": "Gender"},
			"date_of_birth": {"from": "date_of_birth"},
			# Two of the seventy-one have none, and ERPNext requires one. The
			# creation date is when the record was made rather than when the
			# person started, which is wrong by however long the old system
			# lagged — and is the only date the source has.
			"date_of_joining": {"from": "joining_date", "default_from": "creation"},
			# Fourteen job titles, kept as free text over there and as records
			# here. Small and closed, which is the whole test for `into`.
			"designation": {"from": "position", "into": "Designation"},
			"branch": {"from": "branch", "into": "Branch"},
			"cell_number": {"from": "phone"},
			"personal_email": {"from": "email"},
			"status": {"const": "Active"},
			"custom_nationality": {"from": "nationality"},
		},
	},
	{
		"source": "RUA Quotation",
		"target": "Quotation",
		"why": "Priced by area, and every line of it comes across.",
		"map": {
			"party_name": {"from": "party", "link": "RUA Party"},
			"quotation_to": {"const": "Customer"},
			"company": {"const": COMPANY},
			"transaction_date": {"from": "date"},
			"custom_project": {"from": "project", "link": "RUA Project"},
			"terms": {"from": "terms_and_conditions"},
			# The lines. `amount` on their row is the price of one piece and
			# `total` is the line — which is the opposite of what both words
			# mean in ERPNext, where `rate` is per piece and `amount` is the
			# line. Read the wrong way round it multiplies every quotation by
			# its own quantities.
			"items": {
				"rows": "items",
				"map": {
					"item_code": {"const": FABRICATION},
					"item_name": {"from": "item_name"},
					"description": {"from": "description"},
					"qty": {"from": "qty"},
					"rate": {"from": "amount"},
					# Their width and height are prose — `"200.0 cm"` — because
					# the old form had one box and no unit. As numbers they can
					# be added, and an area is a quotation's real quantity.
					"custom_width_cm": {"from": "width", "number": True},
					"custom_height_cm": {"from": "height", "number": True},
				},
			},
		},
	},
	{
		"source": "RUA LPO",
		"target": "Purchase Order",
		"why": "Their purchase order, under its real name — and with the "
		       "supplier's own part numbers on it.",
		"map": {
			"supplier": {"from": "party", "link": "RUA Party"},
			"company": {"const": COMPANY},
			"transaction_date": {"from": "date"},
			"project": {"from": "project", "link": "RUA Project"},
			"custom_supplier_reference": {"from": "supplier_reference_number"},
			# Required by ERPNext and absent from theirs — a purchase order
			# with no date wanted is a purchase order nobody can chase. The
			# order's own date is the honest stand-in: it is not a promise
			# anybody made, and inventing a lead time would be.
			"schedule_date": {"from": "date"},
			# Real part numbers — `M70032-G3` is an Alumil profile — and they
			# stay in `item_name` rather than becoming `item_code`: an Item per
			# code is an item master, and building one out of purchase history
			# invents a catalogue nobody agreed to. The code is on the line
			# where a buyer reads it, and the master is a decision for later.
			"items": {
				"rows": "items",
				"map": {
					"item_code": {"const": MATERIAL},
					"item_name": {"from": "item"},
					"description": {"from": "item"},
					"qty": {"from": "qty"},
					"rate": {"from": "unit_price"},
					"received_qty": {"from": "received_quantity"},
				},
			},
		},
	},
	{
		"source": "RUA Invoice",
		"target": "Sales Invoice",
		"why": "Tax invoices only. A Proforma is not a receivable and posting "
		       "one to the ledger is how a set of books stops reconciling.",
		"filters": [["RUA Invoice", "type", "=", "Tax Invoice"],
		            ["RUA Invoice", "status", "=", "Final"]],
		"map": {
			"customer": {"from": "party", "link": "RUA Party"},
			"company": {"const": COMPANY},
			"posting_date": {"from": "date"},
			"project": {"from": "project", "link": "RUA Project"},
			"remarks": {"from": "remarks"},
			# Retention is the one thing ERPNext does not model. It rides across
			# as a field so nothing is lost, and becomes a deduction against a
			# Retention Receivable account in the step that follows — which is
			# the decision `docs/RUA.md` §3 says wants an accountant first.
			"custom_retention_percentage": {"from": "retention_percentage"},
			"custom_legacy_number": {"from": "name"},
			# Their per-project sequence for final tax invoices. Frappe's naming
			# series is global, so this cannot be the id and is kept beside it.
			"custom_project_serial": {"from": "serial_number"},
			# Their invoice has no lines at all — the amount is a header field,
			# because a progress invoice is one number against a contract. So
			# it becomes one line, and the description is what the invoice is
			# for rather than a part number.
			"items": {
				"rows": "__self",
				"map": {
					"item_code": {"const": FABRICATION},
					"description": {"const": "Work executed to date"},
					"qty": {"const": 1},
					"rate": {"from": "amount"},
				},
			},
			"taxes": {"const": VAT_ROW},
		},
	},
	{
		"source": "RUA Payment",
		"target": "Payment Entry",
		"why": "The change that buys them a ledger: today a payment is a row "
		       "with an amount and nothing behind it.",
		"filters": [["RUA Payment", "status", "=", "Submitted"],
		            ["RUA Payment", "type", "in", list(PAYMENT_TYPES)]],
		"map": {
			"payment_type": {"from": "type", "values": PAYMENT_TYPES},
			# Not a constant. Every Receive on the live site points at a client
			# or a consultant and every Pay at a supplier, so the party's side
			# of the ledger is what `type` has been saying all along — and a
			# supplier payment posted against a customer is the kind of wrong
			# that balances and still means nothing.
			"party_type": {"from": "type", "values": PAYMENT_PARTIES},
			"party": {"from": "party", "link": "RUA Party"},
			"company": {"const": COMPANY},
			"posting_date": {"from": "date"},
			"paid_amount": {"from": "amount"},
			"received_amount": {"from": "amount"},
			"reference_no": {"from": "ref_number"},
			"reference_date": {"from": "date"},
			"project": {"from": "project", "link": "RUA Project"},
			"remarks": {"from": "remarks"},
			# Petty cash is not a different kind of transaction, whatever the
			# old system's type list implies — it is a supplier payment that
			# came out of the cash box. So it stays a Payment Entry and the
			# cash box becomes the mode of payment, which is the field ERPNext
			# keeps that answer in.
			"mode_of_payment": {"from": "type", "values": PAYMENT_MODES, "default": ""},
			# Which account each side moves. ERPNext fills these in the browser
			# from the company's defaults and not on the server, so a payment
			# imported without them is refused for want of an exchange rate it
			# has no currency to look up.
			"paid_from": {"from": "type", "values": {
				"Receive": DEBTORS, "Pay": CASH, "Pay: Petty Cash": CASH}},
			"paid_to": {"from": "type", "values": {
				"Receive": CASH, "Pay": CREDITORS, "Pay: Petty Cash": CREDITORS}},
			# One currency, so one rate. Said rather than left out: without it
			# ERPNext asks, and there is nobody to ask.
			"source_exchange_rate": {"const": 1},
			"target_exchange_rate": {"const": 1},
		},
	},
	{
		"source": "RUA Attendance",
		"target": "Attendance",
		"why": "307 rows becoming about twenty thousand. One row per day "
		       "holding an object keyed by employee is what a system with no "
		       "reporting looks like from the inside — nobody can ask how many "
		       "days somebody worked in March, because the answer is inside "
		       "thirty-one JSON blobs.",
		# The fan-out. Each key of `attendance_log` is an employee id and each
		# value is that employee's day, so one row becomes one Attendance per
		# employee — which is the shape every report HRMS ships expects.
		"fan_out": {"from": "attendance_log", "shape": "map"},
		"map": {
			"employee": {"from": "__key", "link": "RUA Employee"},
			"attendance_date": {"from": "date"},
			"company": {"const": COMPANY},
			# Three booleans where a real system keeps one status, so the answer
			# is in none of them individually. Absent wins where it is set;
			# everything else is a day worked.
			"status": {"when": [["absent", "Absent"]], "default": "Present"},
			# And late is not a status in ERPNext — it is a flag on a day that
			# was worked, which is exactly what it means here too.
			"late_entry": {"from": "late"},
			"custom_overtime_hours": {"from": "overtime"},
		},
	},
	{
		"source": "RUA Document",
		"target": "Compliance Document",
		"why": "The register OneSpace ships. 408 rows of visas, licences and "
		       "insurance that have never warned anybody about anything.",
		"map": {
			"title": {"from": "document_name"},
			"document_number": {"from": "document_number"},
			"issue_date": {"from": "issue_date"},
			"expiry_date": {"from": "expiry_date"},
			"place_of_issue": {"from": "place_of_issue"},
			"file": {"from": "document"},
			"remind_days": {"const": 30},
			"notes": {"from": "tags"},
		},
	},
	{
		"source": "RUA Letter",
		"target": "Correspondence",
		"why": "The other register OneSpace ships. Bilingual, and the only "
		       "thing in this plan that arrives more capable than it left.",
		"map": {
			"kind": {"from": "type", "values": {"LTR": "Letter", "FRM": "Form"},
			         "default": "Letter"},
			"subject": {"from": "subject"},
			"subject_ar": {"from": "subject_ar"},
			"to_party": {"from": "to"},
			"to_party_ar": {"from": "to_ar"},
			"body": {"from": "content"},
			"body_ar": {"from": "content_ar"},
			"letter_date": {"from": "date"},
			"status": {"from": "status", "values": {"Draft": "Draft", "Final": "Issued",
			                                        "Cancelled": "Cancelled"},
			           "default": "Draft"},
			"signed_by": {"from": "signee"},
			"signed_by_title": {"from": "signee_title"},
			"signed_by_ar": {"from": "signee_ar"},
			"signed_by_title_ar": {"from": "signee_title_ar"},
			"is_template": {"from": "is_template"},
			"cancellation_reason": {"from": "cancellation_reason"},
			"issued_file": {"from": "deliverable"},
			"signature": {"from": "signature"},
		},
	},
]
