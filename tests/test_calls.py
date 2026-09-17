"""A call, logged by hand — `docs/ONECRM.md` stage 5, `onecrm/calls.py`.

Three claims.

**The verb writes nothing.** It answers `{"create": …}`, which is the engine's
own "this record is the start of another one", so the permission to log a call
is the Calls screen's rather than the button's.

**Who was on the other end is read generically.** A candidate list of
fieldnames tried against whatever doctype the button was pressed on, because
the next app to want this verb keeps its phone number somewhere else again.

**And the timeline entry is timed by `at`.** A call logged on Friday about
Tuesday belongs on Tuesday: it is the one source in that merged column whose
time a person typed.
"""

import types

import pytest


@pytest.fixture
def calls(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onecrm"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onecrm.calls")


def meta(calls, doctype: str, fields):
	"""A doctype that has exactly these fields, for `_held` to read."""
	held = set(fields)
	calls.frappe._meta[doctype] = types.SimpleNamespace(
		track_changes=0,
		title_field="",
		get_field=lambda name: None,
		has_field=lambda name: name in held,
	)


def held(calls, monkeypatch, values: dict):
	def get_value(doctype, name, fields, as_dict=False):
		if as_dict:
			return calls.frappe._dict({one: values.get(one) for one in fields})
		return values.get(fields)

	monkeypatch.setattr(calls.frappe.db, "get_value", get_value)


# --------------------------------------------------------------------------- #
# The verb
# --------------------------------------------------------------------------- #

def test_the_verb_does_not_write_a_call(calls, monkeypatch):
	"""Two presses, and the second one is the reader's. A verb that inserted
	would be a second create path around the screen's own permission."""
	meta(calls, "Opportunity", ["contact_display", "contact_mobile"])
	held(calls, monkeypatch, {"contact_display": "Nadia Fares",
	                          "contact_mobile": "+971500000000"})
	inserted = []
	monkeypatch.setattr(calls.frappe, "get_doc",
	                    lambda *a, **k: inserted.append(a) or None)

	answer = calls.about_a_deal("CRM-OPP-0001")
	assert not inserted
	assert answer["create"]["screen"] == "calls"


def test_the_dialog_is_already_about_this_record(calls, monkeypatch):
	"""The whole claim of the verb: the dynamic pair is filled in, so a call
	about a job, a tenant or a patient is the same two presses."""
	meta(calls, "Lead", ["lead_name", "mobile_no"])
	held(calls, monkeypatch, {"lead_name": "Nadia Fares",
	                          "mobile_no": "+971500000000"})

	values = calls.about_a_lead("CRM-LEAD-0004")["create"]["values"]
	assert values["about_doctype"] == "Lead"
	assert values["about_name"] == "CRM-LEAD-0004"


def test_a_number_is_found_wherever_the_doctype_keeps_it(calls, monkeypatch):
	"""An Opportunity keeps it in `contact_mobile` and a Lead in `mobile_no`.
	A map from doctype to field would not have heard of the third."""
	meta(calls, "Contact", ["first_name", "mobile_no"])
	held(calls, monkeypatch, {"first_name": "Nadia", "mobile_no": "+9715000"})

	values = calls.about_a_contact("Nadia Fares-1")["create"]["values"]
	assert values["number"] == "+9715000"


def test_a_doctype_with_none_of_them_still_opens_the_dialog(calls, monkeypatch):
	"""A blank box is what a person is about to type into anyway. The verb
	refusing would be the worse half of a generic candidate list."""
	meta(calls, "Prospect", [])
	held(calls, monkeypatch, {})

	values = calls.about_an_organisation("PROS-0002")["create"]["values"]
	assert "number" not in values
	# But never nameless: the record's own id is better than an empty With box.
	assert values["with_whom"] == "PROS-0002"


def test_the_title_is_the_fallback_for_who_was_rung(calls, monkeypatch):
	meta(calls, "Prospect", [])
	calls.frappe._meta["Prospect"].title_field = "company_name"
	monkeypatch.setattr(calls.frappe.db, "get_value",
	                    lambda doctype, name, fields, as_dict=False:
	                    "Brightwater Hotels" if not as_dict else calls.frappe._dict())

	values = calls.about_an_organisation("PROS-0002")["create"]["values"]
	assert values["with_whom"] == "Brightwater Hotels"


def test_a_record_you_cannot_read_is_not_a_call_you_can_log(calls, monkeypatch):
	meta(calls, "Opportunity", [])
	monkeypatch.setattr(calls.frappe, "has_permission", lambda *a, **k: False)
	with pytest.raises(calls.frappe.PermissionError):
		calls.about_a_deal("CRM-OPP-0001")


def test_the_verb_is_offered_where_there_is_a_person_behind_the_record(calls):
	"""Every screen whose record has somebody to ring, and the same key on all
	of them — a button that is called something different per screen is a
	button nobody learns."""
	declared = calls.actions()
	assert set(declared) == {
		"onecrm/deals", "onecrm/my-deals", "onecrm/leads", "onecrm/contacts",
		"onecrm/organisations",
	}
	for screen, verbs in declared.items():
		assert [one["key"] for one in verbs] == ["log-a-call"], screen
		assert verbs[0]["method"].startswith("oneapp.onecrm.calls."), screen


def test_every_method_the_verb_names_exists(calls):
	"""The declaration is the only thing that knows which doctype a screen is
	over — `run_action` hands a method the record's name and nothing else — so
	a typo here is a button that throws on press."""
	for verbs in calls.actions().values():
		attribute = verbs[0]["method"].rsplit(".", 1)[-1]
		assert callable(getattr(calls, attribute))


# --------------------------------------------------------------------------- #
# The timeline source
# --------------------------------------------------------------------------- #

ROW = {
	"name": "CALL-00001", "with_whom": "Nadia Fares", "way": "Outgoing",
	"number": "+971500000000", "at": "2026-01-05 11:15:00", "minutes": 14,
	"outcome": "Answered", "person": "robin@acme.test",
	"note": "Wants the fit-out priced.",
}


def rows(calls, monkeypatch, found=(ROW,), users=()):
	monkeypatch.setattr(calls.frappe.db, "table_exists", lambda name: True)
	monkeypatch.setattr(calls.frappe, "get_list",
	                    lambda *a, **k: [dict(one) for one in found])
	monkeypatch.setattr(calls.frappe, "get_all", lambda *a, **k: list(users))


def test_a_call_is_timed_by_when_it_happened(calls, monkeypatch):
	"""Not by `creation`. A call logged on Friday about Tuesday belongs on
	Tuesday, and it is the one source in that column a person types the time
	into."""
	rows(calls, monkeypatch)
	entry = calls.entries("Opportunity", "CRM-OPP-0001", {})[0]
	assert entry["on"] == ROW["at"]
	assert entry["kind"] == "call"


def test_the_person_is_named_rather_than_addressed(calls, monkeypatch):
	"""A timeline that reads `robin@acme.test` is a timeline nobody scans."""
	rows(calls, monkeypatch,
	     users=[{"name": "robin@acme.test", "full_name": "Robin Ellis"}])
	entry = calls.entries("Opportunity", "CRM-OPP-0001", {})[0]
	assert entry["by"] == "Robin Ellis"
	assert entry["by_id"] == "robin@acme.test"


def test_the_column_reads_on_the_readers_behalf(calls, monkeypatch):
	"""`get_list` and never `get_all` — the rule every source in
	`spaceview/surround.py` follows, because a call is as private as the
	record it is on."""
	import inspect
	source = inspect.getsource(calls.entries)
	assert "frappe.get_list(" in source
	assert "frappe.get_all(" not in source


def test_a_bench_without_the_table_answers_nothing(calls, monkeypatch):
	"""A doctype that has not been migrated yet must not take the record with
	it — the timeline is a merge, and one missing source is not a page that
	will not open."""
	monkeypatch.setattr(calls.frappe.db, "table_exists", lambda name: False)
	assert calls.entries("Opportunity", "CRM-OPP-0001", {}) == []


def test_the_key_is_unique_across_kinds(calls, monkeypatch):
	"""The merged column is keyed by `key`, and a call and a file with the
	same id would collide into one row."""
	rows(calls, monkeypatch)
	entry = calls.entries("Opportunity", "CRM-OPP-0001", {})[0]
	assert entry["key"] == "call:CALL-00001"


def test_the_source_is_registered_with_the_others(calls):
	"""Stage 3 built the registry so that this was one line. The test is that
	it is in the list, not that it could be."""
	from oneapp.onespace.spaceview import surround

	assert calls.entries in surround.SOURCES
