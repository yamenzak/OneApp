"""Every VDV part this product has an opinion about, and what that opinion is.

VDV is not one specification. It is a shelf of them, written by different
committees over thirty years, and the single most expensive thing in a German
integration project is discovering in week six that the part the customer
meant is not the part you built. So the shelf is written down: what each part
carries, **which door it arrives through**, and whether we read it.

## The three doors, and why the distinction is the useful one

A part's number tells you nothing about how its data reaches a workspace.
Three answers, and they are three different acquisition problems:

  `folder`   a file, in a drop folder or an upload. The ÖPNV-Datenmodell
             family and NeTEx. Read by `sources.py` walking a folder.
  `stream`   a subscription over HTTP between two systems. The Ist-Daten
             family, and 457-2's counted occupancy. Read by `streaming.py`.
  `vehicle`  a service on the vehicle's own LAN. The whole of IBIS-IP (301).
             **A workspace never sees these directly**: they are device-to-
             device inside one bus, so something on the vehicle has to relay
             them out. `live.report` is that door.

That last one is the distinction worth having in a table rather than in
somebody's head. "Support VDV 301-2-15" sounds like a parser; it is actually a
bridge, a fleet of vehicles that have the service fitted, and an agreement
about what leaves the vehicle. The parser is the small part.

## What `state` claims

  `read`        bytes in this format become rows in our model today.
  `recognised`  `sniff.py` identifies it and says there is no reader, which is
                a customer being told "not yet" rather than shown a parse
                error.
  `declared`    named here, so a conversation about it starts from the same
                page. Nothing reads it.
  `unknown`     the part exists and we have not established what it says.
                Listed anyway, because a gap somebody can see is worth more
                than a list that quietly stops at 457.

## `verified`

True where the row was written with the published document open. False where
it was written from working knowledge of the family — which README §1 already
warns about, and which is exactly the set of rows to re-read before writing a
parser against one. The `spec` URL is where to go.
"""

import frappe

#: Where the shelf lives. Every `spec` below is this plus the document's own
#: name, which is how VDV publishes them.
VDV = "https://www.vdv.de"

FOLDER, STREAM, VEHICLE = "folder", "stream", "vehicle"


def _part(part, title, family, door, carries, state="declared", reader="",
          spec="", verified=False, note=""):
	return {
		"part": part, "title": title, "family": family, "door": door,
		"carries": carries, "state": state, "reader": reader,
		"spec": f"{VDV}/{spec}.pdfx" if spec else "",
		"verified": verified, "note": note,
	}


#: The shelf. Ordered by family and then by number, which is how somebody
#: looking for "the planning one" reads it.
PARTS = [
	# --- ÖPNV-Datenmodell: planning data, as files ------------------------ #
	_part(
		"451", "Dateiformat für die Datenübertragung zwischen ÖPNV-Anwendungen",
		"ÖPNV-Datenmodell", FOLDER,
		"The container every other ÖPNV-Datenmodell part is written in: `tbl;` "
		"names a table, `atr;` names its columns, `rec;` is a row. Not a "
		"schema — the schema is 452 and 455.",
		state="read", reader="vdv452", spec="vdv-schrift-451", verified=True,
		note="Our reader implements this container and 452's tables together, "
		     "which is why there is no `vdv451.py`.",
	),
	_part(
		"452", "VDV-Standardschnittstelle Liniennetz/Fahrplan",
		"ÖPNV-Datenmodell", FOLDER,
		"The network and the timetable: stops, lines, routes, trips, running "
		"times, the operating calendar. Version 1.6.2 adds connection "
		"definitions, territorial authorities and electromobility.",
		state="read", reader="vdv452", spec="452v1-6-2-sds", verified=True,
	),
	_part(
		"455", "ÖPNV-Datenmodell: Dienstplan und Personal",
		"ÖPNV-Datenmodell", FOLDER,
		"Duties, driver rosters and the staff behind them — `DIENSTPLAN`, "
		"`PERSONAL`, `FAHRER_NR`.",
		state="recognised", spec="schri455-beschlossene-korrekturen-zu-v1-0a",
		verified=True,
		note="Deliberately not read. GTFS has no word for a duty, and README "
		     "§1 is the argument for not growing a second model to hold one. "
		     "It is also the most personal data in the family.",
	),
	_part(
		"462", "Austausch von Liniennetz- und Fahrplandaten mit CEN-TS 16614 (NeTEx)",
		"ÖPNV-Datenmodell", FOLDER,
		"The same ground 452 covers, in the European standard. VDV's "
		"application handbook for NeTEx.",
		state="recognised", spec="vdv-462-netex-schrift-v00-26d", verified=True,
		note="`sniff` knows a `PublicationDelivery` root and says there is no "
		     "reader yet. The obvious next importer after 452.",
	),

	# --- Ist-Daten: what is happening now, as a subscription -------------- #
	_part(
		"453", "Ist-Daten-Schnittstelle: Anschlusssicherung",
		"Ist-Daten", STREAM,
		"Connection protection between operators — which vehicle is waiting "
		"for which, and the subscription handshake the whole Ist-Daten family "
		"shares.",
		state="declared",
		note="The payload is close to 454's and the handshake is not built: a "
		     "source subscribes, the far side pushes, and a subscription has "
		     "to be renewed before it lapses. That is the next feeds stage.",
	),
	_part(
		"454", "Ist-Daten-Schnittstelle: Fahrplanauskunft",
		"Ist-Daten", STREAM,
		"The prognosis interface: `IstFahrt` per trip, with a predicted time "
		"at each stop it has still to call at.",
		state="read", reader="streaming",
		note="A prognosis interface rather than a positions one — most "
		     "deliveries carry no coordinate at all, so a vehicle is placed at "
		     "the last stop it stated it called at and never between stops.",
	),
	_part(
		"456", "Ist-Daten-Schnittstelle, further parts",
		"Ist-Daten", STREAM, "",
		state="unknown",
		note="Listed so the gap is visible. Nothing here has been established "
		     "against the document.",
	),

	# --- Fahrgastzählung: counted occupancy ------------------------------- #
	_part(
		"457-1", "Fahrgastzählung: Grundlagen",
		"Fahrgastzählung", STREAM,
		"What a counting system is, what it has to be able to say, and the "
		"quality it has to say it to.",
		state="declared",
	),
	_part(
		"457-2", "Fahrgastzählung: Rohdatensatz",
		"Fahrgastzählung", STREAM,
		"The counter itself: an `OccupancyMessage` saying, per counting area, "
		"how many of each class are aboard and how many that area holds.",
		state="read", reader="streaming",
		note="The one dialect where occupancy is a measurement rather than a "
		     "word somebody's threshold produced. Areas are summed, not "
		     "averaged; a faulty counter is dropped rather than read as zero.",
	),
	_part(
		"457-3", "Fahrgastzählung: Bereitstellung ausgewerteter Daten",
		"Fahrgastzählung", FOLDER,
		"Counted boardings and alightings, per door and per class, after the "
		"operator's own correction pass.",
		state="read", reader="vdv457",
		note="The only source of a boarding this product will draw as a fact. "
		     "`CountingAfterClearing` carries no per-stop time, so those rows "
		     "are matched by stop and day and flagged inexact.",
	),

	# --- IBIS-IP: the vehicle's own LAN ----------------------------------- #
	_part(
		"301-1", "IBIS-IP: Systemarchitektur",
		"IBIS-IP", VEHICLE,
		"How devices on a vehicle find each other and talk: the service "
		"model, discovery, and the transport under all of it.",
		state="declared", spec="vdv-301-1-ibis-ip-teil-1-systemarchitektur",
		verified=True,
	),
	_part(
		"301-2", "IBIS-IP: Basisdienste und gemeinsame Konventionen",
		"IBIS-IP", VEHICLE,
		"What every service shares: `Get`, `Subscribe`, `Unsubscribe`, and the "
		"shape of a response.",
		state="declared", spec="301-2-sde-v2.4-common-conventions", verified=True,
	),
	_part(
		"301-2-1", "IBIS-IP: Common structures and enumerations",
		"IBIS-IP", VEHICLE,
		"The vocabulary the rest of the family is written in — and the reason "
		"this row matters more than its number suggests: `DoorOpenState`, "
		"`GNSSQuality`, `LocationState`, `RouteDeviation`, `TripState`, "
		"`DoorCountingObjectClass` and thirty more are defined here, once.",
		state="declared", spec="301-2-1-sde-v2-4-commonstructure-enums",
		verified=True,
		note="The vocabulary the events arc is built on: a legend on a chart "
		     "is only honest if its values are the specification's own.",
	),
	_part(
		"301-2-3", "IBIS-IP: CustomerInformationService",
		"IBIS-IP", VEHICLE,
		"What the vehicle is telling passengers: the trip it is running, the "
		"next stops, the connections at them.",
		state="declared", spec="301-2-3-sdes-v2-3-customerinformationservice",
		verified=True,
	),
	_part(
		"301-2-8", "IBIS-IP: PassengerCountingService",
		"IBIS-IP", VEHICLE,
		"Counts per door and per class, at the moment the doors closed — the "
		"on-vehicle source of what 457-2 carries off it.",
		state="declared", spec="301-2-8-sds-v2-1-passengercounting", verified=True,
	),
	_part(
		"301-2-15", "IBIS-IP: DoorStateService",
		"IBIS-IP", VEHICLE,
		"Per door, to the second: whether it is open (`DoorsOpen`, "
		"`AllDoorsClosed`, `SingleDoorOpen`, `SingleDoorClosed`) and whether "
		"it is usable (`Locked`, `Normal`, `EmergencyRelease`).",
		state="declared", spec="301-2-15-sd-v2-1-doorstateservice",
		verified=True,
		note="The spec's own reason for existing is that a door release signal "
		     "does not say which door opened, and 457 requires door-specific "
		     "counts. Which is also why a dwell drawn from this is real and a "
		     "dwell drawn from positions is a guess.",
	),
	_part(
		"301-2-16", "IBIS-IP: TicketValidationService",
		"IBIS-IP", VEHICLE,
		"Each validation as it happens, and whether it was accepted "
		"(`Valid`, `notvalid`, `NoCard`).",
		state="declared", spec="301-2-16-sdes-v2-3-ticketvalidation", verified=True,
		note="Personal data the moment it is kept per card. Nothing here reads "
		     "it, and a reader would need §9's answer first.",
	),
	_part(
		"301-2-18", "IBIS-IP: SystemMonitoringService",
		"IBIS-IP", VEHICLE,
		"Whether the equipment on the vehicle is working: per device and per "
		"service, `running`, `defective`, `standby`, `notavailable`.",
		state="declared", spec="301-2-18-sdes-v2-2-systemmonitoringservice",
		verified=True,
		note="The one that turns a data-quality complaint into an answer: a "
		     "vehicle whose counter was defective all Tuesday is a fact, not a "
		     "theory about missing rows.",
	),
	_part(
		"301-3", "IBIS-IP: Netzwerkinfrastruktur",
		"IBIS-IP", VEHICLE,
		"The physical and network layer under the services.",
		state="declared", spec="301-3-sdes-network-infrastructure", verified=True,
	),

	# --- Auskunft: telling a passenger ------------------------------------ #
	_part(
		"430", "Mobile Kundeninformation im ÖV: Systemarchitektur",
		"Auskunft", STREAM,
		"How a passenger's phone is served — the architecture 431 implements.",
		state="declared", spec="vdv-430-mobile-kundeninformation-im-oev",
		verified=True,
	),
	_part(
		"431-1", "EKAP: Systemarchitektur",
		"Auskunft", STREAM,
		"The real-time communication and information platform between "
		"operators and the systems that answer passengers.",
		state="declared", spec="vdv-431-1-ekap-systemarchitektur", verified=True,
	),
	_part(
		"431-2", "EKAP: Schnittstellenbeschreibung (TRIAS)",
		"Auskunft", STREAM,
		"TRIAS: journey planning, stop events and trip information as a "
		"request/response service.",
		state="declared", spec="vdv-431-2-ekap-schnittstellenbeschreibung",
		verified=True,
		note="An outward interface as much as an inward one — the shape a "
		     "workspace would answer in, rather than only read.",
	),
]

#: By part number, for a reader that has one in its hand.
BY_PART = {one["part"]: one for one in PARTS}

#: Which format names in `sniff.py` correspond to which part, so the two lists
#: cannot drift. A delivery identified as `VDV 452` and a registry row saying
#: nothing reads 452 would be a product lying about itself in one of two
#: directions; `tests/test_vdv_registry.py` reads both back.
FORMATS = {
	"VDV 452": "452",
	"VDV 454": "454",
	"VDV 457-2": "457-2",
	"VDV 457-3": "457-3",
	"NeTEx": "462",
}


def readers() -> dict:
	"""The format-to-module map `sources.LOADERS` is, derived rather than typed.

	Two lists of which formats have a reader is one list too many: the day a
	reader ships, the registry row and the loader table have to change
	together or a customer is told the wrong thing about their own feed.

	**Folder parts only**, and the filter is load-bearing rather than tidy.
	`sources.deliver` dispatches on `load(feed, content)`; a stream part's
	reader is `streaming.py`, which has no such function and is reached by
	the dialect a Stream source declares. Without this filter a 454 document
	saved into a drop folder would dispatch to a module attribute that does
	not exist — a stack trace where the honest answer is "this arrives over a
	subscription, not in a folder".
	"""
	out = {}
	for format, part in FORMATS.items():
		one = BY_PART.get(part) or {}
		if one.get("state") == "read" and one.get("reader") and one.get("door") == FOLDER:
			out[format] = one["reader"]
	return out


def families() -> list[str]:
	seen = []
	for one in PARTS:
		if one["family"] not in seen:
			seen.append(one["family"])
	return seen


@frappe.whitelist(methods=["GET"])
def coverage() -> dict:
	"""The shelf, for the screen that shows what this product reads.

	A read and not a table somebody maintains: an operator asking "do you
	support 457-3" is asking a question about the software, and the software
	is the thing that should answer.
	"""
	if not frappe.has_permission("Transit Source", "read"):
		frappe.throw(frappe._("You cannot see this."), frappe.PermissionError)

	counted = {}
	for one in PARTS:
		counted[one["state"]] = counted.get(one["state"], 0) + 1

	return {
		"parts": PARTS,
		"families": families(),
		"counts": counted,
		"doors": {
			FOLDER: "A file, in a folder or an upload.",
			STREAM: "A subscription between two systems.",
			VEHICLE: "A service on the vehicle's own network, relayed out.",
		},
	}
