#!/usr/bin/env python3
"""The brand marks, out of the artifact they were designed in and into assets.

Fifteen app marks were drawn as one HTML page — a gallery with an inspector, a
dock test and the SVG source for each. That page is the design, and it is kept
whole at `scripts/brand/marks.source.html` rather than being transcribed:
retyping fifteen SVGs is fifteen chances to move a coordinate, and the next
revision of the page would have to be retyped again.

So this reads it. Everything below the `const APPS = [` line is a list of
objects with an id, a name, a category, a subtitle, a colour and a `renderSvg`
returning the mark's body, and this pulls those out and writes three things:

    scripts/brand/marks.json                     what was read, for a human to
                                                 diff when the page is revised
    apps/oneapp/frontend/src/lib/brand/marks.js  the SPA's copy
    apps/oneapp/oneapp/public/brand/<id>.svg     standalone files, for a
                                                 favicon, an email, a print

Run it after the page changes:

    python3 scripts/gen_brand.py

Two things it does deliberately.

**It does not parse HTML.** The page is a JavaScript array inside a `<script>`,
and an HTML parser would hand back the whole script as one text node. What is
actually being read is a small, very regular JavaScript literal, so the reading
is line-oriented and refuses anything it does not recognise rather than
guessing — a mark that silently came through empty would be an invisible icon
nobody could account for.

**It rewrites every `id` inside a mark.** Each mark carries its own
`<linearGradient>` and `<mask>` with ids like `g-onesheet`. Those are global to
the document: draw the same mark twice and there are two elements with one id,
and — worse — a Vue `v-if` that unmounts the first instance takes the gradient
the second one is still pointing at with it. So the ids are made unique per
render instead, which the component does by substituting a token this puts in.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "scripts" / "brand" / "marks.source.html"
READ_BACK = ROOT / "scripts" / "brand" / "marks.json"
JS = ROOT / "apps" / "oneapp" / "frontend" / "src" / "lib" / "brand" / "marks.js"
SVG_DIR = ROOT / "apps" / "oneapp" / "oneapp" / "public" / "brand"

#: What the component substitutes for, once per instance. Not a `{}` or a `%s`:
#: this travels through JSON, JavaScript and an SVG attribute, and has to be
#: something none of the three treats as syntax.
UNIQUE = "__ONE__"

#: The parent mark, which lives in the page's header rather than in `APPS` —
#: it is the platform's own, not an app's. Read from there by its own marker.
PARENT_ID = "one"

_FIELD = re.compile(r"^\s*(id|name|category|subtitle|color):\s*'([^']*)',?\s*$")
_START = re.compile(r"^\s*renderSvg:\s*\(\)\s*=>\s*`\s*$")
_ID_ATTR = re.compile(r'\bid="([^"]+)"')
_URL_REF = re.compile(r'url\(#([^)]+)\)')


def apps(text: str) -> list[dict]:
	"""Every object in the `APPS` array, in the order the page lists them."""
	if "const APPS = [" not in text:
		raise SystemExit("no APPS array — has the page been rewritten?")

	lines = text[text.index("const APPS = ["):].splitlines()
	found, one, body = [], None, None

	for line in lines:
		if body is not None:
			# The closing backtick sits at the end of the mark's last line
			# rather than on one of its own — `…mask="url(#m-onespace)" />` +
			# "`" — so the end of the template is the end of a line, not a line.
			if line.rstrip().endswith("`"):
				body.append(line.rstrip()[:-1])
				one["body"] = _tidy("\n".join(body))
				body = None
			else:
				body.append(line)
			continue

		if line.strip() == "{":
			one = {}
			continue

		matched = _FIELD.match(line)
		if matched and one is not None:
			one[matched.group(1)] = matched.group(2)
			continue

		if _START.match(line) and one is not None:
			body = []
			continue

		if line.strip().startswith("}") and one:
			if "id" in one and "body" in one:
				found.append(one)
			one = None

	if not found:
		raise SystemExit("read no marks — the page's shape has changed")
	return found


def parent(text: str) -> dict:
	"""The platform mark out of the page's header.

	Its own function because it is not in `APPS` and is not an app: it is what
	sits beside the workspace name in the rail and on the sign-in page, and what
	the wordmark's small "One" belongs to.
	"""
	at = text.index('<!-- Parent ONE mark -->')
	block = text[at:text.index("</svg>", at)]
	body = block[block.index("<defs>"):]
	return {
		"id": PARENT_ID,
		"name": "One",
		"category": "core",
		"subtitle": "The platform",
		"color": "#4f46e5",
		"body": _tidy(body),
	}


def _tidy(body: str) -> str:
	return "\n".join(line[10:] if line.startswith(" " * 10) else line.strip()
	                 for line in body.strip().splitlines())


def uniquify(body: str) -> str:
	"""Suffix every id the mark defines, and every reference to one.

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

	body = _ID_ATTR.sub(_id, body)
	return _URL_REF.sub(_ref, body)


def write_js(marks: list[dict]) -> None:
	JS.parent.mkdir(parents=True, exist_ok=True)
	rows = []
	for mark in marks:
		rows.append(
			"  %s: {\n"
			"    name: %s,\n"
			"    colour: %s,\n"
			"    said: %s,\n"
			"    body: %s,\n"
			"  },"
			% (
				json.dumps(mark["id"]),
				json.dumps(mark["name"]),
				json.dumps(mark["color"]),
				json.dumps(mark.get("subtitle", "")),
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
		" * `body` is what goes inside a `<svg viewBox=\"0 0 100 100\">` — defs,\n"
		" * masks and shapes. Every id it declares carries a %s token which\n"
		" * `BrandMark.vue` replaces with something unique per instance: two copies\n"
		" * of one mark on a page would otherwise be two elements with one id, and\n"
		" * unmounting either takes the gradient the other is pointing at.\n"
		" *\n"
		" * `colour` is the mark's own, for the rare surface that needs the hue\n"
		" * without the drawing — a dot beside a name, a chart series.\n"
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


def write_svgs(marks: list[dict]) -> None:
	"""One standalone file per mark, for everything that is not the SPA.

	Not uniquified: a file on its own is its own document, so its ids collide
	with nothing. Which is also why these are the wrong thing to inline into a
	page — that is what the component is for.
	"""
	SVG_DIR.mkdir(parents=True, exist_ok=True)
	for mark in marks:
		(SVG_DIR / f"{mark['id']}.svg").write_text(
			'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" '
			'width="100" height="100" role="img" aria-label="%s">\n%s\n</svg>\n'
			% (mark["name"], mark["body"]),
			encoding="utf-8",
		)


def main() -> None:
	text = SOURCE.read_text(encoding="utf-8")
	marks = [parent(text), *apps(text)]

	READ_BACK.write_text(json.dumps(marks, indent=2) + "\n", encoding="utf-8")
	write_js(marks)
	write_svgs(marks)

	print(f"{len(marks)} marks: {', '.join(m['id'] for m in marks)}")
	print(f"  {JS.relative_to(ROOT)}")
	print(f"  {SVG_DIR.relative_to(ROOT)}/*.svg")


if __name__ == "__main__":
	main()
