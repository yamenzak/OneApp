"""What a vehicle says about itself, and the vocabulary it says it in.

Every other reader here takes a *feed* — a network, a timetable, a position.
This one takes the things that happen on one vehicle during a shift: a door
opened, a door jammed, the trip ended, the counter broke, the GPS lost its
fix. Small facts, each with a moment and a name, and between them the answer
to most of the questions an operator actually asks after a bad Tuesday.

## Where it comes from, and why that is the hard part

IBIS-IP (VDV 301) is a **vehicle LAN protocol**. The services talk to each
other over the bus inside one vehicle — the ticket printer to the on-board
computer, the counter to the display — and nothing outside the vehicle is a
participant. So there is no endpoint to poll and no folder to walk: something
on the vehicle has to subscribe to the services it cares about and relay what
it hears. `live.report` is where that relay lands, `vdv.py` marks the whole
301 family `vehicle` for exactly this reason, and the parser below is the
small end of the work.

That shape is also why this module takes **already-parsed structures** rather
than bytes. A bridge on a vehicle has done the XML; asking it to re-serialise
an `IBIS-IP.dateTime` document so we can parse it again would be two parsers
and one more thing to disagree about.

## Edges, not samples

The one rule the whole table rests on. A door state service will happily
answer "closed" every second for eight hours; writing that down turns a
useful fact table into a worse copy of `observation`. **A row is written only
where the state changed**, which is what makes "the third door on 1042 was
jammed from 07:12 to 07:41" a query over eleven rows rather than over two
million.

`changed()` is the whole of it, and it is here rather than in the bridge
because a bridge that filters is a bridge that has to be trusted and updated.

## A row says what it ended

Storing edges leaves a question: how long was the door open? That is the gap
between two rows, and an aggregate that had to read every row in order to find
it would defeat the tier. So each row carries `was` — the state it ended — and
`number`, how long that state had lasted. At `at`, this part went from `was`
to `value`, having been `was` for `number` seconds.

Stamped on the row that *ends* a state rather than by updating the row that
began it, which is what keeps this table append-only.

## The enumerations are the specification's own

Copied from VDV 301-2-1 (01/2023) chapters 2.23, 2.24 and 3.x, spelled as
that document spells them — `AllDoorsClosed`, not `all_doors_closed`. Two
reasons, and the second is the real one. A legend on a chart is only honest
if its values are the ones the operator's own supplier uses. And a value we
have never seen must still land: an enumeration is a *known* set, not a
closed one, and a vehicle reporting something not below is written down as
what it said rather than dropped — `KNOWN` is what the UI colours, not what
the table accepts.
"""

import frappe
from frappe import _
from frappe.utils import cint, get_datetime

#: What kind of thing happened. Ours rather than VDV's — one word per service
#: we read, because a chart's first cut is "show me door events" and the
#: service name is too long to be a chip.
DOOR = "door"
DOOR_OPERATION = "door_operation"
TRIP_STATE = "trip_state"
LOCATION = "location"
DEVIATION = "deviation"
GNSS = "gnss"
DEVICE = "device"
SERVICE = "service"
VALIDATION = "validation"
COUNTING = "counting"

#: Every kind, and which VDV part it comes from — read by the registry's own
#: test and by the facet bar, so a kind cannot be drawn without being
#: attributable.
KINDS = {
	DOOR: "301-2-15",
	DOOR_OPERATION: "301-2-15",
	TRIP_STATE: "301-2-1",
	LOCATION: "301-2-1",
	DEVIATION: "301-2-1",
	GNSS: "301-2-1",
	DEVICE: "301-2-18",
	SERVICE: "301-2-18",
	VALIDATION: "301-2-16",
	COUNTING: "301-2-8",
}

#: The values each kind may carry, from VDV 301-2-1. A value outside these is
#: still written — see the module docstring — and simply has no colour.
KNOWN = {
	# 3.9 DoorOpenStateEnumeration
	DOOR: ("DoorsOpen", "AllDoorsClosed", "SingleDoorOpen", "SingleDoorClosed"),
	# 3.10 DoorOperationStateEnumeration
	DOOR_OPERATION: ("Locked", "Normal", "EmergencyRelease"),
	# 3.27 TripStateEnumeration
	TRIP_STATE: ("EmptyRun", "OnTrip", "OffTrip", "TripBreak", "OffDuty", "unknown"),
	# 3.17 LocationStateEnumeration
	LOCATION: ("AfterStop", "AtStop", "BetweenStop", "BeforeStop"),
	# 3.19 RouteDeviationEnumeration
	DEVIATION: ("onroute", "offroute", "unknown"),
	# 3.14 GNSSQualityEnumeration
	GNSS: ("dGPS", "Estimated", "GPS", "NotValid", "Unknown"),
	# 3.5 DeviceStateEnumeration
	DEVICE: ("defective", "notavailable", "running", "readyForShutdown"),
	# 3.22 ServiceStateEnumeration
	SERVICE: ("defective", "notrunning", "running", "starting", "standby"),
	# 3.25 TicketValidationEnumeration
	VALIDATION: ("Valid", "notvalid", "NoCard"),
	# 3.8 DoorCountingQualityEnumeration
	COUNTING: ("Defect", "Other", "Regular", "Sabotage"),
}

#: Which values mean something is wrong. The one piece of judgement in this
#: module, and it is what turns a stream of states into an attention list: a
#: door held on emergency release and a counter reporting sabotage are the
#: rows somebody should see without having to ask.
TROUBLE = {
	(DOOR_OPERATION, "EmergencyRelease"),
	(DOOR_OPERATION, "Locked"),
	(DEVIATION, "offroute"),
	(GNSS, "NotValid"),
	(DEVICE, "defective"),
	(SERVICE, "defective"),
	(COUNTING, "Defect"),
	(COUNTING, "Sabotage"),
}

#: 3.7 DoorCountingObjectClassEnumeration. Not an event value — a column on a
#: count — but it belongs beside the rest of the vocabulary, and it is the
#: reason a boarding can be "two adults, a pram and a bike" rather than four.
CLASSES = ("Adult", "Bike", "Child", "Pram", "Wheelchair", "Unidentified", "Other")

#: How long a state may go unrepeated before a repeat counts as news again.
#: Without it a vehicle that sits `AllDoorsClosed` overnight writes nothing at
#: all and a reader cannot tell "unchanged" from "the bridge died at 22:40".
#: Fifteen minutes is short enough to see a gap and long enough that a
#: heartbeat is not a fact table.
STALE_S = 900


def is_known(kind: str, value: str) -> bool:
	return value in (KNOWN.get(kind) or ())


def is_trouble(kind: str, value: str) -> bool:
	return (kind, value) in TROUBLE


def changed(previous: dict | None, kind: str, part: str, value: str, at) -> bool:
	"""Whether this is news, which is the only reason to write a row.

	`previous` is the last row for this `(vehicle, kind, part)` — the caller
	holds it, because the caller is reading a batch and a lookup per event
	would be one query per door per stop.
	"""
	if not previous:
		return True
	if (previous.get("value") or "") != (value or ""):
		return True

	# The same state again, long enough later that the silence was itself
	# worth recording. See `STALE_S`.
	before = previous.get("at")
	if not before:
		return True
	return (get_datetime(at) - get_datetime(before)).total_seconds() >= STALE_S


def read(vehicle: str, reported: list[dict], seen: dict | None = None) -> list[dict]:
	"""One relay's worth of events, as rows for the `vehicleEvent` tier.

	`reported` is what the bridge heard, each entry `{kind, value, at}` with
	an optional `part` (a `DoorID`, a device id), `number` (a count, a span in
	seconds) and the service fields a 301 device does *not* know — `line` and
	`trip_key` — which arrive empty from a vehicle and are filled in later by
	`arrivals.py`, exactly as 457-2's rows are.

	`seen` is the last value per `(kind, part)`, carried across calls by the
	caller so a window of relays is one conversation rather than several.
	"""
	if not vehicle:
		frappe.throw(_("An event has to name the vehicle it happened on."))

	state = seen if seen is not None else {}
	rows = []

	for one in reported or []:
		kind = (one.get("kind") or "").strip()
		if kind not in KINDS:
			# Named rather than ignored: a bridge relaying a service we have
			# not modelled should be a question somebody can answer, not a
			# silence. The caller logs it; nothing is written.
			continue

		at = one.get("at")
		if not at:
			continue

		part = str(one.get("part") or "")[:64]
		value = str(one.get("value") or "")[:64]
		key = (kind, part)

		if not changed(state.get(key), kind, part, value, at):
			continue

		when = get_datetime(at)
		# What this row ends, and how long that lasted. The pair is what makes
		# the row self-describing and what lets `eventHour` hold a
		# distribution of durations without anything having to read the table
		# in order. An event the caller gave its own `number` keeps it — a
		# count is a number too, and only a state has a span.
		before = state.get(key)
		was = (before or {}).get("value") or ""
		lasted = cint(one.get("number"))
		if before and not lasted:
			lasted = max(int((when - get_datetime(before["at"])).total_seconds()), 0)

		rows.append({
			"at": when,
			"vehicle": vehicle,
			"line": one.get("line") or "",
			"trip_key": one.get("trip_key") or "",
			"stop": one.get("stop") or "",
			"kind": kind,
			"part": part,
			"value": value,
			"was": was,
			"number": lasted,
			"trouble": 1 if is_trouble(kind, value) else 0,
			"hour": when.hour,
			"dow": when.weekday(),
		})
		state[key] = {"value": value, "at": when}

	return rows


def spans(rows: list[dict], kind: str) -> list[dict]:
	"""Turn edges back into durations: how long each state lasted.

	The other half of storing edges. "Door 3 was open for 14 seconds" is not a
	row — it is the gap between two rows — and every screen that wants a dwell
	or an outage wants this rather than the edges themselves.

	The last state of a batch has no end and is returned with `until` empty
	rather than closed at the batch boundary, which would invent a door
	closing because a window ended.
	"""
	held = [one for one in rows if one.get("kind") == kind]
	held.sort(key=lambda one: (one.get("part") or "", get_datetime(one["at"])))

	out = []
	for index, one in enumerate(held):
		after = held[index + 1] if index + 1 < len(held) else None
		same = after and (after.get("part") or "") == (one.get("part") or "")
		until = get_datetime(after["at"]) if same else None
		out.append({
			"part": one.get("part") or "",
			"value": one.get("value") or "",
			"from": get_datetime(one["at"]),
			"until": until,
			"seconds": int((until - get_datetime(one["at"])).total_seconds()) if until else None,
		})
	return out


def dwell(rows: list[dict]) -> int:
	"""How long the doors were open, in seconds. The measured dwell.

	`stopEvent.dwell_s` is inferred from positions — the time a vehicle spent
	inside a stop's radius, honest to the feed's own resolution and no finer.
	This is the real thing, and 301-2-15 exists because of exactly this
	distinction: the spec's own stated purpose is that a door *release* signal
	does not say which door opened, and 457 needs door-specific timing.

	Summed over the union rather than per door, because a vehicle with two
	doors open at once stood there once.
	"""
	open_spans = [
		one for one in spans(rows, DOOR)
		if one["value"] in ("DoorsOpen", "SingleDoorOpen") and one["seconds"]
	]
	if not open_spans:
		return 0

	open_spans.sort(key=lambda one: one["from"])
	total, edge = 0, None
	for one in open_spans:
		start, end = one["from"], one["from"] + _delta(one["seconds"])
		if edge and start <= edge:
			if end > edge:
				total += int((end - edge).total_seconds())
				edge = end
			continue
		total += one["seconds"]
		edge = end
	return total


def _delta(seconds: int):
	from datetime import timedelta

	return timedelta(seconds=seconds)


@frappe.whitelist(methods=["GET"])
def vocabulary() -> dict:
	"""The event vocabulary, for a legend that has to match the specification.

	Sent rather than duplicated in the browser for the reason every other
	declared list here is: a chart drawing a value the server never writes,
	or missing one it does, is a legend that is quietly wrong.
	"""
	return {
		"kinds": [
			{
				"kind": kind,
				"part": part,
				"values": list(KNOWN.get(kind) or ()),
				"trouble": [value for (one, value) in TROUBLE if one == kind],
			}
			for kind, part in KINDS.items()
		],
		"classes": list(CLASSES),
	}
