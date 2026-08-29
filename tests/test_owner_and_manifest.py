"""Roles, permissions and the workspace owner.

The tenant site defines its own roles rather than reusing ERPNext's — we use
those apps for their logic, not their idea of who an "Accounts Manager" is — so
the roles start with no permissions and this is where both halves come from.

The failure modes here are quiet ones: a role created with desk access reopens
/app to every customer, and an owner with no account has a workspace they cannot
sign in to.
"""

import pytest


@pytest.fixture
def sync(stub_frappe, monkeypatch):
	from oneapp.oneapp_core import sync as module

	return module


def test_access_levels_are_ordered(sync):
	read = sync.ACCESS_LEVELS["Read"]
	write = sync.ACCESS_LEVELS["Write"]
	manage = sync.ACCESS_LEVELS["Manage"]

	assert set(read) <= set(write) <= set(manage)
	assert not read.get("write") and write.get("write")
	assert not write.get("delete") and manage.get("delete")


def test_read_grants_nothing_that_changes_data(sync):
	dangerous = {"write", "create", "delete", "submit", "cancel", "amend"}
	assert not dangerous & set(sync.ACCESS_LEVELS["Read"])


def test_perm_fields_cover_every_level(sync):
	# A key in a level that PERM_FIELDS does not carry is silently dropped when
	# the DocPerm is written, so the role quietly has less access than declared.
	for level in sync.ACCESS_LEVELS.values():
		assert set(level) <= set(sync.PERM_FIELDS)


def test_owner_role_is_never_revoked(sync):
	source = (
		__import__("pathlib").Path(sync.__file__).read_text()
	)
	assert "- {owner_role}" in source, (
		"the owner role must be excluded from revocation, or the owner loses "
		"access to their own workspace on the next sync"
	)


def test_roles_are_created_without_desk_access(sync):
	import pathlib

	source = pathlib.Path(sync.__file__).read_text()
	# Every Role this app creates has to be desk_access 0. Frappe derives
	# User.user_type from role flags, so one role with it set turns every holder
	# into a System User, which is exactly who /app admits.
	assert '"desk_access": 0' in source
	assert '"desk_access": 1' not in source


def test_role_reconciliation_is_not_limited_to_system_users(sync):
	import pathlib

	source = pathlib.Path(sync.__file__).read_text()
	assert '"user_type": "System User"' not in source, (
		"our roles carry no desk access, so every member is a Website User; "
		"filtering on System User would skip all of them"
	)


def test_owner_is_skipped_without_an_email_or_role(sync):
	assert sync.sync_owner({}, "OneApp Workspace Owner") is False
	assert sync.sync_owner({"email": "a@b.com"}, None) is False


def test_control_plane_sends_what_the_tenant_reads(stub_frappe):
	"""The two halves of the sync contract, which nothing else connects."""
	import ast
	import pathlib

	root = pathlib.Path(__file__).resolve().parents[1]
	control = (root / "apps/oneapp_control/oneapp_control/api/tenant.py").read_text()
	tenant = (root / "apps/oneapp/oneapp/oneapp_core/sync.py").read_text()

	sent = set()
	for node in ast.walk(ast.parse(control)):
		if isinstance(node, ast.FunctionDef) and node.name == "sync":
			for inner in ast.walk(node):
				if isinstance(inner, ast.Return) and isinstance(inner.value, ast.Dict):
					sent = {
						k.value for k in inner.value.keys
						if isinstance(k, ast.Constant) and isinstance(k.value, str)
					}

	for key in ("permissions", "owner", "owner_role"):
		assert key in sent, f"control plane no longer sends {key!r}"
		assert f'"{key}"' in tenant, f"tenant no longer reads {key!r}"


def test_tenant_environment_comes_from_its_shard(stub_frappe):
	"""The tooling's guard asks what is on a bench; a tenant says where it runs.

	Both answers have to come from the same place or they disagree — and the
	disagreement is silent, because each looks right on its own.
	"""
	import pathlib

	source = (
		pathlib.Path(__file__).resolve().parents[1]
		/ "apps/oneapp_control/oneapp_control/control_plane/doctype/tenant/tenant.py"
	).read_text()
	assert "inherit_environment_from_shard" in source
	assert 'get_value("Shard", self.shard, "environment")' in source


def test_environment_defaults_to_production_everywhere(stub_frappe):
	# A path that forgets to set it should protect the bench, not expose it.
	import json
	import pathlib

	root = pathlib.Path(__file__).resolve().parents[1]
	for doctype in ("tenant", "shard"):
		spec = json.loads(
			(root / f"apps/oneapp_control/oneapp_control/control_plane/doctype/{doctype}/{doctype}.json").read_text()
		)
		field = next(f for f in spec["fields"] if f["fieldname"] == "environment")
		assert field["default"] == "Production", f"{doctype}.environment must default safe"
