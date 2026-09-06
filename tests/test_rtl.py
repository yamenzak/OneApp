"""Arabic runs the other way, and the layout has to run with it.

`dir="rtl"` on `<html>` flips text, flex order and scroll direction for free.
What it cannot flip is a class that names a side: `ml-2` is two units of margin
on the *left*, in every language, so a label spaced away from its icon in
English is a label sitting on top of it in Arabic.

Tailwind's logical properties are the fix and are a rename — `ms-` for margin
at the start of the line, `me-` at the end, `ps-`/`pe-`, `start-`/`end-`,
`text-start`/`text-end`, `border-s`/`border-e`. This is the guard that keeps
them.

A physical direction is still occasionally right: a resize handle that grabs
the window's right edge, a chevron that must point right whichever way the text
runs. Those say so in a comment on the same line, which is both the exemption
and the explanation.
"""

import re

from copy_reader import ROOT, sources

# Side-naming utilities, as they appear inside a class attribute. The leading
# boundary keeps `overflow-hidden` out of `hidden`, and `-mr-1` — a negative
# margin — in.
PHYSICAL = re.compile(
	r"(?<![\w-])-?(?:"
	r"m[lr]-[\w.\[\]/-]+"
	r"|p[lr]-[\w.\[\]/-]+"
	r"|(?:left|right)-[\w.\[\]/-]+"
	r"|text-(?:left|right)"
	r"|border-[lr](?:-[\w.\[\]/-]+)?"
	r"|rounded-(?:[lrtb][lr]|[lr])(?:-[\w.\[\]/-]+)?"
	r"|(?:float|clear)-(?:left|right)"
	r")(?![\w-])"
)

LOGICAL = {
	"ml": "ms",
	"mr": "me",
	"pl": "ps",
	"pr": "pe",
	"left": "start",
	"right": "end",
	"text-left": "text-start",
	"text-right": "text-end",
	"border-l": "border-s",
	"border-r": "border-e",
}

# The word that buys a line an exemption. Deliberately one word and not a
# machine-readable pragma: it has to be readable by whoever finds the line.
EXCUSED = "rtl-ok"


def offenders():
	"""`(file, line number, the class)` for every physical direction."""
	for where, raw in sources():
		for number, line in enumerate(raw.splitlines(), 1):
			if EXCUSED in line:
				continue
			for found in PHYSICAL.findall(line):
				yield where, number, found


def test_no_side_is_named_in_a_class():
	guilty = sorted(offenders())
	assert not guilty, (
		"these name a side, so they point the wrong way in Arabic — use the "
		f"logical property ({', '.join(f'{a}→{b}' for a, b in list(LOGICAL.items())[:4])}, "
		f"…), or say `{EXCUSED}` on the line and why:\n  "
		+ "\n  ".join(f"{where}:{number}  {found}" for where, number, found in guilty)
	)


def test_the_scan_would_notice():
	"""A regex that matches nothing passes for the wrong reason."""
	assert PHYSICAL.findall('class="ml-2 pr-3 text-left border-l left-0 -mr-1"') == [
		"ml-2",
		"pr-3",
		"text-left",
		"border-l",
		"left-0",
		"-mr-1",
	]
	# And does not match the words that merely contain one.
	assert not PHYSICAL.findall("overflow-hidden ms-2 me-auto ps-1 text-start rounded-md")


def test_the_document_says_which_way_round_it_runs():
	"""`dir` is set from the language, in one place, before the app mounts."""
	runtime = (ROOT / "apps/oneapp/frontend/src/lib/runtime/translate.js").read_text()
	assert "export function direction" in runtime
	assert "'ar'" in runtime, "Arabic is not in the right-to-left list"

	for spa in ("apps/oneapp", "apps/oneapp_control"):
		main = (ROOT / spa / "frontend/src/main.js").read_text()
		assert "documentElement.dir" in main, f"{spa} never sets `dir`"
