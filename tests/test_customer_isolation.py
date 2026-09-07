"""Customer endpoint isolation.

Customers act on the control plane, where every other tenant's billing lives.
One account may own several workspaces, so an endpoint has to take a workspace
name — which makes "no parameter at all" unavailable as a defence. The rule
instead is:

    every endpoint touching a workspace goes through require_workspace() or
    require_workspace_admin(), which verify who is asking before returning
    anything.

Two resolvers rather than one, and the line between them is the point:
`require_workspace` is the owner and nobody else, and is what anything that
spends money uses; `require_workspace_admin` also admits an Admin member, which
is what `Tenant Member.access` says an Admin is — "the owner's role, without
being the billing contact". A flag on one function would be a flag somebody
passes wrong on the endpoint that moves money.

Concentrating it in two named functions is what makes it auditable. These tests
read the source rather than executing it, because what is asserted is a property
of the interface: they hold regardless of what any function body does.
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


#: The endpoints an Admin member may reach — exactly the allow-list the tenant
#: relay carries, and read back from it below so the two cannot drift.
ADMIN_MAY_REACH = {
	"members", "invite_member", "remove_member", "set_member_roles",
	"roles", "save_role", "delete_role",
	"domain_instructions", "request_custom_domain",
	"marketplace", "enable_space", "redeem_claim_code",
}


def test_every_workspace_endpoint_verifies_who_is_asking(endpoints):
	"""An endpoint taking a workspace but never checking it owns nothing."""
	for node, _decorator in endpoints:
		args = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
		if "workspace" not in args:
			continue
		source = ast.unparse(node)
		assert "require_workspace(" in source or "require_workspace_admin(" in source, (
			f"{node.name}() takes a workspace but never resolves it"
		)


def test_only_the_named_endpoints_admit_an_admin(endpoints):
	"""The wider door opens onto exactly the rooms it was widened for.

	Anything that spends — checkout, a plan change, a credit pack — is the
	owner's, and the failure this guards is the quiet one: a new endpoint
	written by copying the one above it, which happened to be a People endpoint.
	"""
	for node, _decorator in endpoints:
		if "require_workspace_admin(" not in ast.unparse(node):
			continue
		assert node.name in ADMIN_MAY_REACH, (
			f"{node.name}() admits an Admin member. If that is right, say so in "
			"ADMIN_MAY_REACH and in the tenant relay's allow-list; if it moves "
			"money, it wants require_workspace()"
		)


def test_the_relay_allows_exactly_what_admits_an_admin():
	relay = (
		ROOT / "apps/oneapp_control/oneapp_control/api/tenant.py"
	).read_text()
	body = relay[relay.index("def _may_be_asked"):relay.index("def workspace_admin")]
	named = {
		line.split("customer.")[1].strip().rstrip(",")
		for line in body.splitlines() if "customer." in line and ":" in line
	}
	assert named == ADMIN_MAY_REACH, (
		"a workspace reaches these through the relay and nothing else does, so "
		"the two lists are the same list"
	)


@pytest.mark.parametrize("resolver", ["require_workspace(", "require_workspace_admin("])
def test_a_refusal_does_not_disclose_existence(resolver):
	"""A customer must not be able to probe which workspace names are taken, so
	'not yours' and 'does not exist' return the same error — and so does 'you
	are a member here but not an admin'."""
	source = CUSTOMER_API.read_text()
	at = source.index("def " + resolver.rstrip("("))
	end = source.index("\ndef ", at + 1)
	# Below the docstring: one of these explains itself by quoting the words,
	# and a count over the whole function would be counting the explanation.
	body = source[at:end]
	body = body[body.index('"""', body.index('"""') + 3):]
	assert body.count("Workspace not found") == 1
	assert "does not exist" not in body


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


def code_of(path, name: str) -> str:
	"""A function's statements, without its docstring.

	The prose says what the rule is and names the thing it forbids, so matching
	on the whole source would find the very word the rule is about.
	"""
	import ast

	source = path.read_text() if hasattr(path, "read_text") else path
	fn = next(
		n for n in ast.walk(ast.parse(source))
		if isinstance(n, ast.FunctionDef) and n.name == name
	)
	return "\n".join(ast.unparse(n) for n in fn.body if not isinstance(n, ast.Expr))


def test_a_pack_purchase_does_not_trust_a_client_supplied_price():
	"""Taking both size and price from the caller would let anyone buy a million
	credits for a penny — and taking the size alone would still let them buy the
	expensive pack at the cheap one's price. So the caller names a code and
	nothing else."""
	body = code_of(CUSTOMER_API, "buy_credits")
	assert "amount" not in body, "buy_credits passes an amount"
	assert "credits" not in body, "buy_credits passes a size"
	# The code a customer typed may go through — it is validated server-side and
	# resolves to a Stripe promotion code, never to an amount.
	assert "checkout.start_credit_pack(tenant.name, pack, code)" in body


def test_the_checkout_prices_a_pack_from_the_catalogue():
	"""The receipt names a product that exists, and a reprice archives the old
	Stripe id like everything else we sell — neither of which an inline
	`price_data` amount can do."""
	body = code_of(ROOT / "apps/oneapp_control/oneapp_control/billing/checkout.py",
	               "start_credit_pack")
	assert "pack_catalogue.sellable(pack)" in body
	assert "price_data" not in body, "the amount is being built inline again"
	assert "stripe_price_id" in body


def test_storage_is_not_bought_with_credits():
	"""Mixing the currencies means a large upload silently drains the AI budget
	— a bill nobody can predict from their own behaviour. Storage is an add-on
	on the subscription; credits are a pack. Neither path may reach the other."""
	assert "ledger" not in code_of(CUSTOMER_API, "set_addon")
	assert "storage" not in code_of(CUSTOMER_API, "buy_credits").lower()


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
