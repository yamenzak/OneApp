"""RUA Contracting — aluminium, glass and cladding, in Abu Dhabi.

Read `docs/RUA.md` first: it is the argument, and this is the half a machine
reads. Its companion is `oneapp/oneapp_core/plans/rua.py`, which brings their
four years of records across; between them they are the whole delivery.

Everything here is over a doctype ERPNext, HRMS or OneSpace already ships. That
is the point of the move: a party becomes a Customer, an LPO becomes a Purchase
Order, and twenty-six bespoke doctypes stop being anybody's code to maintain.
What is bespoke is the *vocabulary* — they say LPO and not Purchase Order, and
a screen that calls it the other thing is a screen they have to translate every
time they read it.

**Restricted**, because it is one company's system. It is granted to their
workspace and appears in nobody else's launcher.
"""

import json

SPACE = {
	"space_code": "rua",
	"space_label": "RUA",
	"module": "Rua",
	"role_name": "OneSpace Rua",
	"icon": "lucide-hard-hat",
	"sort_order": 20,
	"availability": "Restricted",
	"description": "Projects, quotations, LPOs, invoices and the people on site.",
}

# What the space may reach. Three jobs off one list — the DocPerms written for
# its role, what the entitlement grants, and the allowlist a workspace's own
# custom role draws from — so a doctype missing here is reachable by nobody.
#
# `Manage` where a doctype is submittable, because submitting an invoice is the
# point of having one. `Read` for the masters a screen only ever resolves a link
# against: a person picking a customer does not need permission to invent an
# Item or move a Territory.
DOCTYPES = [
	("Project", "Manage", 0),
	("Quotation", "Manage", 0),
	("Purchase Order", "Manage", 0),
	("Sales Invoice", "Manage", 0),
	("Payment Entry", "Manage", 0),
	("Customer", "Write", 0),
	("Supplier", "Write", 0),
	("Employee", "Write", 0),
	("Attendance", "Manage", 0),
	("Compliance Document", "Manage", 0),
	("Correspondence", "Manage", 0),
	# Read only, and every one of them is something a screen resolves rather
	# than something a person edits here.
	("Item", "Read", 0),
	("Company", "Read", 0),
	("Territory", "Read", 0),
	("Customer Group", "Read", 0),
	("Supplier Group", "Read", 0),
	("Designation", "Read", 0),
	("Branch", "Read", 0),
	("Department", "Read", 0),
	("Account", "Read", 0),
	("Cost Center", "Read", 0),
	("Mode of Payment", "Read", 0),
	("UOM", "Read", 0),
	("Currency", "Read", 0),
	("Fiscal Year", "Read", 0),
	("Address", "Write", 0),
	("Contact", "Write", 0),
]

SCREENS = [
	{
		# The spine. Everything else in this space hangs off a project, and it
		# is the first thing anybody opens.
		"screen": "projects", "label": "Projects", "singular": "Project",
		"icon": "lucide-hard-hat", "document_type": "Project",
		"fields": "project_name,custom_stage,customer,estimated_costing,"
		          "percent_complete,custom_location",
		"order_by": "modified desc",
		"view_types": "list,board,dashboard",
		# Opening a project is not opening a form. It is a building, a contract
		# value, a percentage done, the variation orders hanging off it and
		# every quotation, LPO, invoice and payment written against it — see
		# `oneapp_core/showcase.py`. The hero is what is filed against the
		# record, which for these people is the architect's perspectives.
		"view_settings": json.dumps({"showcase": {
			"images": True,
			"eyebrow_field": "custom_location",
			"badge_field": "custom_stage",
			"facts": [
				{"field": "estimated_costing", "label": "Contract"},
				{"field": "percent_complete", "label": "Complete"},
				{"field": "customer", "label": "Client"},
			],
			# Their variation orders. Thirty-five of eighty-two projects are
			# one, and until now the only way to see which belonged to what was
			# to read the titles.
			"children": {"screen": "projects", "field": "custom_parent_project",
			             "label": "Variations", "icon": "lucide-git-branch"},
			# Each names a screen in this space and the field on it pointing
			# back here. The browser then asks the ordinary list endpoint with
			# that filter, so the columns are the ones that screen already
			# shows and the permissions are the ones it already checks.
			"tabs": [
				{"screen": "quotations", "field": "custom_project",
				 "label": "Quotations", "icon": "lucide-file-text"},
				{"screen": "lpos", "field": "project",
				 "label": "LPOs", "icon": "lucide-shopping-cart"},
				{"screen": "invoices", "field": "project",
				 "label": "Invoices", "icon": "lucide-receipt"},
				{"screen": "payments", "field": "project",
				 "label": "Payments", "icon": "lucide-banknote"},
			],
		}}),
		# Their own five words, not ERPNext's three. `custom_stage` is the
		# distinction the people using this actually make — Tender and Job in
		# Hand are both Open to a ledger and a world apart to a sales team.
		"status_field": "custom_stage",
	},
	{
		"screen": "quotations", "label": "Quotations", "singular": "Quotation",
		"icon": "lucide-file-text", "document_type": "Quotation",
		"fields": "party_name,custom_project,transaction_date,grand_total,status",
		"order_by": "transaction_date desc",
		"view_types": "list,board",
		"status_field": "status",
	},
	{
		# Their word. ERPNext calls it a Purchase Order and every person in
		# this company calls it an LPO, and the screen is for the people.
		"screen": "lpos", "label": "LPOs", "singular": "LPO",
		"icon": "lucide-shopping-cart", "document_type": "Purchase Order",
		"fields": "supplier,custom_supplier_reference,project,transaction_date,"
		          "grand_total,status",
		"order_by": "transaction_date desc",
		"view_types": "list,board",
		"status_field": "status",
	},
	{
		"screen": "invoices", "label": "Invoices", "singular": "Invoice",
		"icon": "lucide-receipt", "document_type": "Sales Invoice",
		"fields": "customer,project,custom_project_serial,posting_date,"
		          "grand_total,outstanding_amount,status",
		"order_by": "posting_date desc",
		"view_types": "list,dashboard",
		"status_field": "status",
	},
	{
		"screen": "payments", "label": "Payments", "singular": "Payment",
		"icon": "lucide-banknote", "document_type": "Payment Entry",
		"fields": "party,payment_type,posting_date,paid_amount,reference_no,project",
		"order_by": "posting_date desc",
		"view_types": "list,dashboard",
		"status_field": "status",
	},
	{
		# Clients and consultants both — a consultant is a customer nobody
		# invoices, which is a group and not a doctype.
		"screen": "clients", "label": "Clients", "singular": "Client",
		"icon": "lucide-building-2", "document_type": "Customer",
		"fields": "customer_name,customer_group,territory,mobile_no,tax_id",
		"order_by": "customer_name asc",
		"view_types": "list",
	},
	{
		"screen": "suppliers", "label": "Suppliers", "singular": "Supplier",
		"icon": "lucide-truck", "document_type": "Supplier",
		"fields": "supplier_name,supplier_group,mobile_no,tax_id",
		"order_by": "supplier_name asc",
		"view_types": "list",
	},
	{
		"screen": "team", "label": "Team", "singular": "Employee",
		"icon": "lucide-users", "document_type": "Employee",
		"fields": "employee_name,designation,branch,custom_nationality,"
		          "date_of_joining,status",
		"order_by": "employee_name asc",
		# Grid first: Employee has an image field, so its grid is a wall of
		# faces — which is how anybody actually finds a person on site.
		"view_types": "grid,list",
		"status_field": "status",
	},
	{
		# Twenty thousand rows and climbing, which is the whole reason it is a
		# screen: in the system this replaces the answer to "how many days did
		# he work in March" was inside thirty-one JSON blobs.
		"screen": "attendance", "label": "Attendance", "singular": "Day",
		"icon": "lucide-calendar-check", "document_type": "Attendance",
		"fields": "employee_name,attendance_date,status,late_entry,"
		          "custom_overtime_hours",
		"order_by": "attendance_date desc",
		"view_types": "list,dashboard",
		"status_field": "status",
	},
	{
		# The two registers OneSpace ships itself. A licence that expires and a
		# letter that has to be numbered are what a company *is*, and neither
		# is anybody's customer data.
		"screen": "compliance", "label": "Compliance", "singular": "Document",
		"icon": "lucide-shield", "document_type": "Compliance Document",
		"fields": "title,category,document_number,expiry_date,status,issued_by",
		# Most urgent first, and by status rather than by date: SQL sorts a null
		# expiry above every real one, so a register ordered by date leads with
		# the papers that never expire. The four statuses are *named* so their
		# alphabetical order is their urgency order.
		"order_by": "status asc, expiry_date asc",
		"view_types": "list,board",
		"status_field": "status",
	},
	{
		"screen": "correspondence", "label": "Correspondence", "singular": "Letter",
		"icon": "lucide-mail", "document_type": "Correspondence",
		"fields": "kind,subject,to_party,letter_date,status",
		"order_by": "creation desc",
		"view_types": "list",
		"status_field": "status",
	},
]
