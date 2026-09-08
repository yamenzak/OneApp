"""Where a map gets its ground.

Every map surface in the product — the engine's map view type, and any space
that draws its own — needs the same two answers: what to paint under the
records, and who to credit for it. Neither is a workspace's choice. Which tile
store a bench points at is decided by whoever runs the bench, it is the same
for every workspace on the instance, and an air-gapped install has to be able
to change it in one place rather than in every screen that happens to draw a
map. So it is site config, read once, and handed to the app on the boot payload
beside the accent.

Three settings, in the order they win:

  * ``oneapp_map_style`` — a whole MapLibre style, as a URL. The full-control
    answer: a self-hosted vector style, a paid provider, an offline bundle.
    Given one, nothing else here applies.

  * ``oneapp_map_tiles`` — a raster tile template, ``{z}/{x}/{y}``. The common
    answer, because a raster source is a URL rather than a style document and
    because a tile that fails to load is one grey square rather than a map that
    never loads at all. A style URL that 404s takes the whole map with it.

  * ``oneapp_map_attribution`` — who to credit, when the default is not right.

With none of them set the default is CARTO's Positron basemap, which is OSM
data drawn quietly: grey ground, thin roads, low-contrast labels, so a route
line and a moving vehicle are the loudest things on the screen. That is the
point of choosing it over ``tile.openstreetmap.org``, whose own rendering is
built to show OSM's data rather than to sit under someone else's, and whose
tile usage policy asks applications not to use it as a basemap anyway.

The browser fetches tiles directly, so the tile host sees the reader's IP and
viewport. That is a disclosure, and it is why the default is named in the
subprocessor clause any space that draws a map contributes, why it is one
config key to move, and why a map still draws with no tile host at all: a flat
ground and the records on it. That is not a degraded mode to apologise for —
it is what a schematic looks like, and it means this works offline, in a test,
and on a bench nobody has pointed at a tile store.
"""

import frappe

# CARTO's Positron, over OpenStreetMap data. `{r}` is MapLibre's own retina
# placeholder — it resolves to "@2x" on a high-density screen and to nothing
# otherwise, which is the whole of retina support.
DEFAULT_TILES = "https://basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png"
DEFAULT_DARK = "https://basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png"
DEFAULT_ATTRIBUTION = "© OpenStreetMap contributors © CARTO"

#: Who the default sends a request to, for the subprocessor clauses. A space
#: that draws a map names these; see `onemobility/legal.py`.
DEFAULT_HOSTS = ("basemaps.cartocdn.com",)


def boot() -> dict:
	"""The basemap, for the boot payload. See `www/one.py`."""
	style = (frappe.conf.get("oneapp_map_style") or "").strip()
	tiles = (frappe.conf.get("oneapp_map_tiles") or "").strip()
	dark = (frappe.conf.get("oneapp_map_tiles_dark") or "").strip()

	# An explicit empty string is how an instance says "no third-party tiles":
	# `frappe.conf` cannot hold a false that is distinguishable from unset, so
	# the opt-out is its own key rather than an empty value for another.
	if frappe.conf.get("oneapp_map_plain"):
		return {"style": "", "tiles": "", "dark": "", "attribution": ""}

	return {
		"style": style,
		"tiles": tiles or DEFAULT_TILES,
		"dark": dark or (DEFAULT_DARK if not tiles else tiles),
		"attribution": (frappe.conf.get("oneapp_map_attribution") or "").strip()
		or DEFAULT_ATTRIBUTION,
	}


def hosts() -> tuple[str, ...]:
	"""The tile hosts this instance actually talks to, for a legal clause."""
	boot_value = boot()
	if not boot_value["tiles"] and not boot_value["style"]:
		return ()
	for value in (boot_value["style"], boot_value["tiles"]):
		if not value:
			continue
		if value.startswith(DEFAULT_TILES[:40]):
			return DEFAULT_HOSTS
	# A configured host is the operator's own business to disclose; naming it
	# here would put a deployment detail into a published agreement.
	return DEFAULT_HOSTS if boot_value["tiles"] == DEFAULT_TILES else ()
