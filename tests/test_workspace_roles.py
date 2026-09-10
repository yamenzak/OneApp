"""Roles a workspace hands out: the ones a space ships and the ones it builds.

A space used to carry exactly one role and give it every doctype in its
manifest, so "has this app" and "may do everything in this app" were the same
sentence. They are not — a shop wants someone who raises invoices and someone
who only reads them, and neither of those is a second app.

Three things have to hold, and each has a way of failing silently:

  * a workspace already running must not change. Its spaces declare no roles, so
    the default role has to still be the space's own `role_name` and still get
    every grant. Anything else re-permissions every live tenant on one deploy.
  * a member's roles are *reconciled*, not added. The interesting case is
    removal: somebody moved off Sales keeps selling until something takes the
    role away, and nothing else on a tenant site is going to.
  * a custom role may only reach what the workspace's own spaces already expose.
    That is the entire security argument for letting a customer build one.
"""

import pytest


@pytest.fixture
def registry(stub_frappe, monkeypatch):
	from oneapp_control.entitlements import registry as module

	return module, stub_frappe


@pytest.fixture
def sync(stub_frappe):
	from oneapp.onespace import sync as module

	return module


SPACE = {"space_code": "books", "space_label": "Books", "role_name": "OneSpace Books"}


# --------------------------------------------------------------------------- #
# A space that declares no roles is the shape every space had until now
# --------------------------------------------------------------------------- #

def test_a_space_with_no_roles_still_has_one(registry, monkeypatch):
	module, _ = registry
    # No rows in the child table — an untouched space.
	monkeypatch.setattr(module.frappe, "get_all", lambda *a, **k: [])

	roles = module.space_roles(SPACE)
	assert len(roles) == 1
	assert roles[0]["is_default"], "the only role a space has must be its default"


def test_the_default_role_keeps_the_spaces_existing_name(registry, monkeypatch):
	"""The compatibility hinge. Every live tenant holds `OneSpace Books`; if the
	default resolved to anything else, one deploy would take the app away from
	everybody and hand it back under a name nothing had DocPerms for."""
	module, _ = registry
	assert module.frappe_role_for(SPACE, None) == "OneSpace Books"
	assert module.frappe_role_for(SPACE, {"label": "Sales", "is_default": 1}) == "OneSpace Books"


def test_a_second_role_is_named_after_the_first(registry):
	module, _ = registry
	assert module.frappe_role_for(SPACE, {"label": "Sales", "is_default": 0}) == (
		"OneSpace Books Sales"
	)


def test_a_space_that_names_no_default_gets_one(registry, monkeypatch):
	"""Otherwise entitling an app grants an app nobody can open."""
	module, _ = registry
	monkeypatch.setattr(module.frappe, "get_all", lambda *a, **k: [
		{"role_key": "sales", "label": "Sales", "is_default": 0, "description": None},
		{"role_key": "reader", "label": "Reader", "is_default": 0, "description": None},
	])
	roles = module.space_roles(SPACE)
	assert sum(1 for r in roles if r["is_default"]) == 1
	assert roles[0]["is_default"], "the first row is the one that becomes the default"


# --------------------------------------------------------------------------- #
# Keys
# --------------------------------------------------------------------------- #

def test_a_custom_role_is_told_apart_from_a_shipped_one(registry):
	module, _ = registry
	assert module.is_custom(module.custom_key("Bookkeeper"))
	assert not module.is_custom(module.role_key("books", "sales"))


def test_a_custom_frappe_role_says_it_is_custom(registry):
	"""An operator reading a tenant's roles should be able to tell at a glance
	which of them we shipped and which the customer built."""
	module, _ = registry
	assert module.custom_frappe_role("Bookkeeper").startswith("OneSpace Custom ")


def test_keys_split_on_commas_and_tolerate_whitespace(registry):
	module, _ = registry
	assert module._keys(" books:sales , custom:Bookkeeper ,, ") == [
		"books:sales", "custom:Bookkeeper",
	]
	assert module._keys(None) == []
	assert module._keys("") == []


# --------------------------------------------------------------------------- #
# What a tenant site does with the roles it is sent
# --------------------------------------------------------------------------- #

class FakeUser:
	"""Just enough User for `_set_role`: a roles list and a save that counts."""

	def __init__(self, roles=()):
		self.roles = [type("Row", (), {"role": r})() for r in roles]
		self.saves = 0

	def append(self, _field, value):
		self.roles.append(type("Row", (), value)())

	def save(self, **_kw):
		self.saves += 1

	def held(self):
		return {r.role for r in self.roles}


GRANTED = {"OneSpace Books", "OneSpace Books Sales", "OneSpace Custom Bookkeeper"}


def test_a_role_that_was_taken_away_is_taken_away(sync):
	"""The case the whole reconciliation exists for. Adding is the easy half;
	somebody moved off Sales keeps selling until something removes the role, and
	nothing else on a tenant site is going to."""
	user = FakeUser({"OneSpace Books", "OneSpace Books Sales"})
	sync._reconcile_app_roles(user, ["OneSpace Books"], GRANTED)
	assert user.held() == {"OneSpace Books"}


def test_a_role_the_manifest_does_not_grant_is_refused(sync):
	"""A payload naming `System Manager` would be a workspace owner granting
	themselves the desk — and with it the signing secret in site_config, which
	is enough to forge usage reports and credit commits. The control plane would
	never send that; a permission path that is safe only because of what the
	sender chooses to send is not a permission path."""
	user = FakeUser()
	sync._reconcile_app_roles(user, ["System Manager", "OneSpace Books"], GRANTED)
	assert user.held() == {"OneSpace Books"}


def test_a_role_outside_the_granted_set_is_left_alone(sync):
	"""Narrow on removal too: an ERPNext or site-administrator role this app did
	not create is not ours to take away."""
	user = FakeUser({"System Manager", "OneSpace Books"})
	sync._reconcile_app_roles(user, [], GRANTED)
	assert user.held() == {"System Manager"}


def test_nothing_is_saved_when_nothing_changes(sync):
	user = FakeUser({"OneSpace Books"})
	sync._reconcile_app_roles(user, ["OneSpace Books"], GRANTED)
	assert user.saves == 0, "a sync that changes nothing should write nothing"


def test_the_workspace_wide_roles_are_not_reconciled_away(sync):
	"""The bug this test exists for.

	`_granted_roles` reads every `OneSpace *` role on the site, and the
	membership marker and the owner role are both among them. Reconciling a
	member's app roles against that whole set took back the marker the caller
	had set two lines earlier — and the marker is what tells a member account
	from a user the site created for its own reasons, so the next sync would
	have seen them as a stranger and disabled their sign-in.

	Read at the call site, which is the half that has to hold: the function
	itself is right to reconcile everything it is handed.
	"""
	source = _source(sync)
	body = source[source.index("def sync_members") :]
	call = body[body.index("_reconcile_app_roles(") :]
	call = call[: call.index("\n\n")]
	assert "member_role" in call and "owner_role" in call, (
		"the workspace-wide roles are back inside the reconciliation, so a "
		"member loses their membership marker the moment they hold no app role"
	)


def test_a_role_outside_the_manifest_is_never_granted(sync):
	"""`granted` bounds both halves of the reconciliation.

	Without it, a payload naming `System Manager` would be a workspace owner
	granting themselves the desk — and with it the signing secret in
	site_config, which is enough to forge usage reports and credit commits. The
	control plane would never send that; a permission path that is safe only
	because of what the sender chooses to send is not a permission path.
	"""
	source = _source(sync)
	body = source[source.index("def _reconcile_app_roles") :]
	body = body[: body.index("\ndef ")]
	assert "if role in granted" in body, "wanted roles are no longer filtered"
	assert "for role in sorted(granted)" in body, (
		"removal no longer walks the granted set, so a role can only be added"
	)


def test_only_our_own_roles_are_reconciled(sync):
	"""`_granted_roles` has to be narrow twice over: our prefix, and no desk
	access. A role that can reach /app is never one of ours — `ensure_role`
	turns that off on everything it makes — so anything with it is somebody
	else's and must not be touched."""
	source = _source(sync)
	body = source[source.index("def _granted_roles") :]
	body = body[: body.index("\ndef ")]
	assert '"desk_access": 0' in body
	assert 'startswith("OneSpace ")' in body


def _source(module) -> str:
	from pathlib import Path

	return Path(module.__file__).read_text()


# --------------------------------------------------------------------------- #
# What a workspace's own role is allowed to reach
# --------------------------------------------------------------------------- #

def test_the_operator_space_is_entitled_to_nobody():
	"""It was General, and `spaces_for_tenant` hands every General space to every
	tenant — so the operator console was in every workspace's permission
	manifest, and each tenant site was told to create an `OneSpace Operator`
	role with permissions over Tenant, Subscription and the credit ledger.

	Inert while nothing read it: those doctypes do not exist on a tenant site
	and `sync_permissions` skips what it cannot find. It stopped being inert the
	moment `allowed_doctypes` got its first caller — the workspace's own role
	builder — because the builder offers exactly that list. Measured against a
	real site, the allowlist went from 34 doctypes to 11 when this changed.

	`local_spaces`, which is what actually serves the control site, filters on
	`is_active` alone — so nothing here ever depended on General.
	"""
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent / "apps/oneapp_control/oneapp_control"
	operator = (root / "entitlements/operator.py").read_text()
	manifest = operator[operator.index("def manifest()"):]
	assert '"availability": "Restricted"' in manifest, (
		"the operator console is General again, so every tenant's permission "
		"manifest carries it and every workspace's role builder offers the "
		"control plane's own doctypes"
	)

	registry = (root / "entitlements/registry.py").read_text()
	local = registry[registry.index("def local_spaces"):]
	local = local[: local.index("\ndef ")]
	assert "availability" not in local, (
		"local_spaces now filters on availability, so making the operator space "
		"Restricted would hide it from the console it exists for"
	)


def test_a_custom_role_is_bounded_by_the_allowlist():
	"""The whole security argument for letting a customer author permissions.

	Checked in `validate` rather than only in the API, because the operator
	console is a second door onto the same records and an allowlist one door
	skips is not an allowlist.
	"""
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent / "apps/oneapp_control/oneapp_control"
	controller = (root / "control_plane/doctype/workspace_role/workspace_role.py").read_text()
	assert "def validate(" in controller
	assert "allowed_doctypes" in controller, (
		"a custom role is no longer bounded by what the workspace's spaces expose"
	)
	assert "validate_grants_are_allowed" in controller


# --------------------------------------------------------------------------- #
# Two grants for one role and one doctype
#
# A space that ships more than one role always produces them. A grant naming no
# role reaches *every* role in the space — that is the floor, and it is how a
# manifest says "anybody here can at least see this" — and the role that does
# more then names the same doctype again at a higher level. So a planner's
# manifest carries both a Read and a Write row for `Transit Line`.
# --------------------------------------------------------------------------- #

def _perm(sync, stub_frappe, manifest):
	"""Run the applier over a manifest and hand back what it wanted written."""
	written = {}

	stub_frappe.db.records[("DocType", "Transit Line")] = 1
	stub_frappe.db.records[("Role", "Planner")] = 1
	stub_frappe.get_all = lambda *a, **k: []

	class FakePerm:
		def __init__(self, values):
			self.__dict__.update(values)

		def set(self, field, value):
			setattr(self, field, value)

		def insert(self, **kwargs):
			written[(self.parent, self.role)] = self
			return self

	stub_frappe.get_doc = lambda values, *a, **k: FakePerm(values)
	stub_frappe.clear_cache = lambda *a, **k: None

	sync.sync_permissions(manifest)
	return written


FLOOR = {"role": "Planner", "doctype": "Transit Line", "access": "Read", "if_owner": False}
ABOVE = {"role": "Planner", "doctype": "Transit Line", "access": "Write", "if_owner": False}


def test_the_wider_of_two_grants_wins(sync, stub_frappe):
	found = _perm(sync, stub_frappe, [FLOOR, ABOVE])

	assert found[("Transit Line", "Planner")].write == 1


def test_and_wins_from_either_side(sync, stub_frappe):
	"""The bug this replaced: the applier keyed on (doctype, role) and let the
	last row overwrite, so the answer depended on the order the rows came out
	of a child table. Reordering a manifest for readability would have demoted
	somebody, silently, on the next sync."""
	found = _perm(sync, stub_frappe, [ABOVE, FLOOR])

	assert found[("Transit Line", "Planner")].write == 1


def test_an_unrestricted_grant_beats_an_only_mine_one(sync, stub_frappe):
	"""`if_owner` narrows. A role told "write your own" and "write all of them"
	writes all of them — the second sentence is the one that means something."""
	mine = dict(ABOVE, if_owner=True)
	found = _perm(sync, stub_frappe, [mine, ABOVE])

	assert found[("Transit Line", "Planner")].if_owner == 0


def test_only_mine_survives_when_it_is_the_only_grant(sync, stub_frappe):
	found = _perm(sync, stub_frappe, [dict(ABOVE, if_owner=True)])

	assert found[("Transit Line", "Planner")].if_owner == 1


# --------------------------------------------------------------------------- #
# Two controls, one write
#
# `set_member_roles` takes the access level and the role keys together, because
# they are one decision about one person on one screen. But they are two
# controls, and each has to be writable without touching the other.
# --------------------------------------------------------------------------- #

def _customer():
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent
	return (root / "apps/oneapp_control/oneapp_control/api/customer.py").read_text()


def test_changing_somebody_s_access_does_not_wipe_their_roles():
	"""Latent for as long as nothing set a role: the endpoint wrote
	`row.roles = _validated_roles(tenant, roles)` unconditionally, and `roles`
	defaults to None, which validates to the empty string. So the roles half of
	the picker would have cleared itself the first time an admin used the
	access half beside it — and `setMemberAccess` sends only the access."""
	source = _customer()
	body = source[source.index("def set_member_roles("):]
	body = body[: body.index("\n@frappe")]

	assert "if roles is not None:" in body, (
		"roles are written even when the caller sent none, so changing access "
		"takes every role away"
	)


def test_an_empty_list_still_means_take_them_all_away():
	"""The other half of the same rule. `None` is "not part of this change";
	`[]` is a person the admin just unticked everything for, and the two must
	not collapse into each other."""
	source = _customer()
	validated = source[source.index("def _validated_roles("):]
	validated = validated[: validated.index("\ndef ")]

	assert "if roles is None:" in validated, (
		"the empty list and the missing argument are told apart in the caller "
		"only, so a second caller will get this wrong"
	)


# --------------------------------------------------------------------------- #
# What no manifest may grant
#
# The allowlist used to be an allowlist by *absence*, and its own docstring
# said so: User, Role and DocType were unreachable "because they appear in no
# manifest, not because someone remembered to name them". Absence is a thing
# that is true until somebody writes a line, and the dev fixture had already
# written it — `zzmock` granted `Role` at Manage, so the workspace role builder
# offered "Role — Manage" in a dropdown and a customer could pick it.
# --------------------------------------------------------------------------- #

def test_the_permission_system_is_named_rather_than_merely_absent(registry):
	module, _ = registry

	for doctype in ("User", "Role", "DocType", "Custom DocPerm", "Server Script"):
		assert doctype in module.NEVER_GRANTED, doctype


def _one_space(module, monkeypatch, stub, grants):
	"""A workspace with one space, granting exactly `grants`."""
	monkeypatch.setattr(module, "spaces_for_tenant", lambda t: [dict(SPACE)])
	monkeypatch.setattr(module, "space_roles", lambda app: [
		{"role_key": "member", "label": "Books", "is_default": 1}
	])
	stub.get_all = lambda *a, **k: list(grants)
	monkeypatch.setattr(module, "_custom_manifest", lambda t: [])


def test_a_space_that_asks_for_one_is_refused_rather_than_obeyed(
	registry, monkeypatch
):
	"""The shipped manifest is covered too, not only what a customer builds.
	A space naming `Role` is a bug in the space, and the honest behaviour is
	for the grant to do nothing rather than to work — otherwise every member
	of that space holds it and no screen anywhere says why."""
	module, stub = registry
	_one_space(module, monkeypatch, stub, [
		{"document_type": "Sales Invoice", "access": "Write", "if_owner": 0, "role": ""},
		{"document_type": "Role", "access": "Manage", "if_owner": 0, "role": ""},
	])

	found = module.permission_manifest("acme")

	assert [row["doctype"] for row in found] == ["Sales Invoice"]


def test_the_refusal_is_logged_rather_than_thrown(registry, monkeypatch):
	"""This runs on every sync. A bad manifest row must not stop a workspace's
	other twenty doctypes from reaching it."""
	module, stub = registry
	logged = []
	stub.log_error = lambda **kwargs: logged.append(kwargs.get("message", ""))
	_one_space(module, monkeypatch, stub, [
		{"document_type": "User", "access": "Manage", "if_owner": 0, "role": ""},
	])

	assert module.permission_manifest("acme") == []
	assert logged and "User" in logged[0]


def test_the_builder_is_never_offered_one(registry, monkeypatch):
	"""`allowed_doctypes` is derived from the manifest, so the subtraction
	above is what keeps it out of the dropdown — one rule, not two."""
	module, stub = registry
	_one_space(module, monkeypatch, stub, [
		{"document_type": "Sales Invoice", "access": "Write", "if_owner": 0, "role": ""},
		{"document_type": "DocType", "access": "Read", "if_owner": 0, "role": ""},
	])

	assert module.allowed_doctypes("acme") == ["Sales Invoice"]


def test_a_role_that_already_holds_one_stops_granting_it(registry, monkeypatch):
	"""A row written before the rule, or through some other door. The sync is
	the last place to catch it, so it catches it."""
	module, stub = registry
	monkeypatch.setattr(module, "spaces_for_tenant", lambda t: [])

	rows = {
		"Workspace Role": [{"name": "WR-1", "role_label": "Bookkeeper"}],
		"Workspace Role Grant": [
			{"document_type": "Note", "access": "Read", "if_owner": 0},
			{"document_type": "Role", "access": "Manage", "if_owner": 0},
		],
	}
	stub.get_all = lambda doctype, *a, **k: list(rows.get(doctype, []))

	found = module.permission_manifest("acme")

	assert [row["doctype"] for row in found] == ["Note"]


def test_the_save_door_says_which_kind_of_no_it_is():
	"""Two refusals, two sentences. "Your apps do not expose that" is a fact
	about this workspace that buying something would change; "nobody may grant
	that" is not, and telling somebody the first when the second is true sends
	them to sales."""
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent
	source = (root / "apps/oneapp_control/oneapp_control/control_plane/doctype"
	          "/workspace_role/workspace_role.py").read_text()

	assert "NEVER_GRANTED" in source, (
		"the builder's own door leans on the allowlist alone, so a doctype "
		"refused for being dangerous is reported as one the apps do not expose"
	)
	assert source.index("NEVER_GRANTED") < source.index("not in allowed"), (
		"the allowlist is checked first, so the wrong sentence wins"
	)


def test_the_fixture_no_longer_demonstrates_the_escalation():
	"""It granted `Role` at Manage to make the picker's Create row reachable.
	A fixture teaching a hole is a fixture teaching the wrong lesson."""
	from pathlib import Path

	root = Path(__file__).resolve().parent.parent
	source = (root / "scripts/seed_dev_space.py").read_text()
	grants = source[source.index("DOCTYPES = ["):]
	grants = grants[: grants.index("\n]")]

	assert '"document_type": "Role"' not in grants
