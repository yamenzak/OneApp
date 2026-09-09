"""The basemap we own, and the three things that could silently rot it.

`scripts/gen_basemap.py` turns a permissively-licensed style into ours. That
transformation is the kind that fails quietly: a style that still asks MapTiler
for a font renders with no labels rather than with an error, and a layer that
kept Positron's own greys is a grey among greys nobody spots.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
STYLE = os.path.join(
	ROOT, "apps", "oneapp", "oneapp", "public", "basemaps", "canvas.json"
)


@pytest.fixture(scope="module")
def gen():
	sys.path.insert(0, SCRIPTS)
	import gen_basemap

	return gen_basemap


@pytest.fixture(scope="module")
def style():
	with open(STYLE, encoding="utf-8") as handle:
		return json.load(handle)


def test_the_file_on_disk_is_what_the_generator_writes(gen):
	"""The rule the whole repository runs on: edit the generator, not the file.

	Run as a subprocess rather than by calling `build()`, so what is compared is
	the bytes — indentation, key order and the trailing newline included, since
	those are what a diff on the next run would show."""
	before = open(STYLE, encoding="utf-8").read()
	subprocess.run([sys.executable, os.path.join(SCRIPTS, "gen_basemap.py")],
	               check=True, capture_output=True)
	assert open(STYLE, encoding="utf-8").read() == before, (
		"canvas.json is not what scripts/gen_basemap.py produces — run it"
	)


def test_nothing_reaches_for_a_key_we_do_not_have(style):
	"""Upstream fetches tiles and glyphs from `api.maptiler.com?key={key}`.

	Leaving either behind is invisible in review and near-invisible on screen:
	the glyph request 403s and the map draws every road and no label at all."""
	raw = json.dumps(style)
	for trace in ("api.maptiler.com", "{key}", "Metropolis"):
		assert trace not in raw, f"{trace} survived the transformation"


def test_the_ground_and_the_letters_come_from_one_host(style, gen):
	assert style["sources"] == {"openmaptiles": {"type": "vector", "url": gen.TILES}}
	assert style["glyphs"] == gen.GLYPHS


def test_it_asks_for_no_images_at_all(style):
	"""The sprite went with the city dots, and the two have to go together: a
	style with an `icon-image` and no sprite draws a warning per feature."""
	assert "sprite" not in style
	for layer in style["layers"]:
		for where in ("layout", "paint"):
			assert not [
				key for key in (layer.get(where) or {}) if key.startswith("icon-")
			], f"{layer['id']} still has icon properties"


def test_every_colour_is_one_we_chose(style, gen):
	"""Which is the whole point of owning the file. A layer that kept upstream's
	palette is a grey among greys, and the only way to notice is this."""
	ours = set(gen.INK.values())
	for layer in style["layers"]:
		for key, value in (layer.get("paint") or {}).items():
			if not key.endswith("-color") or not isinstance(value, str):
				continue
			assert value in ours, f"{layer['id']}.{key} is {value}, which is not ours"


def test_the_credit_the_licence_requires_is_still_reachable(style, gen):
	"""OpenMapTiles' licence asks for a visible credit to them and to
	OpenStreetMap. We add none ourselves — `onespace/basemap.py` deliberately
	sends nothing on the style path — so it has to come from the TileJSON this
	source names, and the day that stops being an OpenFreeMap URL is the day the
	credit disappears with it."""
	assert style["sources"]["openmaptiles"]["url"] == gen.TILES
	assert gen.TILES.startswith("https://tiles.openfreemap.org/")


def test_the_licence_it_was_derived_from_travels_with_it(style):
	"""JSON has no comments, so the notice lives in `metadata` — which is the
	same obligation as the one at the top of any file taken from Frappe."""
	note = style.get("metadata", {}).get("oneapp:derived-from", "")
	assert "positron-gl-style" in note and "BSD 3-Clause" in note
	assert os.path.exists(os.path.join(SCRIPTS, "basemaps", "POSITRON-LICENSE.md"))
