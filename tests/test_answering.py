"""How long a record waited for an answer — `docs/ONECRM.md` stage 6.

Four claims, and the first is the checkpoint the stage was written for.

**Working time, not wall clock.** A lead that arrives at six on Friday evening
is not late at nine on Saturday morning. That takes a working week and a
holiday list and nothing less, and a measure that gets it wrong is a measure a
desk switches off within the week.

**A target is a row, not a condition.** One field and one value, never an
expression: a row an operator can edit must not be a row an operator can run
code from.

**The deadline is written once.** A lead re-saved on Thursday does not get
until Monday — a measure that resets itself every time somebody looks at the
record is the failure mode every SLA implementation has had at least once.

**And the first answer is the measurement.** A second email is not a second
chance to have been on time.
"""

import datetime
import types

import pytest


@pytest.fixture
def answering(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onecrm"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onecrm.answering")


#: Nine to five, Monday to Friday — the week the space ships with.
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")

OFFICE = [{"day": day, "works": 1, "from_time": "09:00:00",
           "to_time": "17:00:00"} for day in WEEKDAYS]


def site(answering, monkeypatch, targets=(), week=(), holidays=(), fields=()):
	"""A bench with these targets, this week and these holidays on it."""
	def get_all(doctype, filters=None, **k):
		filters = filters or {}
		if doctype == answering.TARGET:
			rows = [dict(one) for one in targets]
			if filters.get("applies_to"):
				rows = [one for one in rows
				        if one.get("applies_to") == filters["applies_to"]]
			if k.get("pluck"):
				return [one[k["pluck"]] for one in rows]
			return rows
		if doctype == answering.WEEK:
			return [dict(one) for one in week]
		if doctype == "Holiday":
			return [{"holiday_date": one} for one in holidays]
		return []

	monkeypatch.setattr(answering.frappe, "get_all", get_all)
	held = set(fields) or {answering.DUE, answering.ANSWERED, answering.STATE,
	                       answering.WHICH, "source"}
	# The holiday list has to exist for its days to be read: `_holidays` asks,
	# because a target pointing at a list somebody deleted should measure in
	# plain working hours rather than throw.
	answering.frappe.db.records[("Holiday List", "Public holidays")] = True
	answering.frappe._meta["Lead"] = types.SimpleNamespace(
		track_changes=0, get_field=lambda name: None,
		has_field=lambda name: name in held,
	)


def doc(doctype="Lead", **values):
	"""A document thin enough to validate, thick enough to be written to."""
	class Doc(dict):
		def __getattr__(self, key):
			try:
				return self[key]
			except KeyError:
				raise AttributeError(key) from None

		def get(self, key, default=None):
			return dict.get(self, key, default)

		def set(self, key, value):
			self[key] = value

	held = Doc(values)
	held["doctype"] = doctype
	return held


# --------------------------------------------------------------------------- #
# The working week
# --------------------------------------------------------------------------- #

TARGET = {"name": "Answer a lead", "hours": 4, "holiday_list": None,
          "applies_to": "Lead", "when_field": "", "when_value": ""}


def test_friday_evening_is_not_late_on_saturday_morning(answering, monkeypatch):
	"""The checkpoint. Four working hours from six on Friday lands at one on
	Monday, because Saturday and Sunday are not hours anybody was working."""
	site(answering, monkeypatch, week=OFFICE)
	# Friday the 2nd of January 2026, at six in the evening.
	due = answering.deadline(datetime.datetime(2026, 1, 2, 18, 0), TARGET)
	assert due == datetime.datetime(2026, 1, 5, 13, 0)


def test_the_clock_runs_inside_the_day_it_is_in(answering, monkeypatch):
	"""Ten in the morning plus four working hours is two in the afternoon.
	The uninteresting case, and the one that must not be broken by the
	interesting ones."""
	site(answering, monkeypatch, week=OFFICE)
	due = answering.deadline(datetime.datetime(2026, 1, 2, 10, 0), TARGET)
	assert due == datetime.datetime(2026, 1, 2, 14, 0)


def test_time_before_the_day_opens_waits_for_it(answering, monkeypatch):
	"""Something that arrives at three in the morning is answered from nine,
	not from three: a target is working hours and nobody was working."""
	site(answering, monkeypatch, week=OFFICE)
	due = answering.deadline(datetime.datetime(2026, 1, 2, 3, 0), TARGET)
	assert due == datetime.datetime(2026, 1, 2, 13, 0)


def test_a_target_longer_than_a_day_spills_into_the_next_one(answering, monkeypatch):
	"""Eight working hours is a whole day, so something arriving at two on
	Thursday is due at two on Friday — not at ten on Thursday night."""
	site(answering, monkeypatch, week=OFFICE)
	due = answering.deadline(datetime.datetime(2026, 1, 1, 14, 0),
	                         {**TARGET, "hours": 8})
	assert due == datetime.datetime(2026, 1, 2, 14, 0)


def test_a_holiday_is_not_a_working_day(answering, monkeypatch):
	"""The other half of the checkpoint, and the reason the holiday list is
	ERPNext's own rather than a second list here: a workspace keeps one."""
	site(answering, monkeypatch, week=OFFICE,
	     holidays=[datetime.date(2026, 1, 2)])
	due = answering.deadline(datetime.datetime(2026, 1, 1, 16, 0),
	                         {**TARGET, "holiday_list": "Public holidays"})
	# An hour left on Thursday, three more owed; Friday is off, so Monday.
	assert due == datetime.datetime(2026, 1, 5, 12, 0)


def test_an_empty_week_means_every_hour(answering, monkeypatch):
	"""The honest reading of a desk that has not said otherwise, and what a
	support line running at night actually wants."""
	site(answering, monkeypatch, week=[])
	due = answering.deadline(datetime.datetime(2026, 1, 3, 22, 0), TARGET)
	assert due == datetime.datetime(2026, 1, 4, 2, 0)


def test_a_week_with_no_working_time_is_refused(answering, monkeypatch):
	"""Rather than answered with a date two years out, which nobody would read
	as the error it is."""
	site(answering, monkeypatch,
	     week=[{"day": day, "works": 0} for day in WEEKDAYS])
	with pytest.raises(Exception):
		answering.deadline(datetime.datetime(2026, 1, 2, 10, 0), TARGET)


# --------------------------------------------------------------------------- #
# Which target covers a record
# --------------------------------------------------------------------------- #

def test_the_narrowest_target_wins(answering, monkeypatch):
	"""Ordered by `position`, so the one that names a field sits above the
	catch-all and two targets that both fit resolve the same way every time."""
	site(answering, monkeypatch, week=OFFICE, targets=[
		{**TARGET, "name": "Web leads", "when_field": "source",
		 "when_value": "Website", "hours": 1},
		{**TARGET, "name": "Any lead"},
	])
	held = doc(source="Website")
	assert answering.target_for(held)["name"] == "Web leads"
	assert answering.target_for(doc(source="Phone"))["name"] == "Any lead"


def test_a_target_naming_a_field_the_doctype_has_not_got_is_skipped(
		answering, monkeypatch):
	"""A row typed wrong should cost the record nothing."""
	site(answering, monkeypatch, week=OFFICE, targets=[
		{**TARGET, "name": "Typo", "when_field": "nonesuch",
		 "when_value": "x"},
		{**TARGET, "name": "Any lead"},
	], fields=["custom_respond_by", "custom_answered_on", "custom_answering",
	           "custom_response_target", "source"])
	assert answering.target_for(doc(source="Website"))["name"] == "Any lead"


def test_a_doctype_no_target_names_is_not_measured(answering, monkeypatch):
	site(answering, monkeypatch, week=OFFICE, targets=[TARGET])
	assert answering.target_for(doc("Quotation")) is None


def test_a_target_is_a_row_and_never_an_expression(answering):
	"""The rule, checked where it can be: nothing in this module evaluates
	anything. A row an operator edits must not be a row they run code from."""
	import inspect
	source = inspect.getsource(answering)
	for door in ("eval(", "exec(", "safe_eval", "compile("):
		assert door not in source, door


# --------------------------------------------------------------------------- #
# Applying it, and stopping it
# --------------------------------------------------------------------------- #

def test_the_deadline_is_written_once(answering, monkeypatch):
	"""A lead re-saved on Thursday does not get until Monday. The failure mode
	every SLA implementation has had at least once."""
	site(answering, monkeypatch, week=OFFICE, targets=[TARGET])
	held = doc(creation="2026-01-02 10:00:00")
	answering.apply(held)
	first = held[answering.DUE]

	held["creation"] = "2026-01-08 10:00:00"
	answering.apply(held)
	assert held[answering.DUE] == first


def test_a_record_with_no_target_gets_no_state(answering, monkeypatch):
	"""Not `Waiting`: a record nobody promised to answer in any particular
	time is not a record that is waiting on a promise."""
	site(answering, monkeypatch, week=OFFICE, targets=[])
	held = doc(creation="2026-01-02 10:00:00")
	answering.apply(held)
	assert not held.get(answering.STATE)
	assert not held.get(answering.DUE)


def test_a_record_past_its_deadline_reads_late(answering, monkeypatch):
	site(answering, monkeypatch, week=OFFICE, targets=[TARGET])
	held = doc(**{answering.DUE: "2025-12-01 10:00:00"})
	answering.apply(held)
	assert held[answering.STATE] == answering.LATE


def test_an_answered_record_is_answered_whenever_it_came(answering, monkeypatch):
	"""`Late` is not a fourth state for "answered late": the record says when
	it was answered and when it was due, and the comparison is the report."""
	site(answering, monkeypatch, week=OFFICE, targets=[TARGET])
	held = doc(**{answering.DUE: "2025-12-01 10:00:00",
	              answering.ANSWERED: "2025-12-09 10:00:00"})
	answering.apply(held)
	assert held[answering.STATE] == answering.ANSWERED_STATE


def test_the_first_answer_is_the_one_that_counts(answering, monkeypatch):
	"""A second email is not a second chance to have been on time."""
	site(answering, monkeypatch, week=OFFICE)
	stamped = {answering.DUE: "2026-01-02 13:00:00",
	           answering.ANSWERED: "2026-01-02 11:00:00"}
	monkeypatch.setattr(answering.frappe.db, "get_value",
	                    lambda *a, **k: answering.frappe._dict(stamped))
	assert answering.answered("Lead", "CRM-LEAD-0001") is False


def test_a_record_with_no_deadline_is_not_stamped(answering, monkeypatch):
	"""Nothing promised, nothing to measure — and a column full of answer
	times on records nobody was measuring is a column that means nothing."""
	site(answering, monkeypatch, week=OFFICE)
	monkeypatch.setattr(answering.frappe.db, "get_value",
	                    lambda *a, **k: answering.frappe._dict({}))
	assert answering.answered("Lead", "CRM-LEAD-0001") is False


def test_mail_we_received_is_not_an_answer(answering, monkeypatch):
	"""It is the thing being waited on. Counting it would mean a lead that
	emails twice has answered itself."""
	stamped = []
	monkeypatch.setattr(answering, "answered",
	                    lambda *a, **k: stamped.append(a) or True)
	answering.on_communication(doc("Communication", sent_or_received="Received",
	                               timeline_links=[{"link_doctype": "Lead",
	                                                "link_name": "L1"}]))
	assert not stamped


def test_mail_we_sent_answers_everything_it_was_about(answering, monkeypatch):
	stamped = []
	monkeypatch.setattr(answering, "answered",
	                    lambda *a, **k: stamped.append(a) or True)
	answering.on_communication(doc(
		"Communication", sent_or_received="Sent",
		communication_date="2026-01-02 11:00:00",
		timeline_links=[{"link_doctype": "Lead", "link_name": "L1"},
		                {"link_doctype": "Opportunity", "link_name": "O1"}]))
	assert [one[:2] for one in stamped] == [("Lead", "L1"), ("Opportunity", "O1")]


def test_ringing_them_answers_it_too(answering, monkeypatch):
	"""Stage 5's doctype, earning its keep twice. Outgoing only, for the same
	reason received mail does not count."""
	stamped = []
	monkeypatch.setattr(answering, "answered",
	                    lambda *a, **k: stamped.append(a) or True)
	answering.on_call(doc("One Call", way="Incoming", about_doctype="Lead",
	                      about_name="L1", at="2026-01-02 11:00:00"))
	assert not stamped

	answering.on_call(doc("One Call", way="Outgoing", about_doctype="Lead",
	                      about_name="L1", at="2026-01-02 11:00:00"))
	assert stamped[0][:2] == ("Lead", "L1")


def test_the_sweep_reads_the_doctypes_the_targets_name(answering, monkeypatch):
	"""Not a hard-coded Lead and Opportunity. The whole claim of `applies_to`
	being a Link to DocType is that a job or a ticket is the same measurement,
	and a sweep that knew two doctypes would make that claim false."""
	site(answering, monkeypatch, week=OFFICE, targets=[
		{**TARGET, "applies_to": "Lead"},
		{**TARGET, "name": "Answer a job", "applies_to": "Maintenance Visit"},
	])
	assert answering._measured() == ["Lead", "Maintenance Visit"]


def test_the_sweep_writes_the_column_and_not_a_version(answering, monkeypatch):
	"""The clock moving is not somebody changing the record: a Version row per
	lead per hour would bury the timeline the rest of this arc built."""
	import inspect
	source = inspect.getsource(answering.late_now)
	assert "db.set_value" in source
	assert ".save(" not in source
