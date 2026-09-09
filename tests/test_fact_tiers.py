"""The cold half of a fact table: what ages out, what comes back, what it costs.

`shared/facts.py` is the platform's, not OneMobility's — OneMobility is only the
first module to declare a table against it. So these are about the three things
that were missing from the tiering rather than about transit: a frozen day that
nothing ever deleted, a `hydrate` nothing ever called, and bytes nothing ever
counted.

The fourth thing they pin is the trap under the third: a day somebody asks for
back is a day the sweep will drop again that same night, unless the sweep is
told. A restore-what-you-asked-for that lasts eight hours is worse than none.
"""

from datetime import date, datetime, timedelta

import pytest


@pytest.fixture
def facts(stub_frappe):
	from oneapp.shared import facts as module

	module.reset()
	yield module
	module.reset()


@pytest.fixture
def fact(facts):
	return facts.declare(
		"ping",
		module="Test",
		when="at",
		columns={"at": "datetime", "value": "int"},
		hot_days=30,
		frozen_days=90,
		settings="Test Settings",
	)


class FakeR2:
	def __init__(self, objects=None):
		self.objects = objects or []
		self.deleted = []

	def is_configured(self):
		return True

	def config(self):
		return {"tenant": "acme", "bucket": "oneapp-gl-abc"}

	def list_objects(self, prefix):
		return [row for row in self.objects if row["key"].startswith(prefix)]

	def delete_keys(self, keys):
		self.deleted.extend(keys)
		return len(keys)


def _frozen(name, day, size=1000):
	return {"key": f"tenants/acme/facts/{name}/{day}.jsonl.gz", "size": size,
	        "modified": datetime(2026, 6, 1, 12, 0, 0)}


@pytest.fixture
def bucket(facts, monkeypatch):
	def install(objects):
		fake = FakeR2(objects)
		# Patched onto the real module rather than substituted for it: the
		# package's `__init__` pulls names out of it, so a stand-in breaks the
		# import that the code under test performs.
		from oneapp.onestorage import r2 as storage

		for name in ("is_configured", "config", "list_objects", "delete_keys"):
			monkeypatch.setattr(storage, name, getattr(fake, name))
		return fake

	return install


# --------------------------------------------------------------------------- #
# The window is the workspace's
# --------------------------------------------------------------------------- #

def test_a_declared_window_is_the_default(facts, fact, stub_frappe):
	assert facts.hot_days(fact) == 30
	assert facts.frozen_days(fact) == 90


def test_a_workspace_may_keep_more_or_less(facts, fact, stub_frappe):
	stub_frappe.db.singles[("Test Settings", "hot_days")] = 90
	assert facts.hot_days(fact) == 90


def test_an_empty_field_is_not_a_workspace_asking_for_nothing(facts, fact, stub_frappe):
	"""An unset Int and a deliberate nought are the same value in Frappe.

	Of the two readings only one is safe: a workspace must not be able to throw
	its own history away by clearing a field it had never filled in.
	"""
	stub_frappe.db.singles[("Test Settings", "hot_days")] = 0
	assert facts.hot_days(fact) == 30


def test_a_table_with_no_settings_single_is_unaffected(facts, stub_frappe):
	plain = facts.declare(
		"plain", module="Test", when="at", columns={"at": "datetime"}, hot_days=7
	)
	assert facts.hot_days(plain) == 7


# --------------------------------------------------------------------------- #
# What is in the bucket, and for how long
# --------------------------------------------------------------------------- #

def test_the_index_says_which_days_are_frozen(facts, fact, bucket):
	bucket([_frozen("ping", "2026-03-01"), _frozen("ping", "2026-03-02", size=50)])

	found = facts.frozen_index(fact)

	assert [one["day"] for one in found] == ["2026-03-01", "2026-03-02"]
	assert facts.frozen_bytes() == 1050


def test_a_frozen_day_past_the_window_is_deleted(facts, fact, bucket):
	"""The gap that had no name: nothing expired the frozen prefix at all.

	A fleet freezing ten megabytes a day is four gigabytes a year, per
	workspace, for ever, and the storage meter has never seen a byte of it.
	"""
	fake = bucket([_frozen("ping", "2026-01-01"), _frozen("ping", "2026-05-20")])

	gone = facts.expire_frozen(fact, date(2026, 6, 1))

	assert gone == 1
	assert fake.deleted == ["tenants/acme/facts/ping/2026-01-01.jsonl.gz"]


def test_for_ever_is_still_an_answer(facts, bucket):
	"""Zero keeps everything, and is the default — deleting a customer's
	history is not a thing to start doing on an upgrade."""
	forever = facts.declare(
		"kept", module="Test", when="at", columns={"at": "datetime"}
	)
	fake = bucket([_frozen("kept", "2019-01-01")])

	assert facts.expire_frozen(forever, date(2026, 6, 1)) == 0
	assert fake.deleted == []


# --------------------------------------------------------------------------- #
# Bringing one back
# --------------------------------------------------------------------------- #

def test_a_thawed_day_is_held_against_tonight_s_sweep(facts, fact, monkeypatch):
	"""Otherwise the sweep undoes, at two in the morning, what somebody asked
	for at four in the afternoon — and nothing anywhere says why."""
	monkeypatch.setattr(facts, "hydrate", lambda fact, day: 4200)

	assert facts.thaw(fact, date(2026, 3, 1)) == 4200
	assert facts.held(fact, date(2026, 3, 1))


def test_a_day_that_came_back_empty_is_not_held(facts, fact, monkeypatch):
	monkeypatch.setattr(facts, "hydrate", lambda fact, day: 0)

	facts.thaw(fact, date(2026, 3, 1))

	assert not facts.held(fact, date(2026, 3, 1))


def test_a_day_nobody_asked_for_is_not_held(facts, fact):
	assert not facts.held(fact, date(2026, 3, 1))


def test_the_hold_expires_rather_than_being_cleaned_up(facts, fact, stub_frappe):
	"""It is a decision with a date on it and nothing else. A week in the
	cache, and losing it to a restart costs one re-thaw rather than any data."""
	facts.hold(fact, date(2026, 3, 1))
	key = facts._hold_key(fact, date(2026, 3, 1))

	assert key in stub_frappe.cache.store
	assert facts.THAW_HOLD_DAYS == 7
