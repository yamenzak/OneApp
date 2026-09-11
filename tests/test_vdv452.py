"""The German acquisition path, and the three ways a VDV reader goes wrong.

README §1: the internal model is GTFS's and every format is an importer into
it. So none of what is below asserts that a `REC_ORT` exists anywhere after the
load — it asserts that it became a Transit Stop, which is the whole claim.

Three things can be quietly wrong here rather than loudly. Columns are
positional against the `atr` line that precedes them, so a delivery that
reorders them between versions — legal, and it happens — names a stop after its
longitude. Coordinates are integers at a scale the delivery may not declare, so
the wrong guess puts a Berlin network in the Atlantic. And a call time is
assembled from a start plus segment times rather than read, so an off-by-one in
the accumulation shifts a whole route by one leg and still looks like a
timetable.
"""

import sys
import types

import pytest


@pytest.fixture
def vdv(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import vdv452 as module

	return module


DELIVERY = """chs; "ISO8859-1"
mod; 09.09.2026; 12:00:00; free
tbl; MENGE_UNTERNEHMEN
atr; UNTERNEHMEN; UN_NAME
frm; num[3.0]; char[40]
rec; 1; "Berliner Verkehrsbetriebe"
end; MENGE_UNTERNEHMEN
tbl; REC_ORT
atr; ORT_NR; ORT_NAME; ORT_POS_LAENGE; ORT_POS_BREITE
frm; num[9.0]; char[40]; num[9.0]; num[9.0]
rec; 1000; "Hauptbahnhof"; 13369000; 52525000
rec; 1001; "Alexanderplatz"; 13413000; 52521000
rec; 1002; "Zoologischer Garten"; 13332000; 52507000
end; REC_ORT
tbl; LINIE
atr; LI_NR; LI_KUERZEL; LI_KURZNAME; VERKEHRSMITTEL
frm; num[5.0]; char[8]; char[40]; num[2.0]
rec; 100; "M41"; "Hauptbahnhof - Zoo"; 0
end; LINIE
tbl; LID_VERLAUF
atr; LI_NR; STR_LI_VAR; LI_LFD_NR; ORT_NR
frm; num[5.0]; num[3.0]; num[3.0]; num[9.0]
rec; 100; 1; 1; 1000
rec; 100; 1; 2; 1001
rec; 100; 1; 3; 1002
end; LID_VERLAUF
tbl; SEL_FZT_FELD
atr; ORT_NR; SEL_ZIEL; SEL_FZT
frm; num[9.0]; num[9.0]; num[5.0]
rec; 1000; 1001; 300
rec; 1001; 1002; 420
end; SEL_FZT_FELD
tbl; ORT_HZTF
atr; ORT_NR; HP_HZT
frm; num[9.0]; num[5.0]
rec; 1001; 60
end; ORT_HZTF
tbl; FIRMENKALENDER
atr; BETRIEBSTAG; TAGESART_NR
frm; num[8.0]; num[3.0]
rec; 20260907; 1
rec; 20260908; 1
end; FIRMENKALENDER
tbl; REC_FRT
atr; FRT_FID; LI_NR; STR_LI_VAR; FRT_START; TAGESART_NR; FRT_TEXT
frm; num[9.0]; num[5.0]; num[3.0]; num[5.0]; num[3.0]; char[40]
rec; 900001; 100; 1; 25200; 1; "Zoo"
end; REC_FRT
tbl; REC_UMLAUF
atr; UM_UID; FRT_FID
frm; num[9.0]; num[9.0]
rec; 5; 900001
end; REC_UMLAUF
"""


# --------------------------------------------------------------------------- #
# The format
# --------------------------------------------------------------------------- #

def test_a_delivery_is_read_table_by_table(vdv):
	found = vdv.tables(DELIVERY)
	assert set(found) >= {"REC_ORT", "LINIE", "REC_FRT", "LID_VERLAUF"}
	assert found["REC_ORT"][1]["ORT_NAME"] == "Alexanderplatz"
	assert found["REC_FRT"][0]["FRT_START"] == "25200"


def test_a_record_is_positional_against_the_line_above_it(vdv):
	"""The failure that produces a stop called 52525000. A delivery that
	reorders its columns between two versions is legal, and a reader that
	remembered the first order would not notice."""
	swapped = DELIVERY.replace(
		"atr; ORT_NR; ORT_NAME; ORT_POS_LAENGE; ORT_POS_BREITE",
		"atr; ORT_NAME; ORT_NR; ORT_POS_LAENGE; ORT_POS_BREITE",
	).replace('rec; 1000; "Hauptbahnhof";', 'rec; "Hauptbahnhof"; 1000;')
	assert vdv.tables(swapped)["REC_ORT"][0]["ORT_NAME"] == "Hauptbahnhof"


def test_the_planning_tables_this_product_does_not_draw_are_skipped(vdv):
	"""Vehicle duties, rosters, blocks. Skipped rather than stored and ignored,
	so nobody later mistakes an empty table for a missing feature — and because
	modelling them is the second model §1 exists to refuse."""
	assert "REC_UMLAUF" not in vdv.tables(DELIVERY)


def test_a_delivery_says_what_it_is_written_in(vdv):
	"""Read off the raw bytes because it has to be: the answer decides how to
	decode them, so decoding first to find out is circular."""
	assert vdv._charset(DELIVERY.encode("iso-8859-1")) == "iso-8859-1"
	assert vdv._charset(b'chs; "UTF8"\ntbl; REC_ORT\n') == "utf-8"
	assert vdv._charset(b"tbl; REC_ORT\n") == vdv.DEFAULT_CHARSET


def test_a_coordinate_is_read_at_whichever_scale_it_is_in(vdv):
	"""Two are in use, a great many deliveries declare neither, and the wrong
	guess puts a Berlin network in the Atlantic rather than throwing. Nothing on
	Earth is ambiguous between them, which is what makes the guess safe."""
	assert vdv._degrees(13369000) == pytest.approx(13.369, abs=0.001)
	# The same longitude in tenths of an arc-second.
	assert vdv._degrees(13.369 * vdv.ARCSECOND_TENTHS) == pytest.approx(13.369, abs=0.001)
	assert vdv._degrees("") == 0.0


# --------------------------------------------------------------------------- #
# The model it lands on
# --------------------------------------------------------------------------- #

class Wrote:
	"""What the loader made, without a database under it."""

	def __init__(self, stub_frappe, vdv, monkeypatch):
		self.records = []
		self.schedule = []
		self.runs = {}
		monkeypatch.setattr(vdv.conflicts, "record", self.record)
		monkeypatch.setattr(vdv.timetablelib, "replace", self.replace)
		monkeypatch.setattr(vdv.timetablelib, "runs", self.run)
		monkeypatch.setattr(vdv.model, "ensure_all", lambda: None)
		stub_frappe.get_doc = lambda *a, **k: types.SimpleNamespace(
			name="feed-1", source="vdv", db_set=lambda *a, **k: None,
		)
		stub_frappe.db.get_value = lambda *a, **k: None

	def record(self, doctype, key, values, source="", feed=""):
		self.records.append((doctype, key, values))
		return f"{doctype[-4:].lower()}-{key}"

	def replace(self, source, rows, valid_from=None):
		self.schedule = list(rows)
		return len(self.schedule)

	def run(self, feed, trips):
		self.runs = trips
		return len(trips)

	def of(self, doctype):
		return [one for one in self.records if one[0] == doctype]


@pytest.fixture
def wrote(vdv, stub_frappe, monkeypatch):
	return Wrote(stub_frappe, vdv, monkeypatch)


def test_a_delivery_becomes_stops_lines_and_an_agency(vdv, wrote):
	counts = vdv.load("feed-1", DELIVERY.encode("iso-8859-1"))
	assert (counts["stops"], counts["lines"], counts["trips"]) == (3, 1, 1)

	stop = wrote.of("Transit Stop")[1][2]
	assert stop["stop_name"] == "Alexanderplatz"
	assert stop["latitude"] == pytest.approx(52.521, abs=0.001)

	line = wrote.of("Transit Line")[0][2]
	assert line["short_name"] == "M41" and line["mode"] == "Bus"


def test_the_natural_key_is_the_number_the_operator_uses(vdv, wrote):
	"""`ORT_NR` and `LI_NR`, which are what the authority's own systems say —
	so a GTFS export of the same network and this delivery are comparable, which
	is what makes §6's precedence mean anything."""
	vdv.load("feed-1", DELIVERY.encode("iso-8859-1"))
	assert [one[1] for one in wrote.of("Transit Stop")] == ["1000", "1001", "1002"]
	assert [one[1] for one in wrote.of("Transit Line")] == ["100"]


def test_a_call_time_is_the_start_plus_the_legs_before_it(vdv, wrote):
	"""The arithmetic VDV makes necessary and GTFS does not: travel times are
	stated once per segment rather than once per trip, so a call is assembled.
	An off-by-one here shifts a whole route by one leg and still looks like a
	timetable."""
	vdv.load("feed-1", DELIVERY.encode("iso-8859-1"))
	assert [one["arrives_s"] for one in wrote.schedule] == [
		25200,                    # 07:00, the trip's own start
		25200 + 300,              # five minutes to Alexanderplatz
		25200 + 300 + 60 + 420,   # a minute standing there, then seven more
	]
	assert [one["seq"] for one in wrote.schedule] == [1, 2, 3]


def test_a_dwell_is_between_arriving_and_leaving_and_not_before_arriving(vdv, wrote):
	"""The other half of the same off-by-one, and the one that would make every
	vehicle appear to wait at a stop it has not reached."""
	vdv.load("feed-1", DELIVERY.encode("iso-8859-1"))
	at_alex = wrote.schedule[1]
	assert at_alex["departs_s"] - at_alex["arrives_s"] == 60


def test_a_day_type_becomes_the_weekdays_it_actually_falls_on(vdv, wrote):
	"""VDV states a calendar as dates and this product's timetable is a weekly
	pattern, so the pattern is derived rather than declared. The fixture's
	day-type runs on a Monday and a Tuesday and comes out as those two."""
	vdv.load("feed-1", DELIVERY.encode("iso-8859-1"))
	assert wrote.schedule[0]["days"] == 0b11


def test_a_trip_with_no_pattern_is_not_a_trip_with_no_stops(vdv, wrote):
	"""Skipped, rather than written as a run that calls nowhere — which reads
	on every screen as a service that exists and never arrives."""
	orphan = DELIVERY.replace("rec; 900001; 100; 1; 25200; 1;",
	                          "rec; 900001; 100; 9; 25200; 1;")
	vdv.load("feed-1", orphan.encode("iso-8859-1"))
	assert wrote.schedule == []


def test_a_zipped_delivery_and_a_bare_one_are_both_read(vdv, wrote):
	"""A zip of `.x10` files is the common shape and a single file is legal.
	Refusing one for not being the other is a support ticket, not a validation."""
	import io
	import zipfile

	packed = io.BytesIO()
	with zipfile.ZipFile(packed, "w") as archive:
		archive.writestr("basis.x10", DELIVERY.encode("iso-8859-1"))
	assert vdv.load("feed-1", packed.getvalue())["stops"] == 3


def test_the_reader_is_reachable_by_the_format_a_customer_declares(stub_frappe):
	"""`sources.deliver` does not know which loader it called, which is §1 in
	one line of code: the model is one and the formats are importers onto it."""
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import sources

	assert sources.LOADERS == {
		"GTFS": "gtfs", "VDV 452": "vdv452", "VDV 457-3": "vdv457",
	}
