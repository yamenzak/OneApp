"""VDV 457-3, and the one number this module refused until it existed.

`model.STOP_EVENT` has always declined to carry a boarding, and its docstring
says why: the only one available was the difference between two occupancy
readings, which is an estimate with a counter's error at each end. 457-3 is the
counter itself — in and out, per door, per class — so the refusal narrows from
"no boardings" to "no *inferred* boardings", and every test here is about
keeping that line in the right place.

The other half is where the counts live. `arrivals.build` deletes a day of
`stopEvent` and writes it again, so a count written there would be erased by
the next sweep. They land in `stopCount` and are joined on — an input to that
pass rather than an output of it.
"""

import sys
import zipfile
from io import BytesIO

import pytest


@pytest.fixture
def vdv457(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import vdv457 as module

	return module


def counting(stop, adult_in, adult_out, door="1L", extra=""):
	return f"""
	  <Counting>
	    <DoorID><Value>{door}</Value></DoorID>
	    <DoorState><OpenState><Value>SingleDoorOpen</Value></OpenState></DoorState>
	    <Count>
	      <ObjectClass>Adult</ObjectClass>
	      <In><Value>{adult_in}</Value></In>
	      <Out><Value>{adult_out}</Value></Out>
	    </Count>
	    {extra}
	  </Counting>"""


def visit(stop, doors, status="normal", at="2018-10-26T21:33:52",
          started="2018-10-26T21:33:52", ended="2018-10-26T21:34:22"):
	return f"""
	  <PassengerCountingEvent>
	    <StopInformation>
	      <StopStatus>{status}</StopStatus>
	      <StopRef><Value>{stop}</Value></StopRef>
	    </StopInformation>
	    <CountingArea>
	      <AreaID>00</AreaID>
	      <HeaderCounting QueryType="at stop">
	        <SequentialNumber>1</SequentialNumber>
	        <TimeStamp><Value>{at}</Value></TimeStamp>
	        <TimeStampEventStart><Value>{started}</Value></TimeStampEventStart>
	        <TimeStampEventEnd><Value>{ended}</Value></TimeStampEventEnd>
	      </HeaderCounting>
	      {"".join(doors)}
	    </CountingArea>
	  </PassengerCountingEvent>"""


def delivery(visits, journey="16_01", vehicle="K-HP4711", kind="RawData"):
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<PassengerCountingServiceBGS_457-3.GetAllDataResponse>
  <PassengerCountingServiceJourney>
    <HeaderServiceJourney>
      <ServiceJourneyID>{journey}</ServiceJourneyID>
      <DataType>{kind}</DataType>
      <Destination>Bonn-Rathaus</Destination>
    </HeaderServiceJourney>
    <PassengerCountingMessage>
      <HeaderData>
        <TypeOfSurvey>automatic</TypeOfSurvey>
        <VehicleID>{vehicle}</VehicleID>
      </HeaderData>
      {"".join(visits)}
    </PassengerCountingMessage>
  </PassengerCountingServiceJourney>
</PassengerCountingServiceBGS_457-3.GetAllDataResponse>""".encode()


# --------------------------------------------------------------------------- #
# What it reads
# --------------------------------------------------------------------------- #

def test_a_counted_stop_becomes_one_row(vdv457):
	rows = vdv457.events(delivery([visit("PP_4607", [counting("PP_4607", 12, 13)])]))
	assert len(rows) == 1
	one = rows[0]
	assert (one["stop"], one["vehicle"], one["trip_key"]) == ("PP_4607", "K-HP4711", "16_01")
	assert (one["boarded"], one["alighted"]) == (12, 13)


def test_the_doors_are_summed_because_nothing_above_asks_which_one(vdv457):
	rows = vdv457.events(delivery([visit("PP_4607", [
		counting("PP_4607", 12, 13, door="1L"),
		counting("PP_4607", 23, 12, door="2L"),
	])]))
	assert (rows[0]["boarded"], rows[0]["alighted"]) == (35, 25)


def test_children_board_and_bicycles_do_not(vdv457):
	extra = """
	    <Count><ObjectClass>Child</ObjectClass>
	      <In><Value>5</Value></In><Out><Value>1</Value></Out></Count>
	    <Count><ObjectClass>Bike</ObjectClass>
	      <In><Value>9</Value></In><Out><Value>9</Value></Out></Count>"""
	rows = vdv457.events(delivery([visit("PP_4607", [
		counting("PP_4607", 10, 2, extra=extra),
	])]))
	assert (rows[0]["boarded"], rows[0]["alighted"]) == (15, 3)


def test_the_dwell_is_the_doors_and_not_a_radius(vdv457):
	"""`arrivals.py` infers dwell from how long a vehicle stayed inside a
	circle, at whatever resolution its positions arrive. The counter knows,
	because opening the doors is the event it is counting."""
	rows = vdv457.events(delivery([visit(
		"PP_4607", [counting("PP_4607", 1, 1)],
		started="2018-10-26T21:33:52", ended="2018-10-26T21:34:22",
	)]))
	assert rows[0]["dwell_s"] == 30


def test_a_stop_that_was_not_served_is_not_a_visit_with_no_boardings(vdv457):
	skipped = delivery([visit("PP_4607", [counting("PP_4607", 0, 0)], status="not served")])
	assert vdv457.events(skipped) == []


def test_every_stop_on_the_journey_is_read(vdv457):
	rows = vdv457.events(delivery([
		visit("PP_4607", [counting("PP_4607", 12, 13)], at="2018-10-26T21:33:52"),
		visit("PP_4608", [counting("PP_4608", 12, 1)], at="2018-10-26T21:34:52"),
		visit("PP_4609", [counting("PP_4609", 3, 20)], at="2018-10-26T21:39:52"),
	]))
	assert [one["stop"] for one in rows] == ["PP_4607", "PP_4608", "PP_4609"]


def test_a_zip_of_journeys_is_a_delivery_too(vdv457):
	"""One document is what an IBIS-IP service answers with; a zip is what a
	nightly SFTP drop looks like."""
	bundle = BytesIO()
	with zipfile.ZipFile(bundle, "w") as out:
		out.writestr("a.xml", delivery(
			[visit("PP_4607", [counting("PP_4607", 1, 0)])], journey="j1"))
		out.writestr("b.xml", delivery(
			[visit("PP_4608", [counting("PP_4608", 2, 0)])], journey="j2"))
	rows = vdv457.events(bundle.getvalue())
	assert sorted(one["trip_key"] for one in rows) == ["j1", "j2"]


def test_an_inline_entity_definition_is_refused(vdv457, stub_frappe):
	with pytest.raises(Exception):
		vdv457.events(
			b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///etc/passwd">]>'
			b"<PassengerCountingServiceBGS_457-3.GetAllDataResponse/>"
		)


# --------------------------------------------------------------------------- #
# VDV's own published examples
#
# The shapes above are built by hand so one thing can be varied at a time.
# These two are the files VDV ships with the schema, rebuilt to the same
# structure: a three-stop journey, raw and then corrected.
# --------------------------------------------------------------------------- #

def test_the_published_raw_journey_reads_end_to_end(vdv457):
	rows = vdv457.events(delivery([
		visit("PP_4607", [
			counting("PP_4607", 12, 13, door="1L", extra="""
	    <Count><ObjectClass>Child</ObjectClass>
	      <In><Value>22</Value></In><Out><Value>10</Value></Out></Count>"""),
			counting("PP_4607", 23, 12, door="2L", extra="""
	    <Count><ObjectClass>Child</ObjectClass>
	      <In><Value>5</Value></In><Out><Value>6</Value></Out></Count>"""),
		], at="2018-10-26T21:33:52"),
	], kind="RawData"))
	assert (rows[0]["boarded"], rows[0]["alighted"]) == (62, 41)


def test_a_corrected_journey_replaces_the_raw_one_rather_than_adding_to_it(vdv457):
	"""457-3 sends a journey twice on purpose — `RawData`, then `after
	clearing` once the operator's own correction has run. Appending would make
	the corrected journey count twice, so `load` deletes the journeys a
	delivery names before writing them."""
	import inspect

	body = inspect.getsource(vdv457.load)
	assert "DELETE FROM" in body
	assert "`trip_key` IN" in body


# --------------------------------------------------------------------------- #
# Where they live
# --------------------------------------------------------------------------- #

def test_the_counts_have_their_own_table(stub_frappe):
	"""And not a column on `stopEvent`, which `arrivals.build` deletes and
	rewrites every night — a boarding written there would not survive it."""
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import model

	assert model.STOP_COUNT.name == "stopCount"
	assert model.STOP_COUNT in model.ALL
	for column in ("boarded", "alighted", "dwell_s", "stop", "vehicle", "trip_key"):
		assert column in model.STOP_COUNT.columns


def test_a_visit_carries_the_measured_boarding_and_says_when_it_has_none(stub_frappe):
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import model

	assert "boarded" in model.STOP_EVENT.columns
	assert "alighted" in model.STOP_EVENT.columns
	# Summed rather than averaged: a boarding is a thing that happened, and
	# what a planner asks of a stop-hour is how many people used it.
	measures = model.STOP_EVENT.rollups[0]["measures"]
	assert measures["boarded"] == ("sum", "boarded")
	assert measures["alighted"] == ("sum", "alighted")
	# How much of the hour was counted at all. Without it a stop where one
	# vehicle in ten carries a counter reads as a tenth as busy as it is.
	assert measures["counted"] == ("count", "boarded")


def test_the_nightly_pass_joins_them_and_never_infers_one(stub_frappe):
	"""Two claims in one source read, because both are the decision: every
	visit leaves with `-1` unless a counter reported it, and the counts are
	read from their own table rather than computed from occupancy."""
	import inspect
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import arrivals

	body = inspect.getsource(arrivals._counted)
	assert 'one["boarded"] = -1' in body
	assert "vdv457.since" in body
	assert "occupancy" not in body.split('"""')[2], (
		"a boarding must never be derived from two occupancy readings"
	)


# --------------------------------------------------------------------------- #
# The corrected form, which is a different document
#
# `CountingAfterClearing` instead of `Counting`, no `DoorID`, and — the one
# that matters — no `HeaderCounting`, so no per-stop time and no door timing.
# The operator's clearing pass drops both. A reader that insisted on a
# timestamp would silently ignore every corrected journey, which is the half
# of the interface the numbers are actually taken from.
# --------------------------------------------------------------------------- #

def cleared(stop, adult_in, adult_out, extra=""):
	return f"""
	  <PassengerCountingEvent>
	    <StopInformation>
	      <StopStatus>normal</StopStatus>
	      <StopRef><Value>{stop}</Value></StopRef>
	    </StopInformation>
	    <CountingArea>
	      <AreaID>00</AreaID>
	      <CountingAfterClearing>
	        <Count>
	          <ObjectClass>Adult</ObjectClass>
	          <In><Value>{adult_in}</Value></In>
	          <Out><Value>{adult_out}</Value></Out>
	        </Count>
	        {extra}
	      </CountingAfterClearing>
	    </CountingArea>
	  </PassengerCountingEvent>"""


def corrected(visits, journey="16_02", vehicle="K-HP4723",
              departed="2001-10-26T21:32:52"):
	return f"""<?xml version="1.0" encoding="UTF-8"?>
<PassengerCountingServiceBGS_457-3.GetAllDataResponse>
  <PassengerCountingServiceJourney>
    <HeaderServiceJourney>
      <ServiceJourneyID>{journey}</ServiceJourneyID>
      <DataType>after clearing</DataType>
      <ServiceJourneyDepartureTime>{departed}</ServiceJourneyDepartureTime>
    </HeaderServiceJourney>
    <PassengerCountingMessage>
      <HeaderData><VehicleID>{vehicle}</VehicleID></HeaderData>
      {"".join(visits)}
    </PassengerCountingMessage>
  </PassengerCountingServiceJourney>
</PassengerCountingServiceBGS_457-3.GetAllDataResponse>""".encode()


def test_a_corrected_journey_is_read_even_with_no_per_stop_time(vdv457):
	rows = vdv457.events(corrected([cleared("PP_9950", 12, 5)]))
	assert len(rows) == 1
	assert (rows[0]["boarded"], rows[0]["alighted"]) == (12, 5)


def test_a_corrected_visit_is_stamped_from_the_journey_and_says_so(vdv457):
	"""`exact` is what the join reads: a counter's own stamp is matched inside
	a few minutes, a journey's departure standing in for one only by stop and
	day. Without the flag the second would miss almost every match, because a
	departure time is minutes out by the end of a route."""
	rows = vdv457.events(corrected([cleared("PP_9950", 1, 1)],
	                               departed="2001-10-26T21:32:52"))
	assert rows[0]["exact"] == 0
	assert rows[0]["at"].hour == 21

	raw = vdv457.events(delivery([visit("PP_4607", [counting("PP_4607", 1, 1)])]))
	assert raw[0]["exact"] == 1


def test_a_corrected_journey_with_no_departure_time_is_not_guessed(vdv457):
	assert vdv457.events(corrected([cleared("PP_9950", 1, 1)], departed="")) == []


def test_other_is_not_a_passenger_class(vdv457):
	"""The published corrected example carries one. Adult, Child and
	Unidentified are people; Other is whatever the counter could not place,
	and adding it to a boarding count is adding something unnamed."""
	extra = """
	        <Count><ObjectClass>Other</ObjectClass>
	          <In><Value>3</Value></In><Out><Value>5</Value></Out></Count>"""
	rows = vdv457.events(corrected([cleared("PP_9950", 12, 5, extra=extra)]))
	assert (rows[0]["boarded"], rows[0]["alighted"]) == (12, 5)


def test_an_inexact_stamp_is_matched_by_stop_and_not_by_the_minute(stub_frappe):
	import inspect
	for name in list(sys.modules):
		if name.startswith("oneapp.onemobility"):
			del sys.modules[name]
	from oneapp.onemobility import arrivals

	body = inspect.getsource(arrivals._counted)
	assert 'nearest.get("exact", 1)' in body, (
		"the window must not be applied to a stamp the counter did not make"
	)
