"""The control plane's half of the overage window.

The case this exists for: an add-on line leaves a subscription, `_reconcile_addons`
follows Stripe, and a workspace that did nothing is suddenly over its limit. It
should hear about it and get a window, not a refused upload on an ordinary day.
"""

import datetime

import pytest


@pytest.fixture
def overage(stub_frappe, monkeypatch):
	from oneapp_control.lifecycle import overage as module

	fixed = datetime.date(2026, 6, 1)
	monkeypatch.setattr(module, "today", lambda: str(fixed))
	monkeypatch.setattr(
		module, "getdate",
		lambda v=None: fixed if v is None
		else (v if isinstance(v, datetime.date) else datetime.date.fromisoformat(str(v)[:10])),
	)
	def add_to_date(when, days=0, as_string=False):
		# Frappe's own takes a date or a string. `_warn` passes `today()`, which
		# is a string, and `state` passes a date.
		base = when if isinstance(when, datetime.date) else datetime.date.fromisoformat(
			str(when)[:10]
		)
		out = base + datetime.timedelta(days=days)
		return str(out) if as_string else out

	monkeypatch.setattr(module, "add_to_date", add_to_date)
	monkeypatch.setattr(module.policy, "window", lambda name: 7)
	return module


class FakeTenant:
	def __init__(self, over=(), **kw):
		self.name = "acme"
		self._over = list(over)
		self.over_quota_since = None
		self.over_quota_bytes = 0
		self.storage_used_bytes = 40 * 1024**3
		self.storage_quota_bytes = 10 * 1024**3
		self.database_used_bytes = 0
		self.database_quota_bytes = 2 * 1024**3
		self.written = {}
		self.__dict__.update(kw)

	def get(self, key, default=None):
		return getattr(self, key, default)

	def over_quota(self):
		return list(self._over)

	def db_set(self, field, value=None):
		values = field if isinstance(field, dict) else {field: value}
		self.written.update(values)
		for k, v in values.items():
			setattr(self, k, v)


@pytest.fixture
def quiet(overage, monkeypatch):
	sent = []
	monkeypatch.setattr(overage.events, "record", lambda t, e, **k: sent.append(e))
	monkeypatch.setattr(
		"oneapp_control.notifications.emails.over_quota",
		lambda *a, **k: sent.append("email"),
	)
	return sent


def test_a_workspace_inside_its_limits_is_left_alone(overage, quiet):
	tenant = FakeTenant()
	assert overage.check(tenant) == {"enforced": True, "over": []}
	assert quiet == []


def test_going_over_stamps_the_clock_and_the_ceiling(overage, quiet):
	"""The ceiling is taken now, while it is still true. Taking it at the first
	refused upload would ratchet upward every time one more file got through."""
	tenant = FakeTenant(over=["storage"])
	overage.check(tenant)

	assert tenant.over_quota_since == "2026-06-01"
	assert tenant.over_quota_bytes == 40 * 1024**3
	assert quiet == ["Over Quota", "email"]


def test_the_window_is_not_restarted_by_the_next_hourly_report(overage, quiet):
	tenant = FakeTenant(over=["storage"], over_quota_since="2026-05-28",
	                    over_quota_bytes=40 * 1024**3)
	overage.check(tenant)

	assert tenant.over_quota_since == "2026-05-28"
	assert quiet == [], "one email per crossing, not one per hour"


def test_enforcement_is_paused_inside_the_window(overage, quiet):
	tenant = FakeTenant(over=["storage"], over_quota_since="2026-05-28",
	                    over_quota_bytes=40 * 1024**3)
	found = overage.check(tenant)

	assert found["enforced"] is False
	assert found["grace_until"] == "2026-06-04"
	assert found["ceiling_bytes"] == 40 * 1024**3


def test_enforcement_returns_once_the_window_closes(overage, quiet):
	tenant = FakeTenant(over=["storage"], over_quota_since="2026-05-01",
	                    over_quota_bytes=40 * 1024**3)
	assert overage.check(tenant)["enforced"] is True


def test_the_window_closes_on_its_last_day_not_before(overage, quiet):
	tenant = FakeTenant(over=["storage"], over_quota_since="2026-05-25")
	assert overage.check(tenant)["enforced"] is False  # grace_until is 2026-06-01

	tenant = FakeTenant(over=["storage"], over_quota_since="2026-05-24")
	assert overage.check(tenant)["enforced"] is True


def test_coming_back_under_clears_everything(overage, quiet):
	tenant = FakeTenant(over=[], over_quota_since="2026-05-28",
	                    over_quota_bytes=40 * 1024**3)
	found = overage.check(tenant)

	assert tenant.over_quota_since is None
	assert tenant.over_quota_bytes == 0
	assert found == {"enforced": True, "over": []}
	assert quiet == ["Back Under Quota"]


def test_a_second_resource_going_over_does_not_open_a_second_window(overage, quiet):
	"""One clock. It is cleared only when everything is back under, so a
	workspace that fixed its storage and later filled its database gets a fresh
	window for the second — but one that goes over while already over does not
	get an extension."""
	tenant = FakeTenant(over=["storage", "database"], over_quota_since="2026-05-28")
	overage.check(tenant)

	assert tenant.over_quota_since == "2026-05-28"


def test_the_email_names_every_resource_and_the_date(overage, monkeypatch):
	captured = {}
	monkeypatch.setattr(overage.events, "record", lambda *a, **k: None)
	monkeypatch.setattr(
		"oneapp_control.notifications.emails.over_quota",
		lambda name, resources, grace_until: captured.update(
			resources=resources, grace_until=grace_until
		),
	)

	overage.check(FakeTenant(over=["storage", "database"]))
	assert captured == {"resources": ["storage", "database"], "grace_until": "2026-06-08"}
