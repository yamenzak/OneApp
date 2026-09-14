#!/usr/bin/env python3
"""The brand marks, out of the page they were designed in and into assets.

Twenty-seven app marks were drawn as one HTML page — a gallery with an
inspector, a dock test and the SVG source for each. That page is the design and
is kept whole at `scripts/brand/marks.source.html` rather than being
transcribed: retyping twenty-seven SVGs is twenty-seven chances to move a
coordinate, and the next revision of the page would have to be retyped again.

So this reads it, and the reading is the part that changed. The first design
held each mark as a template literal and this script pulled them out line by
line. This one does not: every mark is a *function* over a shared chassis, a
shared beacon and a superellipse solver, and several pick between variants. A
regex over that would mean re-implementing the geometry in Python and hoping
the two agree, which is the same mistake as transcribing by hand one level up.
`scripts/brand/read_marks.mjs` runs the page's own drawing code instead and
hands back JSON; this turns that into:

    scripts/brand/marks.json                            what was read, for a
                                                        human to diff when the
                                                        page is revised
    apps/oneapp/frontend/src/shared/lib/brand/marks.js  the SPA's copy
    apps/oneapp/oneapp/public/brand/<id>.svg            standalone files, for a
                                                        favicon, an email, a
                                                        print

Run it after the page changes:

    python3 scripts/gen_brand.py

Three things it does deliberately.

**It keeps this repository's names.** The page calls the document editor
OneWriter and the spreadsheet OneWorkbook; here they are OneDoc and OneSheet,
and the file drive is OneStorage rather than OneCloud. `ALIAS` is that map and
nothing else in the product knows the page's ids. A mark is artwork — renaming
four products to match a drawing would be the tail wagging the dog, and every
manifest, doc and route naming `onedoc` would have to move with it.

**It does not tokenise white.** The first design used white as a *knockout* —
a sheet of paper inside a coloured shape — which vanished on a light ground, so
white became a variable that inverted with the theme. Nothing in this set does
that. White here is a highlight at 12% over obsidian, the hot centre of the
beacon, and the light edge of the chassis, every one of them inside a coloured
object. Swapping any of them for a theme token would put grey where the light
is.

**It rewrites every `id` inside a mark.** Each mark inlines the same four
shared filters and gradients — `soft-shadow`, `beacon-grad` — so two marks on
one page are two elements with one id, and a `v-if` unmounting either takes the
gradient the other is pointing at with it. The ids are made unique per render
instead, which `BrandMark.vue` does by substituting a token this puts in.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "scripts" / "brand" / "marks.source.html"
READER = ROOT / "scripts" / "brand" / "read_marks.mjs"
READ_BACK = ROOT / "scripts" / "brand" / "marks.json"
JS = ROOT / "apps" / "oneapp" / "frontend" / "src" / "shared" / "lib" / "brand" / "marks.js"
SVG_DIR = ROOT / "apps" / "oneapp" / "oneapp" / "public" / "brand"

#: What the component substitutes for, once per instance. Not a `{}` or a `%s`:
#: this travels through JSON, JavaScript and an SVG attribute, and has to be
#: something none of the three treats as syntax.
UNIQUE = "__ONE__"

#: The page's id for a mark, against this product's name for the thing it
#: draws. Everything not in here keeps the page's id with the dash taken out —
#: `one-calendar` is `onecalendar`, which is what every manifest already says.
ALIAS = {
	"one-cloud": "onestorage",
	"one-writer": "onedoc",
	"one-workbook": "onesheet",
	"one-people": "onehr",
	"one-hub": "onemarket",
	"one-screen": "onedisplay",
}

#: This product's name, where it differs from the page's. The page is a design
#: document and names things the way the designer thinks of them; the product
#: has shipped four of them under other names for a year.
RENAMED = {
	"onestorage": "OneStorage",
	"onedoc": "OneDoc",
	"onesheet": "OneSheet",
	"onehr": "OneHR",
	"onemarket": "OneMarket",
	"onedisplay": "OneDisplay",
}

#: A mark's colour, for the rare surface that wants the hue without the
#: drawing. Worked out from the artwork rather than declared — see `hue()` —
#: with one exception, because one mark has no single colour: the parent is a
#: four-colour spectrum ring and picking any one stop off it would say the
#: platform is rose. It keeps the indigo the product's own accent already is.
COLOUR = {"one": "#4f46e5"}

_STOP = re.compile(r'<stop\b[^>]*\boffset="(\d+(?:\.\d+)?)%"[^>]*\bstop-color="(#[0-9a-fA-F]{3,8})"')
_FILL = re.compile(r'(?:fill|stroke)="(#[0-9a-fA-F]{3,8})"')
_ID_ATTR = re.compile(r'\bid="([^"]+)"')
_URL_REF = re.compile(r"url\(#([^)]+)\)")
_VIEWBOX = re.compile(r'viewBox="([^"]+)"')
_BODY = re.compile(r"<svg\b[^>]*>(.*)</svg>\s*$", re.S)


def read() -> dict:
	"""The page's own drawing code, run.

	Through node because the page is JavaScript. A bench has one — the SPA is
	built with it — and the alternative is a second implementation of a
	superellipse solver in Python, which would be a second thing to be wrong.
	"""
	try:
		done = subprocess.run(
			["node", str(READER), str(SOURCE)],
			capture_output=True, text=True, check=True,
		)
	except FileNotFoundError:
		raise SystemExit("node is not on PATH; it is what draws the marks")
	except subprocess.CalledProcessError as bad:
		sys.stderr.write(bad.stderr)
		raise SystemExit("the page could not be read — has it been rewritten?")
	return json.loads(done.stdout)


def hue(body: str, common: str) -> str:
	"""The one colour a mark would be reduced to.

	Every mark in this set is built the same way: a gradient from a light tint
	through the true hue to a dark shade. So the *middle* stop is the colour,
	and the first and last are the light on it. Falling back to the first stop
	for a two-stop ramp and to a flat fill for a mark that has no gradient of
	its own.

	The four shared filters are cut out first. They carry the beacon's amber,
	which is in every mark and is nobody's colour.
	"""
	own = body.replace(common.strip(), "")
	stops = _STOP.findall(own)
	middle = [colour for offset, colour in stops if 25 <= float(offset) <= 75]
	if middle:
		return middle[0].lower()
	if stops:
		return stops[0][1].lower()
	flat = _FILL.findall(own)
	return flat[0].lower() if flat else "#64748b"


def uniquify(body: str) -> str:
	"""Suffix every id the mark declares, and every reference to one.

	Only the ids this body declares. A `url(#something)` naming an id from
	somewhere else is left alone — there are none today, and rewriting one
	would break it silently rather than loudly.
	"""
	declared = set(_ID_ATTR.findall(body))
	if not declared:
		return body

	def _id(match):
		return f'id="{match.group(1)}{UNIQUE}"'

	def _ref(match):
		name = match.group(1)
		return f"url(#{name}{UNIQUE})" if name in declared else match.group(0)

	return _URL_REF.sub(_ref, _ID_ATTR.sub(_id, body))


def marks(found: dict) -> list[dict]:
	"""Every mark, under this product's names and with its body pulled out."""
	common = found["common"]
	out = []
	for one in found["marks"]:
		svg = one["svg"]
		box = _VIEWBOX.search(svg)
		body = _BODY.search(svg)
		if not box or not body:
			raise SystemExit(f"{one['id']} is not an <svg> with a viewBox")

		here = ALIAS.get(one["id"], one["id"].replace("-", ""))
		out.append({
			"id": here,
			"name": RENAMED.get(here, one["name"]),
			"category": one["category"],
			# The page's `role` — "Time & Scheduling", "Stock & Counting". Four
			# words saying what the app is for, which is what a tile's tooltip
			# and the app board's caption want. The old subtitles were a
			# sentence each and nothing had room for them.
			"subtitle": one["role"],
			"color": COLOUR.get(here) or hue(svg, common),
			"box": box.group(1),
			"body": tidy(body.group(1)),
			# Kept for the diff and not shipped: what the drawing is and why,
			# in the designer's own words. `marks.json` is the thing a human
			# reads when the page is revised.
			"form": one["form"],
			"desc": one["desc"],
			"palette": one["palette"].replace("&bull;", "·"),
		})
	return out


def tidy(body: str) -> str:
	"""One line per element, without the page's indentation.

	The bodies come out with whatever whitespace the template literal had, and
	half of them are one long line already. Collapsed so the generated file
	diffs as one line per mark rather than as a reflow.
	"""
	return re.sub(r"\s*\n\s*", "", body).strip()


def write_js(found: list[dict]) -> None:
	JS.parent.mkdir(parents=True, exist_ok=True)
	rows = []
	for mark in found:
		rows.append(
			"  %s: {\n"
			"    name: %s,\n"
			"    colour: %s,\n"
			"    said: %s,\n"
			"    box: %s,\n"
			"    body: %s,\n"
			"  },"
			% (
				json.dumps(mark["id"]),
				json.dumps(mark["name"]),
				json.dumps(mark["color"]),
				json.dumps(mark["subtitle"]),
				json.dumps(mark["box"]),
				json.dumps(uniquify(mark["body"])),
			)
		)

	JS.write_text(
		"// Generated by scripts/gen_brand.py from scripts/brand/marks.source.html.\n"
		"// Edit the page, run the script. Do not edit this file.\n"
		"\n"
		"/**\n"
		" * The app marks, as SVG bodies.\n"
		" *\n"
		" * `body` is what goes inside an `<svg>` of this mark's own `box` —\n"
		" * defs, gradients and shapes. Every id it declares carries a %s\n"
		" * token which `BrandMark.vue` replaces with something unique per\n"
		" * instance: every mark inlines the same four shared filters, so two\n"
		" * marks on one page would be two elements with one id, and unmounting\n"
		" * either takes the gradient the other is pointing at.\n"
		" *\n"
		" * `colour` is the mark's own, for the rare surface that needs the hue\n"
		" * without the drawing — a dot beside a name, a chart series. `said` is\n"
		" * what the app is for, in four words.\n"
		" */\n"
		"export const UNIQUE = %s\n"
		"\n"
		"export const MARKS = {\n%s\n}\n"
		"\n"
		"/** Every mark's id, in the order the design lists them. */\n"
		"export const MARK_NAMES = Object.keys(MARKS)\n"
		% (UNIQUE, json.dumps(UNIQUE), "\n".join(rows)),
		encoding="utf-8",
	)


def write_svgs(found: list[dict]) -> None:
	"""One standalone file per mark, for everything that is not the SPA.

	Not uniquified: a file on its own is its own document, so its ids collide
	with nothing. Which is also why these are the wrong thing to inline into a
	page — that is what the component is for.
	"""
	SVG_DIR.mkdir(parents=True, exist_ok=True)
	for name in SVG_DIR.glob("*.svg"):
		# A mark taken out of the design has to leave, or a stale drawing goes
		# on being served at an address nothing generates any more.
		name.unlink()
	for mark in found:
		(SVG_DIR / f"{mark['id']}.svg").write_text(
			'<svg xmlns="http://www.w3.org/2000/svg" viewBox="%s" '
			'width="192" height="192" fill="none" role="img" aria-label="%s">'
			"%s</svg>\n" % (mark["box"], mark["name"], mark["body"]),
			encoding="utf-8",
		)


def main() -> None:
	found = marks(read())

	READ_BACK.write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
	write_js(found)
	write_svgs(found)

	print(f"{len(found)} marks: {', '.join(m['id'] for m in found)}")
	print(f"  {JS.relative_to(ROOT)}")
	print(f"  {SVG_DIR.relative_to(ROOT)}/*.svg")


if __name__ == "__main__":
	main()
