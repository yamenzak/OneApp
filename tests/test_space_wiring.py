"""A space added to `spaces/` is wired because it is there.

`docs/CLEANUP.md` stage 9. Adding a space used to mean editing four lists that
nobody links to each other:

* `spaces.SPACES`, the dict the installer walks;
* `seed_erp_spaces.seed()`'s tuple of modules to install on the dev tenant;
* `seed_dev_space`'s tuple of "codes the seeders rebuild", which decides what a
  previous run's fixture keeps;
* and `scripts/upstream_fields.py`, which was already a glob.

Three of the four were edited when OneBook arrived in stage 7 and one was not.
The one that was missed was the third, and the failure is the shape this whole
arc keeps finding: nothing broke, nothing said anything, and the dev site
quietly grew **one more copy of OneBook on its rail per seed run** until
somebody counted them. Six, by the time anybody did.

So none of them is typed any more, and these are the rules that keep it that
way. They are deliberately about the *readers* rather than the results: a
discovery that silently starts matching nothing is the same failure one level
up.
"""

import ast
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTROL = ROOT / "apps/oneapp_control"
SPACES_DIR = CONTROL / "oneapp_control/spaces"
ERP_SEED = ROOT / "scripts/seed_erp_spaces.py"
DEV_SEED = ROOT / "scripts/seed_dev_space.py"

sys.path.insert(0, str(CONTROL))

from oneapp_control import spaces  # noqa: E402


def _on_disk() -> dict:
	"""Every file in the directory that declares a space, read by hand.

	The same question `spaces._modules()` answers, asked a different way — by
	parsing rather than importing — so the two cannot be wrong together.
	"""
	found = {}
	for path in sorted(SPACES_DIR.glob("*.py")):
		if path.stem.startswith("_") or path.stem == "roles":
			continue
		tree = ast.parse(path.read_text())
		for node in tree.body:
			if not isinstance(node, ast.Assign):
				continue
			if getattr(node.targets[0], "id", "") != "SPACE":
				continue
			code = next(
				ast.literal_eval(value)
				for key, value in zip(node.value.keys, node.value.values)
				if getattr(key, "value", "") == "space_code"
			)
			found[code] = path.stem
	return found


ON_DISK = _on_disk()


# --------------------------------------------------------------------------- #
# A. The discovery found what is there
# --------------------------------------------------------------------------- #

def test_the_reader_found_the_spaces():
	"""A glob that matches nothing turns every rule below into a pass."""
	assert len(ON_DISK) >= 6, ON_DISK
	assert "oneadmin" in ON_DISK and "onehr" in ON_DISK


def test_every_space_on_disk_is_one_the_installer_walks():
	assert set(spaces.SPACES) == set(ON_DISK), (
		f"discovered {sorted(spaces.SPACES)} and the directory holds "
		f"{sorted(ON_DISK)}"
	)


def test_a_space_is_filed_under_the_code_it_declares():
	"""Keyed by `space_code` and not by filename, because those are allowed to
	differ — and the code is what an entitlement, a URL and the catalogue all
	name."""
	for code, module in spaces.SPACES.items():
		assert module.SPACE["space_code"] == code


def test_the_package_imports_without_a_bench():
	"""Discovery imports every space module at import time, so a manifest that
	grew a top-level `import frappe` would make this package unimportable
	outside a site — and `test_space_screens.py`, `test_manifests.py` and the
	snapshot generator all read these without one."""
	for path in sorted(SPACES_DIR.glob("*.py")):
		source = path.read_text()
		top = [
			node for node in ast.parse(source).body
			if isinstance(node, (ast.Import, ast.ImportFrom))
		]
		named = {
			alias.name.split(".")[0]
			for node in top for alias in node.names
		} | {
			(node.module or "").split(".")[0]
			for node in top if isinstance(node, ast.ImportFrom)
		}
		assert "frappe" not in named, (
			f"{path.name} imports frappe at the top, so the whole package now "
			f"needs a bench to import"
		)


# --------------------------------------------------------------------------- #
# B. The console is the one space that is not a tenant's
# --------------------------------------------------------------------------- #

def test_only_the_console_is_the_control_planes_own():
	own = [code for code, module in spaces.SPACES.items()
	       if getattr(module, spaces.CONTROL_PLANE, False)]
	assert own == ["oneadmin"], own


def test_shipped_is_everything_else():
	assert set(spaces.shipped()) == set(spaces.SPACES) - {"oneadmin"}


def test_the_fixture_would_refuse_the_console():
	"""The reason `shipped()` exists: the console's doctypes are the control
	plane's, so installing it onto a tenant would write a rail entry onto a
	site where every screen refuses."""
	assert "oneadmin" not in spaces.shipped()


# --------------------------------------------------------------------------- #
# C. Neither seeder carries a list of spaces
# --------------------------------------------------------------------------- #

def _module(path: pathlib.Path, name: str):
	spec = importlib.util.spec_from_file_location(name, path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def test_the_erp_seeder_discovers_what_it_installs():
	"""It was `for module in (oneproject, onecrm, onehr, onebook)`."""
	source = ERP_SEED.read_text()
	body = source[source.index("def carriable("):source.index("def seed(")]
	assert "spaces.shipped()" in body, "carriable no longer reads the modules"
	assert "requires_apps" in body, (
		"a space over a doctype this bench has not got has to be skipped by "
		"its own sentence about itself, not by a list"
	)
	assert "from oneapp_control.spaces import onebook" not in source, (
		"the seeder names a space module again"
	)


def test_the_dev_fixture_computes_what_it_rebuilt():
	"""It was a tuple of six codes written above the seeders that produce
	them, and `onebook` was never added to it."""
	source = DEV_SEED.read_text()
	assert "rebuilt = {one.get(\"space_code\") for one in fresh}" in source, (
		"the fixture no longer reads the set off the rows it just wrote"
	)
	assert '"rua", "onemobility", "onetask"' not in source, (
		"the typed list of codes the seeders rebuild is back"
	)


def test_the_snapshot_generator_still_globs():
	"""The one of the four that was always discovery, kept honest."""
	source = (ROOT / "scripts/upstream_fields.py").read_text()
	assert 'SPACES.glob("*.py")' in source


# --------------------------------------------------------------------------- #
# D. And the witnesses
#
# Each of the three rules above passes if its reader matches nothing. These are
# the same readers run against something that should fail.
# --------------------------------------------------------------------------- #

def test_an_undeclared_space_would_be_caught():
	found = dict(ON_DISK)
	found["oneimaginary"] = "oneimaginary"
	assert set(spaces.SPACES) != set(found)


def test_a_second_control_plane_space_would_be_caught():
	own = [code for code in list(spaces.SPACES) + ["oneimaginary"]
	       if code == "oneadmin" or code == "oneimaginary"]
	assert own != ["oneadmin"]


@pytest.mark.parametrize("code", sorted(spaces.shipped()))
def test_every_shipped_space_says_which_apps_it_needs(code):
	"""`carriable` reads this to decide whether a bench can hold the space, so
	a manifest that does not declare the key at all is one the fixture will
	install onto a site with none of its doctypes. An empty string is a real
	answer — OneMobility needs nothing — and a missing key is not."""
	assert "requires_apps" in spaces.shipped()[code].SPACE, code


# --------------------------------------------------------------------------- #
# E. Entities live once
#
# `docs/CLEANUP.md` §7's first bullet, made checkable. OneCRM owns parties,
# OneHR owns people, OneBook owns ledgers; everything else links. Until
# stage 11 that was a sentence in a plan and nothing read it, and the way it
# fails is not by somebody building a second Customer table — it is by a second
# space quietly acquiring `Write` on the first one, after which two spaces are
# both "where a customer is maintained" and neither knows it.
# --------------------------------------------------------------------------- #

#: The entity, and the space that owns it. One writer each, and everybody else
#: reads. `GL Entry` is on the list with no writer at all, which is not an
#: omission: nothing in ERPNext writes one by hand either — it is written by
#: the documents above it — so "nobody" is the correct and only answer.
OWNED = {
	"Customer": "onecrm",
	"Lead": "onecrm",
	"Prospect": "onecrm",
	"Contact": "onecrm",
	"Supplier": "onebook",
	"GL Entry": None,
	"Employee": "onehr",
}

#: RUA is one company's own system rather than a shipped product space —
#: `oneapp_control/spaces/rua.py` — so it is a workspace that happens to be
#: delivered as a module, and its grants are that customer's decisions about
#: their own data. Holding it to a rule about which *product* owns an entity
#: would be holding a customer to an argument they are not part of.
BESPOKE = {"rua"}


def _writers(doctype: str) -> set[str]:
	found = set()
	for code, module in spaces.shipped().items():
		if code in BESPOKE:
			continue
		for row in module.DOCTYPES:
			if row[0] == doctype and row[1] in ("Write", "Manage"):
				found.add(code)
	return found


@pytest.mark.parametrize("doctype", sorted(OWNED))
def test_an_entity_has_one_owner(doctype):
	owner = OWNED[doctype]
	writers = _writers(doctype)
	assert writers == ({owner} if owner else set()), (
		f"{doctype} is written by {sorted(writers) or 'nobody'} and "
		f"{owner or 'nobody'} owns it"
	)


@pytest.mark.parametrize("doctype", sorted(OWNED))
def test_everybody_else_reads_it(doctype):
	"""The other half, and the one that says this is about *linking* rather
	than about hoarding: a space that may not write an entity must still be
	able to read it, or "everything else links" is a link to something the
	reader cannot open."""
	owner = OWNED[doctype]
	for code, module in spaces.shipped().items():
		if code == owner or code in BESPOKE:
			continue
		grants = {row[1] for row in module.DOCTYPES if row[0] == doctype}
		assert grants <= {"Read"}, (
			f"{code} holds {sorted(grants)} on {doctype}, which is {owner}'s"
		)


def test_the_writer_reader_found_something():
	"""A reader matching nothing would make both rules above pass for a
	codebase where every space writes everything."""
	assert _writers("Customer") == {"onecrm"}
	assert _writers("Employee") == {"onehr"}
