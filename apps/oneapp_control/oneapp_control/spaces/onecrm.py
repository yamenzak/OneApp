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

# The columns a pipeline arrives with — `docs/ONECRM.md` stage 1.
#
# Rows of `One Deal Stage` rather than ERPNext's `Sales Stage`, which is a row
# with a name and nothing else: no order, so a board drawn from it came out
# Negotiation, Prospecting, Proposal; no colour; and no way for the engine to
# ask which column means won. This declares the *defaults* and nothing else —
# the order the board draws is read off the rows, so a workspace that renames a
# stage or moves one does it by editing a row and every board follows.
#
# Seven, not ERPNext's eight, and they are not the same seven. Theirs are the
# stages of an enterprise software sale — Perception Analysis, Identifying
# Decision Makers — and this product has to open sensibly for a plumber and a
# ministry as well. A workspace that wants those eight adds them; a workspace
# that wants three deletes four.
#
# **On hold** is the one worth arguing for. Every desk has deals that are
# neither moving nor lost — the money is not signed off, the building is not
# ready, the person is on leave — and a pipeline without a column for them has
# them sitting in Negotiation making the forecast wrong. Its category is its
# own, so a report can leave it out of both the live pipeline and the losses.
#
#: name, category, probability, colour, position
STAGES = [
	("New", "Open", 10, "gray", 0),
	("Qualifying", "Ongoing", 25, "blue", 1),
	("Proposal", "Ongoing", 50, "violet", 2),
	("Negotiation", "Ongoing", 75, "amber", 3),
	("On hold", "On hold", 0, "orange", 4),
	("Won", "Won", 100, "green", 5),
	("Lost", "Lost", 0, "red", 6),
]

#: Just the names, for the seeds and the guards that compare the two halves.
STAGE_NAMES = [name for name, _c, _p, _colour, _at in STAGES]

SPACE = {
	"space_code": "onecrm",
	"space_label": "OneCRM",
	"module": "OneCRM",
	"role_name": "OneSpace CRM",
	"requires_apps": "erpnext",
	"icon": "lucide-users",
	"brand": "onecrm",
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
	# And calls that actually happened. Manage rather than Write, and not
	# `if_owner`: a call log whose rows a rep cannot correct is a call log they
	# stop writing, and a desk where you cannot see that a colleague already
	# rang this person rings them twice.
	("One Call", "Manage", 0),
	# A customer is the other side of a won deal. Write rather than Manage —
	# converting a deal creates one, and deleting a customer is an accounting
	# decision made in an accounting space.
	("Customer", "Write", 0),
	# The masters a screen resolves a link against, and nothing more. Every one
	# of these is something a pipeline is *measured* by, which is why not one
	# of them is writable below this line.
	# The stages a pipeline is drawn by. Read for a rep and Write for the
	# manager, which is the rule this space is most emphatic about: a rep who
	# can invent a stage can move a deal into one, and the forecast quietly
	# stops meaning anything.
	("One Deal Stage", "Read", 0),
	# The history, which is written by the controller and read by everybody.
	# Not writable by anyone: a log somebody can edit is not a log.
	("One Stage Change", "Read", 0),
	# What counts as answering in time. Read for a rep and Write for the
	# manager, for exactly the reason the stages are: a rep who can lengthen
	# their own target is a rep who is never late.
	("One Response Target", "Read", 0),
	# Its three child tables: the working week, what is promised at each
	# priority, and the rules deciding which records it covers and what counts
	# as settled. A grid whose doctype the reader cannot see is a grid that
	# draws nothing, so the record would show an empty week and no promise.
	("One Working Day", "Read", 0),
	("One Response Level", "Read", 0),
	("One Response Rule", "Read", 0),
	("Holiday List", "Read", 0),
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
	# What this workspace calls this space's screens — `onespace/words.py`,
	# `docs/ONECRM.md` stage 7. Read for everybody, because the Words tab is
	# on a page they can open and a tab that draws nothing reads as broken;
	# written by the seat that runs the desk, because renaming Deals to
	# Donations changes what every colleague reads.
	("OneSpace Word", "Read", 0),

	# ----- Sales manager --------------------------------------------------- #
	("One Deal Stage", "Write", 0, "manager"),
	("OneSpace Word", "Write", 0, "manager"),
	("One Response Target", "Write", 0, "manager"),
	("One Working Day", "Write", 0, "manager"),
	("One Response Level", "Write", 0, "manager"),
	("One Response Rule", "Write", 0, "manager"),
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

# What a desk answers in, to begin with — `docs/ONECRM.md` stage 6.
#
# Every number in here is meant to be argued with: the point of a target being
# rows rather than a setting is that a workspace changes it in one place rather
# than asking for a deployment. Written once by the seeder and never edited
# again, the same rule `STAGES` follows.
#
# Three targets and not two, because the third is what makes the shape visible:
# a lead that came in off the website is answered faster than one somebody
# typed in from a trade show, and that is a rule on a row rather than a second
# product.
WORKING_WEEK = [
	("Monday", "09:00:00", "17:00:00"),
	("Tuesday", "09:00:00", "17:00:00"),
	("Wednesday", "09:00:00", "17:00:00"),
	("Thursday", "09:00:00", "17:00:00"),
	("Friday", "09:00:00", "17:00:00"),
]

#: Each level is (name, is the default, answer within, settle within), in
#: working hours. Zero settle-within means the target promises nothing about
#: resolution, which is honest for a desk that only promises to reply.
TARGETS = [
	{
		# Narrow, so `position` puts it above the catch-all: somebody who filled
		# in a form five minutes ago is still at their desk, and an hour later
		# they are not. No promise about settling — a web lead is qualified or it
		# is not, and that is not a date anybody can commit to.
		"name": "Answer a web lead",
		"applies_to": "Lead",
		"applies_when": [("source", "is", "Website")],
		"week": WORKING_WEEK,
		"levels": [("Standard", True, 1, 0)],
	},
	{
		# And every other lead. Four working hours, because a lead that goes
		# unanswered is *lost* — which is the argument for measuring leads at
		# all. Settled when somebody has said yes or no to it, read off the field
		# the Leads board is already drawn by.
		"name": "Answer a lead",
		"applies_to": "Lead",
		"week": WORKING_WEEK,
		"levels": [("Standard", True, 4, 0)],
		"resolved_when": [("qualification_status", "is", "Qualified")],
	},
	{
		# A deal, which is the one with two clocks and three priorities. The
		# priority is the deal's own stage: a deal in Negotiation is answered
		# faster than one in New, which is what every desk does by instinct and
		# no CRM writes down.
		"name": "Come back on a deal",
		"applies_to": "Opportunity",
		"priority_field": "custom_stage",
		"week": WORKING_WEEK,
		"levels": [
			("Negotiation", False, 2, 40),
			("Proposal", False, 4, 80),
			("Standard", True, 8, 160),
		],
		# Won and Lost are both settled: a deal somebody decided against is a
		# deal that got dealt with, and a target counting only wins would make
		# losing look like neglect. `status` rather than the stage, because
		# `onecrm/deal.py` writes it from the stage's *category* — so a workspace
		# that renames its last column keeps this working.
		"resolved_when": [("status", "is not", "Open")],
	},
]

# What a measured record carries — `docs/ONECRM.md` stage 6.
#
# Twelve, and every one of them read-only. The deadlines are the target's
# arithmetic, the answers are stamped by the thing that answered — a message
# sent, a call out — and the two states are written from them. A measure
# somebody can type into is not a measure.
#
# On both Lead and Opportunity, in the same order, so a person who has learned
# to read one has learned to read the other. Under a collapsible section of
# their own, because twelve fields threaded through somebody else's form is a
# form nobody can find anything in.
ANSWERING = [
	{"fieldname": "custom_answering_section", "label": "Answering",
	 "fieldtype": "Section Break", "insert_after": "custom_next_step_on",
	 "collapsible": 1},
	{"fieldname": "custom_respond_by", "label": "Answer by",
	 "fieldtype": "Datetime", "read_only": 1,
	 "insert_after": "custom_answering_section", "in_list_view": 1,
	 "description": "When an answer is due, counted in working hours against "
	                "the target's own week and holiday list — so something "
	                "that arrives on Friday evening is not late on Saturday "
	                "morning."},
	{"fieldname": "custom_answered_on", "label": "Answered on",
	 "fieldtype": "Datetime", "read_only": 1,
	 "insert_after": "custom_respond_by",
	 "description": "The answer that stopped this round's clock, whatever form "
	                "it took: a message sent, a call made. Never overwritten "
	                "within a round — a second email is not a second chance to "
	                "have been on time."},
	{"fieldname": "custom_answering", "label": "Answering",
	 "fieldtype": "Select", "options": "\nWaiting\nAnswered\nLate",
	 "read_only": 1, "insert_after": "custom_answered_on", "in_list_view": 1,
	 "description": "Where the reply stands. Written rather than worked out per "
	                "row, because a list sorts by a column and a board groups "
	                "by one."},
	{"fieldname": "custom_answered_in", "label": "Answered in (hours)",
	 "fieldtype": "Float", "precision": "2", "read_only": 1,
	 "insert_after": "custom_answering",
	 "description": "Working hours and not wall clock: a reply that took three "
	                "days over a weekend took one working day, and a desk "
	                "measured in wall clock looks worse in December than in "
	                "June."},
	{"fieldname": "custom_settle_by", "label": "Settle by",
	 "fieldtype": "Datetime", "read_only": 1,
	 "insert_after": "custom_answered_in",
	 "description": "The other clock. Empty where the target promised nothing "
	                "about resolution."},
	{"fieldname": "custom_settled_on", "label": "Settled on",
	 "fieldtype": "Datetime", "read_only": 1,
	 "insert_after": "custom_settle_by",
	 "description": "Stamped the moment the record reaches what its target "
	                "calls settled — on the same save, rather than an hour "
	                "later when a sweep notices."},
	{"fieldname": "custom_settling", "label": "Settling",
	 "fieldtype": "Select", "options": "\nOpen\nSettled\nOverdue",
	 "read_only": 1, "insert_after": "custom_settled_on", "in_list_view": 1},
	{"fieldname": "custom_settled_in", "label": "Settled in (hours)",
	 "fieldtype": "Float", "precision": "2", "read_only": 1,
	 "insert_after": "custom_settling",
	 "description": "From the record's own beginning rather than from the last "
	                "round: a response is a promise per round and a resolution "
	                "happens once."},
	{"fieldname": "custom_rounds", "label": "Rounds", "fieldtype": "Int",
	 "read_only": 1, "insert_after": "custom_settled_in",
	 "description": "How many times somebody has had to be answered. Two is a "
	                "conversation; nine is a record nobody is reading."},
	{"fieldname": "custom_round_began", "label": "This round since",
	 "fieldtype": "Datetime", "read_only": 1,
	 "insert_after": "custom_rounds",
	 "description": "When the clock now running was started — the record's "
	                "creation on the first round, the moment the other side "
	                "wrote back on every one after it."},
	{"fieldname": "custom_response_target", "label": "Target",
	 "fieldtype": "Link", "options": "One Response Target", "read_only": 1,
	 "insert_after": "custom_round_began",
	 "description": "Which target decided the deadlines, so a date somebody "
	                "disagrees with names the row to argue with."},
	{"fieldname": "custom_response_level", "label": "At priority",
	 "fieldtype": "Data", "read_only": 1,
	 "insert_after": "custom_response_target"},
]


CUSTOM_FIELDS = [
	# The column the pipeline is drawn by — `docs/ONECRM.md` stage 1. A Link to
	# a row a workspace maintains, because ERPNext's `Sales Stage` has a name
	# and nothing else and its `status` is six fixed words. The status is
	# written *from* this on save, so the two vocabularies cannot disagree.
	{"dt": "Opportunity", "fieldname": "custom_stage", "label": "Stage",
	 "fieldtype": "Link", "options": "One Deal Stage",
	 "insert_after": "sales_stage", "in_list_view": 1,
	 "description": "How far along this deal is, in the words this workspace "
	                "uses. The stage carries a category, and ERPNext's own "
	                "Status is written from it — `onecrm/deal.py`."},
	# Where it has been, and how long it has been where it is —
	# `docs/ONECRM.md` stage 2. Two halves of one fact: the table is the
	# history a record shows, and the Datetime is the copy a *list* can sort
	# by, because a child table cannot be sorted on and "longest stuck first"
	# is a sort. Both are written by `onecrm/deal.py` and by nothing else.
	{"dt": "Opportunity", "fieldname": "custom_stage_since", "label": "In stage since",
	 "fieldtype": "Datetime", "read_only": 1, "insert_after": "custom_stage",
	 "description": "When this deal arrived at the stage it is in. Sorted "
	                "ascending it is the pipeline read stuck-first, which is "
	                "the question a pipeline review is held to ask."},
	{"dt": "Opportunity", "fieldname": "custom_stage_log", "label": "Stage history",
	 "fieldtype": "Table", "options": "One Stage Change", "read_only": 1,
	 "insert_after": "custom_next_step_on",
	 "description": "Every stage this deal has been in, how long it sat in "
	                "each, and who moved it."},
	{**NEXT_STEP[0], "dt": "Lead", "insert_after": "status"},
	{**NEXT_STEP[1], "dt": "Lead", "insert_after": "custom_next_step"},
	{**NEXT_STEP[0], "dt": "Opportunity", "insert_after": "status"},
	{**NEXT_STEP[1], "dt": "Opportunity", "insert_after": "custom_next_step"},
	# How long this one had to be answered in, and whether it was —
	# `docs/ONECRM.md` stage 6, `onecrm/answering.py`. Four fields on both,
	# because a lead nobody answered in two days is lost and a deal nobody came
	# back to after the meeting is the same loss one stage later.
	#
	# Every one of them read-only. The deadline is the target's arithmetic, the
	# answer is stamped by the thing that answered — a sent message, a call
	# out — and the state is written from the two. A measure somebody can type
	# into is not a measure.
	*[{**one, "dt": dt} for dt in ("Lead", "Opportunity") for one in ANSWERING],
]

SCREENS = [
	{
		# The front page: what this space is about, in the four lists somebody
		# opening it in the morning actually wants. Every block is another
		# screen of this space — `onespace/homepage.py` — so a block draws that
		# screen's own columns and is checked where every list is checked, and
		# a block whose screen this reader cannot open is not sent at all.
		"screen": "home", "label": "Home", "singular": "Day",
		"icon": "lucide-layout-grid",
		"component": "home",
		"view_settings": json.dumps({"home": {"blocks": ["my-deals", "follow-ups", "leads", "quotations"]}}),
	},
	{
		# The pipeline. A board of deals by sales stage, which is the one
		# picture a sales meeting is held over and which the desk renders as a
		# list of rows sorted by modification date.
		#
		# The badge and the columns are deliberately two different fields.
		# `status` is what has *happened* to a deal — Open, Quotation,
		# Converted, Lost — and `custom_stage` is how far along it is. The
		# board is drawn by the stage because that is the pipeline; the badge
		# beside each name is the status, because a Lost deal sitting in
		# Negotiation is exactly the row somebody needs to see.
		#
		# And the two cannot disagree: the stage carries a category and
		# `onecrm/deal.py` writes ERPNext's status from it on save —
		# `docs/ONECRM.md` stage 1. ERPNext's own `Sales Stage` is left where
		# it is, unused by this space and untouched for anything else on the
		# site that reads it.
		"screen": "deals", "label": "Deals", "singular": "Deal",
		"icon": "lucide-shopping-cart", "document_type": "Opportunity",
		# `title` first, which is the deal's own name and not the customer's.
		# The engine draws the first column as the row's title, and a pipeline
		# where every row said the client meant three deals with one company
		# read as the same row three times.
		"fields": "title,customer_name,custom_stage,custom_stage_since,"
		          "opportunity_amount,probability,expected_closing,"
		          "custom_next_step_on,custom_answering,custom_settling,"
		          "opportunity_owner,status",
		"order_by": "expected_closing asc",
		"view_types": "board,list,dashboard,calendar",
		"status_field": "status",
		"field_icons": json.dumps({
			"status": "lucide-flag",
			"custom_stage": "lucide-chart-line",
			"probability": "lucide-chart-pie",
		}),
		"view_settings": json.dumps({
			# Columns a team named, in the order they put them in — and the
			# empty ones too, which is the whole use of a board: a stage you
			# cannot drop a card into is a stage that never gets its first
			# deal. `columns_from` is the screen saying the rows of
			# `One Deal Stage` *are* the columns; `views._columns_from` reads
			# them, permission-checked like everything else.
			"board": {
				"column_field": "custom_stage",
				"columns_from": {"order_by": "position asc, name asc"},
				"card_fields": ["customer_name", "opportunity_amount",
				                "custom_stage_since"],
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
				# The picture a sales meeting is held over: what is sitting
				# at each stage, in pipeline order rather than in size order —
				# which is what `order` is for.
				#
				# A bar and not a funnel, and the difference is not taste. A
				# funnel is drawn as a shape that narrows, and it labels each
				# band as a percentage of the one above it; that is only
				# meaningful where the buckets *nest*, which a stage-by-stage
				# sum does not. Drawn as a funnel, a real pipeline comes out a
				# sawtooth with bands reading 159%. The funnel every CRM shows
				# is cumulative — how much has reached at least this stage —
				# and that is a measure this engine cannot take from one
				# `group_by`. Until it can, the honest chart is a bar.
				{"kind": "bar", "label": "Value by stage",
				 "group_by": "custom_stage", "aggregate": "sum",
				 "field": "opportunity_amount", "order": STAGE_NAMES,
				 "width": 6},
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
			# Where this deal's history starts — `docs/ONECRM.md` stage 4. A
			# deal converted from a lead did not exist before the conversion,
			# so its column began the day somebody pressed a button and the six
			# weeks of email that got it there sat on a record nobody opens
			# again. `party_name` is a Dynamic Link against `opportunity_from`,
			# which is the whole reason this is a declaration rather than a
			# rule: a deal may have come from a Lead, a Customer or a Prospect,
			# and only the record knows which.
			"timeline": {"inherits": "party_name"},
			"showcase": {
				# Who the deal is with, and what kind of party that is —
				# `docs/ONECRM.md` stage 7. `party_name` and not
				# `customer_name`: ERPNext's party is a Dynamic Link against
				# `opportunity_from`, so a deal is with a Lead, a Customer or
				# a Prospect — a person, a company or a public body — and a
				# header that read the customer name said nothing at all on a
				# deal with somebody who is not a customer yet, which is every
				# deal in the pipeline.
				"eyebrow_field": "party_name",
				"eyebrow_kind_field": "opportunity_from",
				"badge_field": "custom_stage",
				"facts": [
					{"field": "opportunity_amount", "label": "Value"},
					{"field": "probability", "label": "Probability"},
					{"field": "expected_closing", "label": "Closing"},
					# How long it has been where it is, which is the question a
					# record is opened with as often as what it is worth —
					# `docs/ONECRM.md` stage 2.
					{"field": "custom_stage_since", "label": "In stage since"},
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
		"fields": "custom_next_step_on,custom_next_step,title,customer_name,"
		          "custom_stage,opportunity_amount,opportunity_owner,status",
		"order_by": "custom_next_step_on asc",
		"filters": json.dumps({
			"status": ["in", ["Open", "Replied", "Quotation"]],
		}),
		"view_types": "calendar,list,board",
		"status_field": "status",
		"view_settings": json.dumps({
			# Whose follow-up it is, for the diary's Mine lens — `docs/WORK.md`
			# §6. The same sentinel a twin screen uses, resolved by the same
			# module, so My deals and a personal calendar cannot disagree
			# about which deals are somebody's.
			"calendar": {"start_field": "custom_next_step_on", "diary": True,
			             "about": {"opportunity_owner": "@me"}},
			"board": {
				"column_field": "custom_stage",
				"columns_from": {"order_by": "position asc, name asc"},
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
		"icon": "lucide-inbox", "document_type": "Lead",
		"fields": "lead_name,company_name,qualification_status,status,email_id,"
		          "mobile_no,territory,utm_source,custom_next_step_on,"
		          # Whether anybody has come back to them yet — stage 6. On
		          # the list and not only on the record, because "which of
		          # these is late" is a question about the page rather than
		          # about a row.
		          "custom_answering",
		"order_by": "modified desc",
		"view_types": "board,list,grid,dashboard",
		"status_field": "status",
		"field_icons": json.dumps({
			"status": "lucide-flag",
			"qualification_status": "lucide-chart-line",
		}),
		"view_settings": json.dumps({
			# Not `company_name`: ERPNext titles a Lead by the organisation, so
			# a card carrying it says the same thing twice and has one fewer
			# line for the person, what they do and where they came from —
			# which is all a card of a lead is for.
			"board": {
				"column_field": "qualification_status",
				"card_fields": ["lead_name", "job_title", "utm_source"],
			},
			"grid": {"card_fields": ["lead_name", "job_title", "utm_source"]},
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
			"grid": {"card_fields": ["industry", "territory", "no_of_employees"]},
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
			"grid": {"card_fields": ["company_name", "designation", "email_id"]},
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
			# An appointment names the customer and not the person who has to
			# be there, so whose it is is who it was assigned to — the one
			# field every doctype already has.
			"calendar": {"start_field": "scheduled_time", "diary": True,
			             "about": {"_assign": "@me"}},
		}),
	},
	{
		# Calls made and taken — `docs/ONECRM.md` stage 5, and `onecrm/calls.py`
		# for why the doctype is ours and why it is about anything.
		#
		# A week first, because that is the question a call log answers that a
		# list does not: not "what did we say to this deal" — the record's own
		# timeline has that — but "how much of Tuesday was on the phone, and to
		# whom". The diary lens is `person`, which is who made the call rather
		# than who logged it, so somebody logging a colleague's call does not
		# put it in their own week.
		"screen": "calls", "label": "Calls", "singular": "Call",
		"icon": "lucide-phone", "document_type": "One Call",
		"fields": "with_whom,way,number,at,minutes,outcome,about_name,person",
		"order_by": "at desc",
		"view_types": "calendar,list,dashboard",
		"view_settings": json.dumps({
			"calendar": {"start_field": "at", "diary": True,
			             "about": {"person": "@me"}},
			"dashboard": {"widgets": [
				{"kind": "number", "label": "Calls", "width": 4},
				{"kind": "number", "label": "Minutes on the phone",
				 "aggregate": "sum", "field": "minutes", "width": 4},
				{"kind": "number", "label": "Average length",
				 "aggregate": "avg", "field": "minutes", "width": 4},
				# The three that are not Answered are the point: a column of
				# attempts is what tells you somebody is avoiding you.
				{"kind": "donut", "label": "How they went",
				 "group_by": "outcome", "width": 6},
				{"kind": "donut", "label": "Which way", "group_by": "way",
				 "width": 6},
				{"kind": "bar", "label": "Who made them", "group_by": "person",
				 "horizontal": True, "width": 12},
			]},
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
	# ----- Configuration ---------------------------------------------------- #
	#
	# One rail entry with the space's own tables behind it —
	# `onespace/configuration.py`. Each is an ordinary screen with a route and
	# `hide_in_nav`, so a tab inherits that screen's columns, permissions and
	# New button rather than being a second way to reach a doctype.
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
		# The columns the pipeline is drawn by, and the one table on this page
		# a manager actually edits. Ordered by `position` because that is what
		# the board reads — so the list and the board are the same order and
		# moving a stage is one number.
		"screen": "stages", "hide_in_nav": 1, "label": "Stages",
		"singular": "Stage",
		"icon": "lucide-chart-line", "document_type": "One Deal Stage",
		"fields": "stage_name,category,probability,colour,position",
		"order_by": "position asc",
		"view_types": "list",
	},
	{
		# How long a lead or a deal has to be answered in, and the week that is
		# counted against — `docs/ONECRM.md` stage 6. The one other table on
		# this page a manager actually edits, and the one that most rewards
		# being in a place somebody can find: a target nobody can see is a
		# number people argue with rather than change.
		"screen": "targets", "hide_in_nav": 1, "label": "Response targets",
		"singular": "Response target",
		"icon": "lucide-clock", "document_type": "One Response Target",
		"fields": "target_name,applies_to,priority_field,holiday_list,"
		          "rolling,position,enabled",
		"order_by": "position asc, target_name asc",
		"view_types": "list",
	},
	{
		"screen": "deal-types", "hide_in_nav": 1, "label": "Deal types", "singular": "Deal type",
				"icon": "lucide-layers", "document_type": "Opportunity Type",
		"fields": "name,description",
		"order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "sources", "hide_in_nav": 1, "label": "Sources", "singular": "Source",
				"icon": "lucide-database", "document_type": "UTM Source",
		"fields": "name,slug,description",
		"order_by": "name asc",
		"view_types": "list",
	},
	{
		"screen": "campaigns", "hide_in_nav": 1, "label": "Campaigns", "singular": "Campaign",
				"icon": "lucide-mail", "document_type": "Campaign",
		"fields": "campaign_name,description",
		"order_by": "campaign_name asc",
		"view_types": "list",
	},
	{
		# A tree, because a territory is one — ERPNext nests them and the desk
		# is the only place that has ever shown it.
		"screen": "territories", "hide_in_nav": 1, "label": "Territories", "singular": "Territory",
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
		"screen": "lost-reasons", "hide_in_nav": 1, "label": "Lost reasons",
		"singular": "Lost reason", "icon": "lucide-git-compare",
		"document_type": "Opportunity Lost Reason",
		"fields": "lost_reason",
		"order_by": "lost_reason asc",
		"view_types": "list",
	},
	{
		"screen": "configuration", "label": "Configuration",
		"singular": "Table", "icon": "lucide-wrench",
		"component": "configuration",
		"view_settings": json.dumps({"configuration": {"screens": [
			"stages", "deal-types", "sources", "campaigns", "territories",
			"lost-reasons",
		]}}),
	},
]


# --------------------------------------------------------------------------- #
# A salesperson's own week
#
# The same idea as OnePeople's — `oneapp/onespace/mine.py` — and the reason to have
# it in two spaces is the reason it is in the engine at all: a screen narrowed
# to its reader is not an HR feature. A pipeline is a forecast to whoever runs
# the team and a to-do list to whoever owns the deals, and those are different
# screens over the same rows.
#
# `@me` with no kind after it is the session's user, which every site has and
# which needs no app to register anything: `opportunity_owner` is a Link to
# User, so the sentinel resolves without leaving the engine.
# --------------------------------------------------------------------------- #

_AT = next(i for i, one in enumerate(SCREENS) if one["screen"] == "deals")
SCREENS.insert(_AT, {
	**SCREENS[_AT],
	"screen": "my-deals", "label": "My deals",
	"filters": json.dumps({"opportunity_owner": "@me"}),
})
