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
PROJECT_STATUS = {
	"Tender": "Open",
	"Job in Hand": "Open",
	"In Progress": "Open",
	"Completed": "Completed",
	"Cancelled": "Cancelled",
}

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
			"territory": {"from": "emirate", "default": "All Territories"},
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
			"gender": {"from": "gender", "default": "Prefer not to say"},
			"date_of_birth": {"from": "date_of_birth"},
			"date_of_joining": {"from": "joining_date"},
			"designation": {"from": "position"},
			"cell_number": {"from": "phone"},
			"personal_email": {"from": "email"},
			"status": {"const": "Active"},
			"custom_nationality": {"from": "nationality"},
		},
	},
	{
		"source": "RUA Quotation",
		"target": "Quotation",
		"why": "The header only. Items are a child table and need the fan-out "
		       "the engine does not do yet — see docs/RUA.md.",
		"map": {
			"party_name": {"from": "party", "link": "RUA Party"},
			"quotation_to": {"const": "Customer"},
			"company": {"const": COMPANY},
			"transaction_date": {"from": "date"},
			"project": {"from": "project", "link": "RUA Project"},
			"terms": {"from": "terms_and_conditions"},
		},
	},
	{
		"source": "RUA LPO",
		"target": "Purchase Order",
		"why": "Their purchase order, under its real name.",
		"map": {
			"supplier": {"from": "party", "link": "RUA Party"},
			"company": {"const": COMPANY},
			"transaction_date": {"from": "date"},
			"project": {"from": "project", "link": "RUA Project"},
			"custom_supplier_reference": {"from": "supplier_reference_number"},
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
		},
	},
	{
		"source": "RUA Payment",
		"target": "Payment Entry",
		"why": "The change that buys them a ledger: today a payment is a row "
		       "with an amount and nothing behind it.",
		"filters": [["RUA Payment", "status", "=", "Submitted"],
		            ["RUA Payment", "type", "in", ["Pay", "Receive"]]],
		"map": {
			"payment_type": {"from": "type",
			                 "values": {"Receive": "Receive", "Pay": "Pay"}},
			"party_type": {"const": "Customer"},
			"party": {"from": "party", "link": "RUA Party"},
			"company": {"const": COMPANY},
			"posting_date": {"from": "date"},
			"paid_amount": {"from": "amount"},
			"received_amount": {"from": "amount"},
			"reference_no": {"from": "ref_number"},
			"reference_date": {"from": "date"},
			"project": {"from": "project", "link": "RUA Project"},
			"remarks": {"from": "remarks"},
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
