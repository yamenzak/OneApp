"""A doctype with exactly one document, as a screen.

`docs/ONEBOOK.md` stage 2. Frappe calls it a Single and the list engine has
nothing to say about one — no list, no record id, no New button — so every
screen mechanism in One passed straight over them and a Single was
reachable from the desk and nowhere else.

OnePeople answered that first, for the six HRMS ships. This stage moved the
page to the engine, because OneBook wanted the same one over an ERPNext Single
and a second copy is a second set of rules about what a page may write.

What is checked here is the part that is not a form: the screen key and the
space code arrive from the browser, and everything else — the doctype, the
fields it may write, whether there is a verb and what method is behind it — is
looked up on this side.
"""

import ast
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/onespace/singles.py"
SCREEN = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/Single.vue"
REGISTRY = ROOT / "apps/oneapp/frontend/src/modules/onespace/screens/index.js"
TOOLS = ROOT / "apps/oneapp/oneapp/onehr/tools.py"
SPACES = ROOT / "apps/oneapp_control/oneapp_control/spaces"
ADAPTERS = ROOT / "apps/oneapp/oneapp/adapters"


@pytest.fixture
def singles(stub_frappe):
	from oneapp.onespace import singles as module

	return module


def manifest(code: str):
	spec = importlib.util.spec_from_file_location(
		f"{code}_manifest", SPACES / f"{code}.py")
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def single_screens(code: str) -> list[dict]:
	return [one for one in manifest(code).SCREENS
	        if (one.get("component") or "") == "single"]


def _table(source: str, name: str) -> dict:
	"""One module-level dictionary, read out of the source.

	Read rather than imported, because these two live behind a Frappe import
	and the question here is what the file says.
	"""
	return ast.literal_eval(
		next(ast.unparse(node.value) for node in ast.walk(ast.parse(source))
		     if isinstance(node, ast.Assign)
		     and getattr(node.targets[0], "id", "") == name)
	)


#: Every space that mounts one today. Named rather than globbed, so a space
#: gaining a Single page arrives here as a failing test and somebody decides
#: whether its declaration is right.
MOUNTING = ("onehr", "onebook")


# --------------------------------------------------------------------------- #
# A. Nothing about the page comes from the request
# --------------------------------------------------------------------------- #

def test_a_screen_that_is_not_a_single_is_refused(singles, monkeypatch):
	"""The endpoint takes a screen key, so the first thing it does is refuse
	one that is a list. Without this, a Single's page is a second door onto
	every doctype in the space, drawn as a form over whatever the first row
	happens to be."""
	monkeypatch.setattr(singles, "_space", lambda code: {
		"space_code": code,
		"screens": [{"screen": "invoices", "document_type": "Sales Invoice"}],
	})
	with pytest.raises(Exception):
		singles._screen("onebook", "invoices")


def test_a_screen_nobody_declared_is_refused(singles, monkeypatch):
	monkeypatch.setattr(singles, "_space", lambda code: {
		"space_code": code, "screens": []})
	with pytest.raises(Exception):
		singles._screen("onebook", "whatever")


def test_a_single_screen_with_no_doctype_is_refused(singles, monkeypatch):
	"""`document_type` on a component screen is how it says who it is for, and
	on this one it is also *what it is*. A page without one has nothing to
	read and no grant to check."""
	monkeypatch.setattr(singles, "_space", lambda code: {
		"space_code": code,
		"screens": [{"screen": "rules", "component": "single"}],
	})
	with pytest.raises(Exception):
		singles._screen("onehr", "rules")


def test_only_the_fields_the_manifest_named_are_written(singles):
	"""The allowlist is the screen's own `fields`, which is where every other
	allowlist in this product lives — so the guards that check a fieldname
	against the real doctype check these pages too."""

	class Doc:
		def __init__(self):
			self.written = {}

		def update(self, values):
			self.written.update(values)

	doc = Doc()
	columns = [{"fieldname": "company"}, {"fieldname": "invoice_type"}]
	singles.apply_values(doc, columns, {
		"company": "Acme", "invoice_type": "Sales", "owner": "root@example.com",
	})
	assert doc.written == {"company": "Acme", "invoice_type": "Sales"}


def test_the_fields_are_read_off_the_screen(singles):
	assert singles.fields_of({"fields": "company, invoice_type ,invoices"}) == [
		"company", "invoice_type", "invoices"]
	assert singles.fields_of({}) == []


# --------------------------------------------------------------------------- #
# B. A verb is named here and nowhere else
# --------------------------------------------------------------------------- #

def test_a_manifest_cannot_name_a_method():
	"""The one thing a space may not declare. A manifest that could say which
	method to call on a Single is a manifest that can call anything, and a
	manifest is synced onto a tenant."""
	for code in MOUNTING:
		for screen in single_screens(code):
			assert "method" not in screen, screen["screen"]
			assert "call" not in screen, screen["screen"]


def test_every_verb_names_a_whole_path(singles):
	"""Module, class and method — not a bare method name. Two things follow:
	an upgrade that moves the class fails at the button rather than reaching
	whatever else answers to that name, and the path is a string this file
	holds, which is what `oneapp/adapters/` is read against."""
	for doctype, verb in singles.VERBS.items():
		assert verb["call"].count(".") >= 3, doctype
		assert verb["verb"] and verb["blurb"], doctype


def test_every_verb_is_declared_as_a_seam():
	"""A call into ERPNext or HRMS that no adapter explains is the thing
	`docs/CLEANUP.md` stage 10 exists to stop."""
	declared = set()
	for path in sorted(ADAPTERS.glob("*.py")):
		tree = ast.parse(path.read_text())
		for node in ast.walk(tree):
			if isinstance(node, ast.Constant) and isinstance(node.value, str):
				declared.add(node.value)

	# The table, read out of the source rather than imported, so this test
	# needs no Frappe at all.
	for verb in _table(SOURCE.read_text(), "VERBS").values():
		if verb["call"].split(".")[0] in ("erpnext", "hrms"):
			assert verb["call"] in declared, verb["call"]


def test_a_tool_is_never_saved():
	"""HRMS's and ERPNext's desks save one, which makes the filters at the top
	of a bulk tool a global that two people running it in the same week
	overwrite for each other. Here the browser sends the values with every
	call and the document is dropped afterwards."""
	source = SOURCE.read_text()
	assert "if doctype in VERBS:" in source, "save() refuses a tool"


def test_the_grant_is_checked_before_frappes_own():
	"""Two questions and both have to be asked. The space's grant is what
	keeps a screen out of somebody's rail; Frappe's permission is what the
	desk asks for and what a `permlevel` is read against. A page that asked
	only the second would be reachable by URL from a space that never granted
	the doctype."""
	source = SOURCE.read_text()
	assert "_refuse_ungranted(space, doctype)" in source
	assert 'frappe.has_permission(doctype, "write" if write else "read")' in source


# --------------------------------------------------------------------------- #
# C. The spaces that mount one
# --------------------------------------------------------------------------- #

def test_the_spaces_that_mount_one_still_do():
	found = {code for code in MOUNTING if single_screens(code)}
	assert found == set(MOUNTING), found


def test_every_single_screen_is_granted_by_its_space():
	"""A component screen naming a doctype is refused by `spaceview.resolve`
	unless the space grants it, so a page whose doctype is ungranted is a rail
	entry that answers 403."""
	for code in MOUNTING:
		granted = {row[0] for row in manifest(code).DOCTYPES}
		for screen in single_screens(code):
			assert screen["document_type"] in granted, (
				f"{code}/{screen['screen']} names "
				f"{screen['document_type']}, which the space does not grant"
			)


def test_every_single_screen_names_its_fields():
	"""A component screen that declares none implies the whole doctype, which
	on this page means every field is writable and the curation guards pass
	over it entirely."""
	for code in MOUNTING:
		for screen in single_screens(code):
			assert (screen.get("fields") or "").strip(), screen["screen"]


def test_the_browser_has_one_component_for_all_of_them():
	"""Keyed with no slash, like `home` and `configuration`: any space may say
	it, and keying it per space would be the same entry once per app."""
	registry = REGISTRY.read_text()
	assert "single: () => import('@/modules/onespace/screens/Single.vue')," in registry
	assert SCREEN.exists()
	for code in MOUNTING:
		for screen in single_screens(code):
			assert f"'{code}/{screen['screen']}':" not in registry, screen["screen"]


def test_the_people_tools_kept_their_own_page():
	"""What stayed in OnePeople is the finder, which is the value: each of the
	three excludes the people the tool would be a no-op for. What left is the
	form under it."""
	source = TOOLS.read_text()
	assert "SETTINGS" not in source, "the two settings pages moved to the engine"
	assert set(_table(source, "TOOLS")) == {
		"allocate", "assign-shifts", "assign-structures"}
