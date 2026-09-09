"""GTFS-Realtime, without a dependency.

GTFS-Realtime is protocol buffers, and the two ways to read it are a library
and the wire format. The library is `protobuf` plus `gtfs-realtime-bindings`,
which is a C extension and a generated module on every tenant bench to decode
four fields out of a message we already know the shape of. The wire format is
varints and length-delimited blocks, and reading the subset this product draws
is the file below.

**What makes that safe rather than clever** is that protobuf's wire format
carries no names — a decoder is a map from field *numbers* to meanings, and
those numbers are frozen by the specification. `gtfs-realtime.proto` has not
renumbered a field since it was published, and cannot: doing so would break
every consumer in the world. So the table in `FIELDS` below is not a guess about
somebody's implementation, it is the published contract.

What is read: a vehicle's position, its occupancy, which trip and route it is
on, and the delay its trip update states. What is skipped: alerts, shapes,
trip modifications, and every field this product does not draw — skipped by
falling off the end of a `match`, which is also how a decoder survives a feed
using a newer version of the specification than this one.

Derived from no Frappe code. The format is Google's, published under the
Apache 2 licence as a specification; nothing here is copied from an
implementation of it.
"""

from frappe.utils import cint

#: Protobuf wire types. Only three of the six are still in use, and only these
#: three appear in a GTFS-Realtime message.
VARINT, FIXED64, LENGTH, FIXED32 = 0, 1, 2, 5

#: How full, as GTFS-Realtime's `OccupancyStatus` enum, turned into the
#: percentage every screen here draws. The midpoint of each band rather than an
#: edge, for the reason `streaming._BANDS` gives: a band is a range, and its
#: edge is a claim about which side of it the vehicle was on.
OCCUPANCY = {0: 5, 1: 25, 2: 60, 3: 80, 4: 92, 5: 97, 6: 99}


def _varint(data: bytes, at: int) -> tuple[int, int]:
	"""One base-128 varint, and where it ended."""
	value, shift = 0, 0
	while at < len(data):
		byte = data[at]
		at += 1
		value |= (byte & 0x7F) << shift
		if not byte & 0x80:
			return value, at
		shift += 7
		if shift > 70:
			break
	raise ValueError("a varint that never ends")


def fields(data: bytes):
	"""Every `(number, wire type, value)` in one message, in order.

	A repeated field appears repeatedly, which is the whole of protobuf's
	repetition — there is no count and no marker, so a decoder that took the
	first occurrence of field 2 would read one vehicle out of a feed carrying
	four thousand.
	"""
	at = 0
	while at < len(data):
		tag, at = _varint(data, at)
		number, wire = tag >> 3, tag & 0x07
		if wire == VARINT:
			value, at = _varint(data, at)
		elif wire == LENGTH:
			size, at = _varint(data, at)
			value, at = data[at:at + size], at + size
			if len(value) != size:
				raise ValueError("a block that runs past the end of the message")
		elif wire == FIXED32:
			value, at = data[at:at + 4], at + 4
		elif wire == FIXED64:
			value, at = data[at:at + 8], at + 8
		else:
			raise ValueError(f"wire type {wire} is not one this reads")
		yield number, wire, value


def _first(data: bytes, number: int, wire: int = LENGTH):
	for found, kind, value in fields(data):
		if found == number and kind == wire:
			return value
	return None


def _text(data: bytes, number: int) -> str:
	found = _first(data, number)
	return found.decode("utf-8", "replace") if found is not None else ""


def _number(data: bytes, number: int):
	for found, kind, value in fields(data):
		if found == number and kind == VARINT:
			return value
	return None


def _float(data: bytes, number: int):
	"""A 32-bit float, unpacked by hand rather than by `struct.unpack` on a
	slice that may be short — a truncated message is a thing a socket produces
	and it must not take the whole window with it."""
	import struct

	raw = _first(data, number, FIXED32)
	if raw is None or len(raw) != 4:
		return None
	return struct.unpack("<f", raw)[0]


def _signed(value):
	"""Protobuf's `int32` is a varint sign-extended to 64 bits, so a delay of
	one second early arrives as 18446744073709551615. Read as unsigned it is a
	vehicle 584 billion years late, which is the kind of number that reaches a
	chart before anybody notices."""
	if value is None:
		return None
	if value >= 1 << 63:
		return value - (1 << 64)
	return value


#: The field numbers this reads, by the message they belong to. Frozen by the
#: specification — see the docstring on why that is what makes this safe.
FIELDS = {
	"entity": 2,           # FeedMessage.entity
	"trip_update": 3,      # FeedEntity.trip_update
	"vehicle": 4,          # FeedEntity.vehicle
	"vp_trip": 1,          # VehiclePosition.trip
	"vp_position": 2,      # VehiclePosition.position
	"vp_timestamp": 5,     # VehiclePosition.timestamp
	"vp_vehicle": 8,       # VehiclePosition.vehicle
	"vp_occupancy": 9,     # VehiclePosition.occupancy_status
	"vp_percentage": 10,   # VehiclePosition.occupancy_percentage
	"pos_lat": 1,          # Position.latitude
	"pos_lon": 2,          # Position.longitude
	"trip_id": 1,          # TripDescriptor.trip_id
	"route_id": 5,         # TripDescriptor.route_id
	"vehicle_id": 1,       # VehicleDescriptor.id
	"vehicle_label": 2,    # VehicleDescriptor.label
	"tu_trip": 1,          # TripUpdate.trip
	"tu_delay": 5,         # TripUpdate.delay
	"tu_stop_time": 2,     # TripUpdate.stop_time_update
	"stu_arrival": 2,      # StopTimeUpdate.arrival
	"ste_delay": 1,        # StopTimeEvent.delay
}


def read(frame: bytes) -> list[dict]:
	"""One `FeedMessage`, as observations in `live.record`'s shape.

	Two passes, because the two halves of a GTFS-Realtime feed are separate
	entities that name the same trip: `vehicle` says where it is, `trip_update`
	says how late it is, and a feed carrying both is the normal case. Joined on
	the trip id — the only thing both of them state.
	"""
	delays: dict[str, int] = {}
	positions = []

	for number, _wire, value in fields(frame):
		if number != FIELDS["entity"] or not isinstance(value, (bytes, bytearray)):
			continue

		update = _first(value, FIELDS["trip_update"])
		if update is not None:
			trip = _first(update, FIELDS["tu_trip"])
			key = _text(trip, FIELDS["trip_id"]) if trip else ""
			if key:
				delay = _signed(_number(update, FIELDS["tu_delay"]))
				if delay is None:
					# No trip-level delay, which is common: it is stated per
					# stop instead, and the first one still ahead of the
					# vehicle is the one a screen means by "how late is it".
					stop = _first(update, FIELDS["tu_stop_time"])
					arrival = _first(stop, FIELDS["stu_arrival"]) if stop else None
					delay = _signed(_number(arrival, FIELDS["ste_delay"])) if arrival else None
				if delay is not None:
					delays[key] = int(delay)

		vehicle = _first(value, FIELDS["vehicle"])
		if vehicle is None:
			continue
		where = _first(vehicle, FIELDS["vp_position"])
		if where is None:
			continue
		lat, lon = _float(where, FIELDS["pos_lat"]), _float(where, FIELDS["pos_lon"])
		if lat is None or lon is None:
			continue

		trip = _first(vehicle, FIELDS["vp_trip"])
		descriptor = _first(vehicle, FIELDS["vp_vehicle"])
		percentage = _number(vehicle, FIELDS["vp_percentage"])
		status = _number(vehicle, FIELDS["vp_occupancy"])

		positions.append({
			"at": _number(vehicle, FIELDS["vp_timestamp"]),
			"vehicle": (
				_text(descriptor, FIELDS["vehicle_id"]) if descriptor else ""
			) or (_text(descriptor, FIELDS["vehicle_label"]) if descriptor else ""),
			"line": _text(trip, FIELDS["route_id"]) if trip else "",
			"trip_key": _text(trip, FIELDS["trip_id"]) if trip else "",
			"lat": lat,
			"lon": lon,
			"occupancy": (
				max(0, min(100, cint(percentage))) if percentage is not None
				else OCCUPANCY.get(status, -1)
			),
		})

	for one in positions:
		one["delay_s"] = delays.get(one["trip_key"], 0)
	return positions
