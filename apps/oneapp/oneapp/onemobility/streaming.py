"""The fourth door: a source that pushes, and never stops.

README §5 lists four doors and says the pipeline behind them is one. Three of
them end at `sources.deliver` because they are *finite*: a file arrives, it is
kept, it is read, the fetch is over. A socket is not finite. It is opened once
and then speaks for as long as the operator's day lasts, and the sentence §5
closes on is the whole of this module — *a source that appends to a buffer and
commits on a timer, reusing the same normalise and resolve steps*.

The normalise step it reuses is `live.record`, which is where every live dialect
already lands: SIRI, GTFS-Realtime and VDV 454 are three spellings of four facts
(§1), so a reader here turns one delivery into rows in that shape and nothing
downstream knows which dialect it came from.

**A stream has no end; a job must have one.** The tempting version holds the
connection open for ever, and it is wrong in three separate ways: a worker that
never returns is a worker gone, a job nobody can end cannot be redeployed past
or stopped by pausing the source, and a connection that died an hour ago looks
exactly like a quiet feed. So a window is opened, read until its deadline, and
closed; the scheduler opens the next one. The seconds between two windows are a
real gap and are the price of every one of those three properties.

**Committing is on a count and on a clock, and it needs both.** On a clock
alone, a busy network holds thousands of positions in memory between ticks and
loses all of them if the worker dies. On a count alone, a two-line operator at
four in the morning holds three rows for the whole window and the live map is
blank while the feed is working perfectly.

What is *not* here is a kept delivery. `sources.deliver` writes every fetch to a
`File` so a number can be traced back to the bytes it came from, and that is
right for a file and impossible for a stream — a day of positions is not a
delivery, and writing one `File` per frame would be a hundred thousand of them.
The observation row is its own record here, and the feed's own timestamp is on
it.
"""

import re
from datetime import datetime, timedelta, timezone

import frappe
from frappe import _
from frappe.utils import cint, convert_utc_to_system_timezone, now_datetime

from . import live

#: How long one window lasts. Just under the five minutes between two runs of
#: `run_streams`, so a window has ended before the next is enqueued — the
#: alternative is a job the deduplicating enqueue keeps skipping, which is a
#: stream that is restarted once an hour instead of once every five minutes.
WINDOW_SECONDS = 280

#: The longest a probe from the Sources screen may hold a web request. See
#: `listen_now`: this is a person waiting on a page, not a worker.
PROBE_SECONDS = 60

#: How long to wait on a stream that has gone quiet before giving up on this
#: window. Not an error: a small operator's feed at four in the morning is
#: silent for minutes at a time and is working.
IDLE_SECONDS = 60

#: Commit at whichever of these comes first. See the docstring: a count without
#: a clock leaves a quiet network's map blank, and a clock without a count
#: leaves a busy one holding thousands of rows it can lose.
COMMIT_ROWS = 400
COMMIT_SECONDS = 10

#: How many times one window will reopen a stream that ended cleanly. Most
#: SIRI endpoints answer one delivery and close, so a window is several
#: connections rather than one; a source that closes the instant it is opened
#: would otherwise be reconnected to a few thousand times in five minutes,
#: which is how a client gets blocked by the authority it is reading.
MAX_OPENS = 8

#: The most a single frame may be before this stops believing it is one. A SIRI
#: vehicle-monitoring delivery for a large network is a few hundred kilobytes; a
#: buffer past this without a closing tag in it is a source sending something
#: that is not framed the way it says it is, and growing it for ever is how a
#: worker dies.
MAX_FRAME = 16 * 1024 * 1024

#: Which live dialects have a reader, and how a connection speaking one is cut
#: into messages. Declared in the shape `sources.LOADERS` is and for the same
#: reason: a customer should be able to say what they have before we can read
#: it, and be told so plainly.
#:
#: **The framing is per format because it has to be.** A stream of XML documents
#: is self-delimiting — the closing root tag is the boundary, and `frames` finds
#: it. A protocol-buffers body is not: it carries no terminator, no length
#: prefix at the top level, and no way to tell a complete message from a
#: truncated one. Its only boundary is the end of the response, which is why
#: GTFS-Realtime is read `whole` and why the reconnect loop in `listen` is what
#: makes it a live feed at all — one body per connection, several connections
#: per window.
READERS: dict[str, tuple] = {
	"SIRI": ("_siri", "xml"),
	"VDV 454": ("_vdv454", "xml"),
	"GTFS Realtime": ("_gtfsrt", "whole"),
}

#: The most one `whole`-framed body may be. A GTFS-Realtime feed for a large
#: network is a few megabytes; past this it is not a feed and holding it in a
#: buffer is how a worker dies — the same argument `MAX_FRAME` makes for a
#: document that never closes.
MAX_BODY = 64 * 1024 * 1024


# --------------------------------------------------------------------------- #
# Framing: bytes off a socket are not documents
# --------------------------------------------------------------------------- #

_OPENS = re.compile(rb"<\s*([A-Za-z_][\w.:-]*)")


def frames(buffer: bytearray) -> list[bytes]:
	"""Take every whole document out of the buffer, leaving the tail.

	A chunk off a socket ends wherever TCP decided it ended, which is usually
	halfway through an element. Parsing that is a parse error every time, and
	the failure mode of getting it wrong is not a crash — it is a feed that
	looks broken while it is working.

	So the buffer is only read as far as a matching close tag for whatever the
	first element was, and everything after it stays for the next chunk.
	"""
	out: list[bytes] = []
	while True:
		# Past the prolog, the DOCTYPE and any comment — `<?`, `<!`.
		opened = _OPENS.search(buffer)
		if not opened:
			break
		name = opened.group(1)
		closed = re.compile(rb"</\s*" + re.escape(name) + rb"\s*>").search(
			buffer, opened.end()
		)
		if not closed:
			if len(buffer) > MAX_FRAME:
				frappe.throw(_("The stream sent {0} bytes without ending a document.")
				             .format(len(buffer)))
			break
		out.append(bytes(buffer[opened.start():closed.end()]))
		del buffer[:closed.end()]
	return out


# --------------------------------------------------------------------------- #
# SIRI
# --------------------------------------------------------------------------- #

_DURATION = re.compile(
	r"^(?P<sign>-)?P(?:(?P<d>\d+)D)?"
	r"(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>[\d.]+)S)?)?$"
)

#: SIRI's occupancy is a word, and a screen draws a percentage. The midpoint of
#: each band rather than its edge: a band is a range and its edge is a claim
#: about which side of it the bus was on, which the feed did not make.
_BANDS = {
	"empty": 5,
	"manyseatsavailable": 25,
	"seatsavailable": 45,
	"fewseatsavailable": 60,
	"standingavailable": 75,
	"standingroomonly": 80,
	"crushedstandingroomonly": 92,
	"full": 97,
	"notacceptingpassengers": 99,
}


def _local(tag: str) -> str:
	"""The tag without its namespace. SIRI documents carry one and feeds
	disagree about which, and matching on the full name is how a reader works
	against one authority and returns nothing for the next."""
	return tag.rpartition("}")[2]


def _find(node, *names: str):
	for child in node.iter():
		if _local(child.tag) in names:
			return child
	return None


def _text(node, *names: str) -> str:
	"""The first of these elements that actually says something.

	One name at a time and in the order given, which is the whole of it: a
	document-order search returns whichever happens to come first, and in VDV
	454 that is the empty `FahrtID` wrapper rather than the `FahrtBezeichner`
	inside it. Every caller here lists its names in order of preference, so
	honouring that order is the difference between reading a trip reference and
	reading nothing.
	"""
	if node is None:
		return ""
	for name in names:
		found = _find(node, name)
		if found is not None and (found.text or "").strip():
			return found.text.strip()
	return ""


def _seconds(text: str) -> int:
	"""An ISO 8601 duration, which is how SIRI says "two minutes late".

	Signed, because `-PT30S` is a bus running early and dropping the sign turns
	every early vehicle into a late one.
	"""
	matched = _DURATION.match((text or "").strip())
	if not matched:
		return 0
	part = matched.groupdict()
	total = (
		int(part["d"] or 0) * 86400
		+ int(part["h"] or 0) * 3600
		+ int(part["m"] or 0) * 60
		+ float(part["s"] or 0)
	)
	return int(-total if part["sign"] else total)


def _moment(text: str) -> datetime:
	"""A SIRI timestamp, on the site's clock.

	Every stamp in a SIRI document carries a zone and every datetime in the
	fact tables is naive site time, so this is the one place the two meet. A
	feed in UTC read as though it were Berlin is a two-hour error that looks
	like a plausible timetable, which is the worst kind there is: nothing
	throws, every screen draws, and the punctuality is wrong for ever.
	"""
	raw = (text or "").strip()
	if not raw:
		return now_datetime()
	when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
	if when.tzinfo is None:
		return when
	utc = when.astimezone(timezone.utc).replace(tzinfo=None)
	return convert_utc_to_system_timezone(utc).replace(tzinfo=None)


def _occupancy(journey) -> int:
	"""How full, as a percentage, or -1 for a vehicle with no counter.

	Three spellings, in the order of how much they actually know: a percentage
	the feed computed, a count against a capacity, and a word. -1 rather than
	nought for the last case, because an empty bus and a bus with no counter
	are different facts — `live.record` says the same thing.
	"""
	percentage = _text(journey, "OccupancyPercentage")
	if percentage:
		return max(0, min(100, int(float(percentage))))

	count = _text(journey, "PassengerCount", "TotalNumberOfPersons")
	capacity = _text(journey, "TotalCapacity", "PassengerCapacity")
	if count and capacity and float(capacity) > 0:
		return max(0, min(100, round(100 * float(count) / float(capacity))))

	word = _text(journey, "Occupancy", "OccupancyStatus").replace("_", "").lower()
	return _BANDS.get(word, -1)


def _siri(frame: bytes) -> list[dict]:
	"""One SIRI vehicle-monitoring delivery, as observations.

	`xml.etree` and not a dependency: this is four fields out of a document and
	the standard library reads it. A DOCTYPE is refused outright rather than
	parsed — an entity-expansion bomb is a few hundred bytes and no SIRI feed
	has ever needed one, so the check costs nothing and closes the whole class.
	"""
	from xml.etree import ElementTree

	if b"<!DOCTYPE" in frame[:2048]:
		frappe.throw(_("A feed may not carry an inline entity definition."))

	root = ElementTree.fromstring(frame)
	rows = []
	for activity in root.iter():
		if _local(activity.tag) != "VehicleActivity":
			continue
		journey = _find(activity, "MonitoredVehicleJourney")
		if journey is None:
			continue
		where = _find(journey, "VehicleLocation")
		if where is None:
			continue

		lat = _text(where, "Latitude")
		lon = _text(where, "Longitude")
		if not (lat and lon):
			continue

		rows.append({
			"at": _moment(
				_text(activity, "RecordedAtTime")
				or _text(root, "ResponseTimestamp")
			),
			"vehicle": _text(journey, "VehicleRef") or _text(activity, "ItemIdentifier"),
			"line": _text(journey, "LineRef", "PublishedLineName"),
			"trip_key": _text(journey, "DatedVehicleJourneyRef", "VehicleJourneyRef"),
			"lat": float(lat),
			"lon": float(lon),
			"occupancy": _occupancy(journey),
			"delay_s": _seconds(_text(journey, "Delay")),
		})
	return rows


# --------------------------------------------------------------------------- #
# VDV 454
# --------------------------------------------------------------------------- #

#: VDV's own word for how full, which is three bands rather than SIRI's seven.
#: Midpoints again, for the reason `_BANDS` gives.
_AUSLASTUNG = {"unbekannt": -1, "gering": 20, "mittel": 55, "hoch": 90}


def _vdv454(frame: bytes) -> list[dict]:
	"""One VDV 454 `AUSNachricht`, as observations.

	454 is a *prognosis* interface rather than a positions one: an `IstFahrt`
	says when a trip called at each stop and when it now expects to reach the
	rest, and a great many deliveries carry no coordinate at all. So where the
	message states a `FahrzeugPosition` that is used, and where it does not the
	vehicle is placed **at the last stop it actually called at**, whose position
	we already hold.

	That is a real claim and not a guess — the feed said the vehicle was there
	at that minute — and it is the same fact `arrivals.py` infers in the other
	direction from positions. What it is *not* is a position between stops:
	a 454 feed draws a network that hops from stop to stop, which is honest to
	what the interface says and is why a customer with 453 positions should
	connect those instead.
	"""
	from xml.etree import ElementTree

	if b"<!DOCTYPE" in frame[:2048]:
		frappe.throw(_("A feed may not carry an inline entity definition."))

	root = ElementTree.fromstring(frame)
	where: dict[str, tuple] = {}
	rows = []

	for journey in root.iter():
		if _local(journey.tag) != "IstFahrt":
			continue

		line = _text(journey, "LinienText", "LinienID")
		trip = _text(journey, "FahrtBezeichner", "FahrtID")
		vehicle = _text(journey, "FahrzeugID", "FahrzeugNummer") or trip
		if not (line or trip):
			continue

		called = None
		for halt in journey.iter():
			if _local(halt.tag) != "IstHalt":
				continue
			actual = _text(halt, "IstAbfahrtPrognose", "IstAnkunftPrognose")
			planned = _text(halt, "Abfahrtszeit", "Ankunftszeit")
			if not actual:
				continue
			when = _moment(actual)
			# The last call it has made, which is the one that says where it
			# is. A later `IstHalt` is a prediction about a stop it has not
			# reached, and drawing a vehicle at one of those is drawing a guess
			# as a fact — see `live.at` on why that is the thing not to do.
			if called and when <= called["at"]:
				continue
			called = {
				"at": when,
				"stop": _text(halt, "HaltID", "HaltestellenID"),
				"delay_s": int((when - _moment(planned)).total_seconds()) if planned else 0,
			}

		if not called:
			continue

		point = _find(journey, "FahrzeugPosition", "GeoPunkt")
		lat = _text(point, "Y", "Latitude", "Breite") if point is not None else ""
		lon = _text(point, "X", "Longitude", "Laenge") if point is not None else ""
		if not (lat and lon):
			lat, lon = _at_stop(called["stop"], where)
		if lat is None or lon is None:
			continue

		rows.append({
			"at": called["at"],
			"vehicle": vehicle,
			"line": line,
			"trip_key": trip,
			"lat": float(lat),
			"lon": float(lon),
			"occupancy": _AUSLASTUNG.get(
				_text(journey, "Auslastung", "Besetztgrad").lower(), -1
			),
			"delay_s": called["delay_s"],
		})
	return rows


def _at_stop(key: str, cache: dict):
	"""Where a stop is, by the key its feed calls it — the same natural key
	`conflicts.py` compares two sources on. Cached per frame, because a busy
	delivery names the same interchange fifty times."""
	if not key:
		return None, None
	if key not in cache:
		row = frappe.db.get_value(
			"Transit Stop", {"stop_key": key}, ["latitude", "longitude"], as_dict=True
		)
		cache[key] = (row.latitude, row.longitude) if row else (None, None)
	return cache[key]


# --------------------------------------------------------------------------- #
# GTFS-Realtime
# --------------------------------------------------------------------------- #

def _gtfsrt(frame: bytes) -> list[dict]:
	"""One protocol-buffers `FeedMessage`. The decoding is `gtfsrt.py`.

	Only the time is done here, and it is done here because it is the same
	question SIRI raises: a GTFS-Realtime timestamp is seconds since the epoch
	in UTC, every datetime in the fact tables is naive site time, and a feed
	read at the wrong offset draws a plausible and wrong timetable for ever.
	"""
	from . import gtfsrt

	rows = gtfsrt.read(frame)
	for row in rows:
		row["at"] = (
			convert_utc_to_system_timezone(
				datetime.fromtimestamp(row["at"], tz=timezone.utc).replace(tzinfo=None)
			).replace(tzinfo=None)
			if row.get("at") else now_datetime()
		)
	return rows


def read(fmt: str, frame: bytes) -> list[dict]:
	"""One frame, in whichever dialect this source speaks."""
	declared = READERS.get(fmt)
	if not declared:
		frappe.throw(_("{0} is not a live format this can read yet.").format(fmt))
	return globals()[declared[0]](frame)


def framing(fmt: str) -> str:
	"""`xml` for a dialect whose documents delimit themselves, `whole` for one
	whose only boundary is the end of the connection."""
	declared = READERS.get(fmt)
	return declared[1] if declared else "xml"


# --------------------------------------------------------------------------- #
# The window
# --------------------------------------------------------------------------- #

def _note(source: str, **values):
	frappe.db.set_value("Transit Source", source, values, update_modified=False)


def listen(source: str, seconds: int = WINDOW_SECONDS) -> dict:
	"""Hold one source's stream open for a window, committing as it goes.

	Returns rather than throws on a quiet feed: silence is not a failure, and
	marking a source Failing for it would make the badge mean "somebody is
	asleep" rather than "this is broken". A connection that refuses, drops with
	an error or answers with a status is a failure and says so on the source,
	where §5's second rule — a failing source stays visible — puts it.

	A stream that ends cleanly inside the window is reopened, because that is
	what most of them do: a SIRI endpoint answers one delivery and closes, and
	a subscription drops on the far side's own timer. Bounded, so a source that
	closes instantly is not hammered for four minutes.
	"""
	import requests

	doc = frappe.get_doc("Transit Source", source)
	if doc.status == "Paused":
		return {"listened": False, "reason": "paused"}
	if doc.kind != "Socket":
		return {"listened": False, "reason": "not a stream"}
	if not (doc.endpoint or "").startswith(("http://", "https://")):
		frappe.throw(_("A socket source needs an http:// or https:// endpoint."))
	if doc.format not in READERS:
		_note(source, last_run=now_datetime(), last_message=(
			_("{0} is not a live format this can read yet.").format(doc.format)))
		return {"listened": False, "reason": "no reader"}

	deadline = now_datetime() + timedelta(seconds=max(5, cint(seconds)))
	auth = (doc.username, doc.get_password("secret")) if doc.username else None

	state = {"pending": [], "written": 0, "seen": 0, "last": now_datetime()}

	def commit():
		if state["pending"]:
			state["written"] += live.record(state["pending"])
			state["pending"] = []
		frappe.db.commit()
		state["last"] = now_datetime()

	opens = 0
	try:
		while now_datetime() < deadline and opens < MAX_OPENS:
			opens += 1
			before = state["seen"]
			_drain(requests, doc, auth, deadline, state, commit)
			# A connection that opened, sent nothing and ended is the far side
			# refusing in a way that is not an error. Reopening it in a tight
			# loop is how a client gets blocked.
			if state["seen"] == before:
				break
	except Exception as failed:
		commit()
		_note(source, status="Failing", last_run=now_datetime(),
		      last_message=str(failed)[:400])
		frappe.db.commit()
		raise

	commit()
	seen, written = state["seen"], state["written"]
	_note(
		source,
		status="Connected" if seen else doc.status,
		last_run=now_datetime(),
		rows_seen=cint(doc.rows_seen) + written,
		last_message=(
			_("Read {0} positions over {1} connections.").format(seen, opens)
			if seen else _("The stream was open and sent nothing.")
		),
	)
	frappe.db.commit()
	return {"listened": True, "seen": seen, "written": written, "opens": opens}


def _drain(requests, doc, auth, deadline, state, commit):
	"""One connection, read until the deadline or until it stops speaking.

	The buffer lives here and not in `listen` on purpose: bytes left over when
	a connection ends are half of a document that connection was sending, and
	gluing them to the front of the next one's first frame would produce a
	document neither side ever sent.
	"""
	buffer = bytearray()
	whole = framing(doc.format) == "whole"
	answer = requests.get(
		doc.endpoint, stream=True, auth=auth, timeout=(30, IDLE_SECONDS)
	)
	try:
		answer.raise_for_status()
		for chunk in answer.iter_content(64 * 1024):
			if chunk:
				buffer.extend(chunk)
				if whole:
					# No boundary until the body ends, so nothing is read yet —
					# only the ceiling is checked, because a body that grows
					# past it is not a feed and buffering it is how a worker
					# dies.
					if len(buffer) > MAX_BODY:
						frappe.throw(_("The stream sent {0} bytes in one message.")
						             .format(len(buffer)))
				else:
					for frame in frames(buffer):
						rows = read(doc.format, frame)
						state["seen"] += len(rows)
						state["pending"].extend(rows)
			if len(state["pending"]) >= COMMIT_ROWS or (
				state["pending"]
				and (now_datetime() - state["last"]).total_seconds() >= COMMIT_SECONDS
			):
				commit()
			if now_datetime() >= deadline:
				return
	except requests.exceptions.Timeout:
		# The feed went quiet for `IDLE_SECONDS`. Everything read before that
		# is still real, and the window has time left to reconnect.
		pass
	finally:
		answer.close()

	# The body ended, which for a `whole` dialect is the only frame boundary
	# there is. Read here rather than in the loop above so a connection that
	# died mid-message contributes nothing instead of half a message —
	# a truncated protobuf decodes to something rather than to an error.
	if whole and buffer:
		rows = read(doc.format, bytes(buffer))
		state["seen"] += len(rows)
		state["pending"].extend(rows)


def run_streams():
	"""One window per socket source. Every five minutes, from `hooks.py`.

	Enqueued rather than run here for the reason `sources.poll` enqueues: this
	holds a worker for the length of a window by design, and doing that on the
	scheduler's own thread would stop every other job on the site for as long
	as the operator's day.

	`deduplicate` is what makes the windows a chain rather than a pile — a
	window that overran is not joined by a second one on the same source.
	"""
	for one in frappe.get_all(
		"Transit Source",
		filters={"status": ("!=", "Paused"), "kind": "Socket",
		         "format": ("in", sorted(READERS))},
		pluck="name",
	):
		frappe.enqueue(
			"oneapp.onemobility.streaming.listen",
			queue="long",
			timeout=WINDOW_SECONDS + 120,
			job_id=f"transit-stream-{one}",
			deduplicate=True,
			source=one,
		)


@frappe.whitelist(methods=["POST"])
def listen_now(source: str, seconds: int = 10) -> dict:
	"""The button beside a socket source: open it briefly and say what came.

	Seconds and not minutes, and capped hard, because this runs inside a web
	request: somebody has just typed an endpoint in and wants to know whether
	it answers, and holding their browser — and a gunicorn worker — for the
	length of a real window to tell them is the wrong trade twice over.

	It is a probe and not a way to start a stream by hand. The scheduler does
	that, and a second window opened alongside it would read the same frames
	into the same table.
	"""
	if not frappe.has_permission("Transit Source", "write", doc=source):
		frappe.throw(_("You cannot run this source."), frappe.PermissionError)
	return listen(source, seconds=min(cint(seconds) or 10, PROBE_SECONDS))
