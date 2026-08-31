"""Storage quota enforcement."""

import pytest


@pytest.fixture
def quota(stub_frappe, monkeypatch):
	from oneapp.oneapp_core.storage import quota as module

	# The ordinary case, so a test only says so when it is about the exception.
	# Left unstubbed this reaches the site-state singleton, which the stub
	# answers with None — an AttributeError in every test about a file size.
	monkeypatch.setattr(module, "overage", lambda: {"enforced": True})
	return module


class FakeFile:
	def __init__(self, size):
		self.file_size = size


def _set_quota(monkeypatch, quota, value):
	monkeypatch.setattr(quota, "quota_bytes", lambda: value)


def _set_used(monkeypatch, quota, value):
	monkeypatch.setattr(quota, "current_usage", lambda: value)


def _enforcing(monkeypatch, quota):
	"""The ordinary case: no overage window open, so the plan's limit stands."""
	monkeypatch.setattr(quota, "overage", lambda: {"enforced": True})


def _in_grace(monkeypatch, quota, ceiling):
	"""A window is open, and this is how large the workspace may grow."""
	monkeypatch.setattr(
		quota, "overage",
		lambda: {"enforced": False, "ceiling_bytes": ceiling, "grace_until": "2026-06-08"},
	)


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


# --------------------------------------------------------------------------- #
# The overage window
# --------------------------------------------------------------------------- #
# A workspace can end up over its limit without doing anything: an add-on line
# leaves the subscription, the quota comes down, and from in here the next
# upload fails on an ordinary day. The control plane opens a window instead —
# and a window that let usage grow without limit would be a free upgrade, so it
# is bounded at what they were already holding.

def test_a_window_lets_a_workspace_over_its_limit_keep_working(quota, monkeypatch):
	_set_quota(monkeypatch, quota, 10 * GB)
	_set_used(monkeypatch, quota, 40 * GB)
	_in_grace(monkeypatch, quota, ceiling=45 * GB)

	quota.enforce_quota(FakeFile(1 * GB))


def test_a_window_does_not_let_usage_grow_past_the_ceiling(quota, monkeypatch):
	"""They can replace a file and delete their way back under. They cannot
	treat the window as a larger plan."""
	_set_quota(monkeypatch, quota, 10 * GB)
	_set_used(monkeypatch, quota, 44 * GB)
	_in_grace(monkeypatch, quota, ceiling=45 * GB)

	with pytest.raises(quota.StorageQuotaExceeded):
		quota.enforce_quota(FakeFile(2 * GB))


def test_the_refusal_inside_a_window_does_not_quote_the_plan_limit(quota, monkeypatch):
	"""Telling somebody 10 GB remains when they are holding 44 is a message
	they cannot act on."""
	_set_quota(monkeypatch, quota, 10 * GB)
	_set_used(monkeypatch, quota, 44 * GB)
	_in_grace(monkeypatch, quota, ceiling=45 * GB)

	with pytest.raises(quota.StorageQuotaExceeded) as caught:
		quota.enforce_quota(FakeFile(2 * GB))

	assert "10.0 GB" not in str(caught.value)
	assert "cannot grow" in str(caught.value)


def test_a_ceiling_below_the_plan_limit_never_shrinks_the_plan(quota, monkeypatch):
	"""A grace window can only be more permissive than the quota it stands in
	for. A stale ceiling would otherwise enforce something nobody agreed to."""
	_set_quota(monkeypatch, quota, 50 * GB)
	_set_used(monkeypatch, quota, 20 * GB)
	_in_grace(monkeypatch, quota, ceiling=1 * GB)

	quota.enforce_quota(FakeFile(1 * GB))


def test_the_database_is_not_blocked_inside_a_window(quota, monkeypatch):
	"""There is no ceiling that would work here: the block is on inserts, and
	half-blocking those gives a workspace that can be typed into and not saved.
	"""
	monkeypatch.setattr(quota, "database_over_quota", lambda: True)
	monkeypatch.setattr(quota, "database_quota_bytes", lambda: 2 * GB)
	_in_grace(monkeypatch, quota, ceiling=45 * GB)

	quota.enforce_database_quota(FakeDoc("Sales Invoice"))


def test_the_database_is_blocked_once_the_window_closes(quota, monkeypatch):
	monkeypatch.setattr(quota, "database_over_quota", lambda: True)
	monkeypatch.setattr(quota, "database_quota_bytes", lambda: 2 * GB)

	with pytest.raises(quota.DatabaseQuotaExceeded):
		quota.enforce_database_quota(FakeDoc("Sales Invoice"))


def test_an_unsynced_site_enforces_rather_than_letting_everything_through(quota,
                                                                         monkeypatch):
	"""Absent reads as "enforce", which is the safe direction."""
	monkeypatch.setattr(quota, "overage", lambda: {})
	assert quota.enforcement_ceiling() is None


class FakeDoc:
	def __init__(self, doctype):
		self.doctype = doctype
