"""OneCRM — leads, the deals they become, and what was quoted against them.

Read `docs/ERP-SPACES.md` first: it is the argument for cutting ERPNext into
three spaces rather than shipping it whole, and this is the second of them.

Over ERPNext's own CRM doctypes, which is the unglamorous right answer: a lead,
an opportunity and a quotation are solved problems, and a second schema for them
would be a second set of rows for the accounting side of the same workspace to
fail to see. What is ours is the presentation and one thing the schema was
missing.

The presentation first. ERPNext's CRM module ships twenty-six doctypes and its
workspace shows most of them, so a salesperson's list of places to go includes
Market Segment and Competitor Detail. Here there are nine places to work and a
Setup heading with six tables under it, and the screens open as the thing they
are: the pipeline is a board of deals by sales stage, the follow-ups are a
calendar of what was promised to whom, the leads are a board of how far each one
got, and each screen carries a dashboard measured over exactly the rows it is
showing.

And the thing that was missing: **a next step**. ERPNext records what a deal is
worth and when it is expected to close, and has nowhere at all to say what
happens next or when. That is the field a salesperson works out of, and without
it the only way to run a week is to open every record in turn. Two fields — see
CUSTOM_FIELDS — and the whole Follow-ups screen falls out of them.

**Generally available.** It says Lead, Deal and Quotation, and it has to survive
people whose sales process is not the first customer's.
"""

import json

SPACE = {
	"space_code": "onecrm",
	"space_label": "OneCRM",
	"module": "OneCRM",
	"role_name": "OneSpace CRM",
	"requires_apps": "erpnext",
	"icon": "lucide-users",
	"sort_order": 50,
	"availability": "Restricted",
	"description": "Leads, deals, quotations and what happens next on each.",
	# Light, and a violet accent so a salesperson moving between this and
	# OneProject knows which application they are in before they read a word.
	"theme": json.dumps({
		"mode": "light",
		"accent": "#6d4aff",
		"radius": "soft",
	}),
}

# --------------------------------------------------------------------------- #
# The two jobs
#
# Somebody *sells* — works leads, moves deals, writes quotations — and somebody
# *runs the desk*, which is the seat that decides what the stages are, who owns
# what, and which deals were lost for which reason.
#
# The split matters more here than anywhere else in this repo, because the
# things a sales manager maintains are the things a pipeline is *measured* by. A
# rep who can edit the sales stages can move a deal to a stage they invented,
# and the forecast quietly stops meaning anything.
# --------------------------------------------------------------------------- #
ROLES = [
	{
		"role_key": "rep",
		"label": "Rep",
		"is_default": 1,
		"description": "Sell: work leads, move deals through the stages, write "
		               "quotations and keep the contacts behind them.",
	},
	{
		"role_key": "manager",
		"label": "Sales manager",
		"description": "Run the desk — the stages, the sources, the territories "
		               "and the lost reasons a pipeline is measured by, plus "
		               "the contracts underneath a won deal.",
	},
]

DOCTYPES = [
	# ----- Everybody ------------------------------------------------------ #
	#
	# The four records selling is actually made of. Not `if_owner`: a desk
	# where a rep cannot see the deal a colleague is covering for them is a
	# desk that loses a deal every time somebody takes a week off.
	("Lead", "Manage", 0),
	("Opportunity", "Manage", 0),
	("Prospect", "Manage", 0),
	("Quotation", "Manage", 0),
	("Contact", "Write", 0),
	("Address", "Write", 0),
	# Booked calls. A rep makes their own and has to be able to close one.
	("Appointment", "Manage", 0),
	# A customer is the other side of a won deal. Write rather than Manage —
	# converting a deal creates one, and deleting a customer is an accounting
	# decision made in an accounting space.
	("Customer", "Write", 0),
	# The masters a screen resolves a link against, and nothing more. Every one
	# of these is something a pipeline is *measured* by, which is why not one
	# of them is writable below this line.
	("Sales Stage", "Read", 0),
	("Opportunity Type", "Read", 0),
	("Opportunity Lost Reason", "Read", 0),
	("UTM Source", "Read", 0),
	("UTM Campaign", "Read", 0),
	("UTM Medium", "Read", 0),
	("Campaign", "Read", 0),
	("Territory", "Read", 0),
	("Customer Group", "Read", 0),
	("Market Segment", "Read", 0),
	("Industry Type", "Read", 0),
	("Salutation", "Read", 0),
	("Gender", "Read", 0),
	("Country", "Read", 0),
	("Currency", "Read", 0),
	("Company", "Read", 0),
	("Price List", "Read", 0),
	("Item", "Read", 0),
	("UOM", "Read", 0),
	("Contract", "Read", 0),
	("Contract Template", "Read", 0),
	("OneSpace Saved View", "Write", 1),

	# ----- Sales manager --------------------------------------------------- #
	("Sales Stage", "Write", 0, "manager"),
	("Opportunity Type", "Write", 0, "manager"),
	("Opportunity Lost Reason", "Write", 0, "manager"),
	("UTM Source", "Write", 0, "manager"),
	("UTM Campaign", "Write", 0, "manager"),
	("UTM Medium", "Write", 0, "manager"),
	("Campaign", "Write", 0, "manager"),
	("Territory", "Write", 0, "manager"),
	("Customer Group", "Write", 0, "manager"),
	("Market Segment", "Write", 0, "manager"),
	("Contract", "Manage", 0, "manager"),
	("Contract Template", "Write", 0, "manager"),
]

# --------------------------------------------------------------------------- #
# The schema its screens read
#
# Two fields on two doctypes, and they are one idea: **what happens next, and
# when**.
#
# ERPNext records a deal's value, its stage, its probability and the date it is
# expected to close, and has nowhere to say that you promised to send a revised
# price on Thursday. Every CRM that people actually use has this field, because
# it is the one a salesperson works out of: a week is a list of next steps
# sorted by date, not a list of deals sorted by value.
#
# The same pair on Lead and on Opportunity, because a lead you are nurturing has
# next steps for months before it becomes a deal, and losing them at the moment
# of conversion is how a qualified lead goes quiet.
#
# Applied by the tenant sync the first time it sees this space and never again.
# --------------------------------------------------------------------------- #
NEXT_STEP = [
	{"fieldname": "custom_next_step", "label": "Next step", "fieldtype": "Data",
	 "description": "What you have said you will do. One line — a whole plan "
	                "belongs in the notes."},
	{"fieldname": "custom_next_step_on", "label": "Next step on",
	 "fieldtype": "Date",
	 "description": "When. The Follow-ups screen is this field sorted "
	                "ascending, so a blank one is a record nothing will remind "
	                "anybody about."},
]

CUSTOM_FIELDS = [
	{**NEXT_STEP[0], "dt": "Lead", "insert_after": "status"},
	{**NEXT_STEP[1], "dt": "Lead", "insert_after": "custom_next_step"},
	{**NEXT_STEP[0], "dt": "Opportunity", "insert_after": "status"},
	{**NEXT_STEP[1], "dt": "Opportunity", "insert_after": "custom_next_step"},
]

SCREENS = [
	{
		# The pipeline. A board of deals by sales stage, which is the one
		# picture a sales meeting is held over and which the desk renders as a
		# list of rows sorted by modification date.
		#
		# The badge and the columns are deliberately two different fields.
		# `status` is what has *happened* to a deal — Open, Quotation,
		# Converted, Lost — and `sales_stage` is how far along it is. The board
		# is drawn by the stage because that is the pipeline; the badge beside
		# each name is the status, because a Lost deal sitting in Negotiation
		# is exactly the row somebody needs to see.
		"screen": "deals", "label": "Deals", "singular": "Deal",
		"icon": "lucide-shopping-cart", "document_type": "Opportunity",
		"fields": "customer_name,sales_stage,opportunity_amount,probability,"
		          "expected_closing,custom_next_step_on,opportunity_owner,status",
		"order_by": "expected_closing asc",
		"view_types": "board,list,dashboard,calendar",
		"status_field": "status",
		"field_icons": json.dumps({
			"status": "lucide-flag",
			"sales_stage": "lucide-chart-line",
			"probability": "lucide-chart-pie",
		}),
		"view_settings": json.dumps({
			"board": {
				"column_field": "sales_stage",
				"card_fields": ["customer_name", "opportunity_amount",
				                "expected_closing"],
			},
			# One date and no span: a deal closes on a day, it does not last
			# from one day to another. So there is no Gantt here on purpose.
			"calendar": {"start_field": "expected_closing"},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Deals", "width": 3},
				{"kind": "number", "label": "Pipeline", "aggregate": "sum",
				 "field": "opportunity_amount", "width": 3},
				{"kind": "number", "label": "Average deal", "aggregate": "avg",
				 "field": "opportunity_amount", "width": 3},
				{"kind": "number", "label": "Average probability",
				 "aggregate": "avg", "field": "probability", "suffix": "%",
				 "width": 3},
				# The funnel is the reason this dashboard exists. Value by
				# stage, narrowing — the shape a forecast has, and the one
				# thing no list of deals can be read as.
				{"kind": "funnel", "label": "Value by stage",
				 "group_by": "sales_stage", "aggregate": "sum",
				 "field": "opportunity_amount", "width": 6},
				{"kind": "donut", "label": "Where each one stands",
				 "group_by": "status", "width": 6},
				{"kind": "bar", "label": "Pipeline by owner",
				 "group_by": "opportunity_owner", "aggregate": "sum",
				 "field": "opportunity_amount", "horizontal": True, "width": 6},
				{"kind": "bar", "label": "By source", "group_by": "utm_source",
				 "horizontal": True, "width": 6},
				{"kind": "line", "label": "Opened by month",
				 "group_by": "transaction_date", "grain": "month", "width": 12},
			]},
			"showcase": {
				"eyebrow_field": "customer_name",
				"badge_field": "sales_stage",
				"facts": [
					{"field": "opportunity_amount", "label": "Value"},
					{"field": "probability", "label": "Probability"},
					{"field": "expected_closing", "label": "Closing"},
					{"field": "custom_next_step", "label": "Next"},
				],
				"tabs": [
					{"screen": "quotations", "field": "opportunity",
					 "label": "Quotations", "icon": "lucide-file-text"},
				],
			},
		}),
	},
	{
		# A week of selling, which is a list of promises in date order and not
		# a list of deals in value order.
		#
		# The same doctype as the screen above with two differences that make it
		# a different place: it is narrowed to the deals still alive, and it is
		# sorted by the date something was promised — so the row at the top is
		# the one that is late. That is why there is no clever filter here and
		# no invented "overdue" vocabulary: ascending *is* overdue-first, and a
		# sort somebody can read is worth more than an operator they cannot.
		"screen": "follow-ups", "label": "Follow-ups", "singular": "Follow-up",
		"icon": "lucide-calendar", "document_type": "Opportunity",
		"fields": "custom_next_step_on,custom_next_step,customer_name,"
		          "sales_stage,opportunity_amount,opportunity_owner,status",
		"order_by": "custom_next_step_on asc",
		"filters": json.dumps({
			"status": ["in", ["Open", "Replied", "Quotation"]],
		}),
		"view_types": "calendar,list,board",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "custom_next_step_on"},
			"board": {
				"column_field": "sales_stage",
				"card_fields": ["custom_next_step", "custom_next_step_on",
				                "customer_name"],
			},
		}),
	},
	{
		# Everything before it is a deal.
		#
		# ERPNext's Lead carries two state fields and they say different things.
		# `status` is nine values long and half of it describes the *deal* the
		# lead turned into — Opportunity, Quotation, Lost Quotation, Converted —
		# so a board drawn by it has four columns that are really about a
		# different record. `qualification_status` is three values and is the
		# actual question a lead sits inside: unqualified, being worked,
		# qualified. So the board is drawn by that and the badge keeps `status`.
		"screen": "leads", "label": "Leads", "singular": "Lead",
		"icon": "lucide-phone", "document_type": "Lead",
		"fields": "lead_name,company_name,qualification_status,status,email_id,"
		          "mobile_no,territory,utm_source,custom_next_step_on",
		"order_by": "modified desc",
		"view_types": "board,list,grid,dashboard",
		"status_field": "status",
		"field_icons": json.dumps({
			"status": "lucide-flag",
			"qualification_status": "lucide-chart-line",
		}),
		"view_settings": json.dumps({
			"board": {
				"column_field": "qualification_status",
				"card_fields": ["company_name", "email_id", "territory"],
			},
			"cards": {"card_fields": ["company_name", "job_title", "territory"]},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Leads", "width": 4},
				{"kind": "number", "label": "Qualified", "width": 4,
				 "filters": {"qualification_status": "Qualified"}},
				{"kind": "number", "label": "Annual revenue represented",
				 "aggregate": "sum", "field": "annual_revenue", "width": 4},
				{"kind": "donut", "label": "How far each one got",
				 "group_by": "qualification_status", "width": 4},
				{"kind": "bar", "label": "By source", "group_by": "utm_source",
				 "width": 4},
				{"kind": "bar", "label": "By territory", "group_by": "territory",
				 "width": 4},
				{"kind": "bar", "label": "By industry", "group_by": "industry",
				 "horizontal": True, "width": 6},
				{"kind": "bar", "label": "By company size",
				 "group_by": "no_of_employees", "width": 6},
			]},
		}),
	},
	{
		# The company behind the people. ERPNext calls it a Prospect, which is
		# a word for a *person* everywhere else in sales, so the screen says
		# Organisation and the doctype keeps its name.
		#
		# A grid first: an organisation is recognised by its name and its size
		# rather than scanned in a column, and the grid is what makes a page of
		# them readable.
		"screen": "organisations", "label": "Organisations",
		"singular": "Organisation",
		"icon": "lucide-store", "document_type": "Prospect",
		"fields": "company_name,industry,territory,no_of_employees,"
		          "annual_revenue,prospect_owner",
		"order_by": "company_name asc",
		"view_types": "grid,list,dashboard",
		"view_settings": json.dumps({
			"cards": {"card_fields": ["industry", "territory", "no_of_employees"]},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Organisations", "width": 4},
				{"kind": "number", "label": "Revenue represented",
				 "aggregate": "sum", "field": "annual_revenue", "width": 4},
				{"kind": "number", "label": "Average revenue", "aggregate": "avg",
				 "field": "annual_revenue", "width": 4},
				{"kind": "bar", "label": "By industry", "group_by": "industry",
				 "horizontal": True, "width": 6},
				{"kind": "donut", "label": "By size",
				 "group_by": "no_of_employees", "width": 6},
				{"kind": "bar", "label": "By territory", "group_by": "territory",
				 "width": 12},
			]},
		}),
	},
	{
		# The people. A grid, because a page of contacts is a page of faces and
		# a name in a column is the one thing nobody recognises.
		"screen": "contacts", "label": "Contacts", "singular": "Contact",
		"icon": "lucide-user-round", "document_type": "Contact",
		"fields": "first_name,last_name,company_name,designation,email_id,"
		          "mobile_no,status",
		"order_by": "first_name asc",
		"view_types": "grid,list",
		"status_field": "status",
		"view_settings": json.dumps({
			"cards": {"card_fields": ["company_name", "designation", "email_id"]},
		}),
	},
	{
		"screen": "quotations", "label": "Quotations", "singular": "Quotation",
		"icon": "lucide-file-text", "document_type": "Quotation",
		"fields": "customer_name,opportunity,transaction_date,valid_till,"
		          "grand_total,status",
		"order_by": "transaction_date desc",
		"view_types": "list,board,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"board": {"card_fields": ["customer_name", "grand_total", "valid_till"]},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Quotations", "width": 4},
				{"kind": "number", "label": "Quoted", "aggregate": "sum",
				 "field": "grand_total", "width": 4},
				{"kind": "number", "label": "Average", "aggregate": "avg",
				 "field": "grand_total", "width": 4},
				{"kind": "donut", "label": "Where each one stands",
				 "group_by": "status", "width": 6},
				{"kind": "bar", "label": "By territory", "group_by": "territory",
				 "aggregate": "sum", "field": "grand_total", "width": 6},
				{"kind": "line", "label": "Quoted by month",
				 "group_by": "transaction_date", "grain": "month",
				 "aggregate": "sum", "field": "grand_total", "width": 12},
			]},
		}),
	},
	{
		# Booked calls, on a calendar, because that is what they are. ERPNext
		# ships the doctype and a portal booking page and no way for the person
		# being booked to see their week.
		"screen": "appointments", "label": "Appointments",
		"singular": "Appointment",
		"icon": "lucide-calendar", "document_type": "Appointment",
		"fields": "customer_name,customer_email,customer_phone_number,"
		          "scheduled_time,status",
		"order_by": "scheduled_time desc",
		"view_types": "calendar,list",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "scheduled_time"},
		}),
	},
	{
		# What a won deal became. Read for a rep and managed by the desk: a
		# contract is the document somebody is held to, and "who may change the
		# dates on it" is not a question a pipeline should be answering.
		"screen": "contracts", "label": "Contracts", "singular": "Contract",
		"icon": "lucide-shield", "document_type": "Contract",
		"fields": "party_name,party_type,start_date,end_date,fulfilment_status,"
		          "status",
		"order_by": "end_date asc",
		"view_types": "list,board,calendar,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"calendar": {"start_field": "start_date", "end_field": "end_date"},
			"board": {"card_fields": ["party_name", "end_date",
			                          "fulfilment_status"]},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Contracts", "width": 4},
				{"kind": "donut", "label": "Signed and not", "group_by": "status",
				 "width": 4},
				{"kind": "donut", "label": "Fulfilment",
				 "group_by": "fulfilment_status", "width": 4},
			]},
		}),
	},
	# ----- Setup ----------------------------------------------------------- #
	#
	# Six tables the pipeline is measured by, under one heading at the end of
	# the rail. Adjacent and last, because the rail draws a heading when the
	# group changes.
	#
	# ERPNext's CRM workspace puts these in among the places you go to work, so
	# a rep's list of destinations contains Market Segment. The measurement
	# vocabulary is the sales manager's job, and this is where saying so costs
	# nothing.
	{
		"screen": "stages", "label": "Sales stages", "singular": "Sales stage",
		"screen_group": "Setup",
		"icon": "lucide-chart-line", "document_type": "Sales Stage",
		"fields": "stage_name",
		"order_by": "stage_name asc",
		"view_types": "list",
	},
	{
		"screen": "deal-types", "label": "Deal types", "singular": "Deal type",
		"screen_group": "Setup",
		"icon": "lucide-layers", "document_type": "Opportunity Type",
		"fields": "name,description",
		"order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "sources", "label": "Sources", "singular": "Source",
		"screen_group": "Setup",
		"icon": "lucide-database", "document_type": "UTM Source",
		"fields": "name,slug,description",
		"order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "campaigns", "label": "Campaigns", "singular": "Campaign",
		"screen_group": "Setup",
		"icon": "lucide-mail", "document_type": "Campaign",
		"fields": "campaign_name,description",
		"order_by": "campaign_name asc",
		"view_types": "list",
	},
	{
		# A tree, because a territory is one — ERPNext nests them and the desk
		# is the only place that has ever shown it.
		"screen": "territories", "label": "Territories", "singular": "Territory",
		"screen_group": "Setup",
		"icon": "lucide-map", "document_type": "Territory",
		"fields": "territory_name,parent_territory,territory_manager,is_group",
		"order_by": "territory_name asc",
		"view_types": "tree,list",
		"view_settings": json.dumps({
			"tree": {"parent_field": "parent_territory",
			         "label_field": "territory_name"},
		}),
	},
	{
		"screen": "lost-reasons", "label": "Lost reasons",
		"singular": "Lost reason", "screen_group": "Setup",
		"icon": "lucide-git-compare",
		"document_type": "Opportunity Lost Reason",
		"fields": "lost_reason",
		"order_by": "lost_reason asc",
		"view_types": "list",
	},
]
