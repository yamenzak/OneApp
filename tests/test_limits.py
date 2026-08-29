"""Database size and background-job caps.

Both are quotas the plan defines and something else has to enforce. They are
tested together because they share a failure mode: enforcing too eagerly breaks
a paying customer's site over a limit they can neither see nor recover from.
"""

import pytest

GB = 1024**3


@pytest.fixture
def quota(stub_frappe):
	from oneapp.oneapp_core.storage import quota as module

	frappe = stub_frappe
	frappe.cache().store.clear()
	frappe.flags = type("Flags", (), {})()
	return module


@pytest.fixture
def jobs(stub_frappe, monkeypatch):
	from oneapp.oneapp_core import jobs as module

	return module


class FakeDoc:
	def __init__(self, doctype):
		self.doctype = doctype


def _measured(quota, monkeypatch, used, allowed):
	monkeypatch.setattr(quota, "database_used_bytes", lambda: used)
	monkeypatch.setattr(quota, "database_quota_bytes", lambda: allowed)


# --- database ---------------------------------------------------------------


def test_verdict_is_false_before_anything_is_measured(quota):
	# An absent verdict must read as "not over". Reading it the other way would
	# freeze every new site until the first sweep ran.
	assert quota.database_over_quota() is False


def test_over_quota_is_measured_and_cached(quota, monkeypatch):
	_measured(quota, monkeypatch, used=3 * GB, allowed=2 * GB)
	assert quota.measure_database_quota() is True
	assert quota.database_over_quota() is True


def test_under_quota_clears_the_verdict(quota, monkeypatch):
	_measured(quota, monkeypatch, used=3 * GB, allowed=2 * GB)
	quota.measure_database_quota()
	_measured(quota, monkeypatch, used=1 * GB, allowed=2 * GB)
	quota.measure_database_quota()
	assert quota.database_over_quota() is False


def test_unset_quota_never_blocks(quota, monkeypatch):
	# Zero means unconfigured, not zero allowed — a failed sync must not freeze
	# a site.
	_measured(quota, monkeypatch, used=500 * GB, allowed=0)
	assert quota.measure_database_quota() is False


def test_reading_the_verdict_never_measures(quota, monkeypatch):
	def explode():
		raise AssertionError("database_over_quota must not measure")

	monkeypatch.setattr(quota, "database_used_bytes", explode)
	monkeypatch.setattr(quota, "database_quota_bytes", explode)
	quota.database_over_quota()


def test_insert_blocked_when_over(quota, monkeypatch):
	_measured(quota, monkeypatch, used=3 * GB, allowed=2 * GB)
	quota.measure_database_quota()
	with pytest.raises(Exception, match="Database limit"):
		quota.enforce_database_quota(FakeDoc("Sales Invoice"))


def test_insert_allowed_when_under(quota, monkeypatch):
	_measured(quota, monkeypatch, used=1 * GB, allowed=2 * GB)
	quota.measure_database_quota()
	quota.enforce_database_quota(FakeDoc("Sales Invoice"))


@pytest.mark.parametrize("doctype", ["Deleted Document", "Version", "Error Log"])
def test_recovery_doctypes_stay_writable(quota, monkeypatch, doctype):
	# Deleting a document writes a Deleted Document. If that insert is blocked,
	# the only way back under the limit is blocked with it.
	_measured(quota, monkeypatch, used=3 * GB, allowed=2 * GB)
	quota.measure_database_quota()
	quota.enforce_database_quota(FakeDoc(doctype))


def test_migrations_are_never_blocked(quota, monkeypatch, stub_frappe):
	_measured(quota, monkeypatch, used=3 * GB, allowed=2 * GB)
	quota.measure_database_quota()

	stub_frappe.flags.in_migrate = True
	try:
		quota.enforce_database_quota(FakeDoc("Sales Invoice"))
	finally:
		stub_frappe.flags.in_migrate = False


# --- background jobs --------------------------------------------------------


def _plan(jobs, monkeypatch, workers):
	monkeypatch.setattr(jobs, "worker_limit", lambda: workers)


def _running(jobs, monkeypatch, count):
	monkeypatch.setattr(jobs, "inflight", lambda: count)


def test_under_the_cap_is_allowed(jobs, monkeypatch):
	_plan(jobs, monkeypatch, 3)
	_running(jobs, monkeypatch, 2)
	jobs.assert_capacity()


def test_at_the_cap_is_refused(jobs, monkeypatch):
	_plan(jobs, monkeypatch, 3)
	_running(jobs, monkeypatch, 3)
	with pytest.raises(Exception, match="background jobs"):
		jobs.assert_capacity()


def test_no_plan_limit_means_no_cap(jobs, monkeypatch):
	_plan(jobs, monkeypatch, 0)
	_running(jobs, monkeypatch, 500)
	jobs.assert_capacity()


def test_uncountable_fails_open(jobs, monkeypatch):
	# A Redis blip must not stop a tenant's work. Failing closed here would turn
	# an infrastructure hiccup into an outage for everyone at once.
	_plan(jobs, monkeypatch, 1)
	_running(jobs, monkeypatch, None)
	jobs.assert_capacity()


def test_small_plans_use_the_shared_queue(jobs, monkeypatch):
	_plan(jobs, monkeypatch, 1)
	assert jobs.queue_for_plan() == jobs.QUEUE_DEFAULT


def test_large_plans_get_their_own_queue(jobs, monkeypatch):
	# So a big import is not stuck behind a small one.
	_plan(jobs, monkeypatch, jobs.LONG_QUEUE_MIN_WORKERS)
	assert jobs.queue_for_plan() == jobs.QUEUE_LONG


def test_summary_reports_the_cap(jobs, monkeypatch):
	_plan(jobs, monkeypatch, 2)
	_running(jobs, monkeypatch, 2)
	assert jobs.summary() == {
		"running": 2,
		"limit": 2,
		"queue": jobs.QUEUE_DEFAULT,
		"at_limit": True,
	}
