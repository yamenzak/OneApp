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

**The emoji is the third thing here and it is not a marker.** A glyph is the
fastest identifier a person has — 🚇 beside U6 is read before the U or the 6 —
but it cannot be the thing that moves on the map, for three reasons that were
settled by rendering them rather than arguing: an emoji is a fixed-colour
bitmap, so it cannot carry occupancy the way a drawn silhouette can; it is a
front or side elevation, so the symbol layer rotating it to a bearing lays the
bus on its side; and at the sixteen pixels a marker actually occupies it is
mush. So it goes everywhere the thing is *named* — lists, records, the facet
bar, a hover card, the key — and nowhere the thing is drawn.
"""

import frappe
from frappe import _

#: The outlines the browser can actually draw, named after their own files.
#:
#: Kept deliberately here rather than derived from the doctype's Select: this is
#: the contract with `frontend/src/modules/onemobility/art/`, and a Select
#: option added without a drawing behind it should fail a test rather than
#: silently draw a capsule.
SHAPES = (
	"metro",
	"tram",
	"tram-old",
	"light-rail",
	"train",
	"high-speed",
	"monorail",
	"locomotive",
	"funicular",
	"bus",
	"bus-articulated",
	"trolleybus",
	"minibus",
	"coach",
	"shuttle",
	"taxi",
	"car",
	"truck",
	"lorry",
	"ambulance",
	"fire",
	"police",
	"ferry",
	"ship",
	"boat",
	"sailing",
	"cable-car",
	"gondola",
	"rickshaw",
	"motorcycle",
	"scooter",
	"bicycle",
	"wheelchair",
)

#: The drawing for anything we cannot place: a plain van, which is
#: unmistakably a vehicle and unmistakably not a claim about which kind.
FALLBACK = "minibus"

#: What each mode is drawn as when nobody has said otherwise.
#:
#: Nearly identity, and the three that are not are the whole reason this exists:
#: a mode is a word off a feed and a shape is a file on disk, and "Rail",
#: "Cable" and "Other" are not the names of drawings. Mapping them here rather
#: than hoping `normalise` guesses is the difference between a sensible default
#: and a van standing in for every train on the network.
BY_MODE = {
	"bus": "bus",
	"tram": "tram",
	"metro": "metro",
	"rail": "train",
	"ferry": "ferry",
	"cable": "cable-car",
	"other": "minibus",
}

#: At most this many code points in an emoji.
#:
#: One emoji is often several — a flag is two, a skin tone adds one, a family
#: joined by zero-width joiners is seven — so a bound of one or two would reject
#: emoji people actually use. The same number, for the same reason, as
#: `onespace/spaceview/saved.py`.
MAX_EMOJI = 8

#: What each shape wears when nobody has chosen. Not a decision about the
#: customer's network — it is what a person would draw if asked, and it is
#: overridable per mode and per line, so it costs a workspace nothing to
#: disagree with. One per drawing, so the glyph and the silhouette always
#: mean the same vehicle.
DEFAULT_EMOJI = {
	"metro": "🚇",
	"tram": "🚊",
	"tram-old": "🚋",
	"light-rail": "🚈",
	"train": "🚆",
	"high-speed": "🚄",
	"monorail": "🚝",
	"locomotive": "🚂",
	"funicular": "🚞",
	"bus": "🚌",
	"bus-articulated": "🚍",
	"trolleybus": "🚎",
	"minibus": "🚐",
	"coach": "🛻",
	"shuttle": "🚖",
	"taxi": "🚕",
	"car": "🚗",
	"truck": "🚚",
	"lorry": "🚛",
	"ambulance": "🚑",
	"fire": "🚒",
	"police": "🚓",
	"ferry": "⛴️",
	"ship": "🚢",
	"boat": "🚤",
	"sailing": "⛵",
	"cable-car": "🚡",
	"gondola": "🚠",
	"rickshaw": "🛺",
	"motorcycle": "🏍️",
	"scooter": "🛵",
	"bicycle": "🚲",
	"wheelchair": "🦽",
}


def normalise(word: str) -> str:
	"""One of `SHAPES`. Never an empty string, never a name with no drawing.

	Takes a shape's own name or a mode's, because both reach it: the doctype
	stores shapes and the fallback ladder ends at a line's mode.
	"""
	key = str(word or "").strip().lower()
	if key in SHAPES:
		return key
	return BY_MODE.get(key, FALLBACK)


def emoji(value: str) -> str:
	"""A glyph, or nothing. Never markup, never a word, never a sentence.

	frappe-ui's own definition, asked before the value is stored rather than
	after: anything with an ASCII letter, digit or space in it is not an emoji,
	and `Icon` renders it as nothing at all. Same rule as the view icon in
	`onespace/spaceview/saved.py`, minus the lucide half — a transit line wears
	a glyph or wears nothing, and a class name reaching the DOM from a feed is
	not a door worth leaving open.
	"""
	glyph = str(value or "").strip()
	if not glyph or len(glyph) > MAX_EMOJI:
		return ""
	if any(char.isascii() and char.isalnum() for char in glyph):
		return ""
	if any(char.isspace() for char in glyph):
		return ""
	return glyph


def by_mode() -> dict:
	"""The customer's mode-to-shape mapping, as `{mode: shape}`.

	Read whole. There are seven modes at most, so this is one small query, and
	the alternative — a lookup per line — is a hundred queries to draw a map.
	"""
	if not frappe.db.table_exists("Transit Marker Style"):
		return {}
	rows = frappe.get_all(
		"Transit Marker Style",
		fields=["mode", "shape", "emoji"],
		limit_page_length=0,
		ignore_permissions=True,
	)
	return {
		str(row["mode"] or "").strip().lower(): {
			"shape": normalise(row["shape"]),
			"emoji": emoji(row.get("emoji")),
		}
		for row in rows
	}


def resolve(lines: list) -> None:
	"""Give every line in `lines` a `marker` and an `emoji`, in place.

	Takes the whole list rather than one line at a time so the mapping is read
	once. `lines` are the dicts `shape()` has already built, so this is the last
	thing done to them and nothing downstream has to know a style exists.
	"""
	mapping = by_mode()
	for line in lines:
		own = str(line.get("marker_shape") or "").strip().lower()
		mode = str(line.get("mode") or "").strip().lower()
		style = mapping.get(mode) or {}
		# The line's own answer first, then its mode's, then the mode itself —
		# which is the identity mapping, and the reason an untouched workspace
		# looks exactly as it did.
		line["marker"] = normalise(own or style.get("shape") or mode)
		# Same ladder for the glyph, with a default at the bottom rather than
		# nothing: a network nobody has decorated should still read at a glance.
		# `emoji_own` says the line chose for itself, so a later change to its
		# mode's glyph leaves it alone — the same thing `marker_shape` does for
		# the silhouette, and the browser needs to know which it is holding.
		own_glyph = emoji(line.get("emoji"))
		line["emoji_own"] = bool(own_glyph)
		line["emoji"] = own_glyph or style.get("emoji") or DEFAULT_EMOJI.get(line["marker"], "")


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
				"shape": (stored.get(mode.lower()) or {}).get("shape") or normalise(mode),
				"emoji": (
					(stored.get(mode.lower()) or {}).get("emoji")
					or DEFAULT_EMOJI.get(normalise(mode), "")
				),
				"custom": mode.lower() in stored,
			}
			for mode in [one.strip() for one in modes.split("\n") if one.strip()]
		],
		"shapes": list(SHAPES),
		"may_write": bool(frappe.has_permission("Transit Marker Style", "write")),
	}


@frappe.whitelist(methods=["POST"])
def set_marker_style(mode: str, shape: str = "", emoji_glyph: str = "") -> dict:
	"""Draw this mode as that shape, or wear that glyph, for everybody.

	A workspace decision rather than a per-person one, which is why it is a
	doctype and not a saved view: a control room where two screens draw the
	same tram differently is a control room having an argument about which
	screen is right.
	"""
	if not frappe.has_permission("Transit Marker Style", "write"):
		frappe.throw(_("You cannot change how the map is drawn."), frappe.PermissionError)

	name = str(mode or "").strip()
	if not name:
		frappe.throw(_("Which mode?"))

	# One endpoint for both halves, and each optional: the picker changes a
	# shape or a glyph, never both at once, and a call that carried the other
	# half back would overwrite whatever somebody else had just set.
	glyph = emoji(emoji_glyph)
	wanted = normalise(shape) if shape else ""

	existing = frappe.db.exists("Transit Marker Style", name)
	if existing:
		row = frappe.get_doc("Transit Marker Style", name)
	else:
		row = frappe.new_doc("Transit Marker Style")
		row.mode = name
		row.shape = normalise(name)

	if wanted:
		row.shape = wanted
	if emoji_glyph:
		row.emoji = glyph
	row.save() if existing else row.insert()

	return {"mode": name, "shape": row.shape, "emoji": row.emoji or ""}
