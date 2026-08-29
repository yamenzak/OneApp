"""Customer endpoint isolation.

Customers act on the control plane, where every other tenant's billing lives.
The rule that keeps them apart is that the tenant is resolved from the session
user and never from a parameter — so there is no argument a caller can supply
that changes which workspace they act on.

These tests read the source rather than executing it, because what is being
asserted is a property of the interface: they would still hold if every function
body changed.
"""

import ast
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CUSTOMER_API = ROOT / "apps/oneapp_control/oneapp_control/api/customer.py"


def whitelisted_functions(path: Path):
	tree = ast.parse(path.read_text())
	for node in tree.body:
		if not isinstance(node, ast.FunctionDef):
			continue
		for decorator in node.decorator_list:
			source = ast.unparse(decorator)
			if "whitelist" in source:
				yield node, source


@pytest.fixture
def endpoints():
	return list(whitelisted_functions(CUSTOMER_API))


def test_there_are_customer_endpoints(endpoints):
	assert endpoints, "no whitelisted functions found — has the file moved?"


def test_no_customer_endpoint_accepts_a_tenant_argument(endpoints):
	"""The whole isolation model. A `tenant` parameter would let any customer
	name someone else's workspace."""
	for node, _decorator in endpoints:
		args = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
		for forbidden in ("tenant", "tenant_name", "site", "customer", "owner", "user"):
			assert forbidden not in args, (
				f"{node.name}() takes '{forbidden}' — it must resolve the tenant "
				"from the session user instead"
			)


def test_no_customer_endpoint_is_guest_accessible(endpoints):
	"""A guest has no tenant to resolve, so my_tenant would raise — but an
	allow_guest here would mean someone intended otherwise."""
	for node, decorator in endpoints:
		assert "allow_guest" not in decorator, f"{node.name}() is guest-accessible"


def test_every_endpoint_resolves_the_tenant_itself(endpoints):
	"""Each one must call my_tenant(), which is where the ownership check lives."""
	exempt = {"credit_packs"}  # static server-side data, tenant-independent

	for node, _decorator in endpoints:
		if node.name in exempt:
			continue
		body = ast.unparse(node)
		assert "my_tenant()" in body, f"{node.name}() never calls my_tenant()"


def test_buy_credits_does_not_trust_a_client_supplied_price():
	"""Taking both size and price from the caller would let anyone buy a million
	credits for a penny."""
	source = CUSTOMER_API.read_text()
	assert "find_pack" in source
	assert "CREDIT_PACKS" in source
	# The amount passed to checkout must come from the pack, not the argument.
	assert "amount=pack[" in source


def test_customer_role_has_no_desk_access():
	"""Desk access on the control plane would expose every other tenant."""
	signup = (ROOT / "apps/oneapp_control/oneapp_control/provisioning/signup.py").read_text()
	assert '"desk_access": 0' in signup


def test_signup_endpoints_are_the_only_guest_surface():
	"""Anything else reachable by a guest is an accident."""
	signup_api = ROOT / "apps/oneapp_control/oneapp_control/api/signup.py"
	guest = [n.name for n, d in whitelisted_functions(signup_api) if "allow_guest" in d]
	assert set(guest) <= {"check_slug", "plans", "start", "status"}, guest


def test_signup_status_does_not_leak_tenant_internals():
	"""The id is effectively public, so the status payload must stay sparse."""
	source = (ROOT / "apps/oneapp_control/oneapp_control/api/signup.py").read_text()
	status_fn = source[source.index("def status("):]
	for leaked in ("hmac_secret", "press_site", "shard", "owner_email", "stripe"):
		assert leaked not in status_fn, f"status() exposes {leaked}"
