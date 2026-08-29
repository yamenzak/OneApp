"""Storage quota enforcement."""

import pytest


@pytest.fixture
def quota(stub_frappe, monkeypatch):
	from oneapp.oneapp_core.storage import quota as module

	return module


class FakeFile:
	def __init__(self, size):
		self.file_size = size


def _set_quota(monkeypatch, quota, value):
	monkeypatch.setattr(quota, "quota_bytes", lambda: value)


def _set_used(monkeypatch, quota, value):
	monkeypatch.setattr(quota, "current_usage", lambda: value)


GB = 1024 ** 3


def test_allows_upload_within_quota(quota, monkeypatch):
	_set_quota(monkeypatch, quota, 10 * GB)
	_set_used(monkeypatch, quota, 1 * GB)
	quota.enforce_quota(FakeFile(1 * GB))


def test_blocks_upload_that_would_exceed(quota, monkeypatch):
	_set_quota(monkeypatch, quota, 10 * GB)
	_set_used(monkeypatch, quota, 9 * GB)
	with pytest.raises(quota.StorageQuotaExceeded):
		quota.enforce_quota(FakeFile(2 * GB))


def test_blocks_exactly_at_the_boundary(quota, monkeypatch):
	_set_quota(monkeypatch, quota, 10 * GB)
	_set_used(monkeypatch, quota, 10 * GB)
	with pytest.raises(quota.StorageQuotaExceeded):
		quota.enforce_quota(FakeFile(1))


def test_allows_filling_exactly_to_quota(quota, monkeypatch):
	_set_quota(monkeypatch, quota, 10 * GB)
	_set_used(monkeypatch, quota, 9 * GB)
	quota.enforce_quota(FakeFile(1 * GB))


def test_unconfigured_quota_does_not_block(quota, monkeypatch):
	"""Zero means unconfigured. Refusing every upload because a sync failed
	would be worse than brief overage."""
	_set_quota(monkeypatch, quota, 0)
	_set_used(monkeypatch, quota, 100 * GB)
	quota.enforce_quota(FakeFile(1 * GB))


def test_zero_byte_file_is_allowed(quota, monkeypatch):
	_set_quota(monkeypatch, quota, 10 * GB)
	_set_used(monkeypatch, quota, 10 * GB)
	quota.enforce_quota(FakeFile(0))


def test_error_message_tells_the_user_what_to_do(quota, monkeypatch):
	_set_quota(monkeypatch, quota, 10 * GB)
	_set_used(monkeypatch, quota, 10 * GB)
	with pytest.raises(quota.StorageQuotaExceeded) as excinfo:
		quota.enforce_quota(FakeFile(5 * GB))

	message = str(excinfo.value)
	assert "Delete some files or upgrade" in message
	assert "GB" in message


@pytest.mark.parametrize(
	"value,expected",
	[(0, "0 B"), (512, "512 B"), (1536, "1.5 KB"), (5 * 1024**3, "5.0 GB")],
)
def test_format_bytes(quota, value, expected):
	assert quota.format_bytes(value) == expected
