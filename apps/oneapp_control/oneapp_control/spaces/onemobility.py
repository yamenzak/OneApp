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

DOCTYPES = [
	("Transit Source", "Manage", 0),
	("Transit Feed", "Write", 0),
	# Read, not Write. A claim is what a source said, and the answer to "this
	# is wrong" is to change the precedence or fix the feed, never to edit the
	# record of what arrived — an editable audit trail is not one.
	("Transit Claim", "Read", 0),
	("Transit Agency", "Write", 0),
	("Transit Line", "Write", 0),
	("Transit Stop", "Write", 0),
	("Transit Vehicle", "Write", 0),
	# How the map draws each mode. Not a record anybody browses — the picker is
	# on the map itself, where the effect is visible — but it is a document, so
	# it gets permissions, a history and an audit trail like everything else.
	("Transit Marker Style", "Write", 0),
	# The engine's own, because a screen that cannot save a view is a screen
	# people stop using by the second week.
	("OneSpace Saved View", "Write", 1),
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
		"screen": "sources", "label": "Sources", "singular": "Source",
		"icon": "lucide-database", "document_type": "Transit Source",
		"fields": "source_name,kind,format,precedence,last_run,status",
		"order_by": "precedence asc",
		"view_types": "list",
		"status_field": "status",
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
		"fields": "label,source,received_on,lines_seen,stops_seen,trips_seen,status",
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
