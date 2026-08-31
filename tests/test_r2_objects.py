"""Object-level R2 access on the control plane.

The bucket admin above it has been there since Phase 6. This is the half the
lifecycle needs — promote, presign, expire, purge — and it is the half that can
delete a customer's only copy of their workspace, so the refusals are the point.
"""

import pytest


@pytest.fixture
def r2(stub_frappe):
	from oneapp_control.cloudflare import r2 as module

	return module


class FakeS3:
	def __init__(self, pages=None):
		self.pages = pages or [{"Contents": [], "IsTruncated": False}]
		self.deleted = []
		self.copied = []
		self.calls = 0

	def list_objects_v2(self, **kwargs):
		page = self.pages[min(self.calls, len(self.pages) - 1)]
		self.calls += 1
		return page

	def delete_objects(self, Bucket, Delete):
		keys = [row["Key"] for row in Delete["Objects"]]
		self.deleted.extend(keys)
		return {}

	def copy_object(self, Bucket, CopySource, Key):
		self.copied.append((CopySource["Key"], Key))


def _install(monkeypatch, r2, fake):
	monkeypatch.setattr(r2, "s3", lambda: fake)
	return fake


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #

def test_listing_follows_every_page(r2, monkeypatch):
	"""A tenant with more than a thousand objects is not a tenant we ignore."""
	fake = _install(monkeypatch, r2, FakeS3([
		{
			"Contents": [{"Key": "backups/acme/a", "Size": 10, "LastModified": 1}],
			"IsTruncated": True,
			"NextContinuationToken": "more",
		},
		{
			"Contents": [{"Key": "backups/acme/b", "Size": 5, "LastModified": 2}],
			"IsTruncated": False,
		},
	]))

	rows = r2.objects("bucket", "backups/acme/")
	assert [row["key"] for row in rows] == ["backups/acme/a", "backups/acme/b"]
	assert fake.calls == 2


def test_listing_comes_back_oldest_first(r2, monkeypatch):
	"""Retention deletes from the front, so the order is load-bearing."""
	_install(monkeypatch, r2, FakeS3([{
		"Contents": [
			{"Key": "b", "Size": 1, "LastModified": 30},
			{"Key": "a", "Size": 1, "LastModified": 10},
			{"Key": "c", "Size": 1, "LastModified": 20},
		],
		"IsTruncated": False,
	}]))

	assert [row["key"] for row in r2.objects("bucket", "backups/acme/")] == ["a", "c", "b"]


def test_prefix_bytes_sums_what_is_there(r2, monkeypatch):
	_install(monkeypatch, r2, FakeS3([{
		"Contents": [
			{"Key": "a", "Size": 100, "LastModified": 1},
			{"Key": "b", "Size": 250, "LastModified": 2},
		],
		"IsTruncated": False,
	}]))

	assert r2.prefix_bytes("bucket", "cold/acme/") == 350


# --------------------------------------------------------------------------- #
# Deleting
# --------------------------------------------------------------------------- #

def test_delete_prefix_refuses_an_empty_prefix(r2, monkeypatch):
	"""`delete_prefix(bucket, "")` would empty the bucket for every tenant in it.

	One missing f-string argument produces exactly that call, which is why the
	refusal is here rather than in the caller.
	"""
	_install(monkeypatch, r2, FakeS3())

	for prefix in ("", "   ", "/", None):
		with pytest.raises(r2.R2Error):
			r2.delete_prefix("bucket", prefix)


def test_delete_prefix_refuses_a_prefix_that_names_no_tenant(r2, monkeypatch):
	"""`backups/` is every workspace's backups, not one workspace's."""
	fake = _install(monkeypatch, r2, FakeS3())

	for prefix in ("backups", "backups/", "cold/", "tenants/"):
		with pytest.raises(r2.R2Error):
			r2.delete_prefix("bucket", prefix)

	assert fake.deleted == []


def test_delete_prefix_accepts_one_scoped_to_a_tenant(r2, monkeypatch):
	fake = _install(monkeypatch, r2, FakeS3([{
		"Contents": [
			{"Key": "cold/acme/2026/db.sql.gz", "Size": 1, "LastModified": 1},
			{"Key": "cold/acme/2026/files.tar", "Size": 1, "LastModified": 2},
		],
		"IsTruncated": False,
	}]))

	assert r2.delete_prefix("bucket", "cold/acme/") == 2
	assert fake.deleted == ["cold/acme/2026/db.sql.gz", "cold/acme/2026/files.tar"]


def test_deleting_nothing_is_not_a_request(r2, monkeypatch):
	fake = _install(monkeypatch, r2, FakeS3())
	assert r2.delete_keys("bucket", []) == 0
	assert fake.deleted == []


def test_deleting_batches_at_the_page_size(r2, monkeypatch):
	"""S3 refuses a delete of more than a thousand keys in one call."""
	fake = _install(monkeypatch, r2, FakeS3())
	keys = [f"backups/acme/{i}" for i in range(2500)]

	assert r2.delete_keys("bucket", keys) == 2500
	assert len(fake.deleted) == 2500


# --------------------------------------------------------------------------- #
# Copying
# --------------------------------------------------------------------------- #

def test_promotion_is_a_server_side_copy(r2, monkeypatch):
	"""The bytes never travel through the control plane.

	Promoting a 4 GB backup should cost a request, not four gigabytes of
	transfer on a machine that has no business moving them.
	"""
	fake = _install(monkeypatch, r2, FakeS3())
	r2.copy("bucket", "backups/acme/x/db.sql.gz", "cold/acme/x/db.sql.gz")

	assert fake.copied == [("backups/acme/x/db.sql.gz", "cold/acme/x/db.sql.gz")]
