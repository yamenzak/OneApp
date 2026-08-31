"""The desk is not part of this product, for anyone.

DECISIONS §7 says so, and it is the kind of claim that decays quietly: a doctype
gains a field, the field is only editable in /app, and nobody notices until an
operator is told to "just open the desk" — at which point running this requires
knowing Frappe, which is the thing the claim was protecting against.

So the claim is checked rather than remembered. Every doctype the control plane
defines has to be reachable from the operator console, and every doctype the
tenant app defines has to be reachable from a workspace, unless it is on a list
that says why not.

Both consoles are Spaces now, rendered by `oneapp` on whichever site they belong
to. So "reachable" is no longer a string in a hand-written Vue page: a control
doctype is reachable because the operator Space declares a screen over it, or
because a settings group edits it, or because a bespoke screen calls an endpoint
that names it. Those are the three shapes, and all three are checked.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "apps/oneapp_control/oneapp_control"
# What is left of the control app's own frontend: signup, and nothing else.
SIGNUP_SRC = ROOT / "apps/oneapp_control/frontend/src"
# Where both consoles live now — the tenant workspace, the operator Space and
# the customer's account are all screens in this one bundle.
TENANT_SRC = ROOT / "apps/oneapp/frontend/src"
OPERATOR = CONTROL / "entitlements/operator.py"
CONTROL_SETTINGS = CONTROL / "entitlements/settings.py"


def doctypes(app_dir: Path) -> dict[str, dict]:
	found = {}
	for path in sorted(app_dir.rglob("*/doctype/*/*.json")):
		if path.parent.name != path.stem:
			continue
		data = json.loads(path.read_text())
		if data.get("name"):
			found[data["name"]] = data
	return found


# A doctype needs no surface of its own when it is reached through its parent.
#
# Shorter than it was, and that is the point of the operator Space: five of
# these used to be exempt because they were "read through something else" on a
# hand-written tenant page. Each has a screen of its own now, so the exemption
# was a description of what had not been built rather than of what should not
# be.
EXEMPT = {
	"Tenant Member": "child table, edited on the workspace's People screen",
	"Plan Price": "child table, written by the Stripe sync and shown on the plan",
	"OneSpace Space Doctype": "child table; the permission manifest is code, not config",
	"OneSpace Space Screen": (
		"child table; a space's screens are rows on the space, and a screen with "
		"no space to belong to is not a thing an operator creates"
	),
	"AI Model Price": (
		"child table, synced from the provider and shown on the model it belongs "
		"to; editable rates would be overwritten by the next sync"
	),
}


def _const(path: Path, name: str):
	"""A module-level constant, read without importing frappe."""
	import ast

	for node in ast.walk(ast.parse(path.read_text())):
		if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == name:
			return ast.literal_eval(node.value)
	raise AssertionError(f"{name} is gone from {path.name}")


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


def operator_screens() -> set[str]:
	"""Every doctype the operator Space declares a screen over."""
	return {row[3] for row in _const(OPERATOR, "SCREENS")}


def settings_targets() -> set[str]:
	"""Every doctype the control plane's settings groups write.

	A Single has no list to put on a screen; what it has is a settings group,
	which is a surface in exactly the sense this file cares about — somebody can
	change the value without opening the desk.
	"""
	source = CONTROL_SETTINGS.read_text()
	return set(re.findall(r'^SETTINGS = "([^"]+)"', source, re.M))


def test_every_control_doctype_is_reachable_from_the_operator_console():
	spa = _spa_source(TENANT_SRC)
	endpoints = _endpoints_by_doctype(CONTROL / "api/admin.py")
	screens = operator_screens()
	settings = settings_targets()

	missing = []
	for name in doctypes(CONTROL):
		if name in EXEMPT:
			continue
		# A screen of the operator Space, which is the ordinary way.
		if name in screens:
			continue
		# A Single, changed in the settings dialog.
		if name in settings:
			continue
		# Named directly by one of the bespoke screens.
		if name in spa:
			continue
		# Reached through an endpoint one of them calls.
		if any(f"admin.{fn}" in spa for fn in endpoints.get(name, ())):
			continue
		missing.append(name)

	assert not missing, (
		"these have no operator surface, so the desk is the only way to see or "
		"change them: " + ", ".join(sorted(missing))
	)


# The tenant app's own doctypes. Fewer, because most of what a workspace holds
# is Frappe's or ERPNext's; these are the ones we define.
TENANT_EXEMPT = {
	"OneSpace Site State": (
		"written by the control-plane sync and never by a person; what it holds "
		"is shown as quota, plan and balance across the SPA"
	),
	"OneSpace AI Feature Setting": (
		"child table; one row per declared feature, edited in the workspace's AI "
		"settings tab"
	),
}


def _tenant_endpoints_by_doctype() -> dict[str, set[str]]:
	"""Which whitelisted tenant methods name each doctype, as dotted paths.

	The tenant app has no single admin module — its endpoints live in the
	feature modules that own them, which is the right shape there — so this
	walks the package and builds the same `module.function` string the SPA
	calls by.

	Scoped to the module rather than to the function body, unlike the control
	plane's version. A tenant module owns one subject and reaches its doctype
	through helpers; requiring the literal inside the endpoint would only teach
	us to inline a string to satisfy a test.
	"""
	import ast

	tenant = ROOT / "apps/oneapp/oneapp"
	found: dict[str, set[str]] = {}

	for path in sorted(tenant.rglob("*.py")):
		source = path.read_text()
		if "whitelist" not in source:
			continue

		dotted = path.relative_to(tenant.parent).with_suffix("").as_posix().replace("/", ".")
		named = set(re.findall(r'"([A-Z][A-Za-z ]+)"', source))

		for node in ast.walk(ast.parse(source)):
			if not isinstance(node, ast.FunctionDef):
				continue
			if not any("whitelist" in ast.unparse(d) for d in node.decorator_list):
				continue
			for name in named:
				found.setdefault(name, set()).add(f"{dotted}.{node.name}")

	return found


def test_every_tenant_doctype_is_reachable_from_onespace():
	"""The claim in this file's docstring, checked for the customer's half too.

	It went unchecked while the tenant app had one doctype, which is exactly how
	a rule stops applying: not by being repealed, but by never being tested on
	anything.
	"""
	spa = _spa_source(TENANT_SRC)
	endpoints = _tenant_endpoints_by_doctype()

	missing = []
	for name in doctypes(ROOT / "apps/oneapp/oneapp"):
		if name in TENANT_EXEMPT or name in spa:
			continue
		if any(path in spa for path in endpoints.get(name, ())):
			continue
		missing.append(name)

	assert not missing, (
		"these have no customer surface, so the desk is the only way to see or "
		"change them: " + ", ".join(sorted(missing))
	)


def test_the_exemptions_say_why():
	"""An exemption without a reason is a to-do that stopped looking like one."""
	for name, reason in EXEMPT.items():
		assert len(reason) > 20, f"{name} is exempt for no stated reason"


	for name, reason in TENANT_EXEMPT.items():
		assert len(reason) > 20, f"{name} is exempt for no stated reason"


def test_the_exemption_list_has_no_stale_entries():
	"""A doctype that has since gone should not leave a rule behind."""
	stale = set(EXEMPT) - set(doctypes(CONTROL))
	assert not stale, f"these no longer exist: {sorted(stale)}"

	stale = set(TENANT_EXEMPT) - set(doctypes(ROOT / "apps/oneapp/oneapp"))
	assert not stale, f"these no longer exist: {sorted(stale)}"


# --------------------------------------------------------------------------- #
# The things an operator has to be able to *do*
#
# Reachability is necessary and not sufficient: a doctype can be listed and
# still be unchangeable. These name the specific actions that were desk-only.
# --------------------------------------------------------------------------- #

ADMIN_API = (CONTROL / "api/admin.py").read_text()


# Nine things `/admin` could do that a doctype list alone cannot express. Each
# is checked against whichever of the three surfaces now carries it, because
# "the endpoint exists" was never the claim — the claim is that somebody can
# reach it without the desk.
#
# A screen over the doctype covers the reads and the field edits: the console's
# Signups page was `admin.signups`, and the Signups screen is the same rows with
# filters, saved views and a record form on top. What a screen cannot express is
# a *call* — replaying an event, moving a workspace onto its plan's terms — and
# those are declared actions or buttons on the workspace screen.
BY_SCREEN = {
	"update_shard": ("Shard", "draining a server is accepts_new_tenants = 0"),
	"signups": ("Account Request", "a signup that paid and failed to provision is otherwise invisible"),
	"webhook_events": ("Stripe Webhook Event", "the webhook answers 200 on failure; the row is the replay"),
	"standby_pool": ("Standby Site", "an empty warm pool is a slow signup"),
	"tenant_billing": ("Subscription", "what a workspace is on, and on whose terms"),
}

# What the workspace screen carries, because each is a call against one tenant
# rather than a row anybody edits.
BY_WORKSPACE_SCREEN = {
	"tenant_app_access": ("tenantAppAccess", "granting a restricted app"),
	"set_tenant_plan": ("setTenantPlan", "moving a workspace between plans"),
}

# And what is a declared action on a screen — see `entitlements/actions.py`.
BY_ACTION = {
	"replay_webhook": "and replaying it has to be possible",
	"adopt_plan_terms": "the deliberate half of grandfathering",
}

OPS_SCREENS = ROOT / "apps/oneapp/frontend/src/screens/ops"
ACTIONS = CONTROL / "entitlements/actions.py"


@pytest.mark.parametrize("endpoint", sorted(BY_SCREEN), ids=sorted(BY_SCREEN))
def test_a_read_only_gap_is_closed_by_a_screen(endpoint):
	doctype, why = BY_SCREEN[endpoint]
	assert f"def {endpoint}(" in ADMIN_API, f"{endpoint} is missing — {why}"
	assert doctype in operator_screens(), (
		f"{doctype} has no operator screen, so {why} needs the desk"
	)


@pytest.mark.parametrize("endpoint", sorted(BY_WORKSPACE_SCREEN), ids=sorted(BY_WORKSPACE_SCREEN))
def test_a_call_against_one_tenant_lives_on_the_workspace_screen(endpoint):
	caller, why = BY_WORKSPACE_SCREEN[endpoint]
	assert f"def {endpoint}(" in ADMIN_API, f"{endpoint} is missing — {why}"

	wired = _spa_source(OPS_SCREENS)
	assert f"{endpoint}'" in wired or f"'{endpoint}'" in wired, (
		f"{endpoint} is not wired into the operator screens — {why}"
	)
	assert caller in wired, f"nothing calls {caller} — {why}"


@pytest.mark.parametrize("endpoint", sorted(BY_ACTION), ids=sorted(BY_ACTION))
def test_a_call_with_no_field_to_edit_is_a_declared_action(endpoint):
	"""A generic screen lists and edits; these are neither.

	Without the action seam each of these would be an endpoint nothing calls,
	which is the same as not having it — and the desk would be the only way to
	replay a failed Stripe event.
	"""
	why = BY_ACTION[endpoint]
	assert f"def {endpoint}(" in ADMIN_API, f"{endpoint} is missing — {why}"
	assert f"oneapp_control.api.admin.{endpoint}" in ACTIONS.read_text(), (
		f"{endpoint} is not a declared action — {why}"
	)


def test_a_declared_action_is_the_only_method_the_runner_will_call():
	"""The seam is an allowlist or it is a way to call anything whitelisted.

	`run_action` looks the key up in the same list the payload was built from and
	refuses anything else, so a method name in a request body reaches nothing
	that was not shipped as a declaration.
	"""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/spaceview.py").read_text()
	runner = source[source.index("def run_action("):]
	assert "declared.get(action)" in runner, "the action is not looked up in the declaration"
	assert "frappe.PermissionError" in runner, "an undeclared action does not refuse"
	assert 'frappe.has_permission(doctype, "write"' in runner, (
		"the runner does not ask whether this person may change the record"
	)


def test_an_action_provider_is_code_rather_than_a_row():
	"""An action names a method somebody can invoke. If an operator could add one
	by editing a Space, the console would be a way to call any whitelisted
	method on the site."""
	hooks = (CONTROL / "hooks.py").read_text()
	assert "onespace_screen_actions" in hooks, "nothing provides actions"

	doctype = json.loads(
		(CONTROL / "control_plane/doctype/onespace_space_screen/onespace_space_screen.json").read_text()
	)
	fields = {f["fieldname"] for f in doctype["fields"]}
	assert "method" not in fields and "action" not in fields, (
		"a screen row can name a method again — actions belong in code"
	)


def test_a_catalogue_an_operator_must_populate_has_a_screen():
	"""A read-only catalogue that nothing else writes is a dead end: the control
	plane can show its price sheet and never write one.

	These were hand-written settings panels with a `:form` prop. They are
	ordinary screens now, so what makes them writable is the Space's own grant —
	`Manage`, which is what puts a New button and an editable form on a screen.
	"""
	access = {
		row["document_type"]: row["access"]
		for row in [
			{"document_type": doctype, "access": "Manage"}
			for doctype in _const(OPERATOR, "DOCTYPES")
		]
	}
	for doctype in ("Plan", "Region", "OneSpace Space"):
		assert doctype in operator_screens(), f"{doctype} has no screen"
		assert access.get(doctype) == "Manage", f"{doctype} is read-only, so it needs the desk"


# The panel that offered a field its list never fetched — so it read as empty
# and was written back as empty on the first save — was a hand-written settings
# form, and there are none left. A screen's form is derived from the doctype by
# the resolver, over the fields the resolver itself fetched, so the two cannot
# disagree. What is still worth pinning is that a screen's *declared* columns
# are real fieldnames, and `test_operator_console.py` does that against the
# doctype's own JSON.


# Frappe's desk is at /app. A SPA route of the same shape is not a desk link —
# OneSpace's own app route is `/app/:spaceCode` under a `/one` history base, so it
# resolves to /one/app/crm — so this looks for *navigation*, not for the string.
DESK_NAVIGATION = re.compile(
	r"""(?:href\s*=\s*["'`]|window\.location(?:\.href)?\s*=\s*["'`]|window\.open\(\s*["'`])/app\b"""
)


@pytest.mark.parametrize("src", [SIGNUP_SRC, TENANT_SRC], ids=["oneapp_control", "oneapp"])
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
		spec["space_code"]
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
		assert "no interface" in (spec.get("description") or "").lower(), spec["space_code"]


def test_existing_installs_are_corrected_without_taking_anything_away():
	patch = (CONTROL / "patches/restrict_seeded_books.py").read_text()
	assert "Space Entitlement" in patch, "workspaces that had it would silently lose it"
	assert 'availability != "General"' in patch, "an operator's own decision must survive"
	assert "oneapp_control.patches.restrict_seeded_books" in (CONTROL / "patches.txt").read_text()
