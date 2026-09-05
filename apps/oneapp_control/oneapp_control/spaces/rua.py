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
	# Every doctype below is ERPNext's or HRMS's — a project, a quotation, an
	# LPO, an attendance row — so a site without them is a site where this
	# space's every screen is empty. Declared, so a grant onto a bench that
	# cannot carry them is refused with the app named rather than succeeding
	# into that.
	"requires_apps": "erpnext,hrms",
	"icon": "lucide-briefcase",
	"sort_order": 20,
	"availability": "Restricted",
	"description": "Projects, quotations, LPOs, invoices and the people on site.",
	# What this space looks like, in four words. See `oneapp_core/theming.py`
	# for the vocabulary and `lib/theme.js` for what each word moves.
	#
	# Dark, because the thing they open first is a photograph of a building and
	# a hero over a white page is a picture in a frame rather than a place. A
	# ground of near-black rather than frappe-ui's own dark grey, so the hero
	# has nowhere to end.
	#
	# The accent is **Caterpillar yellow**, and it is the right one for a reason
	# better than taste: it is the colour of the plant on their own sites, so it
	# is already what "this is ours" looks like to the people who will use this.
	# Red was a placeholder borrowed from a streaming service and read as one.
	#
	# Yellow is also the colour that proved the accent needed to carry its own
	# ink. `--surface-gray-10` is the solid button and frappe-ui puts
	# `--ink-base` on it, which in dark mode is near-black — right on red, and a
	# label you cannot read on `#ffcd11`. The browser now decides that from the
	# accent's luminance rather than a space declaring it, so the next space to
	# pick a bright colour does not discover this the way we did.
	#
	# Soft rather than sharp. The first pass reasoned from the product — glass
	# and aluminium facades, so hard corners — and that is a nice sentence about
	# a screen nobody enjoyed using: a hundred square-cornered boxes on black is
	# a spreadsheet, not a place. The photographs carry the hardness.
	#
	# None of it is code. Any other space says four different words and gets its
	# own personality out of the same components.
	"theme": json.dumps({
		"mode": "dark",
		"accent": "#ffcd11",
		"ground": "#0d0d0f",
		"radius": "soft",
	}),
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
	# On every invoice and LPO line, because ERPNext puts it there. Read only —
	# nobody in this company is moving stock — but without it the line's own
	# picker is refused and the field reads as broken on a document they open
	# every day.
	("Warehouse", "Read", 0),
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


# --------------------------------------------------------------------------- #
# The schema its screens read
#
# Every one is a real distinction their old system kept and ERPNext has no
# column for — a project's Tender/Job in Hand stage, an invoice's retention
# percentage, their own per-project invoice serial. None is a field ERPNext
# already has under another name; those are mapped rather than added.
#
# Declared here rather than in the import plan, which is where they lived until
# now. A field the screens read is part of what the space *is*: a workspace
# granted RUA who never imports anything still opens a project and still needs
# somewhere for its stage to be. The tenant sync applies these the first time it
# sees them and never again, exactly as it does a naming series — a Custom Field
# is the same kind of thing, something we give a workspace somewhere to start
# and then stop touching.
#
# `oneapp/oneapp_core/plans/rua.py` maps into them and creates none of them.
# --------------------------------------------------------------------------- #

# Their five project states, in their words. `PROJECT_STATUS` in the plan maps
# these onto ERPNext's three, and `tests/test_manifests.py` holds the two lists
# to each other — they are one vocabulary in two apps and there is no import
# that can join them.
STAGES = [
	"Tender",
	"Job in Hand",
	"In Progress",
	"Completed",
	"Cancelled",
]

CUSTOM_FIELDS = [
	{"dt": "Project", "fieldname": "custom_stage", "label": "Stage", "fieldtype": "Select",
	 "options": "\n" + "\n".join(STAGES), "insert_after": "status",
	 "description": "Their own five states. Tender and Job in Hand are both "
	                "Open to a project ledger and a real difference to a sales "
	                "team."},
	{"dt": "Project", "fieldname": "custom_location", "label": "Location", "fieldtype": "Data",
	 "insert_after": "custom_stage"},
	{"dt": "Project", "fieldname": "custom_parent_project", "label": "Variation of",
	 "fieldtype": "Link", "options": "Project", "insert_after": "custom_location",
	 "description": "The job this one is a variation order on. Thirty-five of "
	                "theirs are, under thirteen parents."},
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
	 "description": "Held back until the defects period ends. A percentage here "
	                "deducts itself from the invoice and waits in Retention "
	                "Receivable — see `oneapp_core/retention.py`. Zero on every "
	                "invoice the old system ever issued."},
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

SCREENS = [
	{
		# The spine. Everything else in this space hangs off a project, and it
		# is the first thing anybody opens.
		"screen": "projects", "label": "Projects", "singular": "Project",
		"icon": "lucide-briefcase", "document_type": "Project",
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
			             "label": "Variations", "icon": "lucide-wrench"},
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
				 "label": "Payments", "icon": "lucide-wallet"},
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
		"icon": "lucide-wallet", "document_type": "Payment Entry",
		"fields": "party,payment_type,posting_date,paid_amount,reference_no,project",
		"order_by": "posting_date desc",
		"view_types": "list,dashboard",
		"status_field": "status",
	},
	{
		# Clients and consultants both — a consultant is a customer nobody
		# invoices, which is a group and not a doctype.
		"screen": "clients", "label": "Clients", "singular": "Client",
		"icon": "lucide-users", "document_type": "Customer",
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
		"icon": "lucide-user-round", "document_type": "Employee",
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
		"icon": "lucide-clock", "document_type": "Attendance",
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
