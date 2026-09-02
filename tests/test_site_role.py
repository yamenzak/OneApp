"""Which kind of site this is, and the three things that depend on it.

`oneapp` runs on a customer's workspace and on the control plane, where it is
installed for its shell and its Space runtime rather than for anything a tenant
needs. Nearly all of it behaves identically. These pin the handful of places
that must not, and pin the mechanism itself — because the failure mode of
getting this wrong is silent on both sides: a control site quietly acquiring a
tenant's storage arrangement, or a tenant quietly losing it.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "apps/oneapp/oneapp/oneapp_core/site.py"
FILE_OVERRIDE = ROOT / "apps/oneapp/oneapp/oneapp_core/storage/file.py"
SYNC = ROOT / "apps/oneapp/oneapp/oneapp_core/sync.py"
BACKUP = ROOT / "apps/oneapp/oneapp/oneapp_core/backup.py"


@pytest.fixture
def site(stub_frappe):
	import sys

	for name in list(sys.modules):
		if name.startswith("oneapp.oneapp_core"):
			del sys.modules[name]
	from oneapp.oneapp_core import site as module

	return module


def test_a_site_that_says_nothing_is_a_tenant(site, stub_frappe):
	"""Every site that exists today is one, and a migration that requires
	touching every site_config is a migration that will be half-done
	forever."""
	stub_frappe.conf = {}
	assert site.is_tenant()
	assert not site.is_control()


def test_a_site_may_say_it_is_the_control_plane(site, stub_frappe):
	stub_frappe.conf = {"oneapp_role": "control"}
	assert site.is_control()
	assert not site.is_tenant()


def test_case_and_padding_are_forgiven(site, stub_frappe):
	""" "Control" in a config file is not ambiguous about what it meant."""
	for value in ("Control", "  control  ", "CONTROL"):
		stub_frappe.conf = {"oneapp_role": value}
		assert site.is_control(), value


def test_a_value_nobody_recognises_is_a_tenant(site, stub_frappe):
	"""A typo must not silently turn a customer's workspace into something
	else. The safe direction is the one every existing site is already in."""
	for value in ("conrol", "", None, "operator", "control plane"):
		stub_frappe.conf = {"oneapp_role": value}
		assert site.is_tenant(), value


def test_the_role_is_declared_rather_than_derived():
	"""Asking "is oneapp_control installed?" would make a safety property a
	consequence of an app list, and its failure mode is silence: install an app
	for an unrelated reason and a customer's attachments stop going to R2."""
	source = SITE.read_text()
	assert "installed_apps" not in source
	assert "get_installed_apps" not in source
	assert 'frappe.conf.get("oneapp_role")' in source


def test_it_is_a_different_question_from_being_provisioned():
	"""A site can be a tenant and not yet have its identity — that is an
	orphan, and worth telling apart from a site never meant to have one.

	Checked as a call rather than as a word, because the reason the two are
	separate is worth writing down in the module and a substring search would
	then fail on its own explanation.
	"""
	called = {
		node.func.attr
		for node in ast.walk(ast.parse(SITE.read_text()))
		if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
	}
	assert "is_provisioned" not in called


# --------------------------------------------------------------------------- #
# What the role actually gates
# --------------------------------------------------------------------------- #

def test_the_r2_override_is_tenant_only():
	"""The override travels with the app, so without this the control site
	would silently acquire a tenant's storage arrangement."""
	source = FILE_OVERRIDE.read_text()
	assert "site.is_control()" in source
	body = source[source.index("def after_insert"):source.index("def move_to_r2")]
	assert "site.is_control()" in body, "the gate is not on the path that uploads"


@pytest.mark.parametrize("module,function", [
	(SYNC, "sync_from_control_plane"),
	(SYNC, "report_usage_to_control_plane"),
	# The control plane has no tenant to back up on anybody's behalf, and it is
	# not the control plane's own backup — that is Frappe Cloud's job for the
	# site this all runs on.
	(BACKUP, "scheduled_backup"),
])
def test_the_tenant_scheduler_jobs_stand_down_on_the_control_plane(module, function):
	"""It has no control plane to ask. Left ungated they would write a
	misleading "not provisioned" error onto the singleton every fifteen
	minutes."""
	# By AST rather than by slicing to the next `def `: the last function in a
	# module has no next one, and the string version failed on exactly that.
	tree = ast.parse(module.read_text())
	node = next(
		n for n in ast.walk(tree)
		if isinstance(n, ast.FunctionDef) and n.name == function
	)
	body = ast.unparse(node)

	assert "site.is_control()" in body, f"{function} runs on the control plane"
	assert "not_a_tenant" in body, (
		f"{function} should say why it stood down, and not by claiming the site "
		"is unprovisioned — that is a different thing"
	)


def test_every_scheduled_tenant_job_is_accounted_for():
	"""The list that would otherwise drift. A job added to hooks and not
	considered here runs on the control plane and nobody finds out."""
	hooks = ast.parse((ROOT / "apps/oneapp/oneapp/hooks.py").read_text())
	events = next(
		ast.literal_eval(node.value)
		for node in ast.walk(hooks)
		if isinstance(node, ast.Assign)
		and any(getattr(t, "id", None) == "scheduler_events" for t in node.targets)
	)

	scheduled = set()
	for value in events.values():
		if isinstance(value, dict):
			for entries in value.values():
				scheduled |= set(entries)
		else:
			scheduled |= set(value)

	# Gated above, and the two that are correct on any site: measuring this
	# site's own database says nothing to anybody else.
	known = {
		"oneapp.oneapp_core.sync.sync_from_control_plane",
		"oneapp.oneapp_core.sync.report_usage_to_control_plane",
		"oneapp.oneapp_core.backup.scheduled_backup",
		"oneapp.oneapp_core.storage.quota.refresh_database_verdict",
		# Correct on any site, and ungated on purpose: the control plane keeps
		# no Compliance Documents, so the sweep reads an empty table and stops.
		# Gating it would be a branch that exists to say "there is nothing here"
		# where an empty query already says it.
		"oneapp.oneapp_core.expiry.sweep",
	}
	assert scheduled == known, (
		"a scheduled job was added or renamed; decide whether it should run on "
		"the control plane and then add it here"
	)


# --------------------------------------------------------------------------- #
# Which console opens on the control site
# --------------------------------------------------------------------------- #

CONTROL_HOOKS = ROOT / "apps/oneapp_control/oneapp_control/hooks.py"
PORTAL = ROOT / "apps/oneapp_control/oneapp_control/portal.py"


def _hook(path: Path, name: str):
	for node in ast.walk(ast.parse(path.read_text())):
		if isinstance(node, ast.Assign):
			for target in node.targets:
				if isinstance(target, ast.Name) and target.id == name:
					return ast.literal_eval(node.value)
	return None


def test_the_landing_page_is_decided_rather_than_ordered():
	"""`oneapp` is installed on the control site too and declares its own
	`home_page`. Frappe takes the *last* app's, so which console opened would
	depend on the order the two apps happened to be installed in — a decision
	made by a bench rebuild rather than by anybody."""
	assert _hook(CONTROL_HOOKS, "home_page") is None, (
		"the plain hook is back, and with it the ordering dependence"
	)
	assert _hook(CONTROL_HOOKS, "get_website_user_home_page") == (
		"oneapp_control.portal.landing"
	)


def test_the_tenant_app_still_lands_on_its_own_workspace():
	"""Unchanged for every tenant site, which has only the one console."""
	assert _hook(ROOT / "apps/oneapp/oneapp/hooks.py", "home_page") == "one"


def test_everybody_lands_in_the_same_shell_and_the_roles_sort_it_out():
	"""What `role_home_page` used to do, moved to where it belongs.

	It used to branch: an operator to `/admin`, a customer to `/portal`. Both are
	Spaces in one shell now, and which of them a person can open is already
	decided by the role each Space names — `visible_spaces` filters on
	`role_name` and `_space` refuses the rest. Branching here as well would be a
	second copy of that rule, able to disagree with the one that is enforced.

	Still a function rather than the `home_page` string: `oneapp` declares one
	too and Frappe takes the last app's, which depends on install order.
	"""
	source = PORTAL.read_text()
	body = ast.unparse(next(
		n for n in ast.walk(ast.parse(source))
		if isinstance(n, ast.FunctionDef) and n.name == "landing"
	))
	assert "'one'" in body
	assert "CUSTOMER_ROLE" not in body, (
		"landing is branching on a role again — that rule lives on the Space"
	)
	assert "'admin'" not in body and "'portal'" not in body, (
		"landing still names a retired surface"
	)
