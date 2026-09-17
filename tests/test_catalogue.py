"""One declaration of what this app is made of, held to everything it claims.

`oneapp/catalogue.py` says whether each mark is a space, a service or the
engine, which Frappe module owns its doctypes, and whether it exists yet. Four
other things in this repository already knew part of that and none of them knew
all of it — `modules.txt`, the directory listing, `marks.json`, and the
browser's own catalogue.

So these are the four readings, each in the direction that would otherwise fail
silently: a module with no declaration is a directory nobody owns, and a
declaration with no module is a decision about nothing.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "apps/oneapp/oneapp"
MARKS_JSON = ROOT / "scripts/brand/marks.json"
APPS_JS = ROOT / "apps/oneapp/frontend/src/modules/onespace/lib/shell/apps.js"
KINDS_JS = ROOT / "apps/oneapp/frontend/src/shared/lib/brand/kinds.js"

sys.path.insert(0, str(ROOT / "apps/oneapp"))
sys.path.insert(0, str(ROOT / "scripts"))

from oneapp import catalogue  # noqa: E402

#: Directories under the app that are not an app. Frappe's own furniture and
#: the two packages that belong to nobody in particular.
FURNITURE = {
	"config", "locale", "patches", "public", "templates", "www", "shared",
	"__pycache__",
}


def test_every_frappe_module_is_declared():
	"""A module in `modules.txt` with no row here is a directory full of
	doctypes that nothing says the shape of."""
	listed = [one.strip() for one in
	          (APP / "modules.txt").read_text(encoding="utf-8").splitlines()
	          if one.strip()]
	assert sorted(catalogue.modules()) == sorted(listed)


def test_every_declared_module_has_a_directory():
	"""And the other way: `frappe.get_module_path` resolves a module to the
	import path `oneapp.<scrubbed name>`, so a declaration naming a module with
	no directory is a doctype nobody can load a controller for."""
	for module, id in catalogue.modules().items():
		where = APP / module.lower()
		assert where.is_dir(), f"{module} is declared and {where.name}/ is not there"
		assert (where / "__init__.py").exists(), f"{where.name}/ is not a package"


def test_every_directory_under_the_app_is_declared():
	"""The reading that catches a space somebody added and never told anybody
	about. A module that owns no doctypes still has a directory — OnePeople is
	HRMS's schema and ours is the behaviour over it — so this is broader than
	the one above."""
	found = {
		one.name for one in APP.iterdir()
		if one.is_dir() and one.name not in FURNITURE
		and (one / "__init__.py").exists()
	}
	# `onespace` is the engine's directory and `one` is its mark: the catalogue
	# carries the mark, because that is what every other reader names it by.
	found = {"one" if name == "onespace" else name for name in found}
	undeclared = sorted(found - set(catalogue.BY_ID))
	assert not undeclared, f"these directories are in no catalogue row: {undeclared}"


def test_a_declared_mark_is_one_that_is_drawn():
	"""A row naming a mark nothing draws is a tile that renders an empty box.
	The other direction is deliberately *not* checked: `marks.json` has
	drawings for things that are not ours to build."""
	drawn = {one["id"] for one in json.loads(MARKS_JSON.read_text(encoding="utf-8"))}
	for row in catalogue.CATALOGUE:
		if row["mark"]:
			assert row["mark"] in drawn, f"{row['id']} names a mark nobody drew"


def test_a_mark_that_is_drawn_is_either_declared_or_not_ours():
	"""The reading that would otherwise go missing: a mark added to the design
	and never decided about is a drawing with no answer to "what is that"."""
	drawn = {one["id"] for one in json.loads(MARKS_JSON.read_text(encoding="utf-8"))}
	claimed = {row["mark"] for row in catalogue.CATALOGUE if row["mark"]}
	assert not sorted(drawn - claimed), (
		f"drawn and undeclared: {sorted(drawn - claimed)}"
	)


def test_the_browser_carries_no_kind_of_its_own():
	"""It reads `KINDS`, which is generated. A `kind:` typed back into
	`apps.js` is the second copy this stage exists to remove."""
	source = APPS_JS.read_text(encoding="utf-8")
	inline = re.findall(r"^\s*(?:kind|built):", source, re.M)
	assert not inline, f"apps.js declares {len(inline)} kinds of its own"


def test_the_browsers_catalogue_is_the_servers():
	"""Every mark the board draws has a row, so `KINDS[brand]` is never
	undefined — which would render as a tile with no state at all."""
	source = APPS_JS.read_text(encoding="utf-8")
	brands = set(re.findall(r"brand: '([a-z]+)'", source))
	assert brands, "nothing was read out of apps.js"
	missing = sorted(brands - set(catalogue.BY_ID))
	assert not missing, f"the board draws marks the catalogue does not know: {missing}"


def test_the_generated_file_is_what_the_generator_writes():
	"""Checked in rather than built, like the marks, so a reviewer can diff it.
	Which only works if it is current."""
	import gen_catalogue

	assert KINDS_JS.read_text(encoding="utf-8") == gen_catalogue.rendered(), (
		"kinds.js is stale — run python3 scripts/gen_catalogue.py"
	)


def test_the_engine_is_one_thing():
	"""Two engines is a codebase with two desks in it."""
	engines = catalogue.of_kind(catalogue.ENGINE)
	assert [row["id"] for row in engines] == ["one"]


def test_nothing_is_both_kinds_and_every_row_is_one_of_them():
	kinds = {catalogue.SPACE, catalogue.SERVICE, catalogue.ENGINE}
	for row in catalogue.CATALOGUE:
		assert row["kind"] in kinds, f"{row['id']} is a {row['kind']!r}"
	ids = [row["id"] for row in catalogue.CATALOGUE]
	assert len(ids) == len(set(ids)), "a mark is declared twice"


def test_a_shipped_space_wears_a_mark_the_catalogue_calls_a_space():
	"""The reading that makes this file load-bearing rather than descriptive.

	A space manifest declares a `brand`, and the rail, the launcher and the
	marketplace all draw the mark it names. Nothing stopped one naming
	`onestorage` — which would put the file drive's mark on a department, and
	light the drive's tile in the board for a workspace that has no drive.

	Joined on the mark rather than the space code deliberately: a code is a
	customer's word for their own space (`books`, `rua`) and the mark is ours.
	A space wearing no mark is fine — it draws a lucide glyph instead, which is
	the right answer for one somebody wrote themselves.
	"""
	import importlib.util

	where = ROOT / "apps/oneapp_control/oneapp_control/spaces"
	spaces = {row["id"] for row in catalogue.of_kind(catalogue.SPACE, built=None)}
	seen = 0

	for path in sorted(where.glob("*.py")):
		if path.stem == "__init__":
			continue
		spec = importlib.util.spec_from_file_location(f"brand_{path.stem}", path)
		module = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(module)
		mark = getattr(module, "SPACE", {}).get("brand")
		if not mark:
			continue
		seen += 1
		assert mark in spaces, (
			f"{path.stem} wears {mark!r}, which the catalogue calls a "
			f"{catalogue.kind_of(mark) or 'nothing at all'}"
		)

	assert seen >= 4, "no space module named a mark, so this read nothing"


# --------------------------------------------------------------------------- #
# The witnesses — §F3's meta-rail
#
# A guard nobody has seen fail is a guard nobody knows the scan of. Each of
# these says what the reader above it actually read, so a rule that quietly
# started matching nothing fails here rather than passing everywhere.
# --------------------------------------------------------------------------- #

def test_the_readers_found_something():
	drawn = json.loads(MARKS_JSON.read_text(encoding="utf-8"))
	brands = set(re.findall(r"brand: '([a-z]+)'", APPS_JS.read_text(encoding="utf-8")))
	found = [one for one in APP.iterdir()
	         if one.is_dir() and one.name not in FURNITURE
	         and (one / "__init__.py").exists()]

	assert len(catalogue.CATALOGUE) >= 25
	assert len(drawn) >= 25
	assert len(brands) >= 20
	assert len(found) >= 10
	assert len(catalogue.modules()) >= 10


def test_an_undeclared_module_would_be_caught():
	"""The scan of the first guard, shown rather than trusted."""
	listed = set(catalogue.modules()) | {"OneImaginary"}
	assert sorted(catalogue.modules()) != sorted(listed)


def test_a_mark_nobody_draws_would_be_caught():
	drawn = {one["id"] for one in json.loads(MARKS_JSON.read_text(encoding="utf-8"))}
	assert "oneimaginary" not in drawn
