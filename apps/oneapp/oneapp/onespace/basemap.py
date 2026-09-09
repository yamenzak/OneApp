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

With none of them set the default is OpenFreeMap's Positron, a vector style
over OSM data drawn quietly: grey ground, thin roads, low-contrast labels, so a
route line and a moving vehicle are the loudest things on the screen. That is
the point of choosing it over ``tile.openstreetmap.org``, whose own rendering is
built to show OSM's data rather than to sit under someone else's, and whose tile
usage policy asks applications not to use it as a basemap anyway.

**And below the instance, a workspace.** Which tile store to talk to is the
operator's decision; whether places are *named* and how much of the world is
drawn under the records are not — they are about the screens this customer
looks at all day, and a network diagram and a delivery round want different
answers. So `OneSpace Map Settings` is a tenant single holding three: a style
by name, whether to draw labels, and how much detail. It can only narrow what
the instance allows — it picks between the styles in `STYLES` or turns the
ground off entirely, and an instance that has named its own style outright
keeps it. Because the styles are vector, the last two apply without a reload:
`restyle` in `screen/basemap.js` walks the layers already on the map.

The browser fetches tiles directly, so the tile host sees the reader's IP and
viewport. That is a disclosure, and it is why the default is named in the
subprocessor clause any space that draws a map contributes, why it is one
config key to move, and why a map still draws with no tile host at all: a flat
ground and the records on it. That is not a degraded mode to apologise for —
it is what a schematic looks like, and it means this works offline, in a test,
and on a bench nobody has pointed at a tile store.
"""

import frappe
from frappe import _

#: The basemaps a workspace may choose between, as MapLibre style URLs.
#:
#: **Vector, and that is the whole point rather than a detail.** A raster tile
#: is a picture somebody else has already drawn: the only thing a reader can
#: change about it is what goes on top. A vector style is JSON the browser
#: executes, so which layers draw, whether places are named and how much of the
#: world is under the records are all things a workspace can decide at runtime
#: — see `frontend/src/modules/onespace/lib/screen/basemap.js`.
#:
#: OpenFreeMap, because it needs no key and is self-hostable. The default was
#: CARTO's raster Positron and it had quietly stopped being usable: their
#: keyless endpoint now returns every tile stamped "API KEY REQUIRED", which
#: nothing in this product could have noticed — a watermark is a valid PNG.
#:
#: **Canvas is ours**, and is the only one of the four that could be. The other
#: three are documents somebody else wrote and serves, so the most a workspace
#: can do to them is turn layers off. Canvas is a file in this repository —
#: `scripts/gen_basemap.py` writes it — so its palette is a decision we make,
#: and it is the one that can eventually follow the workspace's own accent. Its
#: tiles still come from OpenFreeMap, so it adds nobody to disclose.
STYLES = {
	"Canvas": "/assets/oneapp/basemaps/canvas.json",
	"Positron": "https://tiles.openfreemap.org/styles/positron",
	"Bright": "https://tiles.openfreemap.org/styles/bright",
	"Liberty": "https://tiles.openfreemap.org/styles/liberty",
}

#: Quiet grey, thin roads, low-contrast labels — so a route line and a moving
#: vehicle are the loudest things on the screen.
DEFAULT_STYLE = STYLES["Positron"]

#: Who to credit when nothing else does — which is only the raster path.
#:
#: **A style document credits itself.** Every style here names a TileJSON, and
#: that document carries the full linked attribution the licence actually wants:
#: OpenFreeMap, OpenMapTiles, and OpenStreetMap, each as a link. MapLibre reads
#: it and draws it, so sending our own alongside it stacked two credits into one
#: line — "© OpenStreetMap contributors © OpenFreeMap | OpenFreeMap ©
#: OpenMapTiles Data from OpenStreetMap" — saying the same thing twice, once
#: less completely.
#:
#: A raster template is a URL and nothing else: there is no document to read a
#: credit out of, so one is needed. This is the minimum true of any OSM-derived
#: store; an operator pointing at their own should name themselves, which is
#: what ``oneapp_map_attribution`` is for.
DEFAULT_ATTRIBUTION = "© OpenStreetMap contributors"

#: What a workspace gets before anybody opens the picker. Quiet rather than
#: Full: every screen that draws a map draws *records* on it, and buildings and
#: points of interest are competing with them for the same pixels.
DEFAULTS = {"pick": "Follow the instance", "labels": True, "detail": "Quiet"}

#: Who the default sends a request to, for the subprocessor clauses. A space
#: that draws a map names these; see `onemobility/legal.py`.
DEFAULT_HOSTS = ("tiles.openfreemap.org",)


def chosen() -> dict:
	"""What this workspace has decided about its map.

	`pick` is the *name* of a style and `style` on the boot payload is the URL
	it resolves to — two different things, and calling them both "style" put a
	word where a URL belonged and drew nothing.

	Read defensively. This is on the boot payload, which the control site
	renders too, and `OneSpace Map Settings` is a tenant doctype — so on the
	control plane the table is simply not there, and a map still has to draw.
	"""
	found = dict(DEFAULTS)
	if not frappe.db.exists("DocType", "OneSpace Map Settings"):
		return found
	row = frappe.get_cached_doc("OneSpace Map Settings")
	found["pick"] = (row.get("map_style") or DEFAULTS["pick"]).strip()
	found["labels"] = bool(row.get("map_labels"))
	found["detail"] = (row.get("map_detail") or DEFAULTS["detail"]).strip()
	return found


def boot() -> dict:
	"""The basemap, for the boot payload. See `www/one.py`."""
	style = (frappe.conf.get("oneapp_map_style") or "").strip()
	tiles = (frappe.conf.get("oneapp_map_tiles") or "").strip()
	dark = (frappe.conf.get("oneapp_map_tiles_dark") or "").strip()
	prefer = chosen()

	# The instance's own answer, before this workspace had a say. Sent alongside
	# the resolved one because the picker resolves the *next* style itself: this
	# payload was written when the page loaded, so a reader going back to "Follow
	# the instance" would otherwise be handed whatever they had picked before.
	instance = style or (DEFAULT_STYLE if not tiles else "")

	# An explicit empty string is how an instance says "no third-party tiles":
	# `frappe.conf` cannot hold a false that is distinguishable from unset, so
	# the opt-out is its own key rather than an empty value for another.
	#
	# A workspace that picks Plain says the same thing for itself, which is the
	# air-gapped instance's setting made available to one customer on a shared
	# one. Either way nothing is fetched.
	if frappe.conf.get("oneapp_map_plain") or prefer["pick"] == "Plain":
		return {"style": "", "tiles": "", "dark": "", "attribution": "", **prefer,
		        "styles": dict(STYLES), "instance": instance, "plain": True}

	# The workspace's own choice wins over the instance's default and loses to
	# an instance that has named a style outright: an operator who has pointed
	# a bench at their own tile store has done so for a reason, and a customer
	# picking "Bright" should not send them back off it.
	picked = STYLES.get(prefer["pick"], "")
	# An operator's own credit always wins and is always drawn — they may be
	# serving tiles nobody else knows the provenance of. Otherwise: nothing on
	# the style path, because the style says it better than we would.
	credit = (frappe.conf.get("oneapp_map_attribution") or "").strip()
	resolved = style or picked or (DEFAULT_STYLE if not tiles else "")
	return {
		"style": resolved,
		"tiles": tiles,
		"dark": dark or tiles,
		"attribution": credit or ("" if resolved else DEFAULT_ATTRIBUTION),
		# By name *and* URL, for the same reason `instance` is here.
		"styles": dict(STYLES),
		"instance": instance,
		"plain": False,
		**prefer,
	}


@frappe.whitelist(methods=["POST"])
def set_basemap(style: str = "", labels=None, detail: str = "") -> dict:
	"""Change how this workspace's maps are drawn, for everybody on it.

	Guarded on the workspace owner rather than on a doctype permission: this is
	a presentation decision about every screen in the product, which is the same
	thing branding is, and it is reached from a map rather than from the desk.
	"""
	# Imported here rather than at the top: `workspace` reaches into Frappe's
	# timezone tables at import time, and this module is read by tests that
	# stand up neither.
	from oneapp.onespace.workspace import OWNER_ROLE, SUPPORT_ROLE

	if not set(frappe.get_roles()) & {OWNER_ROLE, SUPPORT_ROLE}:
		frappe.throw(_("Only a workspace admin can change how the map is drawn."),
		             frappe.PermissionError)

	row = frappe.get_doc("OneSpace Map Settings")
	if style:
		if style not in STYLES and style not in ("Follow the instance", "Plain"):
			frappe.throw(_("There is no such basemap."))
		row.map_style = style
	if labels is not None:
		row.map_labels = 1 if frappe.parse_json(labels) else 0
	if detail:
		if detail not in ("Full", "Quiet", "Minimal"):
			frappe.throw(_("There is no such level of detail."))
		row.map_detail = detail
	row.save(ignore_permissions=True)
	frappe.clear_document_cache("OneSpace Map Settings")
	return chosen()


def hosts() -> tuple[str, ...]:
	"""The tile hosts this instance actually talks to, for a legal clause.

	Read off the *instance's* configuration rather than off `boot()`, because a
	published agreement cannot depend on what one workspace picked this morning
	— every curated style is the same host, so a workspace switching between
	them changes nothing a clause has to say.
	"""
	if frappe.conf.get("oneapp_map_plain"):
		return ()
	# A configured host is the operator's own business to disclose; naming it
	# here would put a deployment detail into a published agreement.
	if (frappe.conf.get("oneapp_map_style") or "").strip():
		return ()
	if (frappe.conf.get("oneapp_map_tiles") or "").strip():
		return ()
	return DEFAULT_HOSTS
