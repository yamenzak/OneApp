"""What each of the four seats can actually do, read off a real manifest.

`test_shipped_roles.py` checks the declaration and `test_workspace_roles.py`
checks the ladder in the abstract. This is the one that would have caught the
thing worth catching: run OneCRM's real grant list through the real
`permission_manifest` and ask what a `CRM-User` can do to a deal stage.

Nothing here stubs a manifest. The rows are the ones in
`oneapp_control/spaces/onecrm.py`, so a grant moved up or down a rung shows up
as a failure naming the doctype.
"""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPACES = ROOT / "apps/oneapp_control/oneapp_control/spaces"


def declared(name: str):
	path = SPACES / f"{name}.py"
	spec = importlib.util.spec_from_file_location(f"seats_{name}", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


SEATS = declared("roles")
ORDER = {"Read": 0, "Write": 1, "Manage": 2}


@pytest.fixture
def written(stub_frappe, monkeypatch):
	"""Every (role, doctype) row the control plane would write for OneCRM.

	Widest access per pair, the way `sync.sync_permissions` keeps it: a ladder
	produces two rows for a doctype the manager may write and the user may
	read, and the answer to "what can a manager do" is the wider one.
	"""
	from oneapp_control.entitlements import registry

	space = declared("onecrm")
	rows = [{"document_type": row[0], "access": row[1], "if_owner": row[2],
	         "role": row[3] if len(row) > 3 else ""}
	        for row in space.DOCTYPES]

	monkeypatch.setattr(registry, "spaces_for_tenant",
	                    lambda tenant: [dict(space.SPACE, space_code="onecrm")])
	monkeypatch.setattr(registry, "space_roles",
	                    lambda app: [dict(one) for one in SEATS.ROLES])
	monkeypatch.setattr(registry, "_custom_manifest", lambda tenant: [])
	stub_frappe.get_all = lambda *a, **k: list(rows)

	widest = {}
	for row in registry.permission_manifest("acme"):
		key = (row["role"], row["doctype"])
		if key not in widest or ORDER[row["access"]] > ORDER[widest[key]]:
			widest[key] = row["access"]
	return widest


def test_a_user_reads_a_stage_and_cannot_touch_it(written):
	"""The rule OneCRM is most emphatic about: a rep who can invent a stage can
	move a deal into one, and the forecast quietly stops meaning anything."""
	assert written[("CRM-User", "One Deal Stage")] == "Read"


def test_a_manager_owns_the_stages(written):
	assert written[("CRM-Manager", "One Deal Stage")] == "Write"


def test_the_admin_inherits_everything_the_manager_has(written):
	"""The ladder, stated as the thing it is for. An admin who has to be given
	a manager's grants a second time is an admin missing one of them."""
	manager = {dt: access for (role, dt), access in written.items()
	           if role == "CRM-Manager"}
	admin = {dt: access for (role, dt), access in written.items()
	         if role == "CRM-Admin"}

	assert manager, "the fixture read nothing"
	for doctype, access in manager.items():
		assert ORDER[admin.get(doctype, "Read")] >= ORDER[access], (
			f"CRM-Admin has less than CRM-Manager on {doctype}"
		)


def test_the_auditor_reads_everything_and_writes_nothing(written):
	"""Derived rather than declared, so it cannot drift from what the other
	three reach and cannot be handed a Write by a manifest row."""
	everyone = {dt for (role, dt) in written if role != "CRM-Audit"}
	auditor = {dt: access for (role, dt), access in written.items()
	           if role == "CRM-Audit"}

	assert set(auditor) == everyone, "the auditor cannot see all of it"
	assert set(auditor.values()) == {"Read"}, "the auditor can write"


def test_a_user_still_does_the_job_the_space_is_for(written):
	"""The other half of the rule above. Narrowing a seat until it cannot sell
	is not a permission model, it is a broken product."""
	for doctype in ("Lead", "Opportunity", "Quotation", "One Call"):
		assert written[("CRM-User", doctype)] == "Manage"
