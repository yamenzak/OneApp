"""The six settings that are what most people mean by "make it ours".

`docs/ONEFORMS.md` §14, stage 13. §12 gave a customer `custom_css` and OneCode's
editor, which is the right door for the one person in the building who writes
CSS and no door at all for the person who wants their logo at the top. Both are
real; this is the second one.

**It compiles to the stylesheet that already exists.** Not a second mechanism,
not six more columns the public page has to know about: a theme is written into
`custom_css` between two markers, and `PublicForm.vue` learns nothing. So the
page has one thing loaded, the hand-written half and the compiled half cannot
disagree about precedence, and a customer who outgrows the theme can read what
it wrote and take it over.

**Written by hand still wins.** The theme owns the block between its markers and
nothing else. Everything a person wrote before or after it is kept, and because
the block goes first, a hand-written rule later in the file overrides it — which
is the order somebody would expect from having written the second one on purpose.

**Every value is checked, and the interesting refusals are the ones that follow
for free.** A colour is a hex triple, a size is a number in a range, and a font
is one of a short list of *system* stacks — because `check_css` refuses `@import`
and refuses `url()` to another site, so a theme that offered a web font would be
offering something the stylesheet door would then reject. That constraint is
worth keeping rather than working around: a form a stranger opens should not
fetch anything from anywhere.
"""

import re

import frappe
from frappe import _

#: Where the theme's block starts and ends inside `custom_css`. Comments, so a
#: person reading the stylesheet in OneCode is told what they are looking at and
#: what will be overwritten.
OPENS = "/* OneForms theme — written by the Look panel. Edits inside are lost. */"
CLOSES = "/* end OneForms theme */"

#: `#rgb` or `#rrggbb`. Nothing else: a colour that could be `red` could be
#: `url(…)` a version later, and the panel is a colour picker.
COLOUR = re.compile(r"^#(?:[0-9a-f]{3}|[0-9a-f]{6})$", re.I)

#: The stacks a theme may ask for, and every one of them is already on the
#: reader's machine. See the module docstring: a web font would need an
#: `@import` or a `url()`, and `service.check_css` refuses both.
FONTS = {
	"": "",
	"sans": "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
	"serif": "ui-serif, Georgia, Cambria, 'Times New Roman', serif",
	"mono": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
	"rounded": "ui-rounded, 'SF Pro Rounded', 'Segoe UI', system-ui, sans-serif",
}

#: The numeric settings, and what a number may be. A corner of 400 is a circle
#: and a width of 4000 is a form nobody can read across.
SIZES = {"corner": (0, 32), "width": (360, 960)}

#: What a theme carries. Small on purpose: this is the panel for somebody who
#: does not write CSS, and a panel of forty controls is one they close.
KEYS = ("accent", "ink", "paper", "page", "font", "corner", "width", "mark")


def check(theme: dict) -> dict:
	"""A theme, cleaned, or a refusal naming the setting that is wrong."""
	theme = dict(theme or {})
	out = {}

	for key in ("accent", "ink", "paper", "page"):
		said = str(theme.get(key) or "").strip()
		if not said:
			continue
		if not COLOUR.match(said):
			frappe.throw(_("{0} should be a colour like #2563eb.").format(key))
		out[key] = said.lower()

	font = str(theme.get("font") or "").strip().lower()
	if font and font not in FONTS:
		frappe.throw(_("{0} is not one of the fonts a form can use: {1}.")
		             .format(font, ", ".join(one for one in FONTS if one)))
	if font:
		out["font"] = font

	for key, (least, most) in SIZES.items():
		said = str(theme.get(key) or "").strip()
		if not said:
			continue
		try:
			number = int(float(said))
		except ValueError:
			frappe.throw(_("{0} should be a number.").format(key))
		if not least <= number <= most:
			frappe.throw(_("{0} should be between {1} and {2}.")
			             .format(key, least, most))
		out[key] = number

	mark = str(theme.get("mark") or "").strip()
	if mark:
		# A file on this site, and nothing else. `check_css` would refuse an
		# absolute URL when the block reached it; refusing here means the
		# refusal names the setting rather than the stylesheet.
		if not mark.startswith("/") or mark.startswith("//"):
			frappe.throw(_("The mark should be a file uploaded here, not a link "
			               "to another site."))
		if '"' in mark or ")" in mark:
			frappe.throw(_("That is not a file this form can use."))
		out["mark"] = mark

	return out


def compiled(theme: dict) -> str:
	"""The theme as CSS, or nothing at all where it says nothing.

	Written against the three `data-slot` hooks §12 put on the page, because
	those are what will not move when somebody reflows it. Tailwind utilities
	are not an API — that was the finding then and it is what makes a theme
	possible now.
	"""
	theme = check(theme)
	if not theme:
		return ""

	page, form, title = [], [], []

	if theme.get("page"):
		page.append(f"background: {theme['page']};")
	if theme.get("paper"):
		form.append(f"background: {theme['paper']};")
	if theme.get("ink"):
		form.append(f"color: {theme['ink']};")
	if theme.get("font"):
		form.append(f"font-family: {FONTS[theme['font']]};")
	if theme.get("corner") is not None and "corner" in theme:
		form.append(f"border-radius: {theme['corner']}px;")
	if "width" in theme:
		form.append(f"max-width: {theme['width']}px;")
	if theme.get("ink"):
		title.append(f"color: {theme['ink']};")

	said = []
	if page:
		# `[data-slot="form-page"]` and not `body`: the page's own wrapper
		# carries a background utility and paints over the document, so a rule
		# on `body` is a rule nobody sees. Measured in the browser, on the
		# first theme.
		said.append('[data-slot="form-page"] {\n  ' + "\n  ".join(page) + "\n}")
	if form:
		said.append('[data-slot="public-form"] {\n  ' + "\n  ".join(form) + "\n}")
	if title:
		said.append('[data-slot="form-title"] {\n  ' + "\n  ".join(title) + "\n}")

	if theme.get("accent"):
		# The one control on the page that is an action. Same specificity as the
		# utility it overrides and later in the document, which is what decides
		# it — the theme block is loaded with the page's own stylesheet.
		said.append(
			'[data-slot="form-send"],\n[data-slot="form-next"] {\n'
			f"  background: {theme['accent']};\n"
			"  border-color: " + theme["accent"] + ";\n}"
		)
		said.append('[data-slot="form-progress"] > span:first-child {\n'
		            f"  background: {theme['accent']};\n}}")

	if theme.get("mark"):
		# Above the heading rather than instead of it: a logo that replaced the
		# title would be a form whose name only exists as a picture.
		said.append(
			'[data-slot="form-title"]::before {\n'
			'  content: "";\n'
			"  display: block;\n"
			"  height: 40px;\n"
			"  margin-bottom: 12px;\n"
			f"  background: url({theme['mark']}) left center / contain no-repeat;\n"
			"}"
		)

	if not said:
		return ""
	return "\n\n".join([OPENS, *said, CLOSES])


def into(css: str, theme: dict) -> str:
	"""The stylesheet with the theme's block replaced, and the rest kept.

	First in the file, so a hand-written rule after it wins — which is the order
	somebody would expect from having written the second one on purpose.
	"""
	rest = without(css)
	block = compiled(theme)
	if not block:
		return rest
	return f"{block}\n\n{rest}".strip() if rest else block


def without(css: str) -> str:
	"""Whatever a person wrote, with the theme's block taken out.

	Tolerant of a missing close marker: somebody editing in OneCode may delete
	half of it, and the answer to that is to treat the rest of the file as
	theirs rather than to throw away what follows.
	"""
	css = css or ""
	if OPENS not in css:
		return css.strip()
	before, _found, after = css.partition(OPENS)
	if CLOSES in after:
		after = after.partition(CLOSES)[2]
	else:
		after = ""
	return f"{before.strip()}\n\n{after.strip()}".strip()
