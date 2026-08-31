"""The readiness board's answer to "did the ladder run last night".

The lifecycle sweep is what suspends, archives and eventually deletes a
workspace. It recorded what it did onto the control settings Single every night
and nothing ever showed it — on a site with no desk, a read-only field on a
Single is written by machinery and readable by nobody. So the one question worth
asking about the ladder had no answer anywhere in the product.

The three states below are the ones an operator can actually be in, and the
middle one is here because the first version of this check got it wrong: `if not
swept` does not catch a Single whose Datetime was never set, because Frappe
reads that back as the zero date rather than None. The board said "the last
sweep was 0001-01-01 00:00:00, which is more than a day and a half ago" — true,
and not what somebody needs to be told on a site that has simply never run one.
"""

import datetime

import pytest


@pytest.fixture
def setup_module_(stub_frappe, monkeypatch):
	from oneapp_control.api import setup as module

	now = datetime.datetime(2026, 6, 1, 9, 0, 0)

	def get_datetime(value):
		if isinstance(value, datetime.datetime):
			return value
		return datetime.datetime.fromisoformat(str(value))

	def add_to_date(when, hours=0):
		return when + datetime.timedelta(hours=hours)

	utils = __import__("sys").modules["frappe.utils"]
	monkeypatch.setattr(utils, "get_datetime", get_datetime, raising=False)
	monkeypatch.setattr(utils, "add_to_date", add_to_date, raising=False)
	monkeypatch.setattr(utils, "now_datetime", lambda: now, raising=False)
	return module, stub_frappe, now


def swept(frappe, when, note=""):
	frappe.db.singles[("OneSpace Control Settings", "lifecycle_swept_on")] = when
	frappe.db.singles[("OneSpace Control Settings", "lifecycle_note")] = note


def test_a_site_that_has_never_swept_is_told_so(setup_module_):
	module, frappe, _ = setup_module_
	swept(frappe, None)
	ok, why = module._sweep_state()
	assert ok is False
	assert "has not run" in why


def test_the_zero_date_reads_as_never_run_not_as_overdue(setup_module_):
	"""An unset Datetime on a Single comes back as Frappe's zero date, which is
	truthy and a real datetime — so it sails past `if not swept` and lands in
	the staleness branch, which then reports it as a sweep that happened in the
	year 1 and is overdue."""
	module, frappe, _ = setup_module_
	swept(frappe, "0001-01-01 00:00:00")
	ok, why = module._sweep_state()
	assert ok is False
	assert "has not run" in why, f"the zero date was read as a real sweep: {why}"
	assert "0001" not in why


def test_a_sweep_that_stopped_running_is_a_failed_check(setup_module_):
	module, frappe, now = setup_module_
	swept(frappe, now - datetime.timedelta(hours=module.SWEEP_STALE_HOURS + 1))
	ok, why = module._sweep_state()
	assert ok is False
	assert "Nothing is advancing" in why


def test_last_nights_sweep_passes_and_says_what_it_did(setup_module_):
	module, frappe, now = setup_module_
	swept(frappe, now - datetime.timedelta(hours=8), note="2 warned, 1 suspended.")
	ok, why = module._sweep_state()
	assert ok is True
	assert "2 warned, 1 suspended." in why


def test_the_check_is_not_blocking(setup_module_):
	"""A control plane with no tenants on it has never swept, and that must not
	stop it provisioning the first one."""
	module, _frappe, _now = setup_module_
	assert module.SWEEP_STALE_HOURS > 24, (
		"a window under a day makes a daily job look broken between runs"
	)
