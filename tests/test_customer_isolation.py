"""Customer endpoint isolation.

Customers act on the control plane, where every other tenant's billing lives.
One account may own several workspaces, so an endpoint has to take a workspace
name — which makes "no parameter at all" unavailable as a defence. The rule
instead is:

    every endpoint touching a workspace goes through require_workspace(),
    which verifies ownership before returning anything.

Concentrating it in one function is what makes it auditable. These tests read the
source rather than executing it, because what is asserted is a property of the
interface: they hold regardless of what any function body does.
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


def test_workspace_endpoints_take_a_workspace_not_a_tenant(endpoints):
	"""One name for the parameter, so the ownership check has one shape.

	`tenant`, `site` or `owner` would each be a second convention, and a second
	convention is where the check gets forgotten.
	"""
	for node, _decorator in endpoints:
		args = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
		for forbidden in ("tenant", "tenant_name", "site", "customer", "owner", "user"):
			assert forbidden not in args, (
				f"{node.name}() takes '{forbidden}' — workspace endpoints take "
				"'workspace' and verify it through require_workspace()"
			)


def test_every_workspace_endpoint_verifies_ownership(endpoints):
	"""An endpoint taking a workspace but never checking it owns nothing."""
	for node, _decorator in endpoints:
		args = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
		if "workspace" not in args:
			continue
		assert "require_workspace(" in ast.unparse(node), (
			f"{node.name}() takes a workspace but never calls require_workspace()"
		)


def test_ownership_failure_does_not_disclose_existence():
	"""A customer must not be able to probe which workspace names are taken, so
	'not yours' and 'does not exist' return the same error."""
	source = CUSTOMER_API.read_text()
	check = source[source.index("def require_workspace("):source.index("@frappe.whitelist()")]
	assert check.count("Workspace not found") == 1
	assert "does not exist" not in check


def test_no_customer_endpoint_is_guest_accessible(endpoints):
	"""A guest has no tenant to resolve, so my_tenant would raise — but an
	allow_guest here would mean someone intended otherwise."""
	for node, decorator in endpoints:
		assert "allow_guest" not in decorator, f"{node.name}() is guest-accessible"


def test_listing_workspaces_is_scoped_to_the_session_user(endpoints):
	"""my_workspaces takes no argument at all — it is the one endpoint that
	answers 'which are mine', so it must read the session and nothing else."""
	source = CUSTOMER_API.read_text()
	listing = source[source.index("def my_workspaces("):source.index("def overview(")]
	assert "frappe.session.user" in listing
	assert '"owner_user": user' in listing


@pytest.mark.parametrize("fn,table", [("buy_credits", "CREDIT_PACKS"), ("buy_storage", "STORAGE_PACKS")])
def test_pack_purchases_do_not_trust_a_client_supplied_price(fn, table):
	"""Taking both size and price from the caller would let anyone buy a million
	credits, or a terabyte, for a penny."""
	source = CUSTOMER_API.read_text()
	body = source[source.index(f"def {fn}("):]
	body = body[: body.index("@frappe.whitelist()")] if "@frappe.whitelist()" in body else body

	assert table in body, f"{fn} must look the price up in {table}"
	assert 'chosen["amount"]' in body, f"{fn} must charge the table price, not an argument"
	assert "amount: float" not in body, f"{fn} must not accept an amount"


def test_storage_is_not_bought_with_credits():
	"""Mixing the currencies means a large upload silently drains the AI budget
	— a bill nobody can predict from their own behaviour."""
	source = CUSTOMER_API.read_text()
	body = source[source.index("def buy_storage("):]
	assert "ledger" not in body[: body.index("@frappe.whitelist()")]


def test_customer_role_has_no_desk_access():
	"""Desk access on the control plane would expose every other tenant."""
	signup = (ROOT / "apps/oneapp_control/oneapp_control/provisioning/signup.py").read_text()
	assert '"desk_access": 0' in signup


# The entire public surface of the control plane, and what each one may do.
# Adding to this list is a deliberate act: everything here is reachable without
# any credential at all.
GUEST_SURFACE = {
	"signup_open": "says whether signup can run — no data",
	"regions": "regions with capacity — public catalogue",
	"plans": "pricing — public catalogue",
	"check_slug": "availability of one name the caller supplied",
	"start": "creates an Account Request and a checkout session",
	"status": "progress of one request, by unguessable id",
}


def test_the_guest_surface_is_exactly_what_we_intend():
	"""Anything else reachable without credentials is an accident."""
	signup_api = ROOT / "apps/oneapp_control/oneapp_control/api/signup.py"
	guest = {n.name for n, d in whitelisted_functions(signup_api) if "allow_guest" in d}
	assert guest == set(GUEST_SURFACE), (
		f"guest surface changed: added {guest - set(GUEST_SURFACE)}, "
		f"removed {set(GUEST_SURFACE) - guest}"
	)


def test_no_other_module_exposes_a_guest_endpoint():
	"""Signup and the HMAC tenant channel are the only unauthenticated paths."""
	api_dir = ROOT / "apps/oneapp_control/oneapp_control/api"
	allowed = {"signup.py", "tenant.py"}

	for path in api_dir.glob("*.py"):
		if path.name in allowed or path.name == "__init__.py":
			continue
		guest = [n.name for n, d in whitelisted_functions(path) if "allow_guest" in d]
		assert not guest, f"{path.name} exposes guest endpoints: {guest}"


def test_public_catalogue_endpoints_do_not_mutate():
	"""A GET-shaped endpoint that writes is how rate limits get bypassed."""
	source = (ROOT / "apps/oneapp_control/oneapp_control/api/signup.py").read_text()
	for fn in ("plans", "regions", "signup_open"):
		body = source[source.index(f"def {fn}("):]
		body = body[: body.index("@frappe.whitelist")] if "@frappe.whitelist" in body else body
		for mutation in (".insert(", ".save(", "db_set(", "set_value("):
			assert mutation not in body, f"{fn}() mutates via {mutation}"


def test_signup_start_is_rate_limited():
	"""It creates records and calls Stripe, so it is the one worth scripting."""
	source = (ROOT / "apps/oneapp_control/oneapp_control/api/signup.py").read_text()
	body = source[source.index("def start("):source.index("def status(")]
	assert "_rate_limit(" in body


def test_signup_status_does_not_leak_tenant_internals():
	"""The id is effectively public, so the status payload must stay sparse."""
	source = (ROOT / "apps/oneapp_control/oneapp_control/api/signup.py").read_text()
	status_fn = source[source.index("def status("):]
	for leaked in ("hmac_secret", "press_site", "shard", "owner_email", "stripe"):
		assert leaked not in status_fn, f"status() exposes {leaked}"
