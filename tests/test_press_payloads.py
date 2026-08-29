"""Press request payload shapes.

Press is inconsistent here in a way that costs a real provisioning run to find:
`Site.update_config` the *doc method* takes a mapping, while
`press.api.site.update_config` the *API* takes a list of {key, value, type}.
Handing it a dict makes press iterate the keys as strings and die with a bare
ValueError, which says nothing about the cause.
"""

import json

import pytest


class Recorder:
	"""Stands in for PressClient.call and keeps the arguments."""

	def __init__(self):
		self.method = None
		self.params = None

	def __call__(self, method, **params):
		self.method = method
		self.params = params
		return {}


@pytest.fixture
def client(stub_frappe, monkeypatch):
	from oneapp_control.press import client as module

	c = object.__new__(module.PressClient)
	c.url = "https://cloud.frappe.io"
	c.api_key = "k"
	c.api_secret = "s"
	c.call = Recorder()
	return c


def _sent(client):
	return json.loads(client.call.params["config"])


def test_site_config_is_a_list_of_key_value_type(client):
	client.update_config("acme.frappe.cloud", {"oneapp_tenant": "acme"})
	sent = _sent(client)

	assert isinstance(sent, list), "a dict makes press raise a bare ValueError"
	assert sent == [{"key": "oneapp_tenant", "value": "acme", "type": "String"}]


def test_bench_config_uses_the_same_shape(client):
	client.update_bench_config("bench-1", {"oneapp_mail_domain": "mail.4dl.app"})
	sent = _sent(client)

	assert isinstance(sent, list)
	assert sent[0]["key"] == "oneapp_mail_domain"


@pytest.mark.parametrize(
	"value,expected",
	[
		("text", "String"),
		(200, "Number"),
		(1.5, "Number"),
		(True, "Boolean"),
		({"a": 1}, "JSON"),
		([1, 2], "JSON"),
	],
)
def test_value_types_are_declared(client, value, expected):
	"""Press types unknown keys from the declared type, so a number sent as a
	string comes back as a string in site_config."""
	client.update_config("acme.frappe.cloud", {"k": value})
	assert _sent(client)[0]["type"] == expected


def test_bool_is_not_reported_as_number(client):
	"""bool is a subclass of int — checking int first would mistype it."""
	client.update_config("acme.frappe.cloud", {"flag": True})
	assert _sent(client)[0]["type"] == "Boolean"


def test_site_new_sends_version(client):
	"""Without version press cannot match a dedicated-server bench and falls
	back to its public path, which cannot see private app sources."""
	client.create_site(
		subdomain="acme", domain="frappe.cloud", release_group="bench-1",
		apps=["frappe", "erpnext"], server="s1.frappe.cloud", version="Nightly",
	)
	assert client.call.params["site"]["version"] == "Nightly"


def test_site_new_omits_version_when_absent(client):
	client.create_site(
		subdomain="acme", domain="frappe.cloud", release_group="bench-1",
		apps=["frappe"],
	)
	assert "version" not in client.call.params["site"]
