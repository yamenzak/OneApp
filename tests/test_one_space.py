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
		assert f"'{screen['component']}':" in registry, screen["component"]


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
