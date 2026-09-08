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
	runtime = (ROOT / "apps/oneapp/frontend/src/shared/lib/runtime/translate.js").read_text()
	assert "export function direction" in runtime
	assert "'ar'" in runtime, "Arabic is not in the right-to-left list"

	for spa in ("apps/oneapp", "apps/oneapp_control"):
		main = (ROOT / spa / "frontend/src/main.js").read_text()
		assert "documentElement.dir" in main, f"{spa} never sets `dir`"


# A lucide name that says which way it points. frappe-ui draws these as a CSS
# mask on a class of the same name, so `index.css` mirrors them under
# `[dir=rtl]` — one rule for all of them rather than an edit per component.
#
# Cardinal only. The diagonals are deliberately out: `arrow-up-right` is the
# open-this-elsewhere mark and would arguably flip, but the same name is also
# one of the icons a customer can pick for a value of their own — and turning a
# chosen icon round is a bug, where an external-link arrow pointing the English
# way is a detail.
DIRECTIONAL = re.compile(r"lucide-(?:chevrons?|arrow|corner)-(?:left|right)(?:-to-line)?")


def test_an_arrow_that_means_forward_is_mirrored():
	"""`dir=rtl` flips the layout and cannot flip a picture.

	A chevron beside a collapsed section points at the words it belongs to, and
	Back points at the page you came from; both are wrong in Arabic unless
	something turns them round.
	"""
	used = set()
	for _where, raw in sources():
		used.update(DIRECTIONAL.findall(raw))

	css = (ROOT / "apps/oneapp/frontend/src/index.css").read_text()
	mirrored = set(DIRECTIONAL.findall(css))

	missing = sorted(used - mirrored)
	assert not missing, (
		"these point the wrong way in Arabic — add them to the `[dir='rtl']` "
		"block in index.css:\n  " + "\n  ".join(missing)
	)


def test_both_apps_mirror_the_same_arrows():
	blocks = [
		set(DIRECTIONAL.findall((ROOT / spa / "frontend/src/index.css").read_text()))
		for spa in ("apps/oneapp", "apps/oneapp_control")
	]
	assert blocks[0] == blocks[1], "the two SPAs disagree about which arrows flip"


def test_a_document_leaves_the_right_way_round():
	"""The HTML export is opened where our stylesheet is not — somebody's word
	processor, somebody's mail client — so it has to carry its own direction."""
	source = (ROOT / "apps/oneapp/oneapp/onedoc/export.py").read_text()
	assert 'dir="{direction}"' in source
	# The type scale moved to `typography.py`, which the editor is measured
	# against too — so the mirrored rules live there with the rest of it.
	scale = (ROOT / "apps/oneapp/oneapp/onedoc/typography.py").read_text()
	assert "[dir=rtl] td" in scale, "the exported table still aligns to the left"


def test_the_two_lists_of_right_to_left_languages_agree():
	"""One is Python and one is a browser bundle, so they cannot be shared —
	which is exactly why they drift."""
	import re as _re

	def names(text):
		return set(_re.findall(r"[\"']([a-z]{2,3})[\"']", text))

	browser = (ROOT / "apps/oneapp/frontend/src/shared/lib/runtime/translate.js").read_text()
	server = (ROOT / "apps/oneapp/oneapp/onedoc/export.py").read_text()
	assert names(browser.split("RIGHT_TO_LEFT")[1].split("]")[0]) == names(
		server.split("RIGHT_TO_LEFT")[1].split(")")[0]
	)
