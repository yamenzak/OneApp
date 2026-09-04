"""A space's declared look — what survives the validator, and what it moves.

Two halves, because the feature has two: `theming.shape` decides what a manifest
is allowed to say, and `lib/theme.js` decides which CSS variables each of those
words moves. Both are checked here, the second by reading the module rather than
running it — the mapping is the interesting part and it is a literal.

The rule the whole thing rests on: a theme is *intents*, never tokens. The day a
manifest can name a CSS variable, a space can put its own text colour on our own
surface colour and ship a screen nobody can read. So the shape is closed, and
the browser owns the expansion.
"""

import json
import re
from pathlib import Path

import pytest

from oneapp.oneapp_core import theming

ROOT = Path(__file__).resolve().parent.parent
THEME_JS = ROOT / "apps/oneapp/frontend/src/lib/theme.js"


def test_a_whole_theme_survives():
	asked = {"mode": "dark", "accent": "#E50914", "ground": "#0d0d0f", "radius": "sharp"}
	assert theming.shape(asked) == {
		"mode": "dark",
		# Lowercased, so two manifests spelling the same colour differently
		# produce the same variables and the same screenshot.
		"accent": "#e50914",
		"ground": "#0d0d0f",
		"radius": "sharp",
	}


def test_json_text_is_a_theme():
	"""The field holds Small Text, so this is the shape it actually arrives in."""
	asked = json.dumps({"mode": "dark", "accent": "#e50914"})
	assert theming.shape(asked) == {"mode": "dark", "accent": "#e50914"}


@pytest.mark.parametrize("asked", ["", None, "not json", "[]", 7, [], "null"])
def test_nothing_is_nothing(asked):
	assert theming.shape(asked) == {}


def test_a_bad_field_does_not_take_the_good_ones_with_it():
	"""Field by field, so a typo costs the typo and not the theme."""
	kept = theming.shape(
		{"mode": "midnight", "accent": "#e50914", "ground": "rebeccapurple", "radius": "round"}
	)
	assert kept == {"accent": "#e50914"}


@pytest.mark.parametrize(
	"colour",
	[
		"red",
		"rgb(229, 9, 20)",
		"var(--surface-base)",
		"#e50914; --ink-gray-9: #e50914",
		"#e5091",
		"#e509144",
		"#ggghhh",
		"",
	],
)
def test_only_a_hex_is_a_colour(colour):
	"""Anything that could carry a second declaration is not a colour."""
	assert theming.shape({"accent": colour}) == {}


def test_short_hex_is_a_colour():
	assert theming.shape({"ground": "#ABC"}) == {"ground": "#abc"}


def test_a_theme_cannot_name_a_variable():
	"""The closed shape, stated as a test rather than as a comment.

	Not the security boundary — a theme reaches nothing but CSS on a page the
	reader already opened — but it is the design boundary, and it is the one
	that would quietly erode the first time a space wanted one more knob.
	"""
	kept = theming.shape(
		{
			"mode": "dark",
			"--surface-base": "#000",
			"variables": {"--ink-gray-9": "#fff"},
			"css": "body { display: none }",
		}
	)
	assert kept == {"mode": "dark"}


def _moved() -> set:
	"""Every variable `lib/theme.js` writes, however it writes it.

	Both forms, because it uses both: the tables are `'--token': amount` and the
	one-off is `out['--token'] = ...`. Reading only the first is a guard that
	stops seeing anything the day somebody adds a variable the other way, which
	is the same day it stops being a guard.
	"""
	source = THEME_JS.read_text()
	return set(re.findall(r"'(--[a-z0-9-]+)':", source)) | set(
		re.findall(r"\['(--[a-z0-9-]+)'\]\s*=", source)
	)


def test_the_browser_moves_no_neutral_ink():
	"""An accent may not repaint the scale every row hover in the product uses.

	`--surface-gray-2` is the row hover, `--ink-gray-*` is every word on the
	screen. A theme that moved either would be a theme that made the product
	unreadable in exchange for a brand colour.
	"""
	moved = _moved()
	assert moved, "theme.js names no variables — the mapping moved"
	forbidden = [one for one in moved if one.startswith("--ink-gray")]
	forbidden += [one for one in moved if re.fullmatch(r"--surface-gray-[1-7]", one)]
	assert not forbidden, f"a theme must not move the neutral scale: {sorted(forbidden)}"


def test_the_only_ink_a_theme_moves_is_the_one_on_its_own_accent():
	"""`--ink-base` is allowed, and it is allowed because of what it is.

	frappe-ui puts it on solid buttons and on nothing else, so it is the ink
	*on* a filled surface rather than text on a page — and a filled surface
	whose colour a space chose needs an ink that space did not have to choose.
	White on Caterpillar yellow is the failure this prevents.

	The list is spelled out rather than pattern-matched: an ink token is exactly
	the kind of thing that gets added to a table without anybody weighing what
	it paints, and the next one should have to argue for itself here.
	"""
	inks = {one for one in _moved() if one.startswith("--ink-")}
	assert inks == {"--ink-base", "--ink-blue-link", "--ink-blue-2", "--ink-blue-3"}, (
		f"theme.js moves an ink nobody wrote down: {sorted(inks)}"
	)


def test_the_hairlines_follow_the_ground():
	"""Borders come off the ground, and only the three that are hairlines.

	`--outline-gray-8` is the tab indicator and belongs to the accent; 1 to 3
	are the rules and edges, and they are the ones that read as heavy when a
	space declares a ground much darker than the one frappe-ui measured them
	against.
	"""
	source = THEME_JS.read_text()
	ground = source.split("GROUND_VARIABLES")[1].split("}")[0]
	outlines = source.split("OUTLINE_VARIABLES")[1].split("}")[0]
	assert "--surface-sidebar" in ground, "the ground stops at the navigation again"
	moved = set(re.findall(r"'(--outline-gray-\d)':", outlines))
	assert moved == {"--outline-gray-1", "--outline-gray-2", "--outline-gray-3"}


def test_a_bright_accent_takes_dark_ink_and_a_dark_one_takes_light():
	"""The rule itself, read off the source rather than run.

	A browser check lives in `e2e/theme.spec.js`; this one is here so that
	deleting the rule fails a suite that needs no bench.
	"""
	source = THEME_JS.read_text()
	assert "luminance(accent)" in source, "the accent no longer decides its own ink"
	assert "0.2126" in source, "luminance is not luminance any more"


def test_the_browser_writes_only_variables():
	"""Every property the expansion sets is a custom property.

	`setProperty` will happily take `display`, and the mapping is a literal that
	somebody will one day extend. A theme that could set a real CSS property is
	a manifest that can hide the toolbar.
	"""
	source = THEME_JS.read_text()
	for name in re.findall(r"'([^']+)':\s*[\d.]+,", source):
		assert name.startswith("--"), f"{name} is a CSS property, not a token"
