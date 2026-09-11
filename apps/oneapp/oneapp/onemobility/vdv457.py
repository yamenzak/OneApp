"""VDV 457-3 — how many got on, measured at the door.

The counting-data interface, and the only source in this module that states a
boarding. Everything else here observes a vehicle: where it was, how late it
was, how full it was. 457-3 is the automatic counter's own output — per stop,
per door, per passenger class, how many went in and how many came out — and
that is a different kind of fact from all of them.

`model.STOP_EVENT`'s docstring has always refused a boarding, and it was right
to: the only one available was the difference between two occupancy readings,
which is an estimate with a counter's error at each end. It still refuses that
one. What this adds is the measured kind, and the rule the column now keeps is
that a boarding is written **only where a counter reported it** — `-1`
everywhere else, the same distinction `occupancy` keeps between "empty" and
"nobody said".

**Why the counts do not go straight into `stopEvent`.** That table is derived:
`arrivals.build` deletes a day and writes it again from positions, which is
what makes re-running it free of consequence. A boarding written there would
be erased by the next nightly sweep. So a delivery lands in `stopCount` as it
arrived and the build *joins* it on — the counts are an input to that pass, not
an output of it.

A delivery replaces the journeys it names rather than adding to them, because
457-3 sends a journey twice on purpose: `RawData` first and `after clearing`
once the operator's own correction has run. The second is the better answer to
the same question, and appending would make a corrected journey count twice.

Schema: IBIS-IP_PassengerCountingServiceBGS_457-3_V1.0.xsd (457-3 V1.0, on
IBIS-IP 2.0), published at https://www.vdv.de/afzs.aspx.
"""

import zipfile
from io import BytesIO

import frappe
from frappe import _

from ..shared import facts
from . import model
from .streaming import _find, _ibis, _local, _moment, _text

#: Classes that are people. A bicycle through a door is not a boarding, and a
#: pram is counted beside the adult pushing it — see `streaming._RIDERS`, which
#: draws the same line for the same reason.
RIDERS = {"adult", "child", "unidentified"}

#: A stop the vehicle actually served. Anything else — skipped, diverted, a
#: status this does not know — is not a visit and must not be written as one
#: with nought boardings.
SERVED = "normal"

#: The most events one delivery may carry. A month of a fleet arriving as a
#: single file is a file that should have been several, and reading it into
#: memory is how a worker dies.
MAX_EVENTS = 200_000


def _documents(content: bytes) -> list[bytes]:
	"""The XML in a delivery, which may be one file or a zip of them.

	Both are ordinary: an IBIS-IP service answers with one document, and a
	nightly SFTP drop is usually a zip of a day's journeys.
	"""
	if content[:2] == b"PK":
		with zipfile.ZipFile(BytesIO(content)) as bundle:
			return [
				bundle.read(one)
				for one in bundle.namelist()
				if one.lower().endswith(".xml") and not one.startswith("__MACOSX")
			]
	return [content]


def _counted(area) -> tuple[int, int, bool]:
	"""In and out across every door of one counting area.

	Summed rather than kept per door: a door is an implementation detail of the
	vehicle and nothing above this asks which one somebody used. What it does
	not sum is the object classes — a bike is not a passenger.
	"""
	boarded = alighted = 0
	seen = False
	for count in area.iter():
		if _local(count.tag) != "Count":
			continue
		if _text(count, "ObjectClass").strip().lower() not in RIDERS:
			continue
		seen = True
		boarded += int(float(_ibis(count, "In") or 0))
		alighted += int(float(_ibis(count, "Out") or 0))
	return boarded, alighted, seen


def _dwell(area) -> int:
	"""Doors open to doors shut, which is the dwell rather than a sample of it.

	`arrivals.py` infers this from how long a vehicle stayed inside a radius,
	at whatever resolution its positions arrive — a coarse ruler it is honest
	about. The counter knows exactly, because opening the doors is the event
	it is counting.
	"""
	header = _find(area, "HeaderCounting")
	if header is None:
		return 0
	started, ended = _ibis(header, "TimeStampEventStart"), _ibis(header, "TimeStampEventEnd")
	if not (started and ended):
		return 0
	try:
		gap = (_moment(ended) - _moment(started)).total_seconds()
	except ValueError:
		return 0
	return max(int(gap), 0) if gap < 3_600 else 0


def events(content: bytes) -> list[dict]:
	"""Every counted stop visit in a delivery, as `stopCount` rows.

	Parsing only — no database, so the shape can be tested against VDV's own
	published examples without a site.
	"""
	from xml.etree import ElementTree

	rows: list[dict] = []
	for document in _documents(content):
		if b"<!DOCTYPE" in document[:2048]:
			frappe.throw(_("A delivery may not carry an inline entity definition."))

		root = ElementTree.fromstring(document)
		for journey in root.iter():
			if _local(journey.tag) != "PassengerCountingServiceJourney":
				continue
			head = _find(journey, "HeaderServiceJourney")
			trip = _text(head, "ServiceJourneyID") if head is not None else ""
			# The corrected form carries no per-stop time — see `exact` on
			# `model.STOP_COUNT`. This is the only clock it has.
			departed = _text(head, "ServiceJourneyDepartureTime") if head is not None else ""

			for message in journey.iter():
				if _local(message.tag) != "PassengerCountingMessage":
					continue
				data = _find(message, "HeaderData")
				vehicle = _text(data, "VehicleID") if data is not None else ""

				for event in message.iter():
					if _local(event.tag) != "PassengerCountingEvent":
						continue
					if len(rows) >= MAX_EVENTS:
						frappe.throw(
							_("This delivery carries more than {0} counted stops. "
							  "Send it in parts.").format(MAX_EVENTS)
						)

					where = _find(event, "StopInformation")
					if where is None:
						continue
					if _text(where, "StopStatus").strip().lower() != SERVED:
						continue
					stop = _ibis(where, "StopRef")
					if not stop:
						continue

					boarded = alighted = dwell = 0
					when = None
					counted = False
					for area in event.iter():
						if _local(area.tag) != "CountingArea":
							continue
						up, down, seen = _counted(area)
						if not seen:
							continue
						counted = True
						boarded += up
						alighted += down
						dwell = max(dwell, _dwell(area))
						header = _find(area, "HeaderCounting")
						stamp = _ibis(header, "TimeStamp") if header is not None else ""
						if stamp and when is None:
							when = _moment(stamp)

					if not counted:
						continue
					exact = when is not None
					if when is None:
						if not departed:
							continue
						when = _moment(departed)

					rows.append({
						"at": when,
						"stop": stop,
						"vehicle": vehicle,
						"trip_key": trip,
						"boarded": boarded,
						"alighted": alighted,
						"dwell_s": dwell,
						"exact": 1 if exact else 0,
						"hour": when.hour,
						"dow": when.weekday(),
					})
	return rows


def load(feed_name: str, content: bytes) -> dict:
	"""Read one 457-3 delivery into `stopCount`. Returns what it found.

	Same contract as `gtfs.load` and `vdv452.load` — `sources.deliver` does not
	know which of them it called — with one difference worth naming: those two
	write the *model*, the lines and stops a network is made of, and this
	writes a fact. A 457-3 delivery names stops by the key its own feed uses
	and says nothing about where they are, so it cannot bring a network into
	existence; it is counting one that a planning feed already described.
	"""
	feed = frappe.get_doc("Transit Feed", feed_name)
	model.ensure_all()

	rows = events(content)
	if not rows:
		feed.db_set("notes", _("No counted stop visits in this delivery."),
		            update_modified=False)
		return {"stops": 0, "trips": 0, "counted": 0}

	# A journey is the unit this interface delivers, and it delivers each one
	# twice on purpose — raw, then corrected. So a re-delivery replaces the
	# journeys it names rather than adding to them.
	journeys = sorted({row["trip_key"] for row in rows if row["trip_key"]})
	if journeys:
		marks = ", ".join(["%s"] * len(journeys))
		frappe.db.sql(
			f"DELETE FROM `{model.STOP_COUNT.table}` WHERE `trip_key` IN ({marks})",
			tuple(journeys),
		)
	else:
		# A delivery with no journey reference cannot be replaced by key, so it
		# is replaced by the window it covers. Narrower than a day on purpose:
		# two vehicles counted in the same hour arrive in the same file.
		frappe.db.sql(
			f"DELETE FROM `{model.STOP_COUNT.table}` WHERE `at` BETWEEN %s AND %s",
			(min(r["at"] for r in rows), max(r["at"] for r in rows)),
		)

	written = facts.write(model.STOP_COUNT, rows)
	frappe.db.commit()

	feed.db_set("stops_seen", len({row["stop"] for row in rows}), update_modified=False)
	return {
		"stops": len({row["stop"] for row in rows}),
		"trips": len(journeys),
		"counted": written,
	}


def since(start, end) -> dict:
	"""Counted visits in a window, keyed the way `arrivals.build` joins them.

	Two translations happen here. The first is the stop: `stopCount` keeps the
	key the feed delivered — the same natural key `conflicts.py` compares two
	sources on — and a visit is keyed by the `Transit Stop` it resolved to, so
	the join goes through `stop_key`. Counts for a stop no planning feed has
	described yet are simply not returned; they stay in the table and join on
	their own once it is.

	The second is the clock. The key is `(vehicle, stop)` and not the
	timestamp, because a counter stamps the moment its doors opened and an
	inferred visit is stamped when the vehicle was first *seen* near the stop.
	Matching on the minute would drop most of the joins for a reason that has
	nothing to do with either being wrong. A vehicle calling at one stop twice
	in a day is a second lap, and the caller picks the nearest in time.
	"""
	if not facts.exists(model.STOP_COUNT):
		return {}

	rows = frappe.db.sql(
		f"""SELECT c.`at`, s.`name` AS `stop`, c.`vehicle`, c.`exact`,
		           c.`boarded`, c.`alighted`, c.`dwell_s`
		    FROM `{model.STOP_COUNT.table}` c
		    JOIN `tabTransit Stop` s ON s.`stop_key` = c.`stop`
		    WHERE c.`at` >= %s AND c.`at` < %s""",
		(start, end),
		as_dict=True,
	)
	found: dict = {}
	for row in rows:
		found.setdefault((row["vehicle"], row["stop"]), []).append(row)
	return found
