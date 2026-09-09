"""The other two live dialects, and what each one is honest about.

README §1: SIRI, GTFS-Realtime and VDV 454 are three spellings of the same four
facts, so a reader's whole job is to stop being a dialect. What differs is what
each of them actually knows, and both readers here are as interesting for what
they refuse to invent as for what they read.

VDV 454 is a prognosis interface, not a positions one: it says when a trip
called at each stop, and a great many deliveries carry no coordinate at all. So
a vehicle is placed at the last stop it *called at* — a fact the feed stated —
and never between stops, where the feed said nothing.

GTFS-Realtime is protocol buffers, read here without a dependency. That is safe
rather than clever because the wire format carries no names: a decoder is a map
from field numbers to meanings, and those numbers are frozen by a published
specification that cannot renumber without breaking every consumer in the world.
"""

import struct
import sys
from datetime import datetime, timezone

import pytest


@pytest.fixture
def streaming(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import streaming as module

	return module


@pytest.fixture
def gtfsrt(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import gtfsrt as module

	return module


# --------------------------------------------------------------------------- #
# VDV 454
# --------------------------------------------------------------------------- #

def halt(stop, planned, actual):
	return f"""
	<IstHalt>
	  <HaltID>{stop}</HaltID>
	  <Ankunftszeit>{planned}</Ankunftszeit>
	  <IstAnkunftPrognose>{actual}</IstAnkunftPrognose>
	</IstHalt>"""


def aus(halts, position="", extra="", line="U6"):
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<AUSNachricht>
  <IstFahrt>
    <LinienID>{line}</LinienID>
    <FahrtRef><FahrtID><FahrtBezeichner>t-77</FahrtBezeichner></FahrtID></FahrtRef>
    <FahrzeugID>v-1</FahrzeugID>
    {"".join(halts)}
    {position}
    {extra}
  </IstFahrt>
</AUSNachricht>""".encode()


def test_a_prognosis_message_becomes_the_same_four_facts(streaming, stub_frappe):
	stub_frappe.db.get_value = lambda *a, **k: None
	rows = streaming.read("VDV 454", aus(
		[halt("1000", "2026-09-09T08:00:00Z", "2026-09-09T08:02:30Z")],
		position="<FahrzeugPosition><GeoPunkt><X>13.4</X><Y>52.5</Y></GeoPunkt></FahrzeugPosition>",
	))
	assert len(rows) == 1
	one = rows[0]
	assert (one["vehicle"], one["line"], one["trip_key"]) == ("v-1", "U6", "t-77")
	assert (one["lat"], one["lon"]) == (52.5, 13.4)
	assert one["delay_s"] == 150


def test_a_vehicle_with_no_coordinate_is_placed_where_the_feed_said_it_was(
	streaming, stub_frappe
):
	"""At the last stop it called at, which is a fact the message stated —
	not a guess. Most 454 deliveries carry no position at all, and a reader
	that returned nothing for them would make the commonest German real-time
	interface draw an empty map."""
	import types

	stub_frappe.db.get_value = lambda *a, **k: types.SimpleNamespace(
		latitude=52.52, longitude=13.41,
	)
	rows = streaming.read("VDV 454", aus(
		[halt("1000", "2026-09-09T08:00:00Z", "2026-09-09T08:00:00Z")]
	))
	assert (rows[0]["lat"], rows[0]["lon"]) == (52.52, 13.41)


def test_a_stop_it_has_not_reached_is_not_where_it_is(streaming, stub_frappe):
	"""An `IstHalt` later in the message is a *prediction* about a stop ahead,
	and drawing a vehicle at one of those is drawing a guess as a fact — which
	`live.at` refuses for exactly the same reason."""
	seen = []
	stub_frappe.db.get_value = lambda doctype, filters, *a, **k: seen.append(filters) or None
	streaming.read("VDV 454", aus([
		halt("1000", "2026-09-09T08:00:00Z", "2026-09-09T08:00:00Z"),
		halt("1001", "2026-09-09T08:10:00Z", "2026-09-09T08:11:00Z"),
	]))
	# The later call, because both have been realised and it is the newer of
	# the two — the vehicle is at 1001, not still at 1000.
	assert seen[-1]["stop_key"] == "1001"


def test_a_journey_nothing_has_happened_on_yet_is_not_reported(streaming, stub_frappe):
	"""A message that is all prediction and no history. Reporting it would put
	a vehicle at the start of every trip that has not begun."""
	stub_frappe.db.get_value = lambda *a, **k: None
	quiet = aus([
		"""<IstHalt><HaltID>1000</HaltID>
		    <Ankunftszeit>2026-09-09T08:00:00Z</Ankunftszeit></IstHalt>"""
	])
	assert streaming.read("VDV 454", quiet) == []


def test_how_full_is_three_bands_here_and_seven_in_siri(streaming, stub_frappe):
	"""And both become a percentage, because that is what the map draws. The
	midpoint of a band rather than its edge, for the reason SIRI's does."""
	import types

	stub_frappe.db.get_value = lambda *a, **k: types.SimpleNamespace(
		latitude=52.5, longitude=13.4,
	)
	rows = streaming.read("VDV 454", aus(
		[halt("1000", "2026-09-09T08:00:00Z", "2026-09-09T08:00:00Z")],
		extra="<Auslastung>Hoch</Auslastung>",
	))
	assert rows[0]["occupancy"] == 90


# --------------------------------------------------------------------------- #
# GTFS-Realtime, built by hand
# --------------------------------------------------------------------------- #

def varint(value):
	out = bytearray()
	while True:
		byte = value & 0x7F
		value >>= 7
		out.append(byte | (0x80 if value else 0))
		if not value:
			return bytes(out)


def tag(number, wire):
	return varint((number << 3) | wire)


def block(number, payload):
	return tag(number, 2) + varint(len(payload)) + payload


def number(field, value):
	return tag(field, 0) + varint(value)


def text(field, value):
	return block(field, value.encode())


def single(field, value):
	return tag(field, 5) + struct.pack("<f", value)


def position(lat, lon):
	return block(2, single(1, lat) + single(2, lon))


def vehicle_entity(trip="t-77", route="U6", lat=52.5, lon=13.4, vehicle="v-1",
                   stamp=1789200000, occupancy=None, percentage=None):
	body = block(1, text(1, trip) + text(5, route))
	body += position(lat, lon)
	body += number(5, stamp)
	body += block(8, text(1, vehicle))
	if occupancy is not None:
		body += number(9, occupancy)
	if percentage is not None:
		body += number(10, percentage)
	return block(2, block(1, b"e1") + block(4, body))


def update_entity(trip="t-77", delay=150):
	inner = block(1, text(1, trip))
	# int32 on the wire is sign-extended to sixty-four bits, which is what
	# makes a vehicle running early interesting — see `_signed`.
	inner += tag(5, 0) + varint(delay if delay >= 0 else delay + (1 << 64))
	return block(2, block(1, b"e2") + block(3, inner))


def feed(*entities):
	return block(1, number(1, 2)) + b"".join(entities)


def test_a_feed_message_becomes_the_same_four_facts(gtfsrt):
	rows = gtfsrt.read(feed(vehicle_entity(), update_entity()))
	assert len(rows) == 1
	one = rows[0]
	assert (one["vehicle"], one["line"], one["trip_key"]) == ("v-1", "U6", "t-77")
	assert one["lat"] == pytest.approx(52.5, abs=0.0001)
	assert one["delay_s"] == 150


def test_every_vehicle_is_read_and_not_only_the_first(gtfsrt):
	"""Protobuf's repetition has no count and no marker — a repeated field
	simply appears repeatedly. A decoder that took the first occurrence would
	read one vehicle out of a feed carrying four thousand, which is a bug that
	looks exactly like a quiet network."""
	rows = gtfsrt.read(feed(
		vehicle_entity(vehicle="v-1"),
		vehicle_entity(vehicle="v-2", lat=52.6),
		vehicle_entity(vehicle="v-3", lat=52.7),
	))
	assert [one["vehicle"] for one in rows] == ["v-1", "v-2", "v-3"]


def test_a_vehicle_running_early_is_not_running_late(gtfsrt):
	"""`int32` is sign-extended to sixty-four bits, so thirty seconds early
	arrives as 18446744073709551586. Read as unsigned that is a vehicle 584
	billion years behind, and it reaches a chart before anybody notices."""
	rows = gtfsrt.read(feed(vehicle_entity(), update_entity(delay=-30)))
	assert rows[0]["delay_s"] == -30


def test_the_two_halves_of_a_feed_are_joined_on_the_trip(gtfsrt):
	"""`vehicle` says where it is and `trip_update` says how late it is; they
	are separate entities naming the same trip, and a feed carrying both is the
	normal case. A delay belonging to another trip is not this one's."""
	rows = gtfsrt.read(feed(
		vehicle_entity(trip="a", vehicle="v-a"),
		vehicle_entity(trip="b", vehicle="v-b"),
		update_entity(trip="a", delay=300),
	))
	delays = {one["vehicle"]: one["delay_s"] for one in rows}
	assert delays == {"v-a": 300, "v-b": 0}


def test_a_stop_level_delay_answers_when_there_is_no_trip_level_one(gtfsrt):
	"""Which is the commoner shape. `TripUpdate.delay` is optional and many
	producers state it per stop instead."""
	arrival = block(2, tag(1, 0) + varint(240))
	inner = block(1, text(1, "t-77")) + block(2, arrival)
	rows = gtfsrt.read(feed(
		vehicle_entity(), block(2, block(1, b"e2") + block(3, inner)),
	))
	assert rows[0]["delay_s"] == 240


def test_how_full_prefers_the_number_over_the_band(gtfsrt):
	"""A percentage the producer computed beats an enum we would have to widen
	back into one — the same order of preference SIRI's reader keeps."""
	assert gtfsrt.read(feed(vehicle_entity(percentage=72)))[0]["occupancy"] == 72
	assert gtfsrt.read(feed(vehicle_entity(occupancy=5)))[0]["occupancy"] == 97
	assert gtfsrt.read(feed(vehicle_entity()))[0]["occupancy"] == -1


def test_an_entity_with_no_position_is_not_a_vehicle_at_nought_nought(gtfsrt):
	"""A trip update on its own carries no coordinate, and every feed is full
	of them."""
	assert gtfsrt.read(feed(update_entity())) == []


def test_a_field_this_does_not_read_is_stepped_over(gtfsrt):
	"""Alerts, shapes, trip modifications, and anything a newer version of the
	specification adds. A decoder that threw on an unknown field would stop
	working the week the specification grew one."""
	extra = block(2, block(1, b"e3") + block(5, text(1, "a service alert")))
	rows = gtfsrt.read(feed(vehicle_entity(), extra))
	assert len(rows) == 1


def test_a_truncated_message_is_an_error_and_not_half_a_fleet(gtfsrt):
	"""A socket produces these. Decoded leniently, a cut-off body yields
	whatever happened to be complete — which reaches the map as a network that
	has quietly shrunk."""
	whole = feed(vehicle_entity(), vehicle_entity(vehicle="v-2"))
	with pytest.raises(ValueError):
		gtfsrt.read(whole[:-4])


def test_the_epoch_becomes_the_sites_own_clock(streaming, stub_frappe):
	"""The same question SIRI raises and the same worst-kind-of-bug if it is
	got wrong: nothing throws, every screen draws, and the punctuality is
	wrong for ever. The stub site keeps UTC."""
	rows = streaming.read("GTFS Realtime", feed(vehicle_entity(stamp=1789200000)))
	assert rows[0]["at"] == datetime.fromtimestamp(1789200000, tz=timezone.utc).replace(
		tzinfo=None
	)
