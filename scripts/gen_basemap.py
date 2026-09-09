#!/usr/bin/env python3
"""Our own basemap style, out of a permissive one and a palette we chose.

The three styles in the picker are somebody else's: OpenFreeMap serves
Positron, Bright and Liberty, and the only thing a workspace can do to them is
turn layers off. That is the whole of what `restyle` can offer, because a style
we do not own is a style we cannot recolour.

This writes one we do own. It reads `scripts/basemaps/positron.upstream.json`
— openmaptiles/positron-gl-style, BSD-3, licence beside it — and applies four
kinds of change:

  * **Where it fetches from.** Upstream points at `api.maptiler.com` with a
    `{key}` placeholder, for both tiles and glyphs. Both become OpenFreeMap,
    which needs no key. The tile source is their `/planet` TileJSON, which is
    also how the attribution keeps working: it carries "OpenFreeMap ©
    OpenMapTiles Data from OpenStreetMap", MapLibre draws it, and that is
    exactly the credit the OpenMapTiles licence requires be visible.

  * **The fonts.** Upstream asks for Metropolis, which MapTiler serves and
    OpenFreeMap does not. Noto Sans in its place, which OpenFreeMap has in
    regular and italic.

  * **How a label is spelled.** Upstream writes one as
    `concat(get("name:latin"), get("name:nonlatin"))`, which is safe on
    MapTiler's tiles because that second field is always there. On OpenFreeMap's
    it usually is not, and `concat` of a null throws — so the expression fails
    per feature and the label is simply absent. The map then draws every road,
    every park and every coastline and names nothing, with one console line to
    explain it. So each is rewritten to ask whether there *is* a non-latin name
    first, and to fall back to plain `name` when there is no `name:latin`
    either. This is the same shape OpenFreeMap's own styles use, and it was
    found the way it deserved to be: by rendering the thing and noticing the
    city was missing.

  * **What counts as a big city.** Four label layers sort places by a `rank`
    field, with `rank > 3` and `rank <= 3` on either side of the line.
    OpenFreeMap's tiles frequently do not carry it, and a numeric comparison
    against a missing field does not evaluate false in MapLibre — it throws, and
    the whole *filter* fails, so the feature is dropped. Which is why the first
    render of this came back a perfectly good map of Berlin with the word Berlin
    nowhere on it. Every one of those comparisons gets a default, so an unranked
    place is an ordinary one rather than an absent one.

  * **The furniture.** The dots beside city labels go, and with them the sprite
    — four layers used it, it was the style's only external image, and a map
    that exists to be drawn on does not need a marker of its own competing with
    the ones we put there.

  * **The palette**, which is the point and is `INK` below. Positron is a good
    quiet basemap and is still a *map*: mid-grey water, visible buildings,
    roads with real contrast. This is lighter and cooler across the board — the
    water two steps up, the buildings almost gone, the roads white on a hairline
    — so that a route line and a vehicle are the only saturated things on the
    screen. A dataviz ground rather than a road map.

Run it after changing `INK`, and `tests/test_generated_basemap.py` fails if the
file on disk is not what running it produces:

    python3 scripts/gen_basemap.py
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPSTREAM = os.path.join(ROOT, "scripts", "basemaps", "positron.upstream.json")
OUT = os.path.join(
    ROOT, "apps", "oneapp", "oneapp", "public", "basemaps", "canvas.json"
)

#: Where the tiles and the letters come from. Keyless, and the same host the
#: curated styles already use, so this adds no third party to disclose.
TILES = "https://tiles.openfreemap.org/planet"
GLYPHS = "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf"

#: Metropolis is MapTiler's and they serve it. These two are OpenFreeMap's.
UPRIGHT = ["Noto Sans Regular"]
ITALIC = ["Noto Sans Italic"]

#: The palette, and the only place a colour is decided.
#:
#: Read it as a picture: a near-white ground, water and greenery a step off it
#: and towards cool, roads drawn as white channels between hairlines rather than
#: as grey ribbons, and labels the only thing with any weight. Everything is
#: within a few percent of the ground, which is what makes a red route line and
#: an amber vehicle read as the subject rather than as two more colours.
INK = {
	"ground": "#f7f7f8",
	"water": "#dee7ef",
	"waterway": "#cfdbe5",
	"green": "#eaefe9",
	"wood": "#e5ebe5",
	"residential": "#f1f1f4",
	"ice": "#fbfbfc",
	"building": "#ebebee",
	"building_edge": "#e0e0e5",
	# One casing colour everywhere, so a motorway and a lane differ by width
	# rather than by weight — which is what stops a road network from reading as
	# a second dataset.
	"casing": "#dcdce2",
	"road": "#ffffff",
	"road_minor": "#ebebef",
	"road_faint": "#e7e7ed",
	"rail": "#dfdfe5",
	"rail_dash": "#fafafc",
	"boundary": "#d6d1d9",
	"label": "#767d88",
	"label_quiet": "#8d95a0",
	"label_water": "#93a3b0",
	"halo": "#ffffff",
}

#: Which colour each layer's each paint property takes. A table rather than a
#: transform of the upstream values: a hue rotation would have to be reasoned
#: about backwards from a screenshot every time somebody wanted to move one
#: thing, and this way the design is legible and each entry is a decision.
#:
#: A layer absent from here keeps upstream's colour, and none currently does —
#: `test_generated_basemap` fails if one appears, because a new layer arriving
#: with Positron's own greys in the middle of this is exactly the drift the
#: table exists to prevent.
PAINT = {
	"background": {"background-color": "ground"},
	"park": {"fill-color": "green"},
	"water": {"fill-color": "water"},
	"landcover_ice_shelf": {"fill-color": "ice"},
	"landcover_glacier": {"fill-color": "ice"},
	"landuse_residential": {"fill-color": "residential"},
	"landcover_wood": {"fill-color": "wood"},
	"waterway": {"line-color": "waterway"},
	"water_name": {"text-color": "label_water", "text-halo-color": "halo"},
	"building": {"fill-color": "building", "fill-outline-color": "building_edge"},
	"tunnel_motorway_casing": {"line-color": "casing"},
	"tunnel_motorway_inner": {"line-color": "road_minor"},
	"aeroway-taxiway": {"line-color": "casing"},
	"aeroway-runway-casing": {"line-color": "casing"},
	"aeroway-area": {"fill-color": "road"},
	"aeroway-runway": {"line-color": "road"},
	"road_area_pier": {"fill-color": "ground"},
	"road_pier": {"line-color": "ground"},
	"highway_path": {"line-color": "road_faint"},
	"highway_minor": {"line-color": "road_minor"},
	"highway_major_casing": {"line-color": "casing"},
	"highway_major_inner": {"line-color": "road"},
	"highway_major_subtle": {"line-color": "road_faint"},
	"highway_motorway_casing": {"line-color": "casing"},
	"highway_motorway_inner": {"line-color": "road"},
	"highway_motorway_subtle": {"line-color": "road_faint"},
	"railway_transit": {"line-color": "rail"},
	"railway_transit_dashline": {"line-color": "rail_dash"},
	"railway_service": {"line-color": "rail"},
	"railway_service_dashline": {"line-color": "rail_dash"},
	"railway": {"line-color": "rail"},
	"railway_dashline": {"line-color": "rail_dash"},
	"highway_motorway_bridge_casing": {"line-color": "casing"},
	"highway_motorway_bridge_inner": {"line-color": "road"},
	"highway_name_other": {"text-color": "label_quiet", "text-halo-color": "halo"},
	"highway_name_motorway": {"text-color": "label_quiet", "text-halo-color": "halo"},
	"boundary_state": {"line-color": "boundary"},
	"boundary_country_z0-4": {"line-color": "boundary"},
	"boundary_country_z5-": {"line-color": "boundary"},
	"place_other": {"text-color": "label_quiet", "text-halo-color": "halo"},
	"place_suburb": {"text-color": "label_quiet", "text-halo-color": "halo"},
	"place_village": {"text-color": "label", "text-halo-color": "halo"},
	"place_town": {"text-color": "label", "text-halo-color": "halo"},
	"place_city": {"text-color": "label", "text-halo-color": "halo"},
	"place_capital": {"text-color": "label", "text-halo-color": "halo"},
	"place_city_large": {"text-color": "label", "text-halo-color": "halo"},
	"place_state": {"text-color": "label_quiet", "text-halo-color": "halo"},
	"place_country_other": {"text-color": "label_quiet", "text-halo-color": "halo"},
	"place_country_minor": {"text-color": "label", "text-halo-color": "halo"},
	"place_country_major": {"text-color": "label", "text-halo-color": "halo"},
}

#: Paint keys that are dropped rather than recoloured.
#:
#: Upstream fades some layers in and out with a zoom ramp on opacity, which is
#: right for a style whose colours have contrast to lose. These have almost
#: none, so a half-opacity building is a building nobody can see at all — and
#: the ramp then costs a paint expression per tile for nothing. The opacities
#: that survive are the ones doing real work: landcover appearing with zoom.
DROP_PAINT = {
	"highway_path": ["line-opacity"],
	"highway_minor": ["line-opacity"],
	"tunnel_motorway_casing": ["line-opacity"],
	"aeroway-taxiway": ["line-opacity"],
	"aeroway-runway-casing": ["line-opacity"],
	"aeroway-runway": ["line-opacity"],
	"highway_motorway_casing": ["line-opacity"],
	"highway_motorway_bridge_casing": ["line-opacity"],
	"boundary_state": ["line-opacity"],
	"boundary_country_z0-4": ["line-opacity"],
	"boundary_country_z5-": ["line-opacity"],
	"landuse_residential": ["fill-opacity"],
}

STAMP = "Generated by scripts/gen_basemap.py. Edit that, not this file."


def fonts(value):
	"""Metropolis to Noto, keeping upstream's choice of upright or italic."""
	return ITALIC if any("Italic" in one for one in value) else UPRIGHT


#: A latin name, or the plain one, or nothing — never a failed concat.
LATIN = ["coalesce", ["get", "name:latin"], ["get", "name"]]

#: What a place with no `rank` is treated as. Four, because the line the layers
#: draw is at three: an unranked place should get the ordinary treatment, not
#: the one reserved for somewhere that has declared itself a capital.
UNRANKED = 4


def ranking(node):
	"""Give every `["get", "rank"]` inside a filter a default.

	Walked rather than pattern-matched on the four filters that have one today,
	because the next upstream revision that adds a fifth would otherwise
	reintroduce exactly this bug, and its symptom is a missing label rather than
	an error anybody would see.
	"""
	if isinstance(node, list):
		if node == ["get", "rank"]:
			return ["coalesce", ["get", "rank"], UNRANKED]
		return [ranking(one) for one in node]
	return node


def naming(field):
	"""Rewrite one `text-field` so a missing `name:nonlatin` is not fatal.

	Upstream's two shapes are a bare `to-string(get("name:latin"))` and a
	`concat` of the latin and non-latin names separated by a space or a
	newline. Only the separator is worth keeping from the second: everything
	else about it assumes a field that OpenFreeMap's tiles carry only for the
	places that actually have one.
	"""
	if not isinstance(field, list):
		return field
	if field[0] == "to-string":
		return list(LATIN)
	if field[0] != "concat":
		return field
	between = next((one for one in field[1:] if isinstance(one, str)), " ")
	return [
		"case",
		["has", "name:nonlatin"],
		["concat", ["get", "name:latin"], between, ["get", "name:nonlatin"]],
		list(LATIN),
	]


def build() -> dict:
	with open(UPSTREAM, encoding="utf-8") as handle:
		style = json.load(handle)

	style["name"] = "Canvas"
	style["metadata"] = {
		"oneapp:generated": STAMP,
		"oneapp:derived-from": (
			"openmaptiles/positron-gl-style, BSD 3-Clause — see "
			"scripts/basemaps/POSITRON-LICENSE.md. Copyright (c) 2024 "
			"MapTiler.com & OpenMapTiles contributors, (c) 2015 CartoDB Inc., "
			"derived from CartoDB Basemaps designed by Stamen and Paul Norman, "
			"CC-BY 3.0."
		),
	}
	style["sources"] = {"openmaptiles": {"type": "vector", "url": TILES}}
	style["glyphs"] = GLYPHS
	# Nothing left uses an image, and a sprite URL that is never fetched is a
	# host in the network panel nobody can account for.
	style.pop("sprite", None)

	seen = set()
	for layer in style["layers"]:
		name = layer["id"]
		seen.add(name)

		if "filter" in layer:
			layer["filter"] = ranking(layer["filter"])

		layout = layer.get("layout") or {}
		if layout.get("text-font"):
			layout["text-font"] = fonts(layout["text-font"])
		if "text-field" in layout:
			layout["text-field"] = naming(layout["text-field"])
		for key in [one for one in layout if one.startswith("icon-")]:
			del layout[key]

		paint = layer.get("paint") or {}
		for key in DROP_PAINT.get(name, []):
			paint.pop(key, None)
		for key in [one for one in paint if one.startswith("icon-")]:
			del paint[key]
		for key, ink in PAINT.get(name, {}).items():
			if key in paint:
				paint[key] = INK[ink]

	missing = sorted(seen - set(PAINT))
	if missing:
		raise SystemExit(
			"these layers have no entry in PAINT, so they would keep Positron's "
			"own greys: " + ", ".join(missing)
		)
	unknown = sorted(set(PAINT) - seen)
	if unknown:
		raise SystemExit("PAINT names layers the upstream style does not have: "
		                 + ", ".join(unknown))
	return style


def main():
	style = build()
	os.makedirs(os.path.dirname(OUT), exist_ok=True)
	with open(OUT, "w", encoding="utf-8") as handle:
		json.dump(style, handle, indent=1, ensure_ascii=False)
		handle.write("\n")
	print(f"wrote {os.path.relpath(OUT, ROOT)} — {len(style['layers'])} layers")


if __name__ == "__main__":
	main()
