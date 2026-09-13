"""OneMobility — public transport data, read.

Read `apps/oneapp/oneapp/onemobility/README.md` first: it is the argument, and
this is the half a machine reads.

**Generally available**, which is the difference between this and RUA. RUA was
one company's system and could take their vocabulary and their colours;
this is enabled from the marketplace by anybody, so it says Line and Stop
rather than whatever the first customer says, and has to survive people who do
not work the way that customer does.

Every doctype below is OneSpace's own — a transit network has no home in
ERPNext, and inventing one there would have been a worse answer than six small
doctypes here. Which is also why `requires_apps` is empty: this space needs
nothing but the platform, and a workspace with no ERPNext can enable it.
"""

import json

SPACE = {
	"space_code": "onemobility",
	"space_label": "OneMobility",
	"module": "OneMobility",
	"role_name": "OneSpace Mobility",
	# Nothing. The network is ours, so a bare site can carry this — which is
	# also what makes it saleable to a transport authority who wants a viewer
	# and not an ERP.
	"requires_apps": "",
	"icon": "lucide-bus",
	"sort_order": 30,
	# Ships Restricted, like everything else, and an operator turns it on for
	# the marketplace in OneAdmin. Not a contradiction of "generally
	# available": that is what the *product* is, and this is the switch that
	# stops a half-finished space appearing in every customer's launcher
	# because somebody forgot to think about it. `install()` writes this only
	# on the way in, so flipping it is the operator's decision and stays.
	"availability": "Restricted",
	"description": "Lines, stops, vehicles and where they are — live and back in time.",
	# Light, because a map is the surface and a dark basemap fights the route
	# colours a transit authority has spent decades teaching people to read.
	# The accent is the mark's own deep blue rather than a fourth opinion about
	# what this product is.
	"brand": "onemobility",
	"theme": "light calm soft roomy",
}

# --------------------------------------------------------------------------- #
# The three jobs
#
# A transit authority is not one kind of person, and until now this space was
# handed out as though it were: entitling it gave everybody everything in
# DOCTYPES, so the dispatcher watching the map could rewrite the network and
# the planner could re-point a feed at a different server.
#
# The split is the one the doctypes already imply, which is why it is three and
# not five. Somebody *watches* — that is the control room, and it is by far the
# most common seat. Somebody *maintains the network* — agencies, lines, stops,
# vehicles, and how the map draws them. Somebody *plumbs the data in* — sources
# and feeds, which is the job that can take the map down and is usually one
# person or a contractor.
#
# `viewer` is the default, so entitling OneMobility to a workspace gives every
# member the map and nothing that can break it. A workspace that wants the old
# behaviour hands out all three, which is a decision somebody made rather than
# one they got.
# --------------------------------------------------------------------------- #
ROLES = [
	{
		"role_key": "viewer",
		"label": "Viewer",
		"is_default": 1,
		"description": "See the network, the live map and the history. Saves "
		               "its own views and changes nothing else.",
	},
	{
		"role_key": "planner",
		"label": "Planner",
		"description": "Maintain the network: agencies, lines, stops, vehicles "
		               "and how each mode is drawn.",
	},
	{
		"role_key": "feeds",
		"label": "Feed manager",
		"description": "Own where the data comes from — sources, feeds and the "
		               "order they win in. The job that can take the map down.",
	},
]

# Four parts, not three: the fourth is which role the grant belongs to, and no
# fourth part means all of them. Read the list as three columns — what a viewer
# gets is everything with no role named, and each of the other two adds one
# column of its own on top.
DOCTYPES = [
	# ----- Everybody who holds any of the three -------------------------- #
	#
	# The network, read. A planner and a feed manager both need to see it to do
	# their own job, and a viewer needs nothing else, so this is the floor
	# rather than a role.
	("Transit Agency", "Read", 0),
	("Transit Line", "Read", 0),
	("Transit Stop", "Read", 0),
	("Transit Vehicle", "Read", 0),
	("Transit Marker Style", "Read", 0),
	# Read, not Write, for anybody. A claim is what a source said, and the
	# answer to "this is wrong" is to change the precedence or fix the feed,
	# never to edit the record of what arrived — an editable audit trail is not
	# one. So this is a floor grant with no Write above it anywhere.
	("Transit Claim", "Read", 0),
	# Which feeds exist is not a secret from the people reading their output;
	# what a feed *points at* is, and that stays with the role below.
	("Transit Feed", "Read", 0),
	# The engine's own, because a screen that cannot save a view is a screen
	# people stop using by the second week. `if_owner`, so a viewer's saved
	# views are a viewer's.
	("OneSpace Saved View", "Write", 1),

	# ----- Planner -------------------------------------------------------- #
	#
	# The same doctypes again at a higher level. The floor rows above reach
	# every role in this space, so a planner's manifest carries both a Read and
	# a Write row for `Transit Line` — `sync.sync_permissions` keeps the wider
	# of the two, whatever order they arrive in.
	("Transit Agency", "Write", 0, "planner"),
	("Transit Line", "Write", 0, "planner"),
	("Transit Stop", "Write", 0, "planner"),
	("Transit Vehicle", "Write", 0, "planner"),
	# How the map draws each mode. Not a record anybody browses — the picker is
	# on the map itself, where the effect is visible — but it is a document, so
	# it gets permissions, a history and an audit trail like everything else.
	# The planner's, because it is a decision about how the network reads.
	("Transit Marker Style", "Write", 0, "planner"),

	# ----- Feed manager --------------------------------------------------- #
	("Transit Source", "Manage", 0, "feeds"),
	("Transit Feed", "Write", 0, "feeds"),
]

SCREENS = [
	{
		# The one screen that is not a list of records: a map of the network
		# with a clock, live on the right of now and history on the left. The
		# `component` escape hatch's first honest use — see README §7 for why
		# this is not a view type.
		"screen": "network", "label": "Network", "singular": "Network",
		"icon": "lucide-map", "document_type": "Transit Line",
		"component": "onemobility/network",
		"fields": "short_name,line_name,mode,status",
		"order_by": "short_name asc",
		"view_types": "list",
		"status_field": "status",
	},
	{
		# The aggregate tier, looked at. The second honest use of the escape
		# hatch: a dashboard widget counts a doctype's rows, and none of this
		# is a doctype — `serviceHour` is outside the document system on
		# purpose. See README §7a.
		"screen": "insights", "label": "Insights", "singular": "Insight",
		"icon": "lucide-chart-pie", "document_type": "Transit Line",
		"component": "onemobility/insights",
		"fields": "short_name,line_name,mode,status",
		"order_by": "short_name asc",
		"view_types": "list",
		"status_field": "status",
	},
	{
		# The same tier as Insights, asked about a day that may not have
		# happened. A third screen rather than a fourth tab on Insights: the
		# question is a different one — *what will* rather than *what did* —
		# and the two want different controls, a date against a window.
		# README §7a is the argument for why it is arithmetic and not a model.
		"screen": "outlook", "label": "Outlook", "singular": "Outlook",
		"icon": "lucide-chart-line", "document_type": "Transit Line",
		"component": "onemobility/outlook",
		"fields": "short_name,line_name,mode,status",
		"order_by": "short_name asc",
		"view_types": "list",
		"status_field": "status",
	},
	{
		# What was published against what ran, call by call. §6's other half:
		# `conflicts.py` decides which *record* two sources are describing and
		# this compares two statements about the same *event* — and nothing
		# resolves it, because the gap is the product rather than something to
		# reconcile away.
		#
		# Its own screen and not a tab on Insights, for the reason Outlook is
		# its own: the question is different — *did we run what we said* rather
		# than *how did it run* — and the answer is a table somebody reads row
		# by row, which no chart tab is shaped for.
		"screen": "plan", "label": "Against the plan", "singular": "Call",
		"icon": "lucide-calendar", "document_type": "Transit Line",
		"component": "onemobility/plan",
		"fields": "short_name,line_name,mode,status",
		"order_by": "short_name asc",
		"view_types": "list",
		"status_field": "status",
	},
	{
		"screen": "lines", "label": "Lines", "singular": "Line",
		"icon": "lucide-route", "document_type": "Transit Line",
		"fields": "emoji,short_name,line_name,agency,mode,status",
		"order_by": "short_name asc",
		"view_types": "list,board,grid,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"cards": {"card_fields": ["agency", "mode"]},
			# The network as a *catalogue*, which is a different question from
			# the network as a set of readings. Insights answers how the lines
			# ran; this answers what there are — and it is the one an operator
			# opens after an import, to see whether the feed brought in what
			# they expected before they trust a single number off it.
			"dashboard": {
				"widgets": [
					{"kind": "number", "label": "Lines", "width": 3},
					{"kind": "donut", "label": "By mode", "group_by": "mode", "width": 4},
					{"kind": "bar", "label": "By agency", "group_by": "agency", "width": 5},
					{"kind": "bar", "label": "By status", "group_by": "status", "width": 12},
				],
			},
		}),
	},
	{
		# The engine's map view, over a doctype that is not OneMobility's to
		# keep: any doctype with a position gets this, and stops are simply the
		# first thing that has one.
		"screen": "stops", "label": "Stops", "singular": "Stop",
		"icon": "lucide-map-pin", "document_type": "Transit Stop",
		"fields": "emoji,stop_name,stop_code,zone,status",
		"order_by": "stop_name asc",
		"view_types": "map,list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"map": {
				"lat_field": "latitude",
				"lon_field": "longitude",
				"label_field": "stop_name",
				"colour_field": "status",
			},
			# Served against Inferred is the widget that earns this dashboard.
			# An inferred stop is one we guessed from a position and nobody has
			# confirmed, and a network where that slice is growing is a network
			# whose feed is drifting from its timetable — which is invisible in
			# a list of two thousand stops and obvious in one ring.
			"dashboard": {
				"widgets": [
					{"kind": "number", "label": "Stops", "width": 3},
					{"kind": "donut", "label": "How each one is known",
					 "group_by": "status", "width": 4},
					{"kind": "bar", "label": "By fare zone", "group_by": "zone", "width": 5},
				],
			},
		}),
	},
	{
		"screen": "vehicles", "label": "Vehicles", "singular": "Vehicle",
		"icon": "lucide-bus", "document_type": "Transit Vehicle",
		"fields": "label,vehicle_key,mode,capacity,status,agency",
		"order_by": "label asc",
		"view_types": "list,board,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			# The fleet as an asset register. How many, how much they can carry,
			# and how that splits by mode — which is the number a scheduler and
			# a finance director both want and neither can get from Insights,
			# because that screen only knows about vehicles that reported.
			"dashboard": {
				"widgets": [
					{"kind": "number", "label": "Vehicles", "width": 3},
					{"kind": "number", "label": "Places", "aggregate": "sum",
					 "field": "capacity", "width": 3},
					{"kind": "donut", "label": "By mode", "group_by": "mode", "width": 6},
					{"kind": "bar", "label": "In service, and not",
					 "group_by": "status", "width": 6},
					{"kind": "bar", "label": "Average capacity by mode", "group_by": "mode",
					 "aggregate": "avg", "field": "capacity", "width": 6},
				],
			},
		}),
	},
	{
		# `folder` rather than `format`, because there is no format to show:
		# a delivery says what it is and the column was empty on every row
		# that was not a stream. What a person actually scans this list for
		# is which source points where.
		"screen": "sources", "label": "Sources", "singular": "Source",
		"icon": "lucide-database", "document_type": "Transit Source",
		"fields": "source_name,kind,folder,precedence,last_run,status",
		"order_by": "precedence asc",
		"view_types": "list",
		"status_field": "status",
	},
	{
		# What this reads, and — the part nobody else writes down — which door
		# each VDV part arrives through. A screen rather than a docs page
		# because "do you support 457-3" is asked during a sales call and the
		# answer has to be one somebody can pull up. `onemobility/vdv.py`.
		#
		# `hide_in_nav`, since `docs/UNIFICATION.md` §E5. Its own docstring is
		# a good argument for the *content* and no argument at all for the
		# placement: it sat in the rail beside Sources and Deliveries, where a
		# reader expects to configure something, and it configures nothing. It
		# is a reference, so it is reached from the question — the "What this
		# reads" button on a source — rather than picked cold from a list of
		# places to go and work.
		"screen": "protocols", "label": "Protocols", "singular": "Protocol",
		"icon": "lucide-book-open", "document_type": "Transit Source",
		"component": "onemobility/protocols",
		"fields": "source_name,kind,status",
		"order_by": "source_name asc",
		"view_types": "list",
		"status_field": "status",
		"hide_in_nav": 1,
	},
	{
		# The honest version of "select all sources": not merging, choosing
		# whose answer to draw — and always able to show you the others. §6.
		"screen": "claims", "label": "Disagreements", "singular": "Claim",
		"icon": "lucide-git-compare", "document_type": "Transit Claim",
		"fields": "entity,natural_key,label,source,precedence,differs,verdict",
		"order_by": "natural_key asc",
		"filters": json.dumps({"contested": 1}),
		"hide_new": 1,
		"view_types": "list",
		"status_field": "verdict",
	},
	{
		"screen": "feeds", "label": "Deliveries", "singular": "Delivery",
		"icon": "lucide-file-text", "document_type": "Transit Feed",
		"fields": "label,source,origin,format,received_on,lines_seen,stops_seen,trips_seen,status",
		"order_by": "received_on desc",
		"view_types": "list,dashboard",
		"status_field": "status",
		"view_settings": json.dumps({
			"dashboard": {
				"widgets": [
					{"kind": "count", "label": "Deliveries", "field": ""},
					{"kind": "sum", "label": "Lines", "field": "lines_seen"},
					{"kind": "sum", "label": "Stops", "field": "stops_seen"},
					{"kind": "sum", "label": "Trips", "field": "trips_seen"},
				],
			},
		}),
	},
]

# Nothing. Every doctype above is ours, so there is no third-party schema to
# extend — which is the quiet advantage of a space that does not sit on
# somebody else's app.
CUSTOM_FIELDS = []
