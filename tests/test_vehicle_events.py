"""What a vehicle says about itself, and the one rule the table rests on.

`vdv301.py` is small and two things in it are load-bearing enough that
getting either wrong is invisible until the table is unusable.

**Edges, not samples.** A door state service answers "closed" every second
for eight hours. A reader that writes those down has not built an event tier,
it has built a worse copy of `observation` — and it will not look broken, it
will look slow, a quarter later.

**The vocabulary is the specification's.** `AllDoorsClosed`, not
`all_doors_closed`. A legend is only honest if its values are the ones the
operator's own supplier uses, and a chart whose values were renamed for
tidiness is one nobody can check against their own system.
"""

import sys
from datetime import datetime, timedelta

import pytest


@pytest.fixture
def vdv301(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import vdv301 as module

	return module


def at(minute: int, second: int = 0):
	return datetime(2026, 9, 12, 7, minute, second)


def door(minute, second, value, part="1"):
	return {"kind": "door", "part": part, "value": value, "at": at(minute, second)}


# --------------------------------------------------------------------------- #
# The rule
# --------------------------------------------------------------------------- #

def test_only_a_change_is_written(vdv301):
	"""The whole size argument. Six reports, two of them news."""
	rows = vdv301.read("1042", [
		door(10, 0, "AllDoorsClosed"),
		door(10, 5, "AllDoorsClosed"),
		door(10, 10, "AllDoorsClosed"),
		door(12, 0, "DoorsOpen"),
		door(12, 5, "DoorsOpen"),
		door(12, 20, "AllDoorsClosed"),
	])
	assert [one["value"] for one in rows] == [
		"AllDoorsClosed", "DoorsOpen", "AllDoorsClosed",
	]


def test_each_door_is_its_own_state(vdv301):
	"""Door 1 closing says nothing about door 2, and a reader that kept one
	state per vehicle would drop every second door's events."""
	rows = vdv301.read("1042", [
		door(10, 0, "SingleDoorOpen", part="1"),
		door(10, 0, "SingleDoorOpen", part="2"),
		door(10, 8, "SingleDoorClosed", part="1"),
	])
	assert len(rows) == 3
	assert {one["part"] for one in rows} == {"1", "2"}


def test_an_unchanged_state_is_news_again_after_a_long_silence(vdv301):
	"""Without this a vehicle parked overnight writes nothing at all, and a
	reader cannot tell "unchanged" from "the bridge died at 22:40"."""
	rows = vdv301.read("1042", [
		door(0, 0, "AllDoorsClosed"),
		{"kind": "door", "part": "1", "value": "AllDoorsClosed",
		 "at": at(0, 0) + timedelta(seconds=vdv301.STALE_S + 1)},
	])
	assert len(rows) == 2


def test_the_state_carries_between_calls(vdv301):
	"""A relay every five minutes must not re-write the first event of each
	batch — which is a fact table with a heartbeat in it."""
	seen = {}
	first = vdv301.read("1042", [door(10, 0, "AllDoorsClosed")], seen=seen)
	again = vdv301.read("1042", [door(11, 0, "AllDoorsClosed")], seen=seen)
	assert len(first) == 1 and not again


# --------------------------------------------------------------------------- #
# The vocabulary
# --------------------------------------------------------------------------- #

def test_the_values_are_the_specifications_own(vdv301):
	"""VDV 301-2-1, chapters 3.9 and 3.10. Spelled as that document spells
	them, because an operator checks a legend against their own supplier."""
	assert vdv301.KNOWN["door"] == (
		"DoorsOpen", "AllDoorsClosed", "SingleDoorOpen", "SingleDoorClosed",
	)
	assert vdv301.KNOWN["door_operation"] == ("Locked", "Normal", "EmergencyRelease")
	assert "offroute" in vdv301.KNOWN["deviation"]
	assert "Wheelchair" in vdv301.CLASSES and "Pram" in vdv301.CLASSES


def test_a_value_nobody_has_seen_is_still_written(vdv301):
	"""An enumeration is a known set, not a closed one. A vehicle reporting
	something new is news; dropping it is losing the one row worth reading."""
	rows = vdv301.read("1042", [door(10, 0, "DoorsHalfOpen")])
	assert len(rows) == 1 and rows[0]["value"] == "DoorsHalfOpen"
	assert not vdv301.is_known("door", "DoorsHalfOpen")


def test_trouble_is_stamped_on_the_row(vdv301):
	"""The attention list is a filter on a column, not a scan with a list of
	pairs — the same reason `hour` is denormalised off `at`."""
	rows = vdv301.read("1042", [
		{"kind": "door_operation", "part": "3", "value": "EmergencyRelease", "at": at(10)},
		{"kind": "door_operation", "part": "2", "value": "Normal", "at": at(10)},
	])
	stamped = {one["part"]: one["trouble"] for one in rows}
	assert stamped["3"] == 1 and stamped["2"] == 0


def test_a_service_we_do_not_model_is_skipped_rather_than_stored(vdv301):
	rows = vdv301.read("1042", [
		{"kind": "video", "value": "recording", "at": at(10)},
		door(10, 0, "DoorsOpen"),
	])
	assert [one["kind"] for one in rows] == ["door"]


def test_every_kind_is_attributable_to_a_part(vdv301):
	"""A kind drawn on a chart with no VDV part behind it is a claim nobody
	can check."""
	from oneapp.onemobility import vdv

	for kind, part in vdv301.KINDS.items():
		assert part in vdv.BY_PART, f"{kind} names {part}, which is not on the shelf"
		assert kind in vdv301.KNOWN


# --------------------------------------------------------------------------- #
# Edges back into durations
# --------------------------------------------------------------------------- #

def test_a_span_is_the_gap_between_two_edges(vdv301):
	rows = vdv301.read("1042", [
		door(10, 0, "SingleDoorOpen"),
		door(10, 14, "SingleDoorClosed"),
	])
	held = vdv301.spans(rows, "door")
	assert held[0]["seconds"] == 14
	# The last state has no end, and closing it at the batch boundary would
	# invent a door closing because a window ended.
	assert held[-1]["until"] is None


def test_dwell_is_the_union_of_the_open_doors(vdv301):
	"""A vehicle with two doors open at once stood there once. Summing per
	door would say it stopped for twice as long as it did."""
	rows = vdv301.read("1042", [
		door(10, 0, "SingleDoorOpen", part="1"),
		door(10, 2, "SingleDoorOpen", part="2"),
		door(10, 18, "SingleDoorClosed", part="1"),
		door(10, 20, "SingleDoorClosed", part="2"),
	])
	assert vdv301.dwell(rows) == 20


def test_dwell_is_nought_where_no_door_ever_opened(vdv301):
	rows = vdv301.read("1042", [door(10, 0, "AllDoorsClosed")])
	assert vdv301.dwell(rows) == 0


# --------------------------------------------------------------------------- #
# The tier, and the door
# --------------------------------------------------------------------------- #

def test_the_tier_is_edges_and_keeps_them_longer_than_positions(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import model

	assert model.VEHICLE_EVENT.name == "vehicleEvent"
	# A tenth the rows, so twice the window costs a fifth as much.
	assert model.VEHICLE_EVENT.hot_days > model.OBSERVATION.hot_days

	columns = model.VEHICLE_EVENT.columns
	# Generic on purpose: a column per service would make "read the next VDV
	# service" a migration, and 301 alone has twenty-three of them.
	for one in ("kind", "part", "value", "number", "trouble"):
		assert one in columns
	# Filtered on directly rather than joined to a list of pairs.
	assert ("trouble", "at") in model.VEHICLE_EVENT.keys

	assert model.VEHICLE_EVENT in model.ALL
	assert model.EVENT_HOUR in model.ALL and model.EVENT_DAY in model.ALL


def test_the_relay_door_is_permissioned_like_reporting_a_position(stub_frappe):
	"""Writing what a fleet did is a write about the fleet."""
	import inspect

	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import live

	body = inspect.getsource(live.relay)
	assert 'has_permission("Transit Vehicle", "create")' in body
	assert "PermissionError" in body
	# One vehicle per call, which is what lets the reader hold a state and
	# drop a repeat.
	assert "_last_seen(vehicle)" in body
