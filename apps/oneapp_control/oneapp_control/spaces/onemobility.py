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
	("Transit Agency", "Write", 0),
	("Transit Line", "Write", 0),
	("Transit Stop", "Write", 0),
	("Transit Vehicle", "Write", 0),
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
		"screen": "lines", "label": "Lines", "singular": "Line",
		"icon": "lucide-route", "document_type": "Transit Line",
		"fields": "short_name,line_name,agency,mode,status",
		"order_by": "short_name asc",
		"view_types": "list,board,grid",
		"status_field": "status",
		"view_settings": json.dumps({
			"cards": {"card_fields": ["agency", "mode"]},
		}),
	},
	{
		# The engine's map view, over a doctype that is not OneMobility's to
		# keep: any doctype with a position gets this, and stops are simply the
		# first thing that has one.
		"screen": "stops", "label": "Stops", "singular": "Stop",
		"icon": "lucide-map-pin", "document_type": "Transit Stop",
		"fields": "stop_name,stop_code,zone,status",
		"order_by": "stop_name asc",
		"view_types": "map,list",
		"status_field": "status",
		"view_settings": json.dumps({
			"map": {
				"lat_field": "latitude",
				"lon_field": "longitude",
				"label_field": "stop_name",
				"colour_field": "status",
			},
		}),
	},
	{
		"screen": "vehicles", "label": "Vehicles", "singular": "Vehicle",
		"icon": "lucide-bus", "document_type": "Transit Vehicle",
		"fields": "label,vehicle_key,mode,capacity,status",
		"order_by": "label asc",
		"view_types": "list,board",
		"status_field": "status",
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
