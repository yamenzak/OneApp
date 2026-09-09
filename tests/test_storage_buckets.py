"""Two buckets, and what goes on each of them.

There used to be a pool: buckets capped at a couple of hundred tenants, marked
Full at the cap, a fresh one created behind them. It bounded nothing — the same
lifecycle rule gets written against the next bucket, and a key that reaches a
bucket reaches every tenant in it — and its first execution would have been in
the middle of a signup around the two-hundredth customer.

What is left is a lookup: one bucket per jurisdiction, made on the first signup
that needs it. These pin the two things that were actually wrong underneath the
rotation — a fleet-wide CDN host copied onto every bucket, and one key pair for
all of them.
"""

import pytest


@pytest.fixture
def r2(stub_frappe):
	from oneapp_control.cloudflare import r2 as module

	return module


class FakeDoc:
	"""Enough of a Frappe document for the two calls this module makes of one."""

	def __init__(self, values):
		self.__dict__.update(values)
		self.name = values.get("bucket_name") or values.get("name")
		self.passwords = {}

	def insert(self, **kwargs):
		return self

	def db_set(self, field, value):
		setattr(self, field, value)

	def get(self, field, default=None):
		return getattr(self, field, default)

	def get_password(self, field, raise_exception=False):
		return self.passwords.get(field)


@pytest.fixture
def account(stub_frappe):
	"""The account-wide settings, as they are when nothing is bucket-scoped."""
	settings = FakeDoc({"r2_account_id": "acct", "r2_access_key": "account-key"})
	settings.passwords["r2_secret_key"] = "account-secret"
	stub_frappe.get_single = lambda *a, **k: settings
	return settings


# --------------------------------------------------------------------------- #
# One per jurisdiction
# --------------------------------------------------------------------------- #

def test_a_second_tenant_in_a_jurisdiction_gets_the_same_bucket(r2, stub_frappe, monkeypatch):
	stub_frappe.get_all = lambda *a, **k: [{"name": "oneapp-eu-abc"}]
	monkeypatch.setattr(
		r2, "provision_bucket", lambda j="Global": pytest.fail("made a second bucket")
	)

	assert r2.bucket_in("EU") == "oneapp-eu-abc"


def test_the_first_signup_in_a_jurisdiction_makes_its_bucket(r2, stub_frappe, monkeypatch):
	stub_frappe.get_all = lambda *a, **k: []
	made = []
	monkeypatch.setattr(r2, "provision_bucket", lambda j="Global": made.append(j) or "new")

	assert r2.bucket_in("EU") == "new"
	assert made == ["EU"]


def test_a_bucket_is_born_without_a_public_host(r2, stub_frappe, monkeypatch):
	"""The bug the rotation hid.

	`provision_bucket` used to copy the one fleet-wide `r2_public_base` onto
	every bucket it made, so the second bucket's public objects resolved to the
	first bucket's CDN domain. A hostname is bound to one bucket in Cloudflare;
	there is no value here that could be right for both.
	"""
	created = []
	stub_frappe.get_doc = lambda values: created.append(FakeDoc(values)) or created[-1]
	monkeypatch.setattr(r2, "create_bucket", lambda name, jurisdiction: None)

	name = r2.provision_bucket("EU")

	doc = created[0]
	assert name.startswith("oneapp-eu-")
	assert doc.status == "Active"
	assert getattr(doc, "public_base_url", None) is None
	assert not hasattr(doc, "max_tenants"), "the cap is back"


def test_a_bucket_that_cloudflare_refuses_is_retired_with_the_reason(r2, stub_frappe, monkeypatch):
	created = []
	stub_frappe.get_doc = lambda values: created.append(FakeDoc(values)) or created[-1]

	def refuse(name, jurisdiction):
		raise r2.R2Error("Cloudflare R2 403: nope")

	monkeypatch.setattr(r2, "create_bucket", refuse)

	with pytest.raises(r2.R2Error):
		r2.provision_bucket("Global")

	assert created[0].status == "Retired"
	assert "403" in created[0].last_error


def test_a_tenant_keeps_the_bucket_it_has(r2, stub_frappe, monkeypatch):
	"""Moving objects between buckets is a migration, not a reassignment."""
	stub_frappe.get_doc = lambda *a, **k: FakeDoc(
		{"name": "acme", "storage_bucket": "oneapp-gl-old", "storage_jurisdiction": "Global"}
	)
	monkeypatch.setattr(r2, "bucket_in", lambda j="Global": pytest.fail("re-allocated"))

	assert r2.assign("acme") == "oneapp-gl-old"


# --------------------------------------------------------------------------- #
# Whose keys
# --------------------------------------------------------------------------- #

def test_without_bucket_keys_the_account_keys_are_used(r2, stub_frappe, account):
	stub_frappe.db.records[("Storage Bucket", "oneapp-gl-abc")] = True
	stub_frappe.get_doc = lambda *a, **k: FakeDoc({"name": "oneapp-gl-abc"})

	assert r2._keys("oneapp-gl-abc") == ("account-key", "account-secret")


def test_a_bucket_with_its_own_keys_uses_them(r2, stub_frappe, account):
	"""The EU bucket is the reason to bother.

	A token scoped to it cannot read a Global tenant's objects, which turns the
	jurisdiction from a placement decision into something the credential itself
	enforces.
	"""
	stub_frappe.db.records[("Storage Bucket", "oneapp-eu-abc")] = True
	bucket = FakeDoc({"name": "oneapp-eu-abc", "access_key": "eu-key"})
	bucket.passwords["secret_key"] = "eu-secret"
	stub_frappe.get_doc = lambda *a, **k: bucket

	assert r2._keys("oneapp-eu-abc") == ("eu-key", "eu-secret")


def test_half_a_key_pair_falls_back_rather_than_signing_with_nothing(r2, stub_frappe, account):
	"""An access key typed in and a secret never saved is a plausible half-edit.

	Signing with the key and no secret fails every object call on that bucket;
	falling back to the account pair is the same access the bucket had before
	anybody started scoping it.
	"""
	stub_frappe.db.records[("Storage Bucket", "oneapp-eu-abc")] = True
	stub_frappe.get_doc = lambda *a, **k: FakeDoc(
		{"name": "oneapp-eu-abc", "access_key": "eu-key"}
	)

	assert r2._keys("oneapp-eu-abc") == ("account-key", "account-secret")


def test_the_object_client_asks_for_the_buckets_keys(r2, stub_frappe, account, monkeypatch):
	"""Every object call carries its bucket, so `s3` can be scoped to it."""
	import inspect

	for name in ("objects", "copy", "put", "get", "delete_keys", "presign"):
		source = inspect.getsource(getattr(r2, name))
		assert "s3(bucket)" in source, f"{name} builds a client without its bucket"
