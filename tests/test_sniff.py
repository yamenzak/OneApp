"""What is this, actually.

The format dropdown asks a customer a question about a specification, and the
delivery can answer it itself. Every test here is one of the two halves of
that: the recognition, and the grace — a gzip nobody mentioned, a feed one
folder down, a dropdown that has been wrong for a month.

The rule the whole module turns on is that the *file* wins. A declaration
breaks a tie and is written down when it disagrees, and never overrides what is
actually in the bytes.
"""

import gzip
import io
import sys
import tarfile
import zipfile

import pytest


@pytest.fixture
def sniff(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import sniff as module

	return module


def zipped(names: dict, prefix="") -> bytes:
	out = io.BytesIO()
	with zipfile.ZipFile(out, "w") as bundle:
		for name, body in names.items():
			bundle.writestr(prefix + name, body)
	return out.getvalue()


GTFS = {
	"agency.txt": "agency_id,agency_name\n1,Stadtwerke\n",
	"stops.txt": "stop_id,stop_name,stop_lat,stop_lon\n1,Hbf,50.9,6.9\n",
	"routes.txt": "route_id,route_short_name,route_type\n1,16,0\n",
	"trips.txt": "route_id,service_id,trip_id\n1,w,t1\n",
	"stop_times.txt": "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n"
	                  "t1,08:00:00,08:00:00,1,1\n",
}


# --------------------------------------------------------------------------- #
# Recognising the thing
# --------------------------------------------------------------------------- #

def test_a_gtfs_zip_is_recognised_by_what_is_in_it(sniff):
	found = sniff.identify(zipped(GTFS), "export_2026-09-11.dat")
	assert found.format == "GTFS"
	assert found.certainty == "exact"


def test_the_extension_is_not_what_decides(sniff):
	"""The field most likely to be wrong. A supplier's nightly drop is called
	whatever their script calls it."""
	assert sniff.identify(zipped(GTFS), "timetable.xml").format == "GTFS"
	assert sniff.identify(zipped(GTFS), "").format == "GTFS"


def test_an_occupancy_message_is_read_off_its_root_element(sniff):
	found = sniff.identify(b"<?xml version='1.0'?><OccupancyMessage/>", "a.txt")
	assert (found.format, found.certainty) == ("VDV 457-2", "exact")


def test_a_namespace_nobody_agrees_on_does_not_decide(sniff):
	found = sniff.identify(b'<siri:Siri xmlns:siri="http://www.siri.org.uk/siri"/>')
	assert found.format == "SIRI"


def test_a_vdv_452_delivery_is_recognised_by_its_own_table_lines(sniff):
	body = b"tbl; REC_ORT\natr; ORT_NR\ntbl; LINIE\natr; LI_NR\n"
	found = sniff.identify(body, "whatever.x10")
	assert (found.format, found.certainty) == ("VDV 452", "exact")
	assert "LINIE" in found.found


def test_protocol_buffers_are_recognised_without_a_name(sniff):
	"""GTFS-Realtime carries no name of its own: a FeedMessage opens with
	field 1 length-delimited, and its header's first field is "2.0"."""
	body = b"\x0a\x07\x0a\x032.0\x10\x00"
	found = sniff.identify(body, "feed")
	assert found.format == "GTFS Realtime"


# --------------------------------------------------------------------------- #
# The grace
# --------------------------------------------------------------------------- #

def test_a_gzip_nobody_mentioned_is_unwrapped(sniff):
	found = sniff.identify(gzip.compress(b"<OccupancyMessage/>"), "counts.bin")
	assert found.format == "VDV 457-2"
	assert any("gzip" in note for note in found.notes)


def test_a_feed_one_folder_down_is_still_a_feed(sniff):
	"""The commonest packaging mistake there is, and not an error."""
	found = sniff.identify(zipped(GTFS, prefix="gtfs_export/"))
	assert found.format == "GTFS"
	assert found.certainty == "likely"
	assert any("folder" in note for note in found.notes)


def test_a_tar_is_as_good_as_a_zip(sniff):
	out = io.BytesIO()
	with tarfile.open(fileobj=out, mode="w") as bundle:
		for name, body in GTFS.items():
			raw = body.encode()
			info = tarfile.TarInfo(name)
			info.size = len(raw)
			bundle.addfile(info, io.BytesIO(raw))
	assert sniff.identify(out.getvalue(), "drop.tar").format == "GTFS"


def test_a_feed_missing_one_core_file_is_still_read_and_says_which(sniff):
	partial = {k: v for k, v in GTFS.items() if k != "stop_times.txt"}
	found = sniff.identify(zipped(partial))
	assert found.format == "GTFS"
	assert found.certainty == "likely"
	assert any("no timetable" in note for note in found.notes)


def test_an_archive_of_xml_is_identified_from_the_first_one(sniff):
	"""How a nightly 457-3 drop arrives: a zip of a day's journeys."""
	body = b"<PassengerCountingServiceBGS_457-3.GetAllDataResponse/>"
	found = sniff.identify(zipped({"j1.xml": body, "j2.xml": body}))
	assert found.format == "VDV 457-3"
	assert found.certainty == "likely"


# --------------------------------------------------------------------------- #
# When it cannot say
# --------------------------------------------------------------------------- #

def test_nothing_recognised_says_what_was_found(sniff):
	"""The one outcome a customer can act on. "This contains agency.txt and
	stops.txt but no routes" beats "could not read"."""
	found = sniff.identify(zipped({"readme.md": "hello", "notes.txt": "hi"}))
	assert not found
	assert found.found == ["notes.txt", "readme.md"]


def test_an_xml_this_does_not_read_names_its_root(sniff):
	found = sniff.identify(b"<GanzAndereNachricht><x/></GanzAndereNachricht>")
	assert not found
	assert any("GanzAndereNachricht" in note for note in found.notes)


def test_one_csv_is_not_a_gtfs_feed_and_says_why(sniff):
	found = sniff.identify(b"stop_id,stop_name,stop_lat,stop_lon\n1,Hbf,50.9,6.9\n",
	                       "stops.txt")
	assert not found
	assert any("zip of several" in note for note in found.notes)


def test_an_empty_delivery_is_not_a_mystery(sniff):
	assert sniff.identify(b"").notes == ["The delivery was empty."]


def test_a_broken_zip_says_so_rather_than_looking_like_a_document(sniff):
	found = sniff.identify(b"PK\x03\x04not really a zip at all")
	assert not found
	assert any("could not be opened" in note for note in found.notes)


# --------------------------------------------------------------------------- #
# The file beats the dropdown
# --------------------------------------------------------------------------- #

def test_a_declaration_that_disagrees_is_written_down_and_overruled(sniff):
	found = sniff.reconcile(sniff.identify(zipped(GTFS)), "VDV 452")
	assert found.format == "GTFS"
	assert found.certainty == "likely"
	assert any("set to VDV 452" in note for note in found.notes)


def test_a_declaration_that_agrees_changes_nothing(sniff):
	found = sniff.reconcile(sniff.identify(zipped(GTFS)), "GTFS")
	assert (found.format, found.certainty) == ("GTFS", "exact")
	assert found.notes == []


def test_detect_is_not_a_disagreement(sniff):
	found = sniff.reconcile(sniff.identify(zipped(GTFS)), "Detect")
	assert found.notes == []


def test_a_delivery_nothing_recognised_keeps_the_declaration_to_fall_back_on(sniff):
	"""`reconcile` leaves an unrecognised delivery alone, so `deliver` can try
	the declared reader rather than refusing outright — a format we sniff badly
	is our problem, not the customer's."""
	found = sniff.reconcile(sniff.identify(b"\x00\x01\x02\x03"), "GTFS")
	assert not found.format


# --------------------------------------------------------------------------- #
# And the door uses it
# --------------------------------------------------------------------------- #

def test_detect_is_the_default_on_a_new_source(stub_frappe):
	import json
	import pathlib

	here = pathlib.Path(__file__).resolve().parent.parent
	# The generated doctype, because that is what a customer's form reads.
	spec = json.loads((
		here / "apps/oneapp/oneapp/onemobility/doctype/transit_source/transit_source.json"
	).read_text())
	field = next(f for f in spec["fields"] if f["fieldname"] == "format")
	assert field["default"] == "Detect"
	assert field["options"].startswith("Detect\n")


def test_deliver_reads_the_delivery_rather_than_the_dropdown(stub_frappe):
	import inspect
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import sources

	body = inspect.getsource(sources.deliver)
	assert "sniff.identify" in body
	assert "guess.format or doc.format" in body, (
		"a format we sniff badly must fall back to what the customer declared"
	)
