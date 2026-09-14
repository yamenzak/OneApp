"""One: the space every workspace has, and the front page behind it.

Two things worth pinning, and they are different kinds of thing.

The **space** is a claim about the shell's shape — that there is exactly one
space a workspace does not learn about by syncing, that it is visible to
everybody, and that the control plane does not get one. Each of those is a
line in `onespace/one.py` and each has a failure that is silent: a space with
a `role_name` typo vanishes for everybody, and one provided on the control
site puts a workspace's settings on an operator's console.

The **home page** is a composition. Nothing in `onespace/home.py` reads the
database; every block calls the module that already owns that question. So
what is tested is that it stays that way — a query in this file would be a
fourth opinion about what a notification is — and that a block which cannot be
read is absent rather than fatal, because this runs on the page somebody lands
on.
"""

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ONE = ROOT / "apps/oneapp/oneapp/onespace/one.py"
HOME = ROOT / "apps/oneapp/oneapp/onespace/home.py"
ROUTER = ROOT / "apps/oneapp/frontend/src/router.js"


@pytest.fixture
def one(stub_frappe):
	from oneapp.onespace import one as module

	return module


# --------------------------------------------------------------------------- #
# The space
# --------------------------------------------------------------------------- #

def test_a_workspace_gets_exactly_one_of_it(one, stub_frappe):
	stub_frappe.get_installed_apps = lambda: ["frappe", "oneapp"]
	found = one.local_spaces()
	assert len(found) == 1
	assert found[0]["space_code"] == "one"
	assert found[0]["brand"] == "one"


def test_it_is_open_to_everybody(one, stub_frappe):
	"""An empty `role_name` is what `resolve.visible` has always read as "no
	narrowing". Narrowing is per screen and per tab, where it belongs: a member
	opening Configuration should find the tabs that are theirs, not a door that
	does not open."""
	stub_frappe.get_installed_apps = lambda: ["frappe", "oneapp"]
	assert one.local_spaces()[0]["role_name"] == ""


def test_it_sorts_before_every_space_a_workspace_bought(one, stub_frappe):
	stub_frappe.get_installed_apps = lambda: ["frappe", "oneapp"]
	assert one.local_spaces()[0]["sort_order"] < 0


def test_the_control_plane_is_not_a_workspace(one, stub_frappe):
	"""That site is an operator console. A Configuration page for "this
	workspace" there would be one for the platform's own bookkeeping."""
	stub_frappe.get_installed_apps = lambda: ["frappe", "oneapp", "oneapp_control"]
	assert one.local_spaces() == []


def test_every_screen_it_declares_is_one_the_browser_can_draw(one, stub_frappe):
	"""A `component` naming nothing renders "this screen has nothing to show
	yet", which is the quietest failure a manifest has."""
	registry = (
		ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/index.js"
	).read_text()
	stub_frappe.get_installed_apps = lambda: ["frappe", "oneapp"]
	for screen in one.local_spaces()[0]["screens"]:
		named = screen["component"]
		assert (f"'{named}':" in registry or f"\n  {named}:" in registry), named


def test_the_two_lists_of_spaces_arrive_as_one_order():
	"""It used to be a concatenation, which put whatever a provider returned
	after everything the control plane sent. One is provided and belongs
	first, and a rail whose order depends on where a space came from is a rail
	with a seam in it."""
	source = (ROOT / "apps/oneapp/oneapp/onespace/sync.py").read_text()
	assert "def ordered(" in source
	assert 'ordered(json.loads(doc.spaces_json or "[]") + local_spaces())' in source


# --------------------------------------------------------------------------- #
# The front door
# --------------------------------------------------------------------------- #

def test_the_root_lands_inside_one_rather_than_on_a_page_about_spaces():
	source = ROUTER.read_text()
	assert "Launcher" not in source, "the page of cards is back"
	assert "redirect: { name: 'Screen', params: { spaceCode: ONE } }" in source


def test_a_space_somebody_cannot_open_sends_them_to_one_and_not_to_a_loop():
	"""One is the space they are certain to have, so it is where a refused
	address goes — and it must not redirect *itself* there, which is a browser
	that navigates for ever."""
	source = ROUTER.read_text()
	guard = source[source.index("if (to.name === 'Screen'"):]
	assert "if (to.params.spaceCode === ONE) return true" in guard


# --------------------------------------------------------------------------- #
# The page
# --------------------------------------------------------------------------- #

def test_the_home_page_has_no_query_of_its_own():
	"""Every block calls the module that already owns that question. A read
	here would be a fourth opinion about what a notification is.

	Over the parsed tree rather than the text, because the file *says* the
	words in the paragraph arguing for the rule.
	"""
	reads = {"get_list", "get_all", "get_value", "sql", "get_single_value"}
	called = {
		node.func.attr
		for node in ast.walk(ast.parse(HOME.read_text()))
		if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
	}
	assert not (called & reads), f"home.py reads the database itself: {called & reads}"


def test_every_block_is_tried_and_dropped():
	"""This is the page somebody lands on. One app half through a migration is
	not a reason for a front page to be a stack trace."""
	tree = ast.parse(HOME.read_text())
	body = next(
		node for node in ast.walk(tree)
		if isinstance(node, ast.FunctionDef) and node.name == "_try"
	)
	assert any(isinstance(node, ast.Try) for node in ast.walk(body))
	assert "log_error" in ast.unparse(body), "a block that is always empty must be findable"


def test_the_page_is_one_call():
	"""Three endpoints is three spinners and a page that assembles itself in
	front of the reader — `onehr/me.py` says the same about eight."""
	page = (
		ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/one/Home.vue"
	).read_text()
	calls = re.findall(r"workspace\.(\w+)\(", page)
	assert calls == ["myHome"], calls


# --------------------------------------------------------------------------- #
# The settings, on the page that replaced the dialog
#
# The move is mechanical and its failures are quiet: a panel with no place on a
# page is a panel nobody can open, and a panel placed twice is two doors to one
# room. Both are read off `one.py` and `configuration.py` rather than clicked.
# --------------------------------------------------------------------------- #

CONFIGURATION = ROOT / "apps/oneapp/oneapp/onespace/configuration.py"
TABS = ROOT / "apps/oneapp/oneapp/onespace/tabs.py"


def _placed() -> list[str]:
	"""Every panel One's Configuration puts somewhere, in order."""
	return re.findall(r'\{"panel": "([\w-]+)"\}', ONE.read_text())


def _declared() -> set[str]:
	return set(re.findall(r'"key": "([\w-]+)"', TABS.read_text()))


def _space_panels() -> list[str]:
	block = CONFIGURATION.read_text()
	at = block.index("SPACE_PANELS = (")
	return re.findall(r'"([\w-]+)"', block[at:block.index(")", at)])


def test_every_settings_tab_has_exactly_one_place():
	"""A tab nothing places is a tab nobody can open; one placed twice is two
	doors to one room. Every tab is either on One or on every space."""
	placed = _placed()
	assert len(placed) == len(set(placed)), "a panel is placed twice on One"

	everywhere = set(placed) | set(_space_panels())
	missing = _declared() - everywhere
	assert not missing, f"declared and placed nowhere: {sorted(missing)}"
	assert not (set(placed) & set(_space_panels())), (
		"a panel is both the workspace's and every space's"
	)


def test_the_first_group_is_the_one_everybody_has():
	"""A page that opens on Branding for somebody who cannot write it opens on
	somebody else's business. Everybody has the four in You; half the workspace
	has none of the rest."""
	first = ONE.read_text().index('{"label": "You"')
	assert all(
		ONE.read_text().index(f'{{"label": "{other}"') > first
		for other in ("People", "Workspace", "Storage")
	)


def test_a_space_panel_is_the_engine_s_rather_than_a_manifest_s():
	"""Three settings belong to a space and all three are keyed on a doctype,
	which the space has already declared. A manifest restating them would be
	three lines repeated in every space and forgotten in the next one."""
	assert _space_panels() == ["alerts", "naming", "print-formats"]
	spaces = ROOT / "apps/oneapp_control/oneapp_control/spaces"
	for path in spaces.glob("*.py"):
		assert '"panel"' not in path.read_text(), (
			f"{path.name} declares a settings panel; the engine appends them"
		)


def test_a_space_that_declared_no_configuration_still_gets_one():
	"""Or the three panels above have nowhere to be in most spaces."""
	source = (ROOT / "apps/oneapp/oneapp/onespace/sync.py").read_text()
	assert "def configured(" in source
	assert "configured(" in source[source.index('"spaces":'):source.index('"roles":')]
