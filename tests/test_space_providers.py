"""Where a site's spaces come from.

A tenant is told, over HMAC, and caches the answer. The control plane has no
control plane to ask — it is one — so an app installed there registers a
provider and hands `oneapp` the same list in process.

The seam is deliberately below `state()`, so everything downstream — `_space`,
`_granted_doctypes`, `visible_spaces`, the rail, the resolver — cannot tell the
two apart. These pin that, and pin the two field lists that describe a space to
a site against the doctypes themselves.
"""

import ast
import json
from pathlib import Path

import pytest

from doctype_paths import slug as doctype_slug

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "apps/oneapp_control/oneapp_control/entitlements/registry.py"
CONTROL_HOOKS = ROOT / "apps/oneapp_control/oneapp_control/hooks.py"
TENANT_HOOKS = ROOT / "apps/oneapp/oneapp/hooks.py"


def _literal(path: Path, name: str):
	tree = ast.parse(path.read_text())
	for node in ast.walk(tree):
		if isinstance(node, ast.Assign):
			for target in node.targets:
				if isinstance(target, ast.Name) and target.id == name:
					return ast.literal_eval(node.value)
	return None


def _docfields(doctype: str, module: str) -> set[str]:
	slug = doctype_slug(doctype)
	path = ROOT / f"apps/oneapp_control/oneapp_control/{module}/doctype/{slug}/{slug}.json"
	data = json.loads(path.read_text())
	return {
		f["fieldname"] for f in data["fields"]
		if f.get("fieldtype") not in ("Section Break", "Column Break", "Tab Break")
	}


# --------------------------------------------------------------------------- #
# The seam
# --------------------------------------------------------------------------- #

def test_the_tenant_app_registers_no_provider():
	"""A tenant learns its spaces by syncing. Shipping a provider in `oneapp`
	would give every site a second, silent source for the same list."""
	assert _literal(TENANT_HOOKS, "onespace_space_providers") is None


def test_the_control_app_registers_one():
	assert _literal(CONTROL_HOOKS, "onespace_space_providers") == [
		"oneapp_control.entitlements.registry.local_spaces"
	]


def test_the_provider_exists_and_is_callable():
	tree = ast.parse(REGISTRY.read_text())
	names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
	assert "local_spaces" in names, "the hook names a function that is not there"


def test_state_merges_providers_into_its_space_list():
	"""Below `state()` rather than beside it, so nothing downstream has to
	learn about providers."""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/sync.py").read_text()
	assert "local_spaces()" in source
	assert 'json.loads(doc.spaces_json or "[]") + local_spaces()' in source


def test_a_failing_provider_is_not_a_site_that_will_not_open():
	"""This runs behind every page load of the shell."""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/sync.py").read_text()
	body = source[source.index("def local_spaces"):source.index("def invalidate")]
	assert "except Exception" in body
	assert "log_error" in body


def test_editing_a_space_forgets_the_cache():
	"""`state()` holds the list for five minutes, so without this a screen
	added to a space appears somewhere between now and then — which reads as
	the change not having saved."""
	events = _literal(CONTROL_HOOKS, "doc_events") or {}
	assert events.get("OneSpace Space", {}).get("on_update", "").endswith("forget_spaces")
	assert events.get("OneSpace Space", {}).get("on_trash", "").endswith("forget_spaces")


# --------------------------------------------------------------------------- #
# What describes a space to a site
# --------------------------------------------------------------------------- #

def test_one_field_list_serves_both_readers():
	"""The tenant sync and the local provider describe a space with the same
	fields, or the console and a tenant would render different sidebars from
	the same rows."""
	source = REGISTRY.read_text()
	assert source.count("fields=list(SPACE_FIELDS)") == 2


def test_every_screen_field_is_sent():
	"""`status_field` was stored on the doctype, edited in the console, and
	never sent — so no screen anywhere ever showed a status badge, and nothing
	said why. Read off the doctype rather than restated, because that is the
	only version that catches the next one."""
	declared = _docfields("OneSpace Space Screen", "control_plane")
	sent = set(_literal(REGISTRY, "SCREEN_FIELDS") or ())

	missing = declared - sent
	assert not missing, (
		f"a Space Screen carries {sorted(missing)} and no site is ever told: "
		"add them to SCREEN_FIELDS or take them off the doctype"
	)


def test_every_space_field_is_sent_or_deliberately_held_back():
	"""`is_active` and `availability` decide *whether* a space is sent rather
	than travelling with one, so they are the two that stay behind."""
	declared = _docfields("OneSpace Space", "control_plane")
	sent = {f.split(" as ")[-1] for f in _literal(REGISTRY, "SPACE_FIELDS") or ()}
	sent.add("name")

	# `screens`, `doctypes` and `roles` are all sent — through their own
	# functions, because each is a list a site reads for a different job.
	held_back = {"is_active", "availability", "screens", "doctypes", "roles"}
	missing = declared - sent - held_back
	assert not missing, f"a Space carries {sorted(missing)} and no site is told"
