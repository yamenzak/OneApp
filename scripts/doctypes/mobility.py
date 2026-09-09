"""OneMobility — the reference nouns of a transit network.

Only the things a person opens: a line somebody comments on, a stop somebody
shares, a vehicle somebody assigns. Hundreds to low thousands of rows each, and
every one of them earns the whole record surface — permissions, the timeline,
saved views, printing — for free.

What is *not* here is the data: trips, stop times and vehicle observations are
millions to hundreds of millions of rows, and a Document costs a controller, a
validation pass and a `varchar(140)` key that every index copies. They are
declared in `oneapp/onemobility/model.py` against `shared/facts.py` instead.
`apps/oneapp/oneapp/onemobility/README.md` §3 is the argument.

Named on GTFS's entities rather than VDV's, deliberately: model on VDV and you
have built a German product that needs rewriting the first time somebody in
Vienna asks. The one rename is Route → Line, because riders and staff say "the
12 is late" and nobody has ever said route.
"""

from .spec import MANAGER_PERMS, column, doctype, f, section

MODULE = "OneMobility"
TENANT = dict(app="tenant", module=MODULE, perms=MANAGER_PERMS)


# --------------------------------------------------------------------------- #
# Where the data comes from
# --------------------------------------------------------------------------- #

doctype(
    "Transit Source",
    autoname="field:source_name",
    title_field="source_name",
    search_fields="kind,status",
    states=[
        {"title": "Connected", "color": "Green"},
        {"title": "Paused", "color": "Gray"},
        {"title": "Failing", "color": "Red"},
    ],
    fields=[
        f("source_name", "Data", "Name", reqd=1, in_list_view=1, unique=1,
          description="What this connection is called on screen."),
        f("kind", "Select", "Kind", reqd=1, in_list_view=1,
          options="Upload\nSFTP\nHTTP\nSocket",
          description="How the data arrives. Every kind runs the same pipeline; "
                      "only the fetch differs."),
        f("format", "Select", "Format", reqd=1, in_list_view=1,
          options="GTFS\nGTFS Realtime\nVDV 452\nVDV 454\nNeTEx\nSIRI",
          description="Which dialect it speaks. Each is a normaliser onto the "
                      "one model, never a second model."),
        f("status", "Select", "Status", in_list_view=1, default="Connected",
          options="Connected\nPaused\nFailing"),
        # Precedence, which is the whole answer to "handle duplicates". Two
        # sources claiming one natural key is a conflict, and this is what
        # resolves it — declared by the customer rather than guessed, and the
        # loser is kept and shown rather than dropped.
        f("precedence", "Int", "Precedence", default="100",
          description="Lower wins where two sources disagree about the same "
                      "line, stop or trip. The loser is kept and stays visible."),
        column("cb_source_where"),
        f("endpoint", "Data", "Endpoint",
          description="Host, URL or socket address. Empty for an upload."),
        f("folder", "Data", "Folder",
          description="Where on the host to look, for SFTP."),
        f("username", "Data", "Username"),
        # Frappe's own Password fieldtype: stored in `__Auth`, never returned
        # by a read, never in a list payload. Not a Data field we promise to be
        # careful with.
        f("secret", "Password", "Password or key"),
        section("sec_source_when", "Schedule"),
        f("every_minutes", "Int", "Fetch every (minutes)", default="60",
          description="Zero for a source that pushes to us rather than being "
                      "asked."),
        f("last_run", "Datetime", "Last run", read_only=1),
        f("watermark", "Datetime", "Taken up to", read_only=1,
          description="The newest row this source has been read up to. What "
                      "makes the next fetch incremental rather than whole."),
        column("cb_source_last"),
        f("last_message", "Small Text", "Last message", read_only=1),
        f("rows_seen", "Int", "Rows seen", read_only=1),
    ],
    **TENANT,
)

doctype(
    "Transit Feed",
    autoname="hash",
    title_field="label",
    search_fields="source,status",
    states=[
        {"title": "Received", "color": "Blue"},
        {"title": "Loaded", "color": "Green"},
        {"title": "Refused", "color": "Red"},
    ],
    fields=[
        f("label", "Data", "Feed", reqd=1, in_list_view=1,
          description="One delivery from one source at one moment. Everything "
                      "traces back to a feed, which is what makes a wrong "
                      "number answerable."),
        f("source", "Link", "Source", options="Transit Source", reqd=1,
          in_list_view=1),
        f("status", "Select", "Status", in_list_view=1, default="Received",
          options="Received\nLoaded\nRefused"),
        f("received_on", "Datetime", "Received", in_list_view=1, read_only=1),
        column("cb_feed_counts"),
        f("file", "Attach", "File",
          description="The delivery as it arrived, kept so a load can be "
                      "explained and repeated."),
        f("lines_seen", "Int", "Lines", read_only=1),
        f("stops_seen", "Int", "Stops", read_only=1),
        f("trips_seen", "Int", "Trips", read_only=1),
        section("sec_feed_notes", "What happened"),
        f("notes", "Small Text", "Notes", read_only=1),
    ],
    **TENANT,
)


# --------------------------------------------------------------------------- #
# The network
# --------------------------------------------------------------------------- #

doctype(
    "Transit Agency",
    autoname="field:agency_name",
    title_field="agency_name",
    search_fields="agency_name",
    fields=[
        f("agency_name", "Data", "Agency", reqd=1, in_list_view=1, unique=1),
        f("agency_key", "Data", "Key", reqd=1,
          description="What the feed calls it. The natural key two sources are "
                      "compared on."),
        f("timezone", "Data", "Timezone", default="Europe/Berlin"),
        column("cb_agency_more"),
        f("url", "Data", "Website"),
        f("feed", "Link", "First seen in", options="Transit Feed", read_only=1),
    ],
    **TENANT,
)

doctype(
    "Transit Line",
    autoname="hash",
    title_field="line_name",
    search_fields="short_name,line_name,agency",
    states=[
        {"title": "Running", "color": "Green"},
        {"title": "Suspended", "color": "Amber"},
        {"title": "Retired", "color": "Gray"},
    ],
    fields=[
        f("short_name", "Data", "Number", reqd=1, in_list_view=1,
          description="What a rider calls it — 12, S3, N9."),
        f("line_name", "Data", "Name", reqd=1, in_list_view=1),
        f("agency", "Link", "Agency", options="Transit Agency", in_list_view=1),
        f("line_key", "Data", "Key", reqd=1,
          description="What the feed calls it. The natural key."),
        f("status", "Select", "Status", in_list_view=1, default="Running",
          options="Running\nSuspended\nRetired"),
        column("cb_line_kind"),
        f("mode", "Select", "Mode", in_list_view=1, default="Bus",
          options="Bus\nTram\nMetro\nRail\nFerry\nCable\nOther"),
        # The line's own colour, which every feed carries and every rider knows
        # by sight. Read by the map and the network screen so a drawn route
        # looks like the one on the wall of the station.
        f("colour", "Color", "Colour"),
        # One line drawn differently from the rest of its mode: a heritage tram
        # on a bus network, a rail replacement that is a coach. Empty means
        # "whatever this mode is drawn as", which is what nearly every line is.
        f("marker_shape", "Select", "Drawn as",
          options="\nBus\nTram\nMetro\nRail\nFerry\nCable\nOther",
          description="Overrides the mode's own silhouette on the map. Empty "
                      "follows the mode."),
        f("feed", "Link", "First seen in", options="Transit Feed", read_only=1),
        section("sec_line_shape", "Where it goes"),
        f("shape", "Long Text", "Shape", read_only=1,
          description="The drawn geometry, as a GeoJSON LineString. Written by "
                      "the importer, never typed."),
    ],
    **TENANT,
)

doctype(
    "Transit Stop",
    autoname="hash",
    title_field="stop_name",
    search_fields="stop_name,stop_code",
    states=[
        {"title": "Served", "color": "Green"},
        {"title": "Inferred", "color": "Amber"},
        {"title": "Closed", "color": "Gray"},
    ],
    fields=[
        f("stop_name", "Data", "Stop", reqd=1, in_list_view=1),
        f("stop_code", "Data", "Code", in_list_view=1,
          description="The number on the pole, which is what somebody phoning "
                      "in will read out."),
        f("stop_key", "Data", "Key", reqd=1),
        f("status", "Select", "Status", in_list_view=1, default="Served",
          options="Served\nInferred\nClosed",
          description="Inferred means a vehicle stopped here and no feed "
                      "declared it. It is drawn differently and never quietly "
                      "promoted."),
        column("cb_stop_where"),
        # Two shapes on purpose, and both are read by the engine's map view.
        # The pair is what every feed gives; the Geolocation is what somebody
        # gets when they drag the pin, and is the one a shape would go in.
        f("latitude", "Float", "Latitude", precision="8"),
        f("longitude", "Float", "Longitude", precision="8"),
        f("place", "Geolocation", "Place"),
        f("feed", "Link", "First seen in", options="Transit Feed", read_only=1),
        section("sec_stop_of", "Part of"),
        f("parent_stop", "Link", "Station", options="Transit Stop",
          description="The station this platform belongs to, where a feed says "
                      "so."),
        f("zone", "Data", "Fare zone"),
    ],
    **TENANT,
)

doctype(
    "Transit Vehicle",
    autoname="field:vehicle_key",
    title_field="label",
    search_fields="label,vehicle_key",
    states=[
        {"title": "In service", "color": "Green"},
        {"title": "Depot", "color": "Blue"},
        {"title": "Out of service", "color": "Gray"},
    ],
    fields=[
        f("vehicle_key", "Data", "Key", reqd=1, unique=1,
          description="What the feed calls it."),
        f("label", "Data", "Vehicle", reqd=1, in_list_view=1,
          description="The fleet number painted on the side."),
        f("status", "Select", "Status", in_list_view=1, default="In service",
          options="In service\nDepot\nOut of service"),
        f("mode", "Select", "Mode", in_list_view=1, default="Bus",
          options="Bus\nTram\nMetro\nRail\nFerry\nCable\nOther"),
        column("cb_vehicle_size"),
        f("seats", "Int", "Seats"),
        f("standing", "Int", "Standing places"),
        f("capacity", "Int", "Capacity", read_only=1,
          description="Seats and standing places together, which is what an "
                      "occupancy percentage is a percentage of."),
        f("agency", "Link", "Agency", options="Transit Agency"),
    ],
    **TENANT,
)


# --------------------------------------------------------------------------- #
# How the network is drawn
# --------------------------------------------------------------------------- #

#: The silhouettes the map can draw, and the one word each is called by.
#:
#: Kept in step with `BODIES` in `frontend/src/modules/onemobility/lib/markers.js`
#: — the browser draws them, this names them, and `test_marker_shapes.py` fails
#: if the two lists drift apart.
MARKER_SHAPES = "Bus\nTram\nMetro\nRail\nFerry\nCable\nOther"

doctype(
    "Transit Marker Style",
    autoname="field:mode",
    title_field="mode",
    search_fields="mode,shape",
    fields=[
        f("mode", "Select", "Mode", reqd=1, unique=1, in_list_view=1,
          options="Bus\nTram\nMetro\nRail\nFerry\nCable\nOther",
          description="The mode a line is imported as."),
        # Not the same list twice by accident. A mode is what a network *runs*
        # and a shape is what the map *draws*, and a customer whose Rail is a
        # light rail wants the tram outline without relabelling their network.
        # Identity is the default, so a workspace that never opens this screen
        # gets exactly what it would have got before the doctype existed.
        f("shape", "Select", "Drawn as", reqd=1, in_list_view=1,
          options=MARKER_SHAPES,
          description="Which silhouette the map draws for this mode."),
    ],
    **TENANT,
)
