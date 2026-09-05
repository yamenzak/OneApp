"""A space's own look, declared.

Every space in this product is drawn with the same components, and that is the
right default: a person who learns one space has learned the rest, and a list is
a list. But a space is somebody's *application* — a contractor's job book, a
clinic's day, an operator's console — and eleven of them rendered in one
unchanging grey is a product that reads as one program with a dropdown at the
top rather than as the eleven things it is.

So a space may declare a **theme**, in four words:

    "theme": {
      "mode": "dark",
      "accent": "#E50914",
      "ground": "#0F0F10",
      "radius": "sharp"
    }

Four, and no more, on purpose. The alternative — a manifest that may set any CSS
variable it likes — is a stylesheet in a database, and the first space to reach
for one would put its own text colour on our own surface colour and produce a
screen nobody can read. These four are *intents*: the browser owns which
variables each one moves (`lib/theme.js`), so the mapping can be corrected in
one place when frappe-ui renames a token, and a space cannot paint itself into a
corner it does not know exists.

What each intent means:

* **mode** — light or dark, for the whole app while this space is open. The
  reader's own preference is put back the moment they leave; it is overruled,
  not overwritten. Absent, the reader decides as they always did.
* **accent** — the one colour that is this space's. It moves the solid buttons,
  the tab indicator, the progress fill and the links, and nothing else.
* **ground** — the page's own black or white, and the two surfaces that step up
  from it.
* **radius** — how sharp its corners are. `sharp` is a poster, `soft` is a
  greeting card; the scale moves, the components do not.

This is not the security boundary and does not need to be. A theme reaches
nothing but CSS custom properties on a page the reader already opened, and the
worst a bad one can do is look bad. What this module is for is the other kind of
failure: a hex with a typo, a mode nobody implements, a value that is not a
value — dropped here, so the space renders in the default look rather than in a
broken one.
"""

import re

# `#rgb` and `#rrggbb`. Long enough to be worth a regex, short enough that
# anything else — a colour name, a gradient, a `var()`, a semicolon and a second
# declaration — is not one.
COLOUR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

MODES = ("light", "dark")

# Named rather than numeric, and that is the point of an intent: "sharp" is a
# decision a person can make about their own application, and `0.35` is a number
# they would have to try. The multipliers live in the browser with the scale
# they multiply.
RADII = ("sharp", "soft")


def shape(asked) -> dict:
	"""One space's theme, or nothing.

	Field by field rather than all-or-nothing: a manifest that names a good
	accent and a bad radius should get the accent. The alternative punishes the
	typo by throwing away the part that was right, and the space renders plain
	with nothing to say which half was the problem.
	"""
	if isinstance(asked, str):
		import frappe

		try:
			asked = frappe.parse_json(asked or "null")
		except (TypeError, ValueError):
			return {}
	if not isinstance(asked, dict):
		return {}

	kept = {}

	mode = asked.get("mode")
	if mode in MODES:
		kept["mode"] = mode

	for key in ("accent", "ground"):
		value = asked.get(key)
		if isinstance(value, str) and COLOUR.match(value.strip()):
			kept[key] = value.strip().lower()

	radius = asked.get("radius")
	if radius in RADII:
		kept["radius"] = radius

	return kept
