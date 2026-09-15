"""The app marks: what the design says, and what three generated things say.

A mark is drawn once, in `scripts/brand/marks.source.html`, and lands in three
places — `marks.json` for a human to diff, `marks.js` for the SPA, and one
standalone SVG per mark for a favicon, an email and a print. Nothing checks
those against each other at runtime: a mark that came through empty is an
invisible icon, and an invisible icon is the kind of defect that ships because
the place it is missing from is a 20px square in a rail.

So this is the check, and it is deliberately **pure Python**. The page is
JavaScript and `scripts/brand/read_marks.mjs` runs it in node; re-running that
here would make the whole suite depend on a runtime it otherwise does not need.
`marks.json` is the generator's own record of what it read, it is checked in,
and every other output is derived from it by code this can call directly. So
the split is: node turns the *page* into `marks.json`, which a person does when
the design changes; this holds the other two outputs to it on every run.

The last two tests are the witnesses — §F3's meta-rail. A guard nobody has seen
fail is a guard nobody knows the scan of.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MARKS_JSON = ROOT / "scripts/brand/marks.json"
MARKS_JS = ROOT / "apps/oneapp/frontend/src/shared/lib/brand/marks.js"
SVG_DIR = ROOT / "apps/oneapp/oneapp/public/brand"

MARKS = json.loads(MARKS_JSON.read_text(encoding="utf-8"))

_HEX = re.compile(r"^#[0-9a-f]{6}$")
_ID_ATTR = re.compile(r'\bid="([^"]+)"')
_URL_REF = re.compile(r"url\(#([^)]+)\)")


@pytest.fixture(scope="module")
def gen():
	import sys

	sys.path.insert(0, str(ROOT / "scripts"))
	import gen_brand

	return gen_brand


@pytest.mark.parametrize("mark", MARKS, ids=lambda m: m["id"])
def test_every_mark_is_a_drawing_with_a_box_and_a_colour(mark):
	assert mark["body"].strip(), f"{mark['id']} came through empty"
	assert re.fullmatch(r"0 0 \d+ \d+", mark["box"]), mark["box"]
	assert _HEX.match(mark["color"]), f"{mark['id']} has no usable colour"
	# `said` in the SPA, and the caption under a tile. Four words, not a
	# sentence — the old set's subtitles were "Intelligent Long-Term Cold
	# Storage & Vault" and nothing had room for them.
	assert 0 < len(mark["subtitle"].split()) <= 6, mark["subtitle"]


@pytest.mark.parametrize("mark", MARKS, ids=lambda m: m["id"])
def test_every_reference_inside_a_mark_resolves_inside_it(mark):
	"""A gradient a mark points at is a gradient the same mark declares.

	Every mark inlines the same four shared filters, so these ids collide
	across marks by construction and the uniquifier is what keeps two of them
	on one page apart. A reference to something *not* declared here would
	survive that rewrite pointing at whatever happened to be in the document.
	"""
	declared = set(_ID_ATTR.findall(mark["body"]))
	used = set(_URL_REF.findall(mark["body"]))
	assert used <= declared, f"{mark['id']} points outside itself: {used - declared}"


def test_an_id_is_not_a_name(gen):
	"""The page's ids are the designer's; the ids here are this repository's.

	The *names* are the page's now — OneCloud, OneWriter, OneWorkbook,
	OnePeople — and the ids under them are not, because an id is not a name:
	`onedoc` is a Frappe module written into `modules.txt` and into every
	generated doctype, `onehr` is a space code in the URL, and both are what a
	manifest says. `ALIAS` is the whole of that map, and it follows the rule
	`CLAUDE.md` already states about the repository's own name.
	"""
	ids = {mark["id"] for mark in MARKS}
	assert set(gen.ALIAS.values()) <= ids
	assert not any("-" in one for one in ids), "an id came through un-aliased"
	# And the names are not the ids with a capital letter, which is what a
	# revision of the page quietly dropping `ALIAS` would produce.
	named = {mark["id"]: mark["name"] for mark in MARKS}
	assert named["onedoc"] == "OneWriter" and named["onestorage"] == "OneCloud"


def test_the_spa_copy_is_what_the_generator_would_write(gen, tmp_path):
	written = _regenerate(gen, tmp_path, MARKS)
	assert written["js"] == MARKS_JS.read_text(encoding="utf-8"), (
		"marks.js is not what scripts/gen_brand.py would write — run it"
	)


def test_every_mark_has_a_standalone_file_and_nothing_else_does(gen, tmp_path):
	written = _regenerate(gen, tmp_path, MARKS)
	assert written["svgs"] == {
		one.name: one.read_text(encoding="utf-8") for one in SVG_DIR.glob("*.svg")
	}, "public/brand is not what scripts/gen_brand.py would write — run it"


def test_a_hand_edited_mark_would_be_caught(gen, tmp_path):
	"""The witness for the two above. §F3's one meta-rail."""
	meddled = [dict(one) for one in MARKS]
	meddled[0]["body"] = meddled[0]["body"].replace("<", "<!-- -->", 1)
	written = _regenerate(gen, tmp_path, meddled)
	assert written["js"] != MARKS_JS.read_text(encoding="utf-8")
	assert written["svgs"] != {
		one.name: one.read_text(encoding="utf-8") for one in SVG_DIR.glob("*.svg")
	}


def test_a_dangling_gradient_would_be_caught():
	"""The witness for the reference check."""
	broken = {"id": "x", "body": '<path fill="url(#nowhere)"/>'}
	declared = set(_ID_ATTR.findall(broken["body"]))
	assert set(_URL_REF.findall(broken["body"])) - declared


def _regenerate(gen, tmp_path, marks: list[dict]) -> dict:
	"""Both derived outputs, written somewhere harmless and read back."""
	js, svg_dir = gen.JS, gen.SVG_DIR
	gen.JS, gen.SVG_DIR = tmp_path / "marks.js", tmp_path / "brand"
	try:
		gen.write_js(marks)
		gen.write_svgs(marks)
		return {
			"js": gen.JS.read_text(encoding="utf-8"),
			"svgs": {
				one.name: one.read_text(encoding="utf-8")
				for one in gen.SVG_DIR.glob("*.svg")
			},
		}
	finally:
		gen.JS, gen.SVG_DIR = js, svg_dir


# --------------------------------------------------------------------------- #
# And the other end of it: a mark that is drawn and never appears
#
# The failure this catches is quiet by construction. Somebody adds a mark to
# the design page, runs the generator, and the drawing ships in three files and
# is rendered by nothing — because the thing that decides what is on the board
# is `lib/shell/apps.js` and nobody opened it. A drawing nobody can see is the
# same defect as a facet with no explanation, one level up.
# --------------------------------------------------------------------------- #

CATALOGUE = (
	ROOT / "apps/oneapp/frontend/src/modules/onespace/lib/shell/apps.js"
).read_text(encoding="utf-8")

#: The two the board leaves out, and why. Argued here rather than in a comment
#: in the catalogue so that adding a third costs an argument.
NOT_ON_THE_BOARD = {
	# The shell you are standing in, not somewhere to go. It is the corner's
	# own face when you are not inside anything.
	"one",
	# Ours. The operator console is a different product on a different host,
	# and the one row that leaves this workspace is already in the switcher's
	# foot.
	"oneadmin",
}


def test_every_mark_is_either_on_the_board_or_argued_off_it():
	drawn = {mark["id"] for mark in MARKS}
	listed = set(re.findall(r"brand: '([a-z]+)'", CATALOGUE))
	missing = drawn - listed - NOT_ON_THE_BOARD
	assert not missing, (
		f"drawn and on no board: {sorted(missing)} — add it to CATALOGUE in "
		f"lib/shell/apps.js, or to NOT_ON_THE_BOARD here with the reason"
	)
	assert listed <= drawn, f"the board names marks nothing draws: {sorted(listed - drawn)}"


def test_a_new_mark_nobody_listed_would_be_caught():
	"""The witness. §F3's one meta-rail."""
	drawn = {mark["id"] for mark in MARKS} | {"onewhatever"}
	listed = set(re.findall(r"brand: '([a-z]+)'", CATALOGUE))
	assert drawn - listed - NOT_ON_THE_BOARD == {"onewhatever"}
