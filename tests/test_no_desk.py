"""The desk is not part of this product, for anyone.

DECISIONS §7 says so, and it is the kind of claim that decays quietly: a doctype
gains a field, the field is only editable in /app, and nobody notices until an
operator is told to "just open the desk" — at which point running this requires
knowing Frappe, which is the thing the claim was protecting against.

So the claim is checked rather than remembered. Every doctype the control plane
defines has to be reachable from OneAdmin, and every doctype the tenant app
defines has to be reachable from OneSpace, unless it is on a list that says why
not.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "apps/oneapp_control/oneapp_control"
CONTROL_SRC = ROOT / "apps/oneapp_control/frontend/src"
TENANT_SRC = ROOT / "apps/oneapp/frontend/src"


def doctypes(app_dir: Path) -> dict[str, dict]:
	found = {}
	for path in sorted(app_dir.rglob("*/doctype/*/*.json")):
		if path.parent.name != path.stem:
			continue
		data = json.loads(path.read_text())
		if data.get("name"):
			found[data["name"]] = data
	return found


# A doctype needs no surface of its own when it is reached through its parent,
# or when nothing about it is ever a decision.
EXEMPT = {
	# Child tables. Edited through the document that owns them, and a table with
	# its own page would be a second, disagreeing way in.
	"Tenant Member": "child table, edited on the workspace's People page",
	"Plan Price": "child table, written by the Stripe sync and shown on the plan",
	"OneApp App Doctype": "child table; the permission manifest is code, not config",
	# Written by the system, read through something else.
	"Credit Reservation": (
		"held for an in-flight call and released on completion; the balance it "
		"affects is on the workspace's Billing tab"
	),
	"App Entitlement": "granted and revoked on the workspace's Apps tab",
	"Support Login": "an audit record, listed on the workspace's Activity tab",
	"Credit Ledger Entry": "listed on the workspace's Billing tab",
	"Subscription": "shown, and moved between plans, on the workspace's Billing tab",
}


def _spa_source(src: Path) -> str:
	return "\n".join(
		p.read_text() for p in sorted(src.rglob("*")) if p.suffix in (".vue", ".js")
	)


def _endpoints_by_doctype(module: Path) -> dict[str, set[str]]:
	"""Which whitelisted endpoints read or write each doctype.

	Naming a doctype in the SPA is not the only way to reach it — most of these
	are reached through an endpoint that names it server-side, which is the
	better design. So the check follows that path rather than demanding the
	string appear in a .vue file.
	"""
	import ast

	source = module.read_text()
	tree = ast.parse(source)
	found: dict[str, set[str]] = {}

	for node in ast.walk(tree):
		if not isinstance(node, ast.FunctionDef):
			continue
		decorated = any(
			"whitelist" in ast.unparse(d) for d in node.decorator_list
		)
		if not decorated:
			continue
		body = ast.get_source_segment(source, node) or ""
		for name in re.findall(r'"([A-Z][A-Za-z ]+)"', body):
			found.setdefault(name, set()).add(node.name)
	return found


def test_every_control_doctype_is_reachable_from_oneadmin():
	spa = _spa_source(CONTROL_SRC)
	endpoints = _endpoints_by_doctype(CONTROL / "api/admin.py")

	missing = []
	for name in doctypes(CONTROL):
		if name in EXEMPT:
			continue
		if name in spa:
			continue
		# Reached through an endpoint the SPA actually calls.
		if any(f"admin.{fn}" in spa for fn in endpoints.get(name, ())):
			continue
		missing.append(name)

	assert not missing, (
		"these have no operator surface, so the desk is the only way to see or "
		"change them: " + ", ".join(sorted(missing))
	)


def test_the_exemptions_say_why():
	"""An exemption without a reason is a to-do that stopped looking like one."""
	for name, reason in EXEMPT.items():
		assert len(reason) > 20, f"{name} is exempt for no stated reason"


def test_the_exemption_list_has_no_stale_entries():
	"""A doctype that has since gone should not leave a rule behind."""
	known = set(doctypes(CONTROL))
	stale = set(EXEMPT) - known
	assert not stale, f"these no longer exist: {sorted(stale)}"


# --------------------------------------------------------------------------- #
# The things an operator has to be able to *do*
#
# Reachability is necessary and not sufficient: a doctype can be listed and
# still be unchangeable. These name the specific actions that were desk-only.
# --------------------------------------------------------------------------- #

ADMIN_API = (CONTROL / "api/admin.py").read_text()


@pytest.mark.parametrize(
	"endpoint,why",
	[
		("update_shard", "draining a server is accepts_new_tenants = 0"),
		("signups", "a signup that paid and failed to provision is otherwise invisible"),
		("webhook_events", "the webhook answers 200 on failure; the row is the replay"),
		("replay_webhook", "and replaying it has to be possible"),
		("standby_pool", "an empty warm pool is a slow signup"),
		("tenant_app_access", "granting a restricted app"),
		("tenant_billing", "what a workspace is on, and on whose terms"),
		("adopt_plan_terms", "the deliberate half of grandfathering"),
		("set_tenant_plan", "moving a workspace between plans"),
	],
)
def test_the_operator_can_do_it_without_the_desk(endpoint, why):
	assert f"def {endpoint}(" in ADMIN_API, f"{endpoint} is missing — {why}"

	api = (CONTROL_SRC / "lib/api.js").read_text()
	assert f"admin.{endpoint}" in api, f"{endpoint} is not wired into the SPA — {why}"


def test_a_catalogue_an_operator_must_populate_has_a_form():
	"""A read-only catalogue that nothing else writes is a dead end: the control
	plane can show its price sheet and never write one."""
	for panel, doctype in (
		("PlansSettings.vue", "Plan"),
		("RegionsSettings.vue", "Region"),
		("AppsSettings.vue", "OneApp App"),
	):
		source = (CONTROL_SRC / "components/settings" / panel).read_text()
		assert ':form="FORM"' in source, f"{panel} is read-only, so {doctype} needs the desk"


def test_a_form_only_offers_fields_the_list_actually_fetches():
	"""A field in the form but not in `fields` reads as empty and is written back
	as empty on the first save."""
	offenders = []
	for path in sorted((CONTROL_SRC / "components/settings").glob("*Settings.vue")):
		source = path.read_text()
		if ':form="FORM"' not in source:
			continue

		fields = set(re.findall(r"'(\w+)'", _block(source, "FIELDS", ":fields")))
		form = set(re.findall(r"name: '(\w+)'", _block(source, "FORM", None)))
		missing = form - fields
		if missing:
			offenders.append(f"{path.name}: {sorted(missing)}")
	assert not offenders, "form fields that are never fetched: " + "; ".join(offenders)


def _block(source: str, const: str, attr: str | None) -> str:
	"""The literal a constant or an inline attribute is declared with."""
	match = re.search(rf"const {const} = (\[.*?\n\])", source, re.S)
	if match:
		return match.group(1)
	if attr:
		match = re.search(rf'{attr}="(\[[^"]*\])"', source, re.S)
		if match:
			return match.group(1)
	return ""


# Frappe's desk is at /app. A SPA route of the same shape is not a desk link —
# OneSpace's own app route is `/app/:appCode` under a `/one` history base, so it
# resolves to /one/app/crm — so this looks for *navigation*, not for the string.
DESK_NAVIGATION = re.compile(
	r"""(?:href\s*=\s*["'`]|window\.location(?:\.href)?\s*=\s*["'`]|window\.open\(\s*["'`])/app\b"""
)


@pytest.mark.parametrize("src", [CONTROL_SRC, TENANT_SRC], ids=["oneapp_control", "oneapp"])
def test_no_spa_sends_anyone_into_the_desk(src):
	"""Neither an operator nor a customer is ever handed to /app.

	The one link would be enough: it teaches that the real interface is
	elsewhere, and everything not yet built in the SPA stops looking unfinished.
	"""
	offenders = []
	for path in sorted(src.rglob("*")):
		if path.suffix not in (".vue", ".js"):
			continue
		if DESK_NAVIGATION.search(path.read_text()):
			offenders.append(path.relative_to(src).as_posix())
	assert not offenders, "these navigate into the desk: " + ", ".join(offenders)


# --------------------------------------------------------------------------- #
# Seeded apps
#
# The registry's seed exists so the entitlement pipeline has something running
# through it end to end. It is not a product catalogue, and the difference is
# one field: General availability puts a row in every customer's launcher.
# --------------------------------------------------------------------------- #

INSTALL = CONTROL / "install.py"


def _seed_specs() -> list[dict]:
	import ast as _ast

	source = INSTALL.read_text()
	tree = _ast.parse(source)
	for node in _ast.walk(tree):
		if isinstance(node, _ast.Assign) and getattr(node.targets[0], "id", "") == "SEED_APPS":
			return _ast.literal_eval(_ast.get_source_segment(source, node.value))
	raise AssertionError("SEED_APPS is gone")


def test_a_seeded_app_is_not_offered_to_customers():
	"""Nobody decided to build these. A seed reaching a launcher is a promise of
	software that does not exist, made to someone paying for it — and, for an app
	naming ERPNext doctypes, write access to them over the REST API."""
	offenders = [
		spec["app_code"]
		for spec in _seed_specs()
		if spec.get("availability") != "Restricted"
	]
	assert not offenders, (
		"seeded apps must be Restricted until someone decides to build them: "
		+ ", ".join(offenders)
	)


def test_restricted_is_the_default_a_seed_gets_by_saying_nothing():
	"""Reaching every customer should be opted into, not arrived at by
	forgetting to say."""
	body = INSTALL.read_text()
	seeder = body[body.index("def seed_apps"):]
	assert '"availability": "Restricted"' in seeder


def test_the_seed_says_what_it_is_for():
	"""This one was introduced inside a commit about a generator bug, described
	as "seeds a first app", and read afterwards as a product decision."""
	body = INSTALL.read_text()
	header = body[: body.index("SEED_APPS = [")]
	assert "not a product" in header.lower()

	for spec in _seed_specs():
		assert "no interface" in (spec.get("description") or "").lower(), spec["app_code"]


def test_existing_installs_are_corrected_without_taking_anything_away():
	patch = (CONTROL / "patches/restrict_seeded_books.py").read_text()
	assert "App Entitlement" in patch, "workspaces that had it would silently lose it"
	assert 'availability != "General"' in patch, "an operator's own decision must survive"
	assert "oneapp_control.patches.restrict_seeded_books" in (CONTROL / "patches.txt").read_text()
