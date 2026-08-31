"""Backups into R2: when the site takes one, and when the control plane may
throw an old one away.

The two live on opposite sides of the HMAC boundary on purpose. The site has the
files; the control plane has the policy and, crucially, keeps working when the
site does not. `tests/test_backup_layout.py` is what stops the two ends
disagreeing about where an object goes.
"""

import datetime

import pytest


@pytest.fixture
def backup(stub_frappe):
	from oneapp.oneapp_core import backup as module

	return module


@pytest.fixture
def retention(stub_frappe):
	from oneapp_control.lifecycle import backups as module

	return module


# --------------------------------------------------------------------------- #
# The schedule
# --------------------------------------------------------------------------- #

def test_a_plan_with_no_backups_never_takes_one(backup):
	assert not any(backup.is_backup_hour(hour, 0) for hour in range(24))


def test_one_a_day_lands_at_midnight(backup):
	slots = [hour for hour in range(24) if backup.is_backup_hour(hour, 1)]
	assert slots == [0]


def test_two_a_day_are_twelve_hours_apart(backup):
	assert [h for h in range(24) if backup.is_backup_hour(h, 2)] == [0, 12]


def test_four_a_day_are_six_hours_apart(backup):
	assert [h for h in range(24) if backup.is_backup_hour(h, 4)] == [0, 6, 12, 18]


def test_a_plan_asking_for_more_than_hourly_gets_hourly(backup):
	"""An hour is the finest this schedule can express.

	Answering "never" to a plan that asked for too much would give the most
	expensive tier the fewest backups, which is the wrong way round.
	"""
	assert [h for h in range(24) if backup.is_backup_hour(h, 96)] == list(range(24))


def test_files_come_along_once_a_day(backup):
	"""A dump is megabytes and changes constantly; the tarballs are gigabytes
	and mostly do not."""
	assert backup.is_full_hour(0)
	assert not any(backup.is_full_hour(h) for h in range(1, 24))


# --------------------------------------------------------------------------- #
# What leaves the site
# --------------------------------------------------------------------------- #

def test_the_config_in_a_backup_has_no_secrets(backup, tmp_path):
	"""Frappe copies site_config.json verbatim, which is right for a restore you
	perform yourself and wrong for one stored in the bucket its own keys open."""
	import json

	path = tmp_path / "site_config.json"
	path.write_text(json.dumps({
		"oneapp_tenant": "acme",
		"oneapp_control_url": "https://control.example",
		"oneapp_hmac_secret": "the-shared-secret",
		"oneapp_r2_access_key": "AKIA",
		"oneapp_r2_secret_key": "shhh",
		"db_password": "hunter2",
		"encryption_key": "fernet",
		"oneapp_r2_bucket": "oneapp-gl-abc",
	}))

	found = json.loads(backup.redacted_config(str(path)))

	for key in ("oneapp_hmac_secret", "oneapp_r2_access_key", "oneapp_r2_secret_key",
	            "db_password", "encryption_key"):
		assert found[key] is None, f"{key} left the site inside a backup"

	# The shape survives — which tenant, which control plane, which bucket.
	assert found["oneapp_tenant"] == "acme"
	assert found["oneapp_r2_bucket"] == "oneapp-gl-abc"


def test_an_unreadable_config_is_an_empty_one_not_a_crash(backup, tmp_path):
	assert backup.redacted_config(str(tmp_path / "nope.json")) == b"{}"


# --------------------------------------------------------------------------- #
# Retention
# --------------------------------------------------------------------------- #

def _set(stamp, days_old, keys=("database.sql.gz",)):
	when = datetime.datetime(2026, 6, 1, 12, 0, 0) - datetime.timedelta(days=days_old)
	return {
		"stamp": stamp,
		"keys": [f"backups/acme/{stamp}/{k}" for k in keys],
		"bytes": 100,
		"modified": when,
	}


@pytest.fixture
def dated(retention, monkeypatch):
	"""Real date arithmetic — the stub's `add_to_date` answers None."""
	now = datetime.datetime(2026, 6, 1, 12, 0, 0)
	monkeypatch.setattr(retention, "now_datetime", lambda: now)
	monkeypatch.setattr(
		retention,
		"add_to_date",
		lambda when, days=0, hours=0: when + datetime.timedelta(days=days, hours=hours),
	)
	monkeypatch.setattr(
		retention,
		"get_datetime",
		lambda v: v if isinstance(v, datetime.datetime)
		else datetime.datetime.fromisoformat(str(v)[:19]),
	)
	return retention


def test_nothing_expires_inside_the_window(dated):
	sets = [_set("a", 1), _set("b", 3), _set("c", 5)]
	assert dated.expired(sets, keep_days=7) == []


def test_what_is_past_the_window_expires(dated):
	sets = [_set("a", 30), _set("b", 20), _set("c", 1)]
	assert [s["stamp"] for s in dated.expired(sets, keep_days=7)] == ["a", "b"]


def test_the_newest_set_survives_however_old_it_is(dated):
	"""A workspace whose site stopped backing up a month ago has one copy left.

	A literal reading of a seven-day window would delete it, turning a stalled
	scheduler into data loss.
	"""
	sets = [_set("a", 90), _set("b", 60)]
	assert [s["stamp"] for s in dated.expired(sets, keep_days=7)] == ["a"]


def test_a_lone_set_is_never_expired(dated):
	assert dated.expired([_set("a", 400)], keep_days=1) == []


def test_a_zero_window_is_read_as_a_day(dated):
	"""Zero is not a retention policy anybody types on purpose."""
	assert [s["stamp"] for s in dated.expired([_set("a", 5), _set("b", 0)], 0)] == ["a"]


def test_a_set_with_no_timestamp_is_left_alone(dated):
	"""Not knowing how old something is is not a reason to delete it."""
	orphan = _set("a", 90)
	orphan["modified"] = None
	assert dated.expired([orphan, _set("b", 1)], keep_days=7) == []


# --------------------------------------------------------------------------- #
# Every plan sells a schedule
# --------------------------------------------------------------------------- #

def test_every_seeded_plan_has_a_backup_schedule():
	"""A plan with `backups_per_day` of zero takes no backups at all.

	The doctype default is 1, and a fixture overwrites it with whatever the JSON
	says — including nothing, which lands as zero. So a plan added to the fixture
	without thinking about this ships a tier whose customers have no copies of
	their workspace, and nothing anywhere reports it as wrong.
	"""
	import json
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent
	plans = json.loads(
		(root / "apps/oneapp_control/oneapp_control/fixtures/plan.json").read_text()
	)

	for plan in plans:
		assert plan.get("backups_per_day", 0) >= 1, (
			f"{plan['name']} would take no backups"
		)
		assert plan.get("backup_retention_days", 0) >= 1, (
			f"{plan['name']} would keep no backups"
		)


def test_the_schedule_never_goes_down_as_a_plan_goes_up():
	"""What grows with the tier is how much work a customer can afford to lose.

	Not a claim that the numbers are right — that is a pricing decision — but a
	plan that pays more and is backed up less often is a mistake, and it is one
	nobody would notice from the fixture, where the plans are in no order.
	"""
	import json
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent
	plans = {
		p["name"]: p
		for p in json.loads(
			(root / "apps/oneapp_control/oneapp_control/fixtures/plan.json").read_text()
		)
	}

	ordered = sorted(plans.values(), key=lambda p: p.get("price_monthly") or 0)
	rates = [p["backups_per_day"] for p in ordered]
	kept = [p["backup_retention_days"] for p in ordered]

	assert rates == sorted(rates), [
		(p["name"], p["backups_per_day"]) for p in ordered
	]
	assert kept == sorted(kept), [
		(p["name"], p["backup_retention_days"]) for p in ordered
	]
