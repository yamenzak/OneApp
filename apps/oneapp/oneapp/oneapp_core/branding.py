"""The workspace's own colour, and everywhere a colour has to land.

Frappe already carries most of what a workspace calls itself. `Website Settings`
holds the name, the logo, the favicon and the splash image, and every page the
framework renders for itself — the sign-in page, an error page, a password
reset — reads them, which is why those pages needed nothing from us beyond
`sync.sync_branding` filling them in at provisioning.

What Frappe has no field for is the workspace's *accent*: the one colour a solid
button is. `Website Theme.primary_color` is not it — it is a Link to a bootstrap
colour name, compiled into SCSS for the portal, and recompiling a theme on a
tenant bench to change a button is a build step in the middle of a settings
form. And it would not reach the app anyway: the SPA is one HTML file the
framework serves without a template.

So this module is the accent and its two seams.

The value is an *intent* in the sense `oneapp_core/theming.py` means it — read
that first for why a look is four words and not a stylesheet. It is validated by
the same rule, and expanded into CSS variables by the same browser code
(`lib/shell/theme.js`). A space's own theme still overrides it, which is the
whole point of the pair: the workspace is what everything looks like, and a
space says where it differs.

Where it lands:

  * **The app**, in the boot payload `www/one.py` builds, so it is on the
    document before first paint rather than after a round trip.

  * **The framework's own pages**, as a `<style>` block written between markers
    into `Website Settings.head_html` — which `templates/includes/head.html`
    emits on every web page, sign-in and error pages included. The Continue
    button on the sign-in page is an espresso `.es-button`, and espresso reads
    `--surface-gray-10` and `--ink-base`: the same two tokens the accent moves
    in the app. So one colour reaches both applications, and neither of them
    needed a stylesheet to say so.
"""

import frappe

from oneapp.oneapp_core import theming

#: A site default rather than a field on a single, because there is no Frappe
#: field for this — see the module docstring. `frappe.db.get_default` is the
#: framework's own store for exactly this: one workspace-wide value with no
#: doctype worth inventing.
ACCENT_KEY = "onespace_brand_accent"

#: What we own inside `head_html`, which is otherwise the customer's. Everything
#: between these two lines is rewritten on every save; everything outside them is
#: left exactly as it was found.
OPEN = "/* onespace:brand — written by the Branding settings tab */"
CLOSE = "/* onespace:brand end */"


def accent() -> str:
	"""The workspace's colour, or nothing."""
	return theming.colour(frappe.db.get_default(ACCENT_KEY))


def set_accent(value) -> str:
	"""Store it, and put the framework's pages back in step. Returns what stuck."""
	kept = theming.colour(value)
	frappe.db.set_default(ACCENT_KEY, kept)
	refresh()
	return kept


def boot() -> dict:
	"""What the SPA needs before it paints anything.

	The favicon and the splash image travel with the accent because they have
	the same problem: they are set on `Website Settings`, which the framework
	reads for its own pages and the SPA never sees. The app's tab icon was the
	one in `index.html` — ours, hard-coded — whatever the workspace had chosen.
	"""
	return {
		"accent": accent(),
		"favicon": frappe.db.get_single_value("Website Settings", "favicon") or "",
		"splash": frappe.db.get_single_value("Website Settings", "splash_image") or "",
	}


def refresh() -> None:
	"""Rewrite our block in `head_html` from the accent as it now stands."""
	head = without_ours(frappe.db.get_single_value("Website Settings", "head_html") or "")
	block = css(accent())
	head = "\n\n".join(part for part in (head, block) if part)
	frappe.db.set_single_value("Website Settings", "head_html", head)
	_own_the_footer()


# What the framework puts under every page it renders itself — the sign-in page,
# the reset-password page, an error page — when nothing says otherwise.
#
# `footer_powered` is a field on Website Settings, and Frappe's template falls
# through to "Built on Frappe" when it is empty; ERPNext's own setup overwrites
# it with "Powered by ERPNext". Neither is a sentence a customer of ours should
# be reading: they bought OneSpace, from us. So we set it, once, and the
# framework's fallback never runs.
FOOTER = "OneSpace"


def _own_the_footer() -> None:
	if frappe.db.get_single_value("Website Settings", "footer_powered") != FOOTER:
		frappe.db.set_single_value("Website Settings", "footer_powered", FOOTER)


def without_ours(head: str) -> str:
	"""`head_html` with our block taken out, whatever else it holds.

	Markers and not a full replace: this field is a customer's own analytics
	snippet as often as it is empty, and a settings tab that silently ate one
	would be a support ticket nobody could diagnose from the outside.
	"""
	while OPEN in head and CLOSE in head:
		before, rest = head.split(OPEN, 1)
		head = before + rest.split(CLOSE, 1)[1]
	return head.strip()


def css(colour: str) -> str:
	"""The block, or an empty string for a workspace with no colour set.

	Three surfaces and the ink that goes on them — the same tokens and the same
	amounts as `ACCENT_VARIABLES` in `lib/shell/theme.js`, which is what makes
	the sign-in page and the app one colour rather than two near ones.
	`color-mix` rather than arithmetic here: `lift(c, 0.12)` is exactly 88% of
	the colour and 12% white in sRGB, and letting the browser do it keeps one
	fewer copy of the maths.
	"""
	colour = theming.colour(colour)
	if not colour:
		return ""
	return "\n".join(
		[
			OPEN,
			"<style>",
			# `:root:root` and not `:root`, which is the whole trick and looks
			# like a typo without this line. `head_html` is emitted near the top
			# of the head, *before* the framework's own stylesheets, and
			# espresso declares these tokens at `:root, [data-theme="light"]` —
			# same specificity, later in the cascade, so a plain `:root` block
			# here is overwritten by the file it is meant to override. Doubling
			# the pseudo-class raises specificity without `!important`, and
			# beats the dark rule too, which is right: an accent is the accent
			# in both modes, exactly as the app applies it.
			":root:root {",
			f"\t--surface-gray-10: {colour};",
			f"\t--surface-gray-9: color-mix(in srgb, {colour} 88%, #ffffff);",
			f"\t--surface-gray-8: color-mix(in srgb, {colour} 76%, #ffffff);",
			f"\t--ink-base: {ink(colour)};",
			"}",
			"</style>",
			CLOSE,
		]
	)


def ink(colour: str) -> str:
	"""What is legible *on* the accent: near-black on a bright one, white else.

	WCAG relative luminance and not the mean of the channels, for the reason
	`lib/shell/theme.js` gives at length: green carries most of the perceived
	brightness and blue almost none, so averaging puts white text on yellow.
	"""
	value = theming.colour(colour).lstrip("#")
	if len(value) == 3:
		value = "".join(one * 2 for one in value)
	if len(value) != 6:
		return "#ffffff"

	channels = []
	for at in (0, 2, 4):
		one = int(value[at : at + 2], 16) / 255
		channels.append(one / 12.92 if one <= 0.03928 else ((one + 0.055) / 1.055) ** 2.4)
	luminance = 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
	return "#1c1c1c" if luminance > 0.45 else "#ffffff"
