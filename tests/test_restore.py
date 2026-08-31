"""Restoring a workspace from its cold copy.

The failure this guards against is the quiet one: a restore that completes and
produces an empty or half-configured workspace. Nobody notices until somebody
looks for a record that is not there.
"""

import pytest


@pytest.fixture
def steps(stub_frappe):
	from oneapp_control.provisioning import steps as module

	return module


@pytest.fixture
def backups(stub_frappe):
	from oneapp_control.lifecycle import backups as module

	return module


class FakeJob:
	def __init__(self, **kw):
		self.tenant = "acme"
		self.press_site = "acme-xyz"
		self.agent_job_id = None
		self.payload = "{}"
		self.written = {}
		self.__dict__.update(kw)

	def parsed_payload(self):
		import json

		return json.loads(self.payload)

	def db_set(self, field, value=None):
		values = field if isinstance(field, dict) else {field: value}
		self.written.update(values)


class FakeTenant:
	def __init__(self, **kw):
		self.name = "acme"
		self.cold_storage_key = "cold/acme/20260601-000000"
		self.press_site = "acme-xyz"
		self.written = {}
		self.__dict__.update(kw)

	def get(self, key, default=None):
		return getattr(self, key, default)

	def db_set(self, field, value=None):
		values = field if isinstance(field, dict) else {field: value}
		self.written.update(values)
		for k, v in values.items():
			setattr(self, k, v)


ALL_LINKS = {
	"database.sql.gz": "https://r2/db",
	"public-files.tar": "https://r2/pub",
	"private-files.tar": "https://r2/priv",
	"site-config.json": "https://r2/conf",
}


def _wire(steps, monkeypatch, *, tenant=None, links=None):
	sent = {}
	tenant = tenant or FakeTenant()
	monkeypatch.setattr(steps.frappe, "get_doc", lambda *a: tenant)
	monkeypatch.setattr(
		"oneapp_control.lifecycle.cold.links",
		lambda t, ttl=3600: dict(ALL_LINKS if links is None else links),
	)

	class Client:
		def restore(self, site, files, skip_failing_patches=False):
			sent["site"] = site
			sent["files"] = files
			return {"job": "AJ-1"}

	monkeypatch.setattr(steps, "get_client", lambda: Client())
	return sent


def test_a_restore_hands_press_the_database_and_the_files(steps, monkeypatch):
	sent = _wire(steps, monkeypatch)
	steps.restore_from_cold(FakeJob())

	assert sent["site"] == "acme-xyz"
	assert sent["files"]["database"] == "https://r2/db"
	assert sent["files"]["public"] == "https://r2/pub"
	assert sent["files"]["private"] == "https://r2/priv"


def test_the_redacted_config_is_never_restored(steps, monkeypatch):
	"""Ours has been stripped of every secret before it was stored.

	Restoring it would overwrite the working keys `push_site_config` has just
	written with a set of nulls — a site that comes up and cannot reach the
	control plane, which reads as the restore having failed for reasons nobody
	can see.
	"""
	sent = _wire(steps, monkeypatch)
	steps.restore_from_cold(FakeJob())

	assert "config" not in sent["files"]


def test_a_cold_copy_with_no_database_is_refused(steps, monkeypatch):
	"""It would produce an empty workspace that looks like it worked."""
	_wire(steps, monkeypatch, links={"public-files.tar": "https://r2/pub"})

	with pytest.raises(steps.PressPermanentError):
		steps.restore_from_cold(FakeJob())


def test_a_workspace_with_no_cold_copy_is_refused(steps, monkeypatch):
	_wire(steps, monkeypatch, tenant=FakeTenant(cold_storage_key=None))

	with pytest.raises(steps.PressPermanentError):
		steps.restore_from_cold(FakeJob())


def test_the_payload_can_name_the_copy_to_restore(steps, monkeypatch):
	"""An operator restoring a specific promotion, rather than whichever one the
	tenant currently points at."""
	sent = _wire(steps, monkeypatch, tenant=FakeTenant(cold_storage_key=None))
	steps.restore_from_cold(FakeJob(payload='{"cold_storage_key": "cold/acme/older"}'))

	assert sent["files"]["database"] == "https://r2/db"


def test_finishing_a_restore_takes_the_workspace_off_the_ladder(steps, monkeypatch):
	tenant = FakeTenant(
		status="Archived", purge_after="2026-08-01", purge_warned_on="2026-07-01",
		dunning_started_on="2026-01-01", dunning_stage="Archived",
		suspended_on="2026-02-01", archived_on="2026-03-01",
	)
	monkeypatch.setattr(steps.frappe, "get_doc", lambda *a: tenant)
	monkeypatch.setattr("oneapp_control.lifecycle.events.record", lambda *a, **k: None)
	monkeypatch.setattr("oneapp_control.notifications.emails.restored", lambda *a: None)
	monkeypatch.setattr(steps, "now_datetime", lambda: "2026-06-01 12:00:00")

	steps.finalise_restore(FakeJob())

	assert tenant.status == "Active"
	assert tenant.purge_after is None, "a live workspace must not sit on a purge timer"
	assert tenant.purge_warned_on is None
	assert tenant.dunning_started_on is None
	assert tenant.restored_on is not None


def test_a_restored_workspace_stops_pointing_at_its_cold_copy(steps, monkeypatch):
	"""The objects stay — an hour ago they were somebody's only copy. What
	changes is that retention may now expire them like any other old backup."""
	tenant = FakeTenant()
	monkeypatch.setattr(steps.frappe, "get_doc", lambda *a: tenant)
	monkeypatch.setattr("oneapp_control.lifecycle.events.record", lambda *a, **k: None)
	monkeypatch.setattr("oneapp_control.notifications.emails.restored", lambda *a: None)

	steps.finalise_restore(FakeJob())
	assert tenant.cold_storage_key is None


# --------------------------------------------------------------------------- #
# What retention may do to a promoted copy
# --------------------------------------------------------------------------- #

def test_the_copy_a_workspace_points_at_is_never_expired(backups, monkeypatch):
	"""It may be the only copy of somebody's business."""
	deleted = []
	monkeypatch.setattr(
		backups.frappe.db, "get_value", lambda *a, **k: "cold/acme/20260601-000000"
	)
	monkeypatch.setattr(
		backups, "cold_sets",
		lambda b, t: [{"stamp": "20260601-000000", "keys": ["cold/acme/20260601-000000/db"],
		               "bytes": 1, "modified": None}],
	)
	monkeypatch.setattr(backups.r2, "delete_keys", lambda b, k: deleted.extend(k) or len(k))

	assert backups.expire_orphaned_cold("acme", "bucket", 7) == 0
	assert deleted == []


def test_a_superseded_copy_is_expired_like_any_old_backup(backups, monkeypatch):
	"""A workspace that fell and recovered would otherwise accumulate permanent
	copies of itself, under the one prefix nothing else sweeps."""
	import datetime

	deleted = []
	monkeypatch.setattr(backups.frappe.db, "get_value", lambda *a, **k: "cold/acme/newest")

	def one(stamp, days_old):
		return {
			"stamp": stamp,
			"keys": [f"cold/acme/{stamp}/db"],
			"bytes": 1,
			"modified": datetime.datetime(2026, 6, 1) - datetime.timedelta(days=days_old),
		}

	monkeypatch.setattr(
		backups, "cold_sets",
		lambda b, t: [one("a", 90), one("b", 60), one("newest", 1)],
	)
	monkeypatch.setattr(backups, "now_datetime", lambda: datetime.datetime(2026, 6, 1))
	monkeypatch.setattr(
		backups, "add_to_date",
		lambda w, days=0, hours=0: w + datetime.timedelta(days=days, hours=hours),
	)
	monkeypatch.setattr(
		backups, "get_datetime",
		lambda v: v if isinstance(v, datetime.datetime)
		else datetime.datetime.fromisoformat(str(v)[:19]),
	)
	monkeypatch.setattr(backups.r2, "delete_keys", lambda b, k: deleted.extend(k) or len(k))

	backups.expire_orphaned_cold("acme", "bucket", 7)

	# The held copy never enters the candidate list at all, and of the two that
	# do, the newest is kept the same way an ordinary backup is.
	assert deleted == ["cold/acme/a/db"]
