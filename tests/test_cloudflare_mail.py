"""What we actually send Cloudflare when the platform's mail is brought up.

None of this can be checked against a live account from a test, so what is
checked is the shape of the requests — which is where the mistakes are. A
binding named wrongly, a missing `main_module`, a catch-all that forwards
instead of invoking the worker: each one deploys cleanly and then silently
fails to route a customer's mail.
"""

import json

import pytest


@pytest.fixture
def cf(stub_frappe):
	from oneapp_control.cloudflare import api

	return api


@pytest.fixture
def workers(stub_frappe):
	from oneapp_control.cloudflare import workers as module

	return module


@pytest.fixture
def routing(stub_frappe):
	from oneapp_control.cloudflare import email as module

	return module


class Settings:
	def __init__(self, **kw):
		self.cf_kv_namespace_id = kw.get("namespace", "")
		self.cf_kv_account_id = kw.get("account", "acct-1")
		self.cf_account_id = "acct-1"
		self.cf_zone_id = kw.get("zone", "zone-1")
		self.mail_domain = kw.get("mail_domain", "4dl.app")
		self._secrets = kw.get("secrets", {"cf_admin_token": "admin-token"})

	def get_password(self, field, raise_exception=False):
		return self._secrets.get(field, "")


@pytest.fixture
def sent(monkeypatch, cf):
	"""Every call the code would have made, instead of making it."""
	calls = []

	def record(method, path, purpose="admin", **kwargs):
		calls.append({"method": method, "path": path, "purpose": purpose, **kwargs})
		# Enough of an answer for the callers that read one.
		if path.endswith("/storage/kv/namespaces") and method == "POST":
			return {"id": "ns-new"}
		if path.endswith("/storage/kv/namespaces"):
			return []
		return {}

	monkeypatch.setattr(cf, "call", record)
	return calls


# --------------------------------------------------------------------------- #
# The token boundary
# --------------------------------------------------------------------------- #

def test_a_narrow_token_wins_where_one_is_set(cf, monkeypatch):
	monkeypatch.setattr(
		cf, "settings",
		lambda: Settings(secrets={"cf_admin_token": "admin", "cf_kv_token": "narrow"}),
	)
	assert cf.token("kv") == "narrow"
	assert cf.token("admin") == "admin"


def test_the_account_token_stands_in_where_none_is(cf, monkeypatch):
	"""What makes "give it one token" true."""
	monkeypatch.setattr(cf, "settings", lambda: Settings())
	assert cf.token("kv") == "admin-token"
	assert cf.token("dns") == "admin-token"


# --------------------------------------------------------------------------- #
# The worker
# --------------------------------------------------------------------------- #

def test_the_namespace_is_found_before_it_is_made(workers, cf, sent, monkeypatch, stub_frappe):
	"""Creating a second namespace leaves the worker reading an empty one."""
	monkeypatch.setattr(cf, "settings", lambda: Settings())
	monkeypatch.setattr(
		cf, "call",
		lambda method, path, purpose="admin", **kw: (
			[{"id": "ns-existing", "title": workers.NAMESPACE_TITLE}]
			if method == "GET" else {"id": "ns-new"}
		),
	)
	assert workers.ensure_namespace() == "ns-existing"


def test_the_upload_says_which_module_to_run(workers, cf, sent, monkeypatch):
	monkeypatch.setattr(cf, "settings", lambda: Settings(namespace="ns-1"))

	workers.deploy()

	upload = next(one for one in sent if one["method"] == "PUT")
	metadata = json.loads(upload["files"]["metadata"][1])

	# Without `main_module` Cloudflare has a file and no entry point.
	assert metadata["main_module"] == "email-inbound.js"
	assert metadata["main_module"] in upload["files"]
	assert upload["files"][metadata["main_module"]][2] == "application/javascript+module"


def test_the_worker_is_given_its_map_and_its_domain(workers, cf, sent, monkeypatch):
	monkeypatch.setattr(cf, "settings", lambda: Settings(namespace="ns-1"))

	workers.deploy()

	upload = next(one for one in sent if one["method"] == "PUT")
	bindings = {
		one["name"]: one for one in json.loads(upload["files"]["metadata"][1])["bindings"]
	}

	# The names the worker reads. `env.TENANTS` and `env.MAIL_DOMAIN` are what
	# `src/index.js` asks for, and a binding named anything else is a worker
	# that rejects every message as an unknown recipient.
	assert bindings["TENANTS"]["type"] == "kv_namespace"
	assert bindings["TENANTS"]["namespace_id"] == "ns-1"
	assert bindings["MAIL_DOMAIN"]["text"] == "4dl.app"
	assert "MAX_ATTACHMENT_BYTES" in bindings


def test_the_runtime_date_is_pinned(workers, cf, sent, monkeypatch):
	"""A compatibility date that moved on every deploy would change the runtime
	under a worker nobody edited."""
	monkeypatch.setattr(cf, "settings", lambda: Settings(namespace="ns-1"))

	workers.deploy()

	upload = next(one for one in sent if one["method"] == "PUT")
	metadata = json.loads(upload["files"]["metadata"][1])
	assert metadata["compatibility_date"] == workers.COMPATIBILITY_DATE
	assert "nodejs_compat" in metadata["compatibility_flags"]


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #

def test_the_catch_all_invokes_the_worker(routing, cf, sent, monkeypatch):
	"""`forward` sends mail to an address. `worker` runs our code. The two look
	alike in the API and are not alike at all."""
	monkeypatch.setattr(cf, "settings", lambda: Settings())

	routing.point_catch_all("oneapp-email-inbound")

	rule = next(one for one in sent if one["path"].endswith("rules/catch_all"))
	body = rule["json"]
	assert body["enabled"] is True
	assert body["matchers"] == [{"type": "all"}]
	assert body["actions"] == [
		{"type": "worker", "value": ["oneapp-email-inbound"]}
	]


def test_everything_arriving_matches(routing, cf, sent, monkeypatch):
	"""One rule, for ever. An address is a row on a tenant site, and Cloudflare
	holding a second copy of that list would be a list that goes stale — and
	200 rules is a limit a per-address scheme would eventually meet."""
	monkeypatch.setattr(cf, "settings", lambda: Settings())

	routing.point_catch_all()

	rule = next(one for one in sent if one["path"].endswith("rules/catch_all"))
	assert rule["json"]["matchers"] == [{"type": "all"}]


def test_enabling_twice_is_not_a_failure(routing, cf, monkeypatch):
	"""The bring-up is meant to be pressed whenever somebody is unsure."""
	def already(method, path, purpose="admin", **kw):
		raise cf.CloudflareError("Cloudflare 400: 1001 email routing already enabled")

	monkeypatch.setattr(cf, "settings", lambda: Settings())
	monkeypatch.setattr(cf, "call", already)

	assert routing.enable() == {"already": True}


def test_a_catch_all_pointed_elsewhere_is_not_ours(routing, cf, monkeypatch):
	monkeypatch.setattr(cf, "settings", lambda: Settings())
	monkeypatch.setattr(
		cf, "call",
		lambda *a, **k: {"enabled": True, "actions": [{"type": "forward", "value": ["x@y.com"]}]},
	)
	assert routing.points_at_worker() is False
