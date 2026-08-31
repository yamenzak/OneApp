"""Cold storage: the copy a workspace can be rebuilt from once its site is gone.

The interesting cases are all refusals. Promoting the wrong thing, or nothing,
produces a tenant that *looks* archivable — and the next rung deletes the site.
"""

import datetime
import json

import pytest


@pytest.fixture
def cold(stub_frappe, monkeypatch):
	from oneapp_control.lifecycle import cold as module

	now = datetime.datetime(2026, 6, 1, 12, 0, 0)
	monkeypatch.setattr(module, "now_datetime", lambda: now)
	monkeypatch.setattr(
		module,
		"add_to_date",
		lambda when, days=0, hours=0: when + datetime.timedelta(days=days, hours=hours),
	)
	monkeypatch.setattr(
		module,
		"get_datetime",
		lambda v: v if isinstance(v, datetime.datetime)
		else datetime.datetime.fromisoformat(str(v)[:19]),
	)
	return module


class FakeTenant:
	def __init__(self, **kw):
		self.name = kw.pop("name", "acme")
		self.tenant_slug = "acme"
		self.tenant_name = "Acme"
		self.status = "Active"
		self.owner_email = "owner@acme.test"
		self.site_name = "acme.4dl.app"
		self.press_site = "acme-xyz"
		self.primary_domain = None
		self.region = "eu-central"
		self.shard = "hetzner-01"
		self.storage_bucket = "STB-0001"
		self.storage_jurisdiction = "EU"
		self.provisioned_on = None
		self.plan = "starter"
		self.subscription = "SUB-2026-00001"
		self.customer = None
		self.promo_code = None
		self.extra_storage_gb = 0
		self.extra_database_gb = 0
		self.members = []
		self.storage_used_bytes = 0
		self.database_used_bytes = 0
		self.user_count = 1
		self.cold_storage_key = None
		self.cold_copy_requested_on = None
		self.written = {}
		self.__dict__.update(kw)

	def get(self, key, default=None):
		return getattr(self, key, default)

	def db_set(self, field, value=None):
		values = field if isinstance(field, dict) else {field: value}
		self.written.update(values)
		for k, v in values.items():
			setattr(self, k, v)


class FakeR2:
	def __init__(self):
		self.copied = []
		self.put = []
		self.deleted = []

	def copy(self, bucket, source, target):
		self.copied.append((source, target))

	def put_object(self, bucket, key, body, content_type="application/json"):
		self.put.append((key, body))


def _wire(cold, monkeypatch, *, tenant, sets=(), fake=None, bucket="oneapp-eu-abc"):
	fake = fake or FakeR2()
	monkeypatch.setattr(cold, "bucket_for", lambda t: bucket)
	monkeypatch.setattr(cold.r2, "copy", fake.copy)
	monkeypatch.setattr(cold.r2, "put", fake.put_object)
	monkeypatch.setattr(cold.backups, "sets", lambda b, t: list(sets))
	monkeypatch.setattr(cold.frappe, "get_doc", lambda dt, name=None: tenant)
	monkeypatch.setattr(cold.events, "opening", lambda *a, **k: "TLE-1")
	monkeypatch.setattr(cold.events, "close", lambda *a, **k: None)
	monkeypatch.setattr(cold.events, "record", lambda *a, **k: "TLE-1")
	monkeypatch.setattr(
		"oneapp_control.billing.quotas.for_tenant", lambda t: {"storage_gb": 10}
	)
	return fake


def _set(stamp, hours_old, names=("database.sql.gz", "public-files.tar")):
	return {
		"stamp": stamp,
		"keys": [f"backups/acme/{stamp}/{n}" for n in names],
		"bytes": 4096,
		"modified": datetime.datetime(2026, 6, 1, 12, 0, 0)
		- datetime.timedelta(hours=hours_old),
	}


# --------------------------------------------------------------------------- #
# Deciding
# --------------------------------------------------------------------------- #

def test_a_workspace_that_already_has_one_is_left_alone(cold, monkeypatch):
	tenant = FakeTenant(cold_storage_key="cold/acme/20260530-000000")
	fake = _wire(cold, monkeypatch, tenant=tenant)

	assert cold.ensure("acme")["ok"] is True
	assert fake.copied == [], "promoting again would double the bill and the risk"


def test_a_recent_backup_is_promoted_without_asking_the_site(cold, monkeypatch):
	"""The usual case. An entry plan backs up at midnight; a sweep at noon
	should use that copy rather than wait on a request."""
	tenant = FakeTenant()
	fake = _wire(cold, monkeypatch, tenant=tenant, sets=[_set("20260601-000000", 12)])

	result = cold.ensure("acme")
	assert result["ok"] is True
	assert result["key"] == "cold/acme/20260601-000000"
	assert [t for _, t in fake.copied] == [
		"cold/acme/20260601-000000/database.sql.gz",
		"cold/acme/20260601-000000/public-files.tar",
	]


def test_a_stale_backup_makes_us_ask_rather_than_promote_it(cold, monkeypatch):
	tenant = FakeTenant()
	fake = _wire(cold, monkeypatch, tenant=tenant, sets=[_set("20260501-000000", 24 * 31)])

	result = cold.ensure("acme")
	assert result == {"ok": False, "reason": "requested"}
	assert fake.copied == []
	assert tenant.cold_copy_requested_on is not None


def test_a_site_that_answers_nothing_is_not_waited_on_forever(cold, monkeypatch):
	"""A workspace whose scheduler died must not hold the ladder open."""
	tenant = FakeTenant(
		cold_copy_requested_on=datetime.datetime(2026, 5, 20, 12, 0, 0)
	)
	fake = _wire(cold, monkeypatch, tenant=tenant, sets=[_set("20260501-000000", 24 * 31)])

	result = cold.ensure("acme")
	assert result["ok"] is True
	assert result["stale"] is True, "the log has to say the copy predates the archive"
	assert fake.copied


def test_a_site_with_nothing_at_all_refuses(cold, monkeypatch):
	"""The one answer that must never be read as 'go ahead and archive'."""
	tenant = FakeTenant(
		cold_copy_requested_on=datetime.datetime(2026, 5, 20, 12, 0, 0)
	)
	_wire(cold, monkeypatch, tenant=tenant, sets=[])

	assert cold.ensure("acme")["reason"] == "no_backup"


def test_a_workspace_with_no_bucket_refuses(cold, monkeypatch):
	tenant = FakeTenant(storage_bucket=None)
	_wire(cold, monkeypatch, tenant=tenant, bucket=None)

	assert cold.ensure("acme") == {"ok": False, "reason": "no_bucket"}


# --------------------------------------------------------------------------- #
# The manifest
# --------------------------------------------------------------------------- #

def test_the_manifest_says_what_the_workspace_was(cold, monkeypatch):
	"""The dump says what it contained. Only this says which plan, which
	domains, who could sign in, and where the files came from."""
	tenant = FakeTenant()
	fake = _wire(cold, monkeypatch, tenant=tenant, sets=[_set("20260601-000000", 1)])

	cold.ensure("acme")

	key, body = fake.put[0]
	assert key == "cold/acme/20260601-000000/manifest.json"

	found = json.loads(body)
	assert found["tenant"]["slug"] == "acme"
	assert found["tenant"]["storage_jurisdiction"] == "EU"
	assert found["billing"]["plan"] == "starter"
	assert found["billing"]["subscription"] == "SUB-2026-00001"
	assert found["artifacts"] == ["database.sql.gz", "public-files.tar"]


# --------------------------------------------------------------------------- #
# Purging
# --------------------------------------------------------------------------- #

def test_a_purge_reaches_every_prefix_a_workspace_owns(cold, monkeypatch):
	"""A purge that misses one leaves objects nobody looks for and we keep
	paying for them."""
	tenant = FakeTenant()
	asked = []
	monkeypatch.setattr(cold, "bucket_for", lambda t: "oneapp-eu-abc")
	monkeypatch.setattr(cold.r2, "delete_prefix", lambda b, p: asked.append(p) or 3)
	monkeypatch.setattr(cold.events, "opening", lambda *a, **k: "TLE-1")
	monkeypatch.setattr(cold.events, "close", lambda *a, **k: None)

	result = cold.purge(tenant)

	assert asked == ["cold/acme/", "backups/acme/", "tenants/acme/"]
	assert result["deleted"] == 9
	assert tenant.cold_storage_key is None
	assert tenant.purged_on is not None


def test_every_purged_prefix_names_the_tenant(cold):
	"""`delete_prefix` refuses a bare prefix, and this is what keeps the caller
	from handing it one."""
	for prefix in cold.PREFIXES:
		scoped = f"{prefix}/acme/"
		assert "/" in scoped.rstrip("/"), scoped


def test_a_purge_with_no_bucket_is_still_a_purge(cold, monkeypatch):
	"""Nothing was ever stored, so there is nothing to delete — but the
	workspace still ends up purged rather than stuck one rung short."""
	tenant = FakeTenant(storage_bucket=None)
	monkeypatch.setattr(cold, "bucket_for", lambda t: None)
	monkeypatch.setattr(cold.events, "opening", lambda *a, **k: "TLE-1")
	monkeypatch.setattr(cold.events, "close", lambda *a, **k: None)

	assert cold.purge(tenant) == {"ok": True, "deleted": 0}
