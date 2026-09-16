"""Posting hours to a ledger, where a workspace keeps one.

The rule this file holds is the one in `onetask/billing.py`'s docstring:
**OneTask does not bill.** So what is tested here is the bridge's manners —
that it groups the way a Timesheet is shaped, that it never posts an hour
twice, that it invents no rate, and that a `One Project` is not quietly treated
as an ERPNext `Project`.
"""

import pytest


@pytest.fixture
def billing(stub_frappe):
	import importlib
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.onetask"):
			del sys.modules[name]
	return importlib.import_module("oneapp.onetask.billing")


ROWS = [
	{"name": "T1", "task": "A", "project": "zzFit-out", "person": "ada@x.test",
	 "starts_at": "2026-01-05 09:00:00", "ends_at": "2026-01-05 11:30:00",
	 "minutes": 150, "note": "zzMeasured up."},
	{"name": "T2", "task": "B", "project": "zzFit-out", "person": "ada@x.test",
	 "starts_at": "2026-01-06 09:00:00", "ends_at": "2026-01-06 09:45:00",
	 "minutes": 45, "note": ""},
	{"name": "T3", "task": "C", "project": "zzWebsite", "person": "ada@x.test",
	 "starts_at": "2026-01-06 14:00:00", "ends_at": "2026-01-06 15:00:00",
	 "minutes": 60, "note": ""},
	{"name": "T4", "task": "D", "project": "zzFit-out", "person": "bo@x.test",
	 "starts_at": "2026-01-06 10:00:00", "ends_at": "2026-01-06 10:30:00",
	 "minutes": 30, "note": ""},
]


def test_it_groups_one_sheet_per_person_per_project(billing):
	"""A Timesheet is a person and a table of stretches. One per row would be a
	hundred documents for a month and an invoice nobody can read."""
	found = billing._grouped(ROWS)
	assert sorted(found) == [("ada@x.test", "zzFit-out"),
	                         ("ada@x.test", "zzWebsite"),
	                         ("bo@x.test", "zzFit-out")]
	assert [one["name"] for one in found[("ada@x.test", "zzFit-out")]] == ["T1", "T2"]


def test_a_stretch_carries_hours_and_no_money(billing):
	"""A rate belongs to the customer, the activity and the person, and ERPNext
	has all three in a place somebody maintains. A number invented here is the
	one that disagrees on the invoice."""
	log = billing._log(ROWS[0])
	assert log["hours"] == 2.5
	assert log["description"] == "zzMeasured up."
	assert log["is_billable"] == 1
	assert "rate" not in log and "billing_amount" not in log


def test_a_part_hour_keeps_its_minutes(billing):
	"""Forty-five minutes is 0.75 of an hour. Rounding to a quarter *here*
	would be a pricing decision wearing arithmetic's clothes."""
	assert billing._log(ROWS[1])["hours"] == 0.75


def test_a_workspace_with_no_ledger_is_offered_nothing(billing, monkeypatch):
	monkeypatch.setattr(billing.frappe, "get_installed_apps",
	                    lambda: ["frappe", "oneapp"], raising=False)
	assert billing.installed() is False
	# And no button, rather than a button that throws when pressed.
	assert billing.actions() == {}
	with pytest.raises(Exception):
		billing.post(["T1"])


def test_a_ledger_project_is_matched_by_name_and_is_optional(billing, monkeypatch):
	"""A `One Project` is not an ERPNext `Project` and must not pretend to be.
	Where somebody keeps both under one name they are linked; where they do not,
	the hours still post."""
	monkeypatch.setattr(billing.frappe.db, "exists", lambda *a, **k: True)
	monkeypatch.setattr(billing.frappe.db, "get_value",
	                    lambda doctype, filters=None, field=None, **k:
	                    "PROJ-0001" if filters == {"project_name": "zzFit-out"} else None)
	assert billing._ledger_project("zzFit-out") == "PROJ-0001"
	assert billing._ledger_project("zzWebsite") is None
	assert billing._ledger_project("") is None

	# A site with no ERPNext has no such doctype, and asking is how that is
	# found out rather than assumed.
	monkeypatch.setattr(billing.frappe.db, "exists", lambda *a, **k: False)
	assert billing._ledger_project("zzFit-out") is None


def test_nothing_chosen_is_refused_rather_than_posting_everything(billing, monkeypatch):
	monkeypatch.setattr(billing.frappe, "get_installed_apps",
	                    lambda: ["frappe", "erpnext"], raising=False)
	with pytest.raises(Exception):
		billing.post([])
	with pytest.raises(Exception):
		billing.post("")
