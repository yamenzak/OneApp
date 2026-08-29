"""Which secrets may leave the control plane.

Bench config is readable by every tenant site on that bench. A credential that
can act across all tenants must never end up there, so the boundary is asserted
rather than left to reviewer memory.
"""

import pytest


@pytest.fixture
def bench_config(stub_frappe):
	from oneapp_control.provisioning import bench_config as module

	return module


class FakeSettings:
	"""Every field populated, so anything the builder reads shows up."""

	def __init__(self):
		self.r2_account_id = "acct"
		self.r2_bucket = "bucket"
		self.r2_public_base = "https://cdn.4dl.app"
		self.r2_access_key = "ak"
		self.mail_domain = "mail.4dl.app"
		self.mail_hourly_limit = 200
		self.cf_account_id = "cfacct"
		self.ai_gateway = "oneapp"
		self.ai_markup_multiplier = 1.5
		self.control_plane_url = "https://admin.4dl.app"
		# Control-plane only — must not reach a bench.
		self.cf_kv_namespace_id = "ns-123"
		self.cf_kv_account_id = "cfacct"
		self.press_api_key = "press-key"

	def get_password(self, field, raise_exception=False):
		return f"secret-{field}"


@pytest.fixture
def built(bench_config, stub_frappe):
	stub_frappe.get_single = lambda *a, **k: FakeSettings()
	return bench_config.build_config()


# Anything that grants authority over *other* tenants, or over the control plane
# itself, is forbidden in bench config.
FORBIDDEN = [
	"cf_kv_token",          # could rewrite every tenant's mail routing
	"cf_kv_namespace_id",
	"press_api_secret",     # could create or destroy any site
	"press_api_key",
	"stripe_webhook_secret",  # could forge payment events
]


@pytest.mark.parametrize("secret", FORBIDDEN)
def test_control_plane_secrets_never_reach_a_bench(built, secret):
	serialised = repr(built)
	assert secret not in serialised
	assert f"secret-{secret}" not in serialised


def test_kv_token_absent_even_though_settings_has_one(built):
	"""FakeSettings.get_password returns a value for any field, so this proves
	the builder omits the key rather than merely finding it empty."""
	assert not any("kv" in key.lower() for key in built)


def test_expected_keys_are_present(built):
	for key in (
		"oneapp_r2_bucket",
		"oneapp_cf_email_token",
		"oneapp_mail_domain",
		"oneapp_ai_gateway",
		"oneapp_control_url",
	):
		assert key in built, key


def test_every_key_is_namespaced(built):
	"""Bench config is shared with frappe and erpnext; unprefixed keys could
	collide with theirs."""
	assert all(key.startswith("oneapp_") for key in built), sorted(built)


def test_blank_values_are_dropped(bench_config, stub_frappe):
	"""A half-filled form must not blank a credential already live on the bench."""

	class Sparse(FakeSettings):
		def __init__(self):
			super().__init__()
			self.r2_bucket = ""
			self.mail_domain = None

		def get_password(self, field, raise_exception=False):
			return None

	stub_frappe.get_single = lambda *a, **k: Sparse()
	built = bench_config.build_config()

	assert "oneapp_r2_bucket" not in built
	assert "oneapp_mail_domain" not in built
	assert "oneapp_cf_email_token" not in built


def test_press_credentials_may_come_from_site_config(stub_frappe, monkeypatch):
	"""A fresh control site has nobody signed in and nothing configured.

	Press can write a site's config over its own API, so site config is how a
	new control plane is handed its keys before a human ever opens it. The
	settings doctype still wins, because rotating a key should be a form save
	rather than a redeploy.
	"""
	from oneapp_control.press import client as module

	stub_frappe.conf = {"press_api_key": "from-conf", "press_api_secret": "conf-secret"}
	monkeypatch.setattr(
		module,
		"settings",
		lambda: type("S", (), {
			"press_api_url": None,
			"press_api_key": None,
			"get_password": lambda self, *a, **k: None,
		})(),
	)

	c = module.PressClient()
	assert c.api_key == "from-conf"
	assert c.api_secret == "conf-secret"


def test_settings_win_over_site_config(stub_frappe, monkeypatch):
	from oneapp_control.press import client as module

	stub_frappe.conf = {"press_api_key": "from-conf", "press_api_secret": "conf-secret"}
	monkeypatch.setattr(
		module,
		"settings",
		lambda: type("S", (), {
			"press_api_url": "https://cloud.frappe.io",
			"press_api_key": "from-settings",
			"get_password": lambda self, *a, **k: "settings-secret",
		})(),
	)

	c = module.PressClient()
	assert c.api_key == "from-settings"
	assert c.api_secret == "settings-secret"
