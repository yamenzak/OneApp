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


# --------------------------------------------------------------------------- #
# `One` is the part that is the same on all of them
#
# Every app of ours is `One` and a word, and the prefix is what the twin cuts
# scored through the old artwork were for: "these belong together", said once
# and quietly, rather than four letters of noise repeated down a column. It is
# the *word* that carries the signature now, so `SpaceName` writes the prefix
# a shade back and the rest at full strength.
#
# Two guards, because there are two ways to lose it. A name typed as a literal
# never reaches `SpaceName` at all; a name read correctly and then dropped into
# `{{ }}` reaches the screen flat. Both shipped: the switcher had the first and
# the assistant's own window had the second for as long as it had a title.
# --------------------------------------------------------------------------- #

SRC = [ROOT / "apps/oneapp/frontend/src", ROOT / "apps/oneapp_control/frontend/src"]

#: Every product name, longest first so `OneCloud` is found before `One`.
NAMES = sorted(
	(mark["name"] for mark in MARKS if mark["name"].startswith("One")),
	key=len, reverse=True,
)

#: Where a name may be written down, because this is where it is written down.
#: `marks.js` is the generated map itself and `naming.js` is the reader.
MAY_SAY_A_NAME = {"marks.js", "naming.js"}


def _sources():
	for root in SRC:
		if not root.exists():
			continue
		for path in root.rglob("*"):
			if path.suffix in (".vue", ".js") and not path.name.endswith(".test.js"):
				yield path


def _code(source: str):
	"""Every line that is not inside a comment, numbered.

	A state machine rather than a `startswith`, because the comments in this
	repository are paragraphs: the second line of a `/* */` block starts with
	`*` and the second line of an `<!-- -->` block starts with a word, and it
	is the ones starting with a word that name products and quote them.
	"""
	inside = ""
	for at, line in enumerate(source.splitlines(), 1):
		said = line.strip()
		if inside:
			if inside in said:
				inside = ""
			continue
		if said.startswith("<!--") and "-->" not in said:
			inside = "-->"
			continue
		if said.startswith("/*") and "*/" not in said:
			inside = "*/"
			continue
		if said.startswith(("//", "*", "/*", "<!--")):
			continue
		yield at, line


#: A product name inside a string, which is a name on its way to a screen.
#: In quotes, because a name in a *comment* is this repository's house style —
#: half the reasoning in these files names the product it is about — and a
#: comment is not rendered. `One` itself is left out: it is three letters and
#: it is inside `OneSpace`, `_drawOneColHeader` and the word "one".
TYPED_NAME = re.compile(
	r"""['"`](?:[^'"`]*\b)?(""" + "|".join(
		re.escape(name) for name in NAMES if len(name) > 3
	) + r""")\b[^'"`]*['"`]"""
)


def test_a_product_name_is_read_and_never_typed():
	"""`MARKS[id].name` is the only place a product name is written down.

	`CLAUDE.md`, and the reason is that four of the ids disagree with their
	names on purpose: a string saying "OneWriter" beside `onedoc` is a string
	that will still say "OneWriter" the day the name changes, and nothing will
	notice. It is also the first way the light prefix is lost — a literal
	cannot go through `SpaceName`.

	Strings only. Naming the product in a comment is how everything in this
	repository is explained, and a comment is not drawn.
	"""
	guilty = []
	for path in _sources():
		if path.name in MAY_SAY_A_NAME:
			continue
		for at, line in _code(path.read_text(encoding="utf-8")):
			if TYPED_NAME.search(line):
				guilty.append(f"{path.name}:{at}: {line.strip()[:90]}")

	assert not guilty, (
		"these write a product name rather than reading one — `nameOf(id)`, or "
		"`<SpaceName brand=… />` where it is drawn:\n" + "\n".join(guilty)
	)


#: What produces a product name in a template. Both are real: the assistant's
#: is a workspace setting falling back to the mark, and `nameOf` is the mark.
NAMERS = ("assistantName", r"nameOf\([^)]*\)")

#: An interpolation that renders a name *on its own*. `__(` anywhere in it
#: means the name is inside a sentence — "Ask {0}", "Written by {0}" — which is
#: prose: a two-tone word in the middle of a sentence reads worse than it
#: helps, and a translated string cannot carry markup anyway.
def _drawn(namers):
	return re.compile(
		r"\{\{(?!(?:[^}]*__\())[^}]*\b(?:" + "|".join(namers) + r")[^}]*\}\}"
	)


SAYS_A_NAME = _drawn(NAMERS)

#: `const ownName = computed(() => nameOf('oneai'))` — a local standing for one
#: of the two above, which would otherwise walk straight past the scan. Found
#: per file rather than listed, because the point of the guard is that nobody
#: has to remember to add to it.
ALIASES = re.compile(
	r"const\s+(\w+)\s*=\s*(?:computed\(\s*\(\)\s*=>\s*)?(?:"
	+ "|".join(NAMERS) + r")"
)


def _draws_a_name(source: str):
	"""Every line of this file that renders a product name as text."""
	local = ALIASES.findall(source)
	said = _drawn([*NAMERS, *(re.escape(one) for one in local)]) if local else SAYS_A_NAME

	for at, line in enumerate(source.splitlines(), 1):
		if said.search(line):
			yield at, line


def test_a_name_that_is_drawn_goes_through_the_one_that_writes_it_quietly():
	"""A name rendered as text is a name with a prefix, and the prefix is quiet.

	Only what is *drawn*. A `title`, a `tooltip` and an `aria-label` are plain
	strings by the platform's rules and cannot carry two weights; a name inside
	a sentence — "Ask {0}", "Written by {0}" — is prose, and a two-tone word in
	the middle of a sentence reads worse than it helps. What this catches is
	the name standing on its own as a label, which is where the family shows.
	"""
	guilty = []
	for path in _sources():
		for at, line in _draws_a_name(path.read_text(encoding="utf-8")):
			guilty.append(f"{path.name}:{at}: {line.strip()[:90]}")

	assert not guilty, (
		"these draw a product name flat — use `<SpaceName brand=… />`, which "
		"writes `One` a shade back:\n" + "\n".join(guilty)
	)


def test_a_flat_name_would_be_caught():
	"""The witness. §F3's meta-rail."""
	assert list(_draws_a_name("<p>{{ assistantName }}</p>"))
	assert list(_draws_a_name("<p>{{ nameOf('onedoc') }}</p>"))
	# Including through a local that stands for one — the way round the scan
	# that a file would otherwise take without meaning to.
	assert list(_draws_a_name(
		"<p>{{ ownName }}</p>\nconst ownName = computed(() => nameOf('oneai'))"
	))
	# Including where something else is said first, which is the shape a
	# settings row takes: "what they typed, or ours".
	assert list(_draws_a_name(
		"<p>{{ form.assistant.name || ownName }}</p>\n"
		"const ownName = computed(() => nameOf('oneai'))"
	))
	# And what it deliberately lets through: a name that is not drawn, and a
	# name inside a sentence.
	assert not list(_draws_a_name(':title="assistantName"'))
	assert not list(_draws_a_name("{{ __('Ask {0}', [assistantName]) }}"))
	assert not list(_draws_a_name("{{ __('Written by {0}. Check it.', [assistantName]) }}"))
