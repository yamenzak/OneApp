"""The desk: windows, and what tells them apart.

`docs/DESKTOP.md`. One component draws every window — `DeskWindow.vue` — so
the rules a window keeps are rules about that file and about what its callers
are allowed to hand it.
"""

import re
from pathlib import Path

import where

SPA = Path(where.SPA)


def _windows() -> list[Path]:
	"""Every component that draws a window."""
	return sorted(p for p in SPA.rglob("*.vue") if "<DeskWindow" in p.read_text())


def test_a_window_declares_a_colour_and_never_a_hex():
	"""A desk with four grey windows on it is four rectangles you tell apart by
	reading their titles, which is the thing a title bar exists so you do not
	have to do. So a window takes a `tint`.

	Where the tint comes from is the rule. An app's is its mark's own colour,
	which `gen_brand.py` computes from the drawing and `colourOf` reads back; a
	record preview's is the accent in force, which is the space's theme or the
	workspace's. Neither is a literal. A hex typed into a caller is a colour
	that stops matching its mark the first time the mark is redrawn — and the
	marks are generated, so nobody would notice.
	"""
	for path in _windows():
		source = path.read_text()
		for tint in re.findall(r':tint="([^"]+)"', source):
			assert "#" not in tint, (
				f"{path.name} types a colour into its window's tint ({tint}); "
				"read the mark's own with `colourOf`, or the accent in force"
			)


def test_the_window_mixes_its_tint_rather_than_painting_with_it():
	"""A saturated title bar over grey content is a window from 2005, and eight
	apps each painting a full-strength header would be a desk that looks like a
	paint chart. The bar takes a fraction of the tint mixed into the surface it
	would otherwise have been — which is also what makes one declaration work
	in both light and dark, because the thing it mixes into is the token that
	moves."""
	source = where.source("DeskWindow.vue")
	mixes = re.findall(r"color-mix\(in oklab, \$\{props\.tint\} (\d+)%", source)
	assert mixes, "DeskWindow no longer mixes its tint"
	background = [one for one in mixes if int(one) < 50]
	assert background, (
		"every use of the tint is at half strength or more, so the bar is "
		"painted rather than washed"
	)


def test_every_window_on_the_desk_has_a_colour():
	"""Not a nicety: a window with no tint is the grey every window used to be,
	and one grey window among four coloured ones reads as the broken one.

	There are two answers and every window takes one of them. A window holding
	an *app* wears that app's mark colour. A window holding something out of a
	*space* — a record preview, the list it came from — wears the accent in
	force, which is that space's own."""
	without = [
		path.name for path in _windows() if ':tint="' not in path.read_text()
	]
	assert not without, f"these windows are still grey: {without}"
