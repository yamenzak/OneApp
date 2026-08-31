"""The operator console, declared as a Space.

`/admin` was ~6,000 lines of Vue over eighteen doctypes, almost none of it doing
anything the screen machinery does not already do better — and every improvement
to that machinery stopped at the tenant boundary and never reached the console.

These pin the declaration rather than the rendering: that every screen names a
doctype the control plane actually has, that every fieldname on it is real, and
that the console cannot quietly grant itself something the Space does not
declare. The rendering is the same code every tenant screen uses and is tested
where that lives.
"""

import ast
import json
from pathlib import Path

import pytest

from doctype_paths import slug as doctype_slug

ROOT = Path(__file__).resolve().parent.parent
OPERATOR = ROOT / "apps/oneapp_control/oneapp_control/entitlements/operator.py"
CONTROL = ROOT / "apps/oneapp_control/oneapp_control"
SCREENS_INDEX = ROOT / "apps/oneapp/frontend/src/screens/index.js"


def _const(name):
	for node in ast.walk(ast.parse(OPERATOR.read_text())):
		if isinstance(node, ast.Assign):
			for target in node.targets:
				if isinstance(target, ast.Name) and target.id == name:
					return ast.literal_eval(node.value)
	raise AssertionError(f"{name} is gone from operator.py")


def _doctype_json(doctype: str):
	slug = doctype_slug(doctype)
	found = list(CONTROL.glob(f"*/doctype/{slug}/{slug}.json"))
	return json.loads(found[0].read_text()) if found else None


def _fieldnames(doctype: str) -> set[str]:
	data = _doctype_json(doctype)
	if not data:
		return set()
	names = {f["fieldname"] for f in data["fields"]}
	# Frappe's own, on every doctype and never in a doctype file.
	return names | {"name", "owner", "creation", "modified", "modified_by", "idx", "docstatus"}


SCREENS = _const("SCREENS")
DOCTYPES = _const("DOCTYPES")
COMPONENTS = _const("COMPONENTS")


@pytest.mark.parametrize("row", SCREENS, ids=[s[0] for s in SCREENS])
def test_every_screen_names_a_doctype_the_control_plane_has(row):
	_screen, _label, _icon, doctype, _fields, _status = row
	assert _doctype_json(doctype), f"{doctype} is not a control-plane doctype"


@pytest.mark.parametrize("row", SCREENS, ids=[s[0] for s in SCREENS])
def test_every_default_column_is_a_real_field(row):
	"""The resolver skips a fieldname the site does not have — deliberately,
	so one manifest serves sites on different versions. Which means a typo
	here is invisible: the screen opens with fewer columns than intended and
	nothing says so."""
	screen, _label, _icon, doctype, fields, _status = row
	missing = [f for f in fields.split(",") if f.strip() not in _fieldnames(doctype)]
	assert not missing, f"{screen}: {doctype} has no {missing}"


@pytest.mark.parametrize("row", SCREENS, ids=[s[0] for s in SCREENS])
def test_every_status_field_is_a_real_field(row):
	"""Same silence: `_status_field` drops one the doctype does not have, so
	the badge simply never appears."""
	screen, _label, _icon, doctype, _fields, status = row
	if status:
		assert status in _fieldnames(doctype), f"{screen}: {doctype} has no {status}"


@pytest.mark.parametrize("row", SCREENS, ids=[s[0] for s in SCREENS])
def test_every_screen_is_granted_to_the_space(row):
	"""`_granted_doctypes` refuses a screen whose doctype the Space did not
	grant — that is what makes a screen an allowlist rather than a label. A
	screen missing from DOCTYPES is a PermissionError on open."""
	screen, _label, _icon, doctype, _fields, _status = row
	assert doctype in DOCTYPES, f"{screen} names {doctype}, which the Space does not grant"


def test_the_space_grants_nothing_it_does_not_show():
	"""The converse, and the one that keeps this honest: a grant with no
	screen behind it is reachable over REST by anybody holding the role, and
	invisible in the console that is supposed to be the record of what the
	role can do."""
	shown = {row[3] for row in SCREENS}
	assert set(DOCTYPES) == shown, f"granted and not shown: {sorted(set(DOCTYPES) - shown)}"


@pytest.mark.parametrize("row", COMPONENTS, ids=[c[0] for c in COMPONENTS])
def test_every_component_screen_is_registered(row):
	"""A `component` screen whose component nobody registered renders nothing
	— a blank page under a working sidebar entry."""
	_screen, _label, _icon, component = row
	assert f"'{component}'" in SCREENS_INDEX.read_text(), (
		f"{component} is not in the SPA's screen registry"
	)


def test_the_icons_are_ones_the_doctype_allows():
	"""`icon` on a Space Screen is a closed Select — the same short list a
	customer's space picks from. One that is not on it is a validation error
	at seed time, which is a fine place to find out, but not while a migration
	is running on a live control plane."""
	allowed = set(
		next(
			f["options"] for f in _doctype_json("OneSpace Space Screen")["fields"]
			if f["fieldname"] == "icon"
		).split("\n")
	)
	used = {row[2] for row in SCREENS} | {row[2] for row in COMPONENTS}
	assert used <= allowed, f"not selectable: {sorted(used - allowed)}"


def test_the_console_is_owned_by_code():
	"""It is re-seeded from this file on every migration, so a hand-edit in
	the console loses on the next deploy. Stated in the module and asserted
	here, because "why did my change vanish" is the worst way to learn it."""
	source = OPERATOR.read_text()
	assert "def seed(" in source
	assert "delete_doc" in source, "seed() merges, so a removed screen would linger"


def test_every_component_key_belongs_to_this_space():
	"""Keyed `spaceCode/screen`, which is the convention the registry
	documents — so two spaces can each have an `overview` and neither has to
	know about the other. Written out rather than interpolated, so this is
	what catches a rename of the space code."""
	code = _const("SPACE_CODE")
	for screen, _label, _icon, component in COMPONENTS:
		assert component == f"{code}/{screen}", component


def test_the_role_is_not_system_manager():
	"""The Space's DocPerms are what make its screens resolve. Hanging them on
	System Manager would grant them to every operator tool on the site rather
	than to this console."""
	assert _const("ROLE") == "OneSpace Operator"


# --------------------------------------------------------------------------- #
# The account Space, beside it on the same site
#
# The two audiences that now share a control plane. What keeps them apart is
# `role_name` and nothing else, which is why `_space` filtering on it (Batch B)
# was a prerequisite rather than a tidy-up.
# --------------------------------------------------------------------------- #

ACCOUNT = ROOT / "apps/oneapp_control/oneapp_control/entitlements/account.py"


def _account_const(name):
	for node in ast.walk(ast.parse(ACCOUNT.read_text())):
		if isinstance(node, ast.Assign):
			for target in node.targets:
				if isinstance(target, ast.Name) and target.id == name:
					return ast.literal_eval(node.value)
	raise AssertionError(f"{name} is gone from account.py")


ACCOUNT_SCREENS = _account_const("SCREENS")


@pytest.mark.parametrize("row", ACCOUNT_SCREENS, ids=[s[0] for s in ACCOUNT_SCREENS])
def test_every_account_screen_is_registered(row):
	screen, _label, _icon = row
	key = f"{_account_const('SPACE_CODE')}/{screen}"
	assert f"'{key}'" in SCREENS_INDEX.read_text(), f"{key} is not in the SPA's registry"


@pytest.mark.parametrize("row", ACCOUNT_SCREENS, ids=[s[0] for s in ACCOUNT_SCREENS])
def test_every_account_screen_component_exists(row):
	screen, _label, _icon = row
	name = screen.capitalize() if screen != "apps" else "Apps"
	found = list((ROOT / "apps/oneapp/frontend/src/screens/account").glob("*.vue"))
	stems = {p.stem.lower() for p in found}
	assert screen.lower() in stems, f"no component for {screen}; have {sorted(stems)}"


def test_the_account_space_grants_no_doctypes():
	"""Every screen is a component calling the customer-facing methods, each of
	which resolves the workspace from the session and refuses anything the
	caller does not own. A DocPerm here would be a second, weaker path to the
	same data, reachable over REST by anybody holding the role."""
	source = ACCOUNT.read_text()
	assert '"doctypes": []' in source


def test_the_two_spaces_are_kept_apart_only_by_role():
	"""Which is why `_space` filtering on `role_name` was a prerequisite. If
	that regresses, a customer can resolve the operator console by name."""
	assert _account_const("SPACE_CODE") != _const("SPACE_CODE")
	source = ACCOUNT.read_text()
	assert "CUSTOMER_ROLE" in source, "the account Space is not narrowed to customers"
	assert _const("ROLE") not in source
