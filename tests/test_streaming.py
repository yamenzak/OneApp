"""The fourth door: a source that pushes, and never stops.

Three of OneMobility's doors end at a file. This one does not end at all, and
almost everything that can go wrong with it is invisible from the outside: a
half-read document parses as an error every time, a feed in UTC read as though
it were Berlin draws a plausible and wrong timetable for ever, and a stream that
commits only on a timer loses whatever the worker was holding when it died.

So these are tests about framing, about time, and about when the buffer is
written down — not about HTTP, which is `requests`' problem.
"""

import sys
import types
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def streaming(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import streaming as module

	return module


# --------------------------------------------------------------------------- #
# One SIRI delivery, as a feed sends it
# --------------------------------------------------------------------------- #

def activity(ref="v-1", line="U6", lat="52.5", lon="13.4", extra="", at="2026-09-09T09:59:58Z"):
	return f"""
	<VehicleActivity>
	  <RecordedAtTime>{at}</RecordedAtTime>
	  <MonitoredVehicleJourney>
	    <LineRef>{line}</LineRef>
	    <FramedVehicleJourneyRef>
	      <DatedVehicleJourneyRef>t-77</DatedVehicleJourneyRef>
	    </FramedVehicleJourneyRef>
	    <VehicleLocation><Longitude>{lon}</Longitude><Latitude>{lat}</Latitude></VehicleLocation>
	    <VehicleRef>{ref}</VehicleRef>
	    {extra}
	  </MonitoredVehicleJourney>
	</VehicleActivity>"""


def siri(*bodies, ns=' xmlns="http://www.siri.org.uk/siri"'):
	inner = "".join(bodies) or activity()
	return (
		'<?xml version="1.0" encoding="UTF-8"?>'
		f"<Siri{ns}><ServiceDelivery>"
		"<ResponseTimestamp>2026-09-09T10:00:00Z</ResponseTimestamp>"
		f"<VehicleMonitoringDelivery>{inner}</VehicleMonitoringDelivery>"
		"</ServiceDelivery></Siri>"
	).encode()


# --------------------------------------------------------------------------- #
# Framing
# --------------------------------------------------------------------------- #

def test_half_a_document_is_not_a_document(streaming):
	"""A chunk off a socket ends where TCP decided it ended, which is usually
	mid-element. The failure mode of parsing it anyway is not a crash — it is a
	feed that looks broken while it is working perfectly."""
	whole = siri()
	buffer = bytearray(whole[: len(whole) // 2])
	assert streaming.frames(buffer) == []
	assert bytes(buffer) == whole[: len(whole) // 2]

	buffer.extend(whole[len(whole) // 2:])
	assert len(streaming.frames(buffer)) == 1
	assert not buffer


def test_two_documents_in_one_chunk_are_two(streaming):
	"""A busy feed does not wait for us to read one before sending the next."""
	buffer = bytearray(siri() + siri())
	assert len(streaming.frames(buffer)) == 2


def test_the_tail_of_the_next_document_is_kept(streaming):
	"""What is left after the last complete document is the beginning of one,
	and throwing it away loses every frame after the first."""
	buffer = bytearray(siri() + b"<Siri><ServiceDeliv")
	assert len(streaming.frames(buffer)) == 1
	assert bytes(buffer) == b"<Siri><ServiceDeliv"


def test_a_prolog_and_a_comment_are_not_elements(streaming):
	"""`<?xml`, `<!--` and `<!DOCTYPE` all start with a bracket and none of them
	opens a document. Treating one as the root is how the closing tag is never
	found and the buffer grows until the worker dies."""
	buffer = bytearray(b'<?xml version="1.0"?><!-- from the authority -->' + siri())
	frames = streaming.frames(buffer)
	assert len(frames) == 1 and frames[0].startswith(b"<Siri")


def test_a_stream_that_never_closes_a_document_is_refused(streaming, stub_frappe):
	"""Rather than buffered for ever. A source sending something that is not
	framed the way it says it is has to fail visibly at some size."""
	buffer = bytearray(b"<Siri>" + b"x" * (streaming.MAX_FRAME + 1))
	with pytest.raises(stub_frappe.ValidationError):
		streaming.frames(buffer)


# --------------------------------------------------------------------------- #
# SIRI
# --------------------------------------------------------------------------- #

def test_a_delivery_becomes_the_shape_every_live_source_lands_on(streaming):
	"""README §1: SIRI, GTFS-Realtime and VDV 454 are three spellings of four
	facts. A reader's whole job is to stop being a dialect."""
	rows = streaming.read("SIRI", siri())
	assert len(rows) == 1
	one = rows[0]
	assert one["vehicle"] == "v-1"
	assert one["line"] == "U6"
	assert one["trip_key"] == "t-77"
	assert (one["lat"], one["lon"]) == (52.5, 13.4)


def test_it_reads_a_feed_whichever_namespace_it_declares(streaming):
	"""Authorities disagree about the namespace and some send none at all.
	Matching the qualified name is how a reader works against one authority and
	silently returns nothing for the next."""
	assert len(streaming.read("SIRI", siri(ns=""))) == 1
	assert len(streaming.read("SIRI", siri(ns=' xmlns="http://www.siri.org.uk/siri/2.0"'))) == 1


def test_early_is_not_late(streaming):
	"""`Delay` is a signed ISO 8601 duration, and dropping the sign turns every
	vehicle running ahead of its timetable into one running behind it."""
	late = streaming.read("SIRI", siri(activity(extra="<Delay>PT2M30S</Delay>")))
	early = streaming.read("SIRI", siri(activity(extra="<Delay>-PT45S</Delay>")))
	assert late[0]["delay_s"] == 150
	assert early[0]["delay_s"] == -45


def test_a_vehicle_with_no_counter_is_not_an_empty_vehicle(streaming):
	"""-1 rather than nought, which is what `live.record` says too: an empty bus
	and a bus nobody counted are different facts and must not be one colour."""
	assert streaming.read("SIRI", siri())[0]["occupancy"] == -1


def test_occupancy_is_read_in_the_order_of_how_much_it_knows(streaming):
	"""A percentage the feed computed, then a count against a capacity, then a
	word. The word becomes the middle of its band and not an edge — a band is a
	range, and its edge is a claim about which side of it the bus was on that
	the feed never made."""
	def occupancy(extra):
		return streaming.read("SIRI", siri(activity(extra=extra)))[0]["occupancy"]

	assert occupancy("<OccupancyPercentage>72</OccupancyPercentage>") == 72
	assert occupancy("<PassengerCount>30</PassengerCount><TotalCapacity>120</TotalCapacity>") == 25
	assert occupancy("<Occupancy>full</Occupancy>") == 97
	assert 20 < occupancy("<Occupancy>seatsAvailable</Occupancy>") < 60


def test_a_vehicle_that_did_not_say_where_it_is_is_skipped(streaming):
	"""Not written at nought, nought — which is in the Atlantic, and which one
	feed's missing field would put a fleet of buses in."""
	without = activity().replace(
		"<VehicleLocation><Longitude>13.4</Longitude><Latitude>52.5</Latitude></VehicleLocation>",
		"",
	)
	assert streaming.read("SIRI", siri(without)) == []


def test_a_feed_in_utc_is_not_read_as_local_time(streaming):
	"""The worst kind of bug this module could have: nothing throws, every
	screen draws, and the punctuality is wrong for ever. The stub site keeps
	UTC, so a stamp two hours ahead has to land two hours earlier."""
	zulu = streaming.read("SIRI", siri(activity(at="2026-09-09T10:00:00Z")))[0]["at"]
	berlin = streaming.read("SIRI", siri(activity(at="2026-09-09T12:00:00+02:00")))[0]["at"]
	assert zulu == berlin == datetime(2026, 9, 9, 10, 0, 0)


def test_a_document_may_not_declare_a_doctype(streaming, stub_frappe):
	"""An entity-expansion bomb is a few hundred bytes and no SIRI feed has
	ever needed a DTD, so the whole class closes for the price of one check."""
	bomb = b'<?xml version="1.0"?><!DOCTYPE Siri [<!ENTITY a "aaaa">]>' + siri()
	with pytest.raises(stub_frappe.ValidationError):
		streaming.read("SIRI", bomb)


def test_a_dialect_with_no_reader_is_told_so(streaming, stub_frappe):
	"""The same honesty `sources.LOADERS` keeps: a customer can declare what
	they have before we can read it, and hears that rather than a parse error.
	NeTEx is the one still outstanding."""
	assert set(streaming.READERS) == {"SIRI", "VDV 454", "VDV 457-2", "GTFS Realtime"}
	with pytest.raises(stub_frappe.ValidationError):
		streaming.read("NeTEx", siri())


def test_a_dialect_says_how_its_messages_end(streaming):
	"""The decision the two new readers forced. A stream of XML documents is
	self-delimiting — the closing root tag is the boundary. A protobuf body is
	not: no terminator, no top-level length, no way to tell a complete message
	from a truncated one, and its only boundary is the end of the response."""
	assert streaming.framing("SIRI") == "xml"
	assert streaming.framing("VDV 454") == "xml"
	assert streaming.framing("GTFS Realtime") == "whole"


# --------------------------------------------------------------------------- #
# The window
# --------------------------------------------------------------------------- #

class Answer:
	def __init__(self, chunks):
		self.chunks = chunks
		self.closed = False

	def raise_for_status(self):
		pass

	def iter_content(self, size):
		for chunk in self.chunks:
			if isinstance(chunk, Exception):
				raise chunk
			yield chunk

	def close(self):
		self.closed = True


#: A connection that goes quiet, written into a connection's chunk list. The
#: exception has to be the fake module's own `Timeout`, which does not exist
#: until the module does — hence a sentinel rather than an instance.
SILENCE = object()


def fake_requests(*connections):
	"""`requests`, as far as this module uses it: one answer per connection."""
	module = types.ModuleType("requests")

	class Timeout(Exception):
		pass

	module.exceptions = types.SimpleNamespace(Timeout=Timeout)
	module.opened = []

	def get(url, **kw):
		module.opened.append(url)
		at = len(module.opened) - 1
		chunks = connections[at] if at < len(connections) else []
		return Answer([
			module.exceptions.Timeout("read timed out") if one is SILENCE else one
			for one in chunks
		])

	module.get = get
	return module


@pytest.fixture
def socket(streaming, stub_frappe, monkeypatch):
	"""One connected socket source, a clock, and a recorded `live.record`."""
	doc = types.SimpleNamespace(
		name="berlin-vm", status="Connected", kind="Stream", format="SIRI",
		endpoint="https://feed.example/vm", username="", rows_seen=0,
		get_password=lambda field: "",
	)
	stub_frappe.get_doc = lambda *a, **k: doc

	written = []
	monkeypatch.setattr(streaming.live, "record", lambda rows: written.append(list(rows)) or len(rows))

	tick = {"at": datetime(2026, 9, 9, 10, 0, 0), "by": 0}

	def clock():
		tick["at"] += timedelta(seconds=tick["by"])
		return tick["at"]

	monkeypatch.setattr(streaming, "now_datetime", clock)
	return types.SimpleNamespace(doc=doc, written=written, tick=tick)


def run(streaming, monkeypatch, requests, seconds=300):
	monkeypatch.setitem(sys.modules, "requests", requests)
	return streaming.listen("berlin-vm", seconds=seconds)


def test_a_window_reads_a_stream_and_writes_what_came(streaming, socket, monkeypatch):
	out = run(streaming, monkeypatch, fake_requests([siri(), siri()]))
	assert out["seen"] == 2
	assert out["written"] == 2


def test_it_commits_before_the_window_ends(streaming, socket, monkeypatch):
	"""The point of a buffer that commits as it goes. Held to the end, a worker
	that dies at minute four has lost four minutes of a live map — and the
	whole reason to run a window rather than one long connection is that
	workers do die."""
	monkeypatch.setattr(streaming, "COMMIT_ROWS", 2)
	run(streaming, monkeypatch, fake_requests([siri(activity(), activity("v-2")), siri()]))
	assert len(socket.written) == 2, socket.written


def test_a_quiet_feed_is_still_written_down(streaming, socket, monkeypatch):
	"""The other half, and it needs the clock rather than the count: a two-line
	operator at four in the morning holds three rows for the whole window, and
	a map that is blank while the feed works is the same bug seen from the
	other end."""
	socket.tick["by"] = 4
	monkeypatch.setattr(streaming, "COMMIT_ROWS", 1000)
	monkeypatch.setattr(streaming, "COMMIT_SECONDS", 5)
	run(streaming, monkeypatch, fake_requests([siri(), siri(), siri()]), seconds=3600)
	assert len(socket.written) > 1, socket.written


def test_a_stream_that_ends_is_reopened_inside_the_window(streaming, socket, monkeypatch):
	"""Most SIRI endpoints answer one delivery and close. A window that took
	that as the end would read one frame every five minutes."""
	requests = fake_requests([siri()], [siri()], [])
	out = run(streaming, monkeypatch, requests)
	assert out["opens"] == 3
	assert out["seen"] == 2


def test_a_stream_that_sends_nothing_is_not_hammered(streaming, socket, monkeypatch):
	"""A source closing the instant it is opened would otherwise be reconnected
	to a few thousand times in five minutes, which is how a client gets blocked
	by the authority it is reading."""
	requests = fake_requests([])
	assert run(streaming, monkeypatch, requests)["opens"] == 1
	assert len(requests.opened) == 1


def test_silence_is_not_a_failure(streaming, socket, monkeypatch, stub_frappe):
	"""A feed that goes quiet for a minute is a feed. Marking it Failing would
	make the badge mean "somebody is asleep" rather than "this is broken",
	which is the state that makes a status column worth reading."""
	out = run(streaming, monkeypatch, fake_requests([siri(), SILENCE], []))
	assert out["seen"] == 1
	assert not [w for w in stub_frappe.db.writes if (w[2] or {}).get("status") == "Failing"]


def test_a_broken_connection_is_written_on_the_source(streaming, socket, monkeypatch, stub_frappe):
	"""§5's second rule: a failing source stays visible. Five sources and one
	of them quietly stopped a fortnight ago is the failure that makes a data
	product untrustworthy."""
	requests = fake_requests([ConnectionError("refused")])
	monkeypatch.setitem(sys.modules, "requests", requests)
	with pytest.raises(ConnectionError):
		streaming.listen("berlin-vm", seconds=60)
	assert [w for w in stub_frappe.db.writes if (w[2] or {}).get("status") == "Failing"]


def test_a_paused_source_is_not_opened(streaming, socket, monkeypatch):
	socket.doc.status = "Paused"
	requests = fake_requests([siri()])
	assert run(streaming, monkeypatch, requests)["reason"] == "paused"
	assert not requests.opened


def test_a_socket_needs_a_url(streaming, socket, monkeypatch, stub_frappe):
	"""Rather than a host and port. This reads streaming HTTP, and a source
	configured for something else should say so at the first attempt."""
	socket.doc.endpoint = "tcp://feed.example:5000"
	with pytest.raises(stub_frappe.ValidationError):
		run(streaming, monkeypatch, fake_requests([]))


def test_a_source_that_is_not_a_stream_is_not_this_module(streaming, socket, monkeypatch):
	socket.doc.kind = "HTTP"
	assert run(streaming, monkeypatch, fake_requests([]))["reason"] == "not a stream"


# --------------------------------------------------------------------------- #
# The schedule
# --------------------------------------------------------------------------- #

def test_each_stream_is_one_deduplicated_job(streaming, stub_frappe):
	"""Enqueued and not run here, for the reason `sources.poll` enqueues: a
	window holds a worker for minutes by design, and doing that on the
	scheduler's own thread stops every other job on the site. `deduplicate` is
	what makes the windows a chain rather than a pile."""
	stub_frappe.get_all = lambda *a, **k: ["berlin-vm", "wien-vm"]
	streaming.run_streams()

	assert [one[0] for one in stub_frappe.enqueued] == [
		"oneapp.onemobility.streaming.listen"
	] * 2
	first = stub_frappe.enqueued[0][1]
	assert first["job_id"] == "transit-stream-berlin-vm"
	assert first["deduplicate"] is True
	assert first["timeout"] > streaming.WINDOW_SECONDS


def test_a_window_ends_before_the_next_one_is_due(streaming):
	"""The schedule and the window are one decision: a window longer than the
	five minutes between runs would be skipped by its own deduplicating enqueue
	and the stream would restart hourly instead."""
	assert streaming.WINDOW_SECONDS < 300


def test_the_scheduler_asks_for_streams_it_can_read(streaming, stub_frappe):
	"""A source declaring VDV 454 has no reader yet, and enqueuing a window
	that opens a connection to find that out is a connection for nothing."""
	asked = {}
	stub_frappe.get_all = lambda doctype, **k: asked.update(k) or []
	streaming.run_streams()
	assert asked["filters"]["kind"] == "Stream"
	assert asked["filters"]["format"] == ("in", sorted(streaming.READERS))


def test_the_pull_door_still_refuses_to_pull_a_stream(stub_frappe):
	"""`sources.fetch` and this module are the two halves of §5's four doors,
	and a socket belongs to exactly one of them. The refusal is not an error —
	a source that pushes has nothing to be asked for."""
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import sources

	stub_frappe.get_doc = lambda *a, **k: types.SimpleNamespace(
		status="Connected", kind="Stream"
	)
	assert sources.fetch("berlin-vm") == {"fetched": False, "reason": "pushed"}
