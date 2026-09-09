"""Which silhouette the map draws for a line.

The browser draws its markers on a canvas rather than fetching a sprite sheet —
`frontend/src/modules/onemobility/lib/markers.js` says why — and it has seven
outlines: bus, tram, metro, rail, ferry, cable and a plain capsule. Which line
gets which is a *customer's* decision, not ours, and this is where it is kept.

**A mode and a shape are two different things and the mistake is to conflate
them.** A mode is what a network runs — it comes off the feed, it is what
Insights groups by, and renaming it to change a picture would corrupt every
number. A shape is what the map draws. They start identical, which is why a
workspace that never opens this screen sees exactly what it saw before this
module existed; they come apart the first time a customer whose "Rail" is
really a light rail wants the tram outline over their whole S-Bahn.

Two levels, because both questions are real:

* **per mode**, in `Transit Marker Style` — one row, applying to a whole class
  of service. This is the one people use.
* **per line**, in `Transit Line.marker_shape` — a heritage tram on a bus
  network, a rail replacement that is really a coach. Empty follows the mode,
  which is what nearly every line is.

Resolved on the server and sent already resolved, so the browser never carries
the mapping table and never has to decide anything: `shape()` hands it a line
that already knows what it looks like.
"""

import frappe
from frappe import _

#: The outlines the browser can actually draw, lower-cased as it names them.
#:
#: Kept deliberately here rather than derived from the doctype's Select: this
#: is the contract with `markers.js`, and a Select option added without a
#: drawing behind it should fail a test rather than silently draw a capsule.
SHAPES = ("bus", "tram", "metro", "rail", "ferry", "cable", "other")

#: What a mode is drawn as when nobody has said otherwise. Identity, so the
#: doctype is an override and never a thing you must fill in first.
FALLBACK = "other"


def normalise(word: str) -> str:
	"""One of `SHAPES`, or the capsule. Never an empty string, never a guess."""
	key = str(word or "").strip().lower()
	return key if key in SHAPES else FALLBACK


def by_mode() -> dict:
	"""The customer's mode-to-shape mapping, as `{mode: shape}`.

	Read whole. There are seven modes at most, so this is one small query, and
	the alternative — a lookup per line — is a hundred queries to draw a map.
	"""
	if not frappe.db.table_exists("Transit Marker Style"):
		return {}
	rows = frappe.get_all(
		"Transit Marker Style",
		fields=["mode", "shape"],
		limit_page_length=0,
		ignore_permissions=True,
	)
	return {str(row["mode"] or "").strip().lower(): normalise(row["shape"]) for row in rows}


def resolve(lines: list) -> None:
	"""Give every line in `lines` a `marker`, in place.

	Takes the whole list rather than one line at a time so the mapping is read
	once. `lines` are the dicts `shape()` has already built, so this is the last
	thing done to them and nothing downstream has to know a style exists.
	"""
	mapping = by_mode()
	for line in lines:
		own = str(line.get("marker_shape") or "").strip().lower()
		mode = str(line.get("mode") or "").strip().lower()
		# The line's own answer first, then its mode's, then the mode itself —
		# which is the identity mapping, and the reason an untouched workspace
		# looks exactly as it did.
		line["marker"] = normalise(own or mapping.get(mode) or mode)


@frappe.whitelist(methods=["GET"])
def marker_styles() -> dict:
	"""Every mode, and what it is currently drawn as.

	Every mode rather than every stored row: the screen draws a picker with one
	control per mode, and a mode nobody has overridden still needs a row in it
	showing the default. Assembling that in the browser would mean the browser
	holding the list of modes, which is the doctype's to hold.
	"""
	if not frappe.has_permission("Transit Line", "read"):
		frappe.throw(_("You cannot read this."), frappe.PermissionError)

	stored = by_mode()
	modes = frappe.get_meta("Transit Marker Style").get_field("mode").options or ""
	return {
		"styles": [
			{
				"mode": mode,
				"key": mode.lower(),
				"shape": stored.get(mode.lower(), normalise(mode)),
				"custom": mode.lower() in stored,
			}
			for mode in [one.strip() for one in modes.split("\n") if one.strip()]
		],
		"shapes": list(SHAPES),
		"may_write": bool(frappe.has_permission("Transit Marker Style", "write")),
	}


@frappe.whitelist(methods=["POST"])
def set_marker_style(mode: str, shape: str) -> dict:
	"""Draw this mode as that shape, from now on and for everybody.

	A workspace decision rather than a per-person one, which is why it is a
	doctype and not a saved view: a control room where two screens draw the
	same tram differently is a control room having an argument about which
	screen is right.
	"""
	if not frappe.has_permission("Transit Marker Style", "write"):
		frappe.throw(_("You cannot change how the map is drawn."), frappe.PermissionError)

	wanted = normalise(shape)
	name = str(mode or "").strip()
	if not name:
		frappe.throw(_("Which mode?"))

	if frappe.db.exists("Transit Marker Style", name):
		row = frappe.get_doc("Transit Marker Style", name)
		row.shape = wanted.title()
		row.save()
	else:
		frappe.get_doc(
			{"doctype": "Transit Marker Style", "mode": name, "shape": wanted.title()}
		).insert()

	return {"mode": name, "shape": wanted}
