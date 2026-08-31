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
	from oneapp.oneapp_core import sync as module

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
