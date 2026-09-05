"""What a tenant's site carries, and who decided.

Three lists that were one list until now (docs/APPS-AND-SPACES.md):

  * the **bench** carries a superset, and nothing outside it can be installed;
  * the **site** carries a subset, which provisioning writes down;
  * the **grants** imply a third, and the site is kept equal to it.

Every failure in this area is silent, which is why it is worth a file of its
own. `sync_permissions` skips a doctype the site lacks and `_columns` skips a
field it lacks, both deliberately — so a space granted onto a site without its
app produces screens that are simply empty, and a space whose custom fields
nobody made produces one column fewer, and neither says a word.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "apps" / "oneapp_control" / "oneapp_control"
TENANT = ROOT / "apps" / "oneapp" / "oneapp"


@pytest.fixture
def apps(stub_frappe):
	from oneapp_control.entitlements import apps as module

	return module


def declarations(path: Path):
	"""A space or plan module, loaded without its package.

	These are declaration files — `json` is the only thing any of them imports —
	so reading them as modules is both safe and honest: `CUSTOM_FIELDS` builds
	its Select options out of `STAGES`, and a test parsing the literal would be
	reading a different thing than the control plane stores.
	"""
	spec = importlib.util.spec_from_file_location(f"declared_{path.stem}_{id(path)}", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


# --------------------------------------------------------------------------- #
# A. What a space needs of the site it lands on
# --------------------------------------------------------------------------- #

def test_a_space_names_the_apps_its_screens_assume(apps):
	assert apps.declared("erpnext,hrms") == ["erpnext", "hrms"]
	assert apps.declared(" erpnext , , hrms \n payments ") == ["erpnext", "hrms", "payments"]
	assert apps.declared(None) == []


def test_every_shipped_space_that_reaches_another_apps_doctypes_says_so():
	"""The whole check is worth nothing if the spaces do not declare.

	Read off the modules rather than off a list here: a space added tomorrow
	over ERPNext doctypes and declaring no apps is exactly the failure this is
	guarding, and a hand-kept list would not see it.
	"""
	# Doctypes only these apps ship. Not exhaustive — it does not need to be,
	# it needs to be certain.
	OWNED = {
		"erpnext": {"Sales Invoice", "Purchase Order", "Quotation", "Project",
		            "Payment Entry", "Customer", "Supplier", "Item"},
		"hrms": {"Employee", "Attendance", "Leave Application", "Salary Slip"},
	}

	for module in sorted((CONTROL / "spaces").glob("*.py")):
		if module.name == "__init__.py":
			continue
		declared = declarations(module)
		space = getattr(declared, "SPACE", {})
		doctypes = {row[0] for row in getattr(declared, "DOCTYPES", [])}
		named = set(apps_declared(space.get("requires_apps")))

		for app, owned in OWNED.items():
			reached = doctypes & owned
			assert not reached or app in named, (
				f"{module.name} reaches {sorted(reached)} and does not declare {app} "
				"in requires_apps: granting it to a site without that app makes "
				"every one of its screens empty and says nothing"
			)


def apps_declared(raw):
	return [one.strip() for one in str(raw or "").replace("\n", ",").split(",") if one.strip()]


def test_a_site_gets_the_union_of_what_its_spaces_need(apps, monkeypatch):
	monkeypatch.setattr(apps.registry, "spaces_for_tenant", lambda tenant: [
		{"space_code": "books", "requires_apps": "erpnext"},
		{"space_code": "rua", "requires_apps": "erpnext,hrms"},
		{"space_code": "account", "requires_apps": ""},
	])
	assert apps.wanted_for("t") == ["erpnext", "frappe", "hrms", "oneapp"]


def test_a_workspace_that_bought_nothing_still_gets_the_base(apps, monkeypatch):
	"""The point of the whole exercise: a tenant on OneSpace's own registers
	carries neither ERPNext's fifteen hundred doctypes nor HRMS's."""
	monkeypatch.setattr(apps.registry, "spaces_for_tenant", lambda tenant: [
		{"space_code": "account", "requires_apps": None},
	])
	assert apps.wanted_for("t") == ["frappe", "oneapp"]


def test_a_grant_the_bench_cannot_carry_is_refused_with_the_app_named(apps, monkeypatch):
	frappe = apps.frappe
	frappe.db.values[("OneSpace Space", "requires_apps")] = "erpnext,hrms"
	frappe.db.values[("OneSpace Space", "space_label")] = "RUA"
	monkeypatch.setattr(apps, "_tenant", lambda t: type("T", (), {"shard": "s1"})())
	monkeypatch.setattr(apps, "bench_apps", lambda t: ["frappe", "oneapp", "erpnext"])

	with pytest.raises(Exception) as raised:
		apps.assert_can_carry("t", "rua")

	said = str(raised.value)
	assert "hrms" in said, "the refusal has to name the app, or it is the silence again"
	assert "erpnext" not in said, "an app the bench has is not part of the problem"


def test_a_grant_the_bench_can_carry_is_not_refused(apps, monkeypatch):
	apps.frappe.db.values[("OneSpace Space", "requires_apps")] = "erpnext"
	monkeypatch.setattr(apps, "_tenant", lambda t: type("T", (), {"shard": "s1"})())
	monkeypatch.setattr(apps, "bench_apps", lambda t: ["frappe", "oneapp", "erpnext"])

	assert apps.assert_can_carry("t", "books") is None


def test_a_tenant_with_no_shard_yet_is_not_refused(apps, monkeypatch):
	"""Provisioning picks the shard, and refuses there if the one it picked
	cannot carry this. Refusing here would block the grant a signup makes
	before there is anything to check against."""
	apps.frappe.db.values[("OneSpace Space", "requires_apps")] = "erpnext"
	monkeypatch.setattr(apps, "_tenant", lambda t: type("T", (), {"shard": None})())

	assert apps.assert_can_carry("t", "books") is None


# --------------------------------------------------------------------------- #
# C. Closing the gap on a site that is already running
# --------------------------------------------------------------------------- #

def test_nothing_is_installed_onto_a_site_that_does_not_exist_yet(apps, monkeypatch):
	monkeypatch.setattr(apps, "_tenant", lambda t: type("T", (), {"press_site": None})())
	assert apps.reconcile("t") == []


def test_the_gap_between_the_grants_and_the_site_becomes_one_job_per_app(apps, monkeypatch):
	tenant = type("T", (), {"press_site": "s.frappe.cloud", "site_apps": "frappe,oneapp"})()
	monkeypatch.setattr(apps, "_tenant", lambda t: tenant)
	monkeypatch.setattr(apps, "wanted_for", lambda t: ["erpnext", "frappe", "hrms", "oneapp"])
	monkeypatch.setattr(apps, "bench_apps", lambda t: ["frappe", "erpnext", "hrms", "oneapp"])

	queued = []
	import sys
	import types

	runner = types.ModuleType("oneapp_control.provisioning.runner")
	runner.enqueue = lambda tenant, action, payload=None, idempotency_key=None: queued.append(
		(action, payload, idempotency_key)
	)
	import oneapp_control.provisioning as provisioning

	monkeypatch.setitem(sys.modules, "oneapp_control.provisioning.runner", runner)
	monkeypatch.setattr(provisioning, "runner", runner, raising=False)

	assert apps.reconcile("t") == ["erpnext", "hrms"]
	assert [one[0] for one in queued] == ["Install App", "Install App"]
	# One key per app, so a second grant wanting the same app finds the job
	# already queued rather than starting a second install of it.
	assert [one[2] for one in queued] == ["Install App:t:erpnext", "Install App:t:hrms"]


def test_an_app_the_bench_does_not_have_is_not_queued(apps, monkeypatch):
	"""The grant that would have needed it was refused. Queuing it anyway makes
	a job that can only fail, and it would sit at the front of the queue for
	every later install."""
	tenant = type("T", (), {"press_site": "s.frappe.cloud", "site_apps": "frappe,oneapp"})()
	monkeypatch.setattr(apps, "_tenant", lambda t: tenant)
	monkeypatch.setattr(apps, "wanted_for", lambda t: ["frappe", "oneapp", "payments"])
	monkeypatch.setattr(apps, "bench_apps", lambda t: ["frappe", "oneapp"])

	assert apps.reconcile("t") == []


def test_installing_an_app_is_its_own_pipeline():
	from oneapp_control.provisioning import steps

	pipeline = steps.PIPELINES["Install App"]
	assert [name for name, _fn in pipeline] == [
		"install_app", "await_agent", "finalise_install"
	], "an install that is not waited on is an install nothing knows the end of"


def test_the_job_doctype_admits_the_action():
	"""A pipeline for an action the Select refuses is a job that cannot be
	created, and the runner would say `No pipeline defined` — for the one
	action that has one."""
	doctype = json.loads(
		(CONTROL / "control_plane" / "doctype" / "provisioning_job"
		 / "provisioning_job.json").read_text()
	)
	action = next(f for f in doctype["fields"] if f["fieldname"] == "action")
	assert "Install App" in action["options"].split("\n")


def test_a_new_sites_app_list_is_the_tenants_and_not_the_benchs():
	from oneapp_control.provisioning import steps

	source = (CONTROL / "provisioning" / "steps.py").read_text()
	body = source[source.index("def create_site"):source.index("def await_agent")]
	assert "apps=apps_for_site(tenant, shard)" in body, (
		"create_site passing site_apps(shard) is every tenant paying for every "
		"app on the bench, which is the thing this was for"
	)
	assert callable(steps.apps_for_site)


# --------------------------------------------------------------------------- #
# B. The schema a space's screens read
# --------------------------------------------------------------------------- #

def test_ruas_fields_belong_to_its_space_and_not_to_its_import_plan():
	"""They lived in the plan, so a workspace granted RUA who never imported
	anything got RUA's screens without RUA's fields — and nothing said so."""
	plan = (TENANT / "oneapp_core" / "plans" / "rua.py").read_text()
	assert "\nFIELDS = [" not in plan, (
		"the import plan is a data migration; schema arrives with the grant"
	)

	fields = declarations(CONTROL / "spaces" / "rua.py").CUSTOM_FIELDS
	assert len(fields) >= 10
	assert {"dt": "Sales Invoice"}.items() <= next(
		f for f in fields if f["fieldname"] == "custom_retention_percentage"
	).items()


def test_every_declared_field_is_one_a_custom_field_can_be_made_from():
	fields = declarations(CONTROL / "spaces" / "rua.py").CUSTOM_FIELDS
	for field in fields:
		assert field.get("dt") and field.get("fieldname") and field.get("fieldtype"), field
		assert field["fieldname"].startswith("custom_"), (
			f"{field['fieldname']} is not namespaced, so an app adding a field of "
			"that name on the next release collides with it"
		)


def test_the_stages_a_space_offers_are_the_ones_the_plan_maps():
	"""One vocabulary in two apps, with no import that can join them: the space
	is on the control plane and the plan is on the tenant. So the two lists are
	held to each other here instead."""
	stages = declarations(CONTROL / "spaces" / "rua.py").STAGES
	mapped = declarations(TENANT / "oneapp_core" / "plans" / "rua.py").PROJECT_STATUS
	assert stages == list(mapped), (
		"the Select on Project.custom_stage and the values the import writes "
		"into it have drifted: a row would import with a stage the field refuses"
	)


def test_the_plan_no_longer_makes_schema():
	source = (TENANT / "oneapp_core" / "plans" / "__init__.py").read_text()
	body = source[source.index("def prepare"):]
	assert "Custom Field" not in body


def test_a_spaces_fields_travel_to_the_tenant():
	from oneapp_control.entitlements import registry

	assert "custom_fields" in registry.SPACE_FIELDS, (
		"declared on the control plane and never sent is the same as not declared"
	)
	assert "requires_apps" in registry.SPACE_FIELDS


def test_the_sync_applies_them_once_and_never_again():
	source = (TENANT / "oneapp_core" / "sync.py").read_text()
	body = source[source.index("def _seed_custom_fields"):source.index("def sync_notices")]
	assert 'frappe.db.exists("Custom Field"' in body, (
		"a Custom Field reapplied every fifteen minutes undoes an afternoon of "
		"a workspace widening its own columns"
	)
	assert 'frappe.db.exists("DocType", doctype)' in body, (
		"a space whose app is still installing must not fail the whole sync"
	)


def test_the_restricted_half_of_the_manifest_is_not_a_second_column_list():
	"""A field added to SPACE_FIELDS and forgotten in the join would reach every
	General space and no Restricted one — and the Restricted ones are the
	bespoke single-tenant work this whole mechanism exists for."""
	source = (CONTROL / "entitlements" / "registry.py").read_text()
	assert "SELECT {SPACE_COLUMNS}" in source
