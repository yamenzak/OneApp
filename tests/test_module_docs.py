"""Every module documents itself, in six files beside its code.

`docs/CLEANUP.md` §8 is the standard and the argument for it. This is the part
that makes it true a year from now: a rule about where documentation lives is
exactly the rule that holds until the afternoon somebody is in a hurry, and the
failure is silent — a module with no `permissions.md` reads as a module with
nothing to say about permissions.

Six files, the same six everywhere, because a reader who has learned one
module's folder has learned all of them. A module with nothing to say under one
of them says so in a line; an absent file says nothing at all.
"""

import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP = ROOT / "apps/oneapp/oneapp"

sys.path.insert(0, str(ROOT / "apps/oneapp"))

from oneapp import catalogue  # noqa: E402

#: The six, in the order §8 lists them.
PAGES = ("collections.md", "flows.md", "integrations.md", "permissions.md",
         "notifications.md", "ai.md")

#: Directories under the app that are not a module. The same list
#: `test_catalogue.py` uses, and for the same reason.
FURNITURE = {"adapters", "config", "locale", "patches", "public", "templates",
             "www", "shared", "__pycache__"}


def modules() -> list[pathlib.Path]:
	return sorted(
		one for one in APP.iterdir()
		if one.is_dir() and one.name not in FURNITURE
		and (one / "__init__.py").exists()
	)


MODULES = [one.name for one in modules()]


@pytest.mark.parametrize("name", MODULES)
@pytest.mark.parametrize("page", PAGES)
def test_every_module_has_every_page(name, page):
	where = APP / name / "docs" / page
	assert where.is_file(), (
		f"{name} has no docs/{page} — see docs/CLEANUP.md §8. A module with "
		f"nothing to say under it writes one line saying so."
	)


@pytest.mark.parametrize("name", MODULES)
def test_every_module_has_a_front_door(name):
	"""The README is the argument, and the six are the reference. GitHub
	renders this one when somebody browses into the directory."""
	assert (APP / name / "README.md").is_file(), f"{name} has no README.md"


@pytest.mark.parametrize("name", MODULES)
@pytest.mark.parametrize("page", PAGES)
def test_a_page_says_something(name, page):
	"""A heading and a sentence. A file created to satisfy the rule above and
	left empty is worse than the absent file it replaced: it answers the
	question with silence and looks like it answered."""
	text = (APP / name / "docs" / page).read_text(encoding="utf-8")
	body = [line for line in text.splitlines()
	        if line.strip() and not line.startswith("#")]

	assert text.startswith("# "), f"{name}/docs/{page} opens with no heading"
	assert body, f"{name}/docs/{page} is a heading and nothing else"
	assert len(" ".join(body).split()) >= 12, (
		f"{name}/docs/{page} says almost nothing; one honest sentence is the "
		f"minimum and 'this module sends nothing' is an honest sentence"
	)


#: How a folder gets filled without being written. Two shapes, because they
#: need different matching: the shouted markers are case-sensitive, and
#: `ToDo` is a Frappe doctype these pages name on purpose — a case-insensitive
#: "todo" caught OneTask's assignment section, which is the opposite of what
#: this is for.
SHOUTED = ("TODO", "FIXME", "XXX", "TBD")
PHRASES = ("coming soon", "fill this in", "lorem ipsum", "to be written",
           "to be documented")


@pytest.mark.parametrize("name", MODULES)
@pytest.mark.parametrize("page", PAGES)
def test_a_page_is_not_a_placeholder(name, page):
	"""The other way a folder gets filled without being written."""
	text = (APP / name / "docs" / page).read_text(encoding="utf-8")
	for word in SHOUTED:
		assert not re.search(rf"\b{word}\b", text), (
			f"{name}/docs/{page} contains {word}"
		)
	for phrase in PHRASES:
		assert phrase not in text.lower(), (
			f"{name}/docs/{page} contains {phrase!r}"
		)


def test_the_placeholder_scan_would_catch_one():
	"""And does not catch the doctype. `ToDo` is Frappe's and OneTask's
	`integrations.md` names it four times."""
	assert re.search(r"\bTODO\b", "TODO: write this")
	assert not re.search(r"\bTODO\b", "An assignment is Frappe's ToDo.")
	assert not re.search(r"\bTBD\b", "A ToDo cannot be a column.")


@pytest.mark.parametrize("name", MODULES)
def test_the_folder_holds_the_six_and_nothing_else(name):
	"""A seventh file is a subject somebody could not place, which is the
	moment to widen the standard rather than to file it somewhere new."""
	found = {one.name for one in (APP / name / "docs").iterdir() if one.is_file()}
	assert found == set(PAGES), (
		f"{name}/docs holds {sorted(found - set(PAGES))} beyond the six"
	)


def test_the_collections_page_names_the_doctypes_the_module_owns():
	"""The one page whose content is checkable against the code, so it is
	checked: a doctype added to a module and not to its `collections.md` is
	the exact drift this whole stage exists to stop."""
	missing = []
	for one in modules():
		where = one / "doctype"
		if not where.is_dir():
			continue
		said = (one / "docs" / "collections.md").read_text(encoding="utf-8")
		for folder in sorted(where.iterdir()):
			spec = folder / f"{folder.name}.json"
			if not spec.is_file():
				continue
			import json

			named = json.loads(spec.read_text(encoding="utf-8"))["name"]
			if named not in said:
				missing.append(f"{one.name}: {named}")

	assert not missing, (
		"these doctypes are owned by a module whose collections.md does not "
		f"name them: {missing}"
	)


def test_nothing_module_owned_is_left_in_the_root_docs():
	"""§8's second half. What stays at the root is what genuinely has no single
	owner — this plan, the arcs and audits that are history rather than
	reference, the map, and the two tables the tests read back.

	Named rather than inferred: "is this file about one module" is a judgement,
	and a list somebody has to edit deliberately is the honest way to hold a
	judgement. Adding a file to the root `docs/` means adding it here and
	arguing for it in the same commit.
	"""
	allowed = {
		# The map, the plan, and the product as a whole.
		"ARCHITECTURE.md", "CLEANUP.md", "ONESPACE.md", "APPS-AND-SPACES.md",
		# The platform: tenancy, the control plane, the operator console.
		"ONEADMIN.md", "ONEADMIN-SIMPLIFICATION.md", "MARKETPLACE.md",
		# Cross-cutting subjects no one module owns.
		"LANGUAGE.md", "LEGAL.md", "PRINTING.md", "WORKSPACE-SETTINGS.md",
		"COLLABORATION.md", "DESKTOP.md", "SHELL.md",
		# The framework's own desk, read against the whole SPA. It is about
		# every module at once and about none of them: the question is which
		# of 109,000 lines the desk would host, and the answer moves the
		# shell, the screen engine, the operator console and the four
		# bespoke apps in different directions.
		"DESK.md",
		# Arcs and audits: history, and the argument for an order of work.
		# They describe a journey rather than a module's current state, so
		# they do not move into one.
		"AI.md", "DRIVE.md", "WRITER.md", "SHEETS.md", "EMAIL.md",
		"DOCUMENT-MAIL.md", "ONECRM.md", "ERP-SPACES.md", "WORK.md",
		"UNIFICATION.md", "RUA.md",
		# The arc that finishes the books, beside `ONECRM.md` and for the same
		# reason: it is an order of work and an argument for it — call their
		# reports rather than copy them, a statement is not a list, what is
		# deliberately left out — rather than a description of what OneBook is
		# now. `onebook/README.md` and its six are that, and the test §8 sets
		# is whether exactly one module would change when a sentence stops
		# being true. Half the sentences here are about ERPNext's reports and
		# a quarter are about what nobody has built.
		"ONEBOOK.md",
		# And the arc that makes something public, which is the same kind of
		# document for the same reason: it is an order of work and the argument
		# for it — what v17 already has, what `forms_pro` is and is not, why
		# the page is ours to draw — rather than a description of a module that
		# does not exist yet. It moves under `oneforms/` when there is one.
		"ONEFORMS.md",
		# Studies of somebody else's product.
		"HORILLA.md", "ALTERNATIVES.md",
		# The framework under all of it, doctype by doctype. Owned by no module
		# by construction: the question it answers is what *One* does with
		# each of Frappe's two hundred and ninety-six tables, and the answers
		# land in the engine, OneMail, OneCloud, OneCalendar and the control
		# plane at once. `test_frappe_coverage.py` reads it back.
		"FRAPPE.md",
	}
	found = {one.name for one in (ROOT / "docs").iterdir() if one.is_file()}
	assert found <= allowed, (
		f"new at the root of docs/: {sorted(found - allowed)}. Either it "
		f"belongs to one module — §8's test is whether exactly one module "
		f"would have to change when the sentence stops being true — or add it "
		f"here with the reason."
	)
	assert allowed <= found, f"listed and gone: {sorted(allowed - found)}"


def test_the_scan_found_the_modules():
	"""A guard nobody has seen fail is a guard nobody knows the scan of."""
	assert len(MODULES) >= 12, MODULES
	assert "onespace" in MODULES and "oneai" in MODULES
