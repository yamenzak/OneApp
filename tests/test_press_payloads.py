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


# --------------------------------------------------------------------------- #
# Signature collisions
#
# The Recorder above replaces `call` entirely, so it cannot catch a clash between
# `call`'s own positional and a parameter press expects to receive. These tests
# drive the real `call` with the HTTP layer mocked instead.
# --------------------------------------------------------------------------- #

@pytest.fixture
def wired(stub_frappe, monkeypatch):
	"""A real PressClient with only requests.post mocked."""
	from oneapp_control.press import client as module

	sent = {}

	class Response:
		status_code = 200

		@staticmethod
		def json():
			return {"message": {"ok": True}}

	def fake_post(url, headers=None, data=None, timeout=None):
		sent["url"] = url
		sent["body"] = json.loads(data)
		return Response()

	monkeypatch.setattr(module.requests, "post", fake_post)

	c = object.__new__(module.PressClient)
	c.url = "https://cloud.frappe.io"
	c.api_key = "k"
	c.api_secret = "s"
	return c, sent


def test_run_doc_method_does_not_collide_with_call_signature(wired):
	"""press.api.client.run_doc_method takes a parameter named `method`. If
	`call`'s positional shares that name, this raises TypeError before any
	request is made — which broke every domain operation."""
	c, sent = wired
	c.run_doc_method("Site", "acme.frappe.cloud", "add_domain", {"domain": "acme.4dl.app"})

	assert sent["url"].endswith("/api/method/press.api.client.run_doc_method")
	assert sent["body"]["dt"] == "Site"
	assert sent["body"]["dn"] == "acme.frappe.cloud"
	assert sent["body"]["method"] == "add_domain"
	assert json.loads(sent["body"]["args"]) == {"domain": "acme.4dl.app"}


@pytest.mark.parametrize(
	"call,expected_method",
	[
		(lambda c: c.add_domain("s", "d.4dl.app"), "add_domain"),
		(lambda c: c.set_primary_domain("s", "d.4dl.app"), "set_host_name"),
		(lambda c: c.remove_domain("s", "d.4dl.app"), "remove_domain"),
	],
)
def test_domain_operations_reach_the_wire(wired, call, expected_method):
	c, sent = wired
	call(c)
	assert sent["body"]["method"] == expected_method


def test_endpoint_is_not_sent_as_a_parameter(wired):
	"""The endpoint belongs in the URL, not the body."""
	c, sent = wired
	c.site_exists("acme", "frappe.cloud")
	assert "endpoint" not in sent["body"]
	assert sent["body"] == {"subdomain": "acme", "domain": "frappe.cloud"}


# --------------------------------------------------------------------------- #
# Which parameters press parses, and which it does not.
#
# There is no rule to it. `bench.update_config` json.loads its `config`, so a
# dict has to be dumped; `bench.deploy` does not parse `apps` at all and
# iterated a JSON string character by character.
#
# Both failed the same way from the outside: a bare HTTP 500 naming an exception
# type and nothing about the parameter. These pin the shapes that were confirmed
# against the live API — and they are pinned rather than rediscovered, because
# the credentials that confirmed them are gone.
# --------------------------------------------------------------------------- #


def test_bench_config_is_still_a_dumped_string(wired):
	# The counterexample: this one press *does* parse, so it must stay a string.
	client, sent = wired
	client.update_bench_config("bench-1", {"a": 1})
	assert isinstance(sent["body"]["config"], str)


# --------------------------------------------------------------------------- #
# Pipelines
# --------------------------------------------------------------------------- #

def test_no_pipeline_repeats_a_step_name():
	"""The runner resumes by looking the step name up in its pipeline, and
	`list.index` returns the first match.

	A pipeline with two steps called the same thing sends the job back to the
	earlier one every time it reaches the later one, and loops until the attempt
	ceiling. Nothing about the pipeline declaration makes that visible, which is
	why it is a test — the two `await_agent` calls a restore genuinely needs are
	the obvious way to write it and the wrong one.
	"""
	import ast
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent
	tree = ast.parse(
		(root / "apps/oneapp_control/oneapp_control/provisioning/steps.py").read_text()
	)
	pipelines = next(
		node.value
		for node in ast.walk(tree)
		if isinstance(node, ast.Assign)
		and any(getattr(t, "id", None) == "PIPELINES" for t in node.targets)
	)

	for action, steps in zip(pipelines.keys, pipelines.values, strict=True):
		names = [step.elts[0].value for step in steps.elts]
		assert len(names) == len(set(names)), (
			f"{action.value} repeats a step name: "
			f"{[n for n in names if names.count(n) > 1]}"
		)
