"""How long a record waited, and whether it settled — `docs/ONECRM.md` stage 6.

`onecrm/answering.py` is Frappe CRM's `CRM Service Level Agreement` with one
part refused: theirs stores a Python condition on the row and evaluates it, and
a row an operator can edit must never be a row an operator can run code from.
Everything else is here, and these are the claims.

**A rule is a comparison, never an interpreter.** Fieldname, operator, value —
the same three-part shape every filter in this product has.

**A priority is a row with its own two clocks**, matched on whatever field the
doctype keeps a priority in, falling back to a default row rather than leaving
a record unmeasured.

**The clock runs in working time.** A lead that arrives at six on Friday
evening is not late at nine on Saturday morning, and the *durations* are
measured by the same walk that made the deadline — a report that disagreed with
the column beside it would be worse than no report.

**Rolling responses.** An agreement is not about the first reply; it is about
every reply. Somebody writing back after being answered starts the clock again.

**And a second clock for settling**, stopped by the record itself: a deal whose
status leaves Open, a lead somebody qualified.
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

TARGET = {"name": "Answer a lead", "holiday_list": None, "rolling": 1,
          "applies_to": "Lead", "priority_field": ""}

STANDARD = {"level": "Standard", "is_default": 1, "respond_within": 4,
            "resolve_within": 0}


def site(answering, monkeypatch, targets=(), levels=(STANDARD,), rules=None,
         week=OFFICE, holidays=(), fields=()):
	"""A bench with these targets, levels, rules, week and holidays on it."""
	rules = rules or {}

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
		if doctype == answering.LEVEL:
			return [dict(one) for one in levels]
		if doctype == answering.RULE:
			return [dict(one) for one in rules.get(filters.get("parentfield"), ())]
		if doctype == answering.WEEK:
			return [dict(one) for one in week]
		if doctype == "Holiday":
			return [{"holiday_date": one} for one in holidays]
		return []

	monkeypatch.setattr(answering.frappe, "get_all", get_all)
	held = set(fields) or {answering.DUE, answering.ANSWERED, answering.STATE,
	                       answering.SETTLE_BY, answering.SETTLED,
	                       answering.SETTLING, answering.WHICH,
	                       answering.AT_LEVEL, answering.TOOK,
	                       answering.SETTLED_IN, answering.ROUNDS,
	                       answering.ROUND_FROM, "source", "status",
	                       "custom_stage"}
	for doctype in ("Lead", "Opportunity", "Communication", "One Call"):
		answering.frappe._meta[doctype] = types.SimpleNamespace(
			track_changes=0, title_field="", get_field=lambda name: None,
			has_field=lambda name, held=held: name in held,
		)
	answering.frappe.db.records[("Holiday List", "Public holidays")] = True


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
# Rules — a condition without the interpreter
# --------------------------------------------------------------------------- #

def test_nothing_in_this_module_evaluates_anything(answering):
	"""The one thing not taken from Frappe CRM, and the reason: a row an
	operator can edit must not be a row an operator can run code from."""
	import inspect
	source = inspect.getsource(answering)
	for door in ("eval(", "exec(", "safe_eval", "compile(", "__import__"):
		assert door not in source, door


def test_every_rule_has_to_hold(answering):
	"""AND and not OR: a target that fires when *any* of three things is true
	is a target nobody can predict from reading it, and two targets ordered by
	position say the same thing readably."""
	held = doc(source="Website", status="Open")
	assert answering.matches(held, [
		{"fieldname": "source", "operator": "is", "value": "Website"},
		{"fieldname": "status", "operator": "is", "value": "Open"},
	])
	assert not answering.matches(held, [
		{"fieldname": "source", "operator": "is", "value": "Website"},
		{"fieldname": "status", "operator": "is", "value": "Closed"},
	])


def test_no_rules_covers_everything(answering):
	assert answering.matches(doc(), [])


def test_a_rule_naming_a_field_that_is_not_there_is_false(answering):
	"""The opposite of skipping it, and the right way round: a rule is
	somebody narrowing, and a narrowing that silently stops narrowing is how a
	target meant for web leads starts covering every lead there is."""
	assert not answering.matches(doc(source="Website"), [
		{"fieldname": "nonesuch", "operator": "is", "value": "x"},
	])


def test_numbers_compare_as_numbers(answering):
	"""`> 100000` has to mean what it looks like, or a target over big deals
	is a target over deals whose value happens to sort late as text."""
	big = doc(opportunity_amount=250000)
	assert answering.matches(big, [
		{"fieldname": "opportunity_amount", "operator": ">", "value": "100000"},
	])
	assert not answering.matches(doc(opportunity_amount=9), [
		{"fieldname": "opportunity_amount", "operator": ">", "value": "100000"},
	])


def test_the_operators_are_a_closed_set(answering):
	"""Anything outside it is false rather than an error: a row typed wrong
	should narrow to nothing, not take the save with it."""
	assert not answering.matches(doc(source="Website"), [
		{"fieldname": "source", "operator": "matches regex", "value": ".*"},
	])


def test_set_and_not_set_read_a_blank_as_blank(answering):
	assert answering.matches(doc(source="Website"),
	                         [{"fieldname": "source", "operator": "is set"}])
	assert answering.matches(doc(source=""),
	                         [{"fieldname": "source", "operator": "is not set"}])


def test_contains_is_case_blind(answering):
	assert answering.matches(doc(title="Harbour Point CAFE"), [
		{"fieldname": "title", "operator": "contains", "value": "cafe"},
	])


# --------------------------------------------------------------------------- #
# Which target, and at what level
# --------------------------------------------------------------------------- #

def test_the_narrowest_target_wins(answering, monkeypatch):
	"""Ordered by `position`, so the one with rules on it sits above the
	catch-all and two targets that both fit resolve the same way every time."""
	site(answering, monkeypatch,
	     targets=[{**TARGET, "name": "Web leads"}, {**TARGET, "name": "Any lead"}],
	     rules={"applies_when": [{"fieldname": "source", "operator": "is",
	                              "value": "Website"}]})
	assert answering.target_for(doc(source="Website"))["name"] == "Web leads"


def test_a_doctype_no_target_names_is_not_measured(answering, monkeypatch):
	site(answering, monkeypatch, targets=[TARGET])
	assert answering.target_for(doc("Quotation")) is None


def test_the_priority_picks_the_promise(answering, monkeypatch):
	site(answering, monkeypatch, levels=[
		{"level": "Negotiation", "is_default": 0, "respond_within": 2,
		 "resolve_within": 40},
		{"level": "Standard", "is_default": 1, "respond_within": 8,
		 "resolve_within": 160},
	])
	held = doc("Opportunity", custom_stage="Negotiation")
	target = {**TARGET, "priority_field": "custom_stage"}
	assert answering.level_for(held, target)["respond_within"] == 2


def test_a_priority_nobody_made_a_row_for_falls_to_the_default(
		answering, monkeypatch):
	"""Not to *nothing*: a record that is quietly unmeasured is worse than one
	measured by the house promise, and a desk that wanted otherwise deletes the
	default row."""
	site(answering, monkeypatch, levels=[
		{"level": "Negotiation", "is_default": 0, "respond_within": 2,
		 "resolve_within": 40},
		{"level": "Standard", "is_default": 1, "respond_within": 8,
		 "resolve_within": 160},
	])
	held = doc("Opportunity", custom_stage="Somebody's own word")
	target = {**TARGET, "priority_field": "custom_stage"}
	assert answering.level_for(held, target)["level"] == "Standard"


def test_a_target_with_no_priority_field_uses_the_default(answering, monkeypatch):
	site(answering, monkeypatch, levels=[STANDARD])
	assert answering.level_for(doc(), TARGET)["respond_within"] == 4


# --------------------------------------------------------------------------- #
# The working week
# --------------------------------------------------------------------------- #

def test_friday_evening_is_not_late_on_saturday_morning(answering, monkeypatch):
	"""The checkpoint. Four working hours from six on Friday lands at one on
	Monday, because Saturday and Sunday are not hours anybody was working."""
	site(answering, monkeypatch)
	due = answering.deadline(datetime.datetime(2026, 1, 2, 18, 0), TARGET, 4)
	assert due == datetime.datetime(2026, 1, 5, 13, 0)


def test_the_clock_runs_inside_the_day_it_is_in(answering, monkeypatch):
	site(answering, monkeypatch)
	due = answering.deadline(datetime.datetime(2026, 1, 2, 10, 0), TARGET, 4)
	assert due == datetime.datetime(2026, 1, 2, 14, 0)


def test_time_before_the_day_opens_waits_for_it(answering, monkeypatch):
	site(answering, monkeypatch)
	due = answering.deadline(datetime.datetime(2026, 1, 2, 3, 0), TARGET, 4)
	assert due == datetime.datetime(2026, 1, 2, 13, 0)


def test_a_target_longer_than_a_day_spills_into_the_next_one(answering, monkeypatch):
	site(answering, monkeypatch)
	due = answering.deadline(datetime.datetime(2026, 1, 1, 14, 0), TARGET, 8)
	assert due == datetime.datetime(2026, 1, 2, 14, 0)


def test_a_holiday_is_not_a_working_day(answering, monkeypatch):
	site(answering, monkeypatch, holidays=[datetime.date(2026, 1, 2)])
	due = answering.deadline(datetime.datetime(2026, 1, 1, 16, 0),
	                         {**TARGET, "holiday_list": "Public holidays"}, 4)
	assert due == datetime.datetime(2026, 1, 5, 12, 0)


def test_an_empty_week_means_every_hour(answering, monkeypatch):
	site(answering, monkeypatch, week=[])
	due = answering.deadline(datetime.datetime(2026, 1, 3, 22, 0), TARGET, 4)
	assert due == datetime.datetime(2026, 1, 4, 2, 0)


def test_a_week_with_no_working_time_is_refused(answering, monkeypatch):
	site(answering, monkeypatch,
	     week=[{"day": day, "works": 0} for day in WEEKDAYS])
	with pytest.raises(Exception):
		answering.deadline(datetime.datetime(2026, 1, 2, 10, 0), TARGET, 4)


# --------------------------------------------------------------------------- #
# And the durations, by the same walk
# --------------------------------------------------------------------------- #

def test_a_weekend_is_not_three_days_of_work(answering, monkeypatch):
	"""The whole reason durations are measured rather than subtracted: Friday
	at four to Monday at ten is one working hour plus one, not sixty-six."""
	site(answering, monkeypatch)
	took = answering.worked_hours(datetime.datetime(2026, 1, 2, 16, 0),
	                              datetime.datetime(2026, 1, 5, 10, 0), TARGET)
	assert took == 2.0


def test_a_duration_agrees_with_the_deadline_it_is_compared_against(
		answering, monkeypatch):
	"""Same walk, same week. A report measured by a different rule from the
	column beside it is a report nobody trusts twice."""
	site(answering, monkeypatch)
	start = datetime.datetime(2026, 1, 2, 18, 0)
	due = answering.deadline(start, TARGET, 4)
	assert answering.worked_hours(start, due, TARGET) == 4.0


def test_nothing_between_two_moments_the_same(answering, monkeypatch):
	site(answering, monkeypatch)
	at = datetime.datetime(2026, 1, 2, 10, 0)
	assert answering.worked_hours(at, at, TARGET) == 0.0


# --------------------------------------------------------------------------- #
# Applying both clocks
# --------------------------------------------------------------------------- #

def test_a_record_gets_both_deadlines(answering, monkeypatch):
	site(answering, monkeypatch, targets=[TARGET], levels=[
		{"level": "Standard", "is_default": 1, "respond_within": 4,
		 "resolve_within": 16},
	])
	held = doc(creation="2026-01-02 10:00:00")
	answering.apply(held)
	assert held[answering.DUE] == datetime.datetime(2026, 1, 2, 14, 0)
	# Sixteen working hours from Friday at ten: seven left that day, eight on
	# Monday, one on Tuesday morning.
	assert held[answering.SETTLE_BY] == datetime.datetime(2026, 1, 6, 10, 0)
	assert held[answering.STATE] == answering.WAITING
	assert held[answering.SETTLING] == answering.OPEN


def test_a_target_promising_nothing_about_settling_says_nothing(
		answering, monkeypatch):
	"""Zero is honest for a desk that only promises to reply, and an empty
	column reads better than a date nobody committed to."""
	site(answering, monkeypatch, targets=[TARGET])
	held = doc(creation="2026-01-02 10:00:00")
	answering.apply(held)
	assert not held.get(answering.SETTLE_BY)
	assert held[answering.SETTLING] == ""


def test_the_deadline_is_written_once(answering, monkeypatch):
	"""A lead re-saved on Thursday does not get until Monday. The failure mode
	every SLA implementation has had at least once."""
	site(answering, monkeypatch, targets=[TARGET])
	held = doc(creation="2026-01-02 10:00:00")
	answering.apply(held)
	first = held[answering.DUE]
	held["creation"] = "2026-01-08 10:00:00"
	answering.apply(held)
	assert held[answering.DUE] == first


def test_a_record_with_no_target_gets_no_state(answering, monkeypatch):
	site(answering, monkeypatch, targets=[])
	held = doc(creation="2026-01-02 10:00:00")
	answering.apply(held)
	assert not held.get(answering.STATE)
	assert not held.get(answering.DUE)


def test_a_record_past_its_deadline_reads_late(answering, monkeypatch):
	site(answering, monkeypatch, targets=[TARGET])
	held = doc(**{answering.DUE: "2025-12-01 10:00:00"})
	answering.apply(held)
	assert held[answering.STATE] == answering.LATE


def test_the_record_settles_itself_on_the_save_that_settles_it(
		answering, monkeypatch):
	"""Rather than an hour later when a sweep notices — which is the whole
	reason the rules are evaluated against the document in hand."""
	site(answering, monkeypatch, targets=[TARGET],
	     rules={"resolved_when": [{"fieldname": "status", "operator": "is not",
	                               "value": "Open"}]})
	held = doc("Opportunity", creation="2026-01-02 10:00:00", status="Open",
	           **{answering.DUE: "2026-01-02 14:00:00",
	              answering.SETTLE_BY: "2026-01-05 10:00:00",
	              answering.WHICH: TARGET["name"]})
	answering.apply(held)
	assert held[answering.SETTLING] == answering.OPEN

	held["status"] = "Converted"
	answering.apply(held)
	assert held[answering.SETTLED]
	assert held[answering.SETTLING] == answering.SETTLED_STATE


def test_a_target_with_no_settled_rules_never_settles_itself(
		answering, monkeypatch):
	"""Empty means somebody says so by hand, which is the honest reading of a
	desk that has not written down what finished looks like."""
	site(answering, monkeypatch, targets=[TARGET])
	held = doc("Opportunity", creation="2026-01-02 10:00:00", status="Converted",
	           **{answering.DUE: "2026-01-02 14:00:00",
	              answering.SETTLE_BY: "2026-01-05 10:00:00",
	              answering.WHICH: TARGET["name"]})
	answering.apply(held)
	assert not held.get(answering.SETTLED)


# --------------------------------------------------------------------------- #
# What stops a clock
# --------------------------------------------------------------------------- #

def stamped(answering, monkeypatch, row, target=None):
	"""A record in that state, and the writes that reach it.

	Keyed on the doctype rather than on the shape of `fields`, because both
	reads here ask for a list — the record's columns and the target's.
	"""
	writes = []
	held = dict(target or TARGET)

	def get_value(doctype, name, fields=None, **k):
		if doctype == answering.TARGET:
			return answering.frappe._dict(held)
		return answering.frappe._dict(row)

	monkeypatch.setattr(answering.frappe.db, "get_value", get_value)
	monkeypatch.setattr(answering.frappe.db, "set_value",
	                    lambda doctype, name, values, **k: writes.append(values))
	return writes


def test_the_first_answer_of_a_round_is_the_one_that_counts(answering, monkeypatch):
	"""A second email is not a second chance to have been on time."""
	site(answering, monkeypatch)
	stamped(answering, monkeypatch, {answering.DUE: "2026-01-02 13:00:00",
	                                 answering.ANSWERED: "2026-01-02 11:00:00"})
	assert answering.answered("Lead", "CRM-LEAD-0001") is False


def test_a_record_with_no_deadline_is_not_stamped(answering, monkeypatch):
	site(answering, monkeypatch)
	stamped(answering, monkeypatch, {})
	assert answering.answered("Lead", "CRM-LEAD-0001") is False


def test_answering_measures_how_long_it_took(answering, monkeypatch):
	site(answering, monkeypatch)
	writes = stamped(answering, monkeypatch, {
		answering.DUE: "2026-01-02 13:00:00",
		answering.WHICH: TARGET["name"],
		answering.ROUND_FROM: "2026-01-02 09:00:00",
		"creation": "2026-01-02 09:00:00",
	})
	assert answering.answered("Lead", "L1", "2026-01-02 11:30:00") is True
	assert writes[0][answering.TOOK] == 2.5
	assert writes[0][answering.STATE] == answering.ANSWERED_STATE


def test_a_later_round_is_measured_from_when_it_started(answering, monkeypatch):
	"""Not from the record's creation — a deal answered in an hour on its
	fourth round took an hour, and a column saying six weeks measures the
	wrong thing."""
	site(answering, monkeypatch)
	writes = stamped(answering, monkeypatch, {
		answering.DUE: "2026-01-06 13:00:00",
		answering.WHICH: TARGET["name"],
		answering.ROUND_FROM: "2026-01-06 09:00:00",
		"creation": "2026-01-02 09:00:00",
	})
	answering.answered("Lead", "L1", "2026-01-06 10:00:00")
	assert writes[0][answering.TOOK] == 1.0


# --------------------------------------------------------------------------- #
# Rolling responses — the best idea in their implementation
# --------------------------------------------------------------------------- #

def test_writing_back_starts_the_clock_again(answering, monkeypatch):
	"""A desk that answers within the hour and then goes quiet for a fortnight
	has met a first-response target and failed the customer."""
	site(answering, monkeypatch)
	writes = stamped(answering, monkeypatch, {
		answering.DUE: "2026-01-02 13:00:00",
		answering.ANSWERED: "2026-01-02 11:00:00",
		answering.WHICH: TARGET["name"],
		answering.AT_LEVEL: "Standard",
		answering.ROUNDS: 1,
	})
	assert answering.reopened("Lead", "L1", "2026-01-05 10:00:00") is True
	written = writes[0]
	assert written[answering.STATE] == answering.WAITING
	assert written[answering.ANSWERED] is None
	assert written[answering.ROUNDS] == 2
	assert written[answering.DUE] == datetime.datetime(2026, 1, 5, 14, 0)


def test_a_second_question_before_anybody_replied_is_the_same_round(
		answering, monkeypatch):
	"""Somebody chasing an unanswered email has not restarted anything, and a
	clock that reset there would make a desk look better the slower it was."""
	site(answering, monkeypatch)
	stamped(answering, monkeypatch, {answering.DUE: "2026-01-02 13:00:00",
	                                 answering.WHICH: TARGET["name"],
	                                 answering.ROUNDS: 1})
	assert answering.reopened("Lead", "L1") is False


def test_a_settled_record_does_not_reopen(answering, monkeypatch):
	site(answering, monkeypatch)
	stamped(answering, monkeypatch, {
		answering.DUE: "2026-01-02 13:00:00",
		answering.ANSWERED: "2026-01-02 11:00:00",
		answering.SETTLED: "2026-01-03 10:00:00",
		answering.WHICH: TARGET["name"], answering.ROUNDS: 1,
	})
	assert answering.reopened("Lead", "L1") is False


def test_a_target_with_rolling_off_measures_the_first_reply_only(
		answering, monkeypatch):
	site(answering, monkeypatch)
	stamped(answering, monkeypatch, {
		answering.DUE: "2026-01-02 13:00:00",
		answering.ANSWERED: "2026-01-02 11:00:00",
		answering.WHICH: TARGET["name"], answering.ROUNDS: 1,
	}, target={**TARGET, "rolling": 0})
	assert answering.reopened("Lead", "L1") is False


def test_mail_we_sent_answers_and_mail_we_received_reopens(answering, monkeypatch):
	acted = []
	monkeypatch.setattr(answering, "answered",
	                    lambda *a, **k: acted.append(("answered", *a[:2])) or True)
	monkeypatch.setattr(answering, "reopened",
	                    lambda *a, **k: acted.append(("reopened", *a[:2])) or True)

	answering.on_communication(doc(
		"Communication", sent_or_received="Sent",
		communication_date="2026-01-02 11:00:00",
		timeline_links=[{"link_doctype": "Lead", "link_name": "L1"}]))
	answering.on_communication(doc(
		"Communication", sent_or_received="Received",
		communication_date="2026-01-05 09:00:00",
		timeline_links=[{"link_doctype": "Lead", "link_name": "L1"}]))
	assert acted == [("answered", "Lead", "L1"), ("reopened", "Lead", "L1")]


def test_a_draft_is_neither(answering, monkeypatch):
	acted = []
	monkeypatch.setattr(answering, "answered", lambda *a, **k: acted.append(a))
	monkeypatch.setattr(answering, "reopened", lambda *a, **k: acted.append(a))
	answering.on_communication(doc("Communication", sent_or_received="",
	                               timeline_links=[{"link_doctype": "Lead",
	                                                "link_name": "L1"}]))
	assert not acted


def test_a_call_out_answers_and_a_call_in_reopens(answering, monkeypatch):
	"""Stage 5's doctype, earning its keep twice."""
	acted = []
	monkeypatch.setattr(answering, "answered",
	                    lambda *a, **k: acted.append(("answered", *a[:2])))
	monkeypatch.setattr(answering, "reopened",
	                    lambda *a, **k: acted.append(("reopened", *a[:2])))
	answering.on_call(doc("One Call", way="Outgoing", about_doctype="Lead",
	                      about_name="L1", at="2026-01-02 11:00:00"))
	answering.on_call(doc("One Call", way="Incoming", about_doctype="Lead",
	                      about_name="L1", at="2026-01-05 09:00:00"))
	assert acted == [("answered", "Lead", "L1"), ("reopened", "Lead", "L1")]


# --------------------------------------------------------------------------- #
# The sweep
# --------------------------------------------------------------------------- #

def test_the_sweep_reads_the_doctypes_the_targets_name(answering, monkeypatch):
	"""Not a hard-coded Lead and Opportunity. The whole claim of `applies_to`
	being a Link to DocType is that a job or a ticket is the same measurement,
	and a sweep that knew two doctypes would make that claim false."""
	site(answering, monkeypatch, targets=[
		{**TARGET, "applies_to": "Lead"},
		{**TARGET, "name": "Answer a job", "applies_to": "Maintenance Visit"},
	])
	assert answering._measured() == ["Lead", "Maintenance Visit"]


def test_the_sweep_moves_both_clocks(answering, monkeypatch):
	"""A record that settled late and a record that was answered late are two
	different failures, and a sweep that only looked at one of them would
	leave the other reading Open for ever."""
	swept = []
	monkeypatch.setattr(answering, "_measured", lambda: ["Lead"])
	monkeypatch.setattr(answering.frappe, "get_all",
	                    lambda doctype, filters=None, **k: ["L1"])
	monkeypatch.setattr(answering.frappe.db, "set_value",
	                    lambda doctype, name, field, value=None, **k:
	                    swept.append((field, value)))
	assert answering.late_now() == 2
	assert swept == [(answering.STATE, answering.LATE),
	                 (answering.SETTLING, answering.OVERDUE)]


def test_the_sweep_writes_the_column_and_not_a_version(answering):
	"""The clock moving is not somebody changing the record: a Version row per
	lead per hour would bury the timeline the rest of this arc built."""
	import inspect
	source = inspect.getsource(answering._sweep)
	assert "db.set_value" in source
	assert ".save(" not in source


def test_the_column_reads_on_the_readers_behalf_nowhere_here(answering):
	"""The opposite rule to the timeline's, and worth stating: this runs on
	the *record's* behalf from a hook, not on a reader's from a request, so
	`get_all` is right and `get_list` would silently measure nothing for
	whoever happened to trigger the save."""
	import inspect
	assert "frappe.get_list(" not in inspect.getsource(answering)
