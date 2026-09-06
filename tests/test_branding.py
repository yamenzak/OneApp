"""The workspace's own colour, and the two places it has to land.

A brand accent is not like the other settings in the dialog. Everything else
writes a Frappe field and stops; this one has no Frappe field at all, and it has
to reach two applications that share no rendering path — the SPA, which is one
HTML file, and the framework's own pages, which are Jinja. So the risks are
different, and they are what is checked here:

  * that the same colour reaches both, expanded the same way, rather than
    diverging into a sign-in page one shade off the app it signs into;
  * that writing it never eats the `head_html` a customer put there;
  * and that a value that is not a colour is dropped rather than injected —
    this one ends up inside a `<style>` block on a page served to strangers.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
THEME_JS = ROOT / "apps/oneapp/frontend/src/lib/shell/theme.js"
SPA = ROOT / "apps/oneapp/frontend/src"


# Imported inside fixtures, not at module scope: `frappe` is stubbed by an
# autouse fixture in conftest, so a module-level import would run against the
# real name and bind a module the next test throws away.
@pytest.fixture
def branding():
	from oneapp.oneapp_core import branding as module

	return module


@pytest.fixture
def theming():
	from oneapp.oneapp_core import theming as module

	return module


@pytest.fixture
def workspace():
	from oneapp.oneapp_core import workspace as module

	return module


# --------------------------------------------------------------------------- #
# The value
# --------------------------------------------------------------------------- #

def test_a_colour_is_the_same_kind_of_value_a_space_declares(branding, theming):
	"""One validator, so a workspace and a space cannot disagree about `#FFF`."""
	assert branding.css("#E50914").count("#e50914") == 3
	assert theming.colour("#E50914") == "#e50914"


@pytest.mark.parametrize(
	"asked",
	[
		"red",
		"#12345",
		"rgb(1,2,3)",
		# The reason this matters more here than in a manifest: the value is
		# written into a `<style>` block on the sign-in page.
		"#fff; } body { display: none } .x {",
		"</style><script>alert(1)</script>",
		None,
		7,
	],
)
def test_anything_that_is_not_a_colour_writes_no_css(branding, asked):
	assert branding.css(asked) == ""


def test_no_colour_is_no_block_rather_than_an_empty_one(branding, stub_frappe):
	branding.set_accent("")
	assert branding.OPEN not in stub_frappe.db.singles[("Website Settings", "head_html")]


# --------------------------------------------------------------------------- #
# Both applications, one colour
# --------------------------------------------------------------------------- #

def _amounts() -> dict:
	"""`ACCENT_VARIABLES` as the browser holds it: token → lift toward white."""
	source = THEME_JS.read_text()
	table = source.split("const ACCENT_VARIABLES = {")[1].split("}")[0]
	return {
		token: float(amount)
		for token, amount in re.findall(r"'(--[a-z0-9-]+)':\s*([\d.]+)", table)
	}


def test_the_css_moves_the_tokens_the_browser_moves_by_the_amounts_it_moves_them(branding):
	"""The block and `lib/shell/theme.js` are two copies of one mapping.

	`lift(c, a)` is `c + (255 - c) * a`, which in sRGB is exactly `(1 - a)` of
	the colour mixed with `a` of white — so the percentages below are not an
	approximation of the app's expansion, they are the same arithmetic handed to
	the browser instead of done here. A token that drifts on either side is a
	sign-in page a shade off the workspace behind it.
	"""
	block = branding.css("#0f62fe")
	amounts = _amounts()
	for token in ("--surface-gray-10", "--surface-gray-9", "--surface-gray-8"):
		assert token in amounts, f"{token} left theme.js; the block still writes it"
		want = round((1 - amounts[token]) * 100)
		expected = f"{token}: #0f62fe;" if not amounts[token] else (
			f"{token}: color-mix(in srgb, #0f62fe {want}%, #ffffff);"
		)
		assert expected in block, f"{token} does not match theme.js"


def test_the_ink_on_the_accent_is_decided_the_same_way_in_both(branding):
	"""Luminance, not the mean — the rule `theme.js` spells out at length."""
	# Caterpillar yellow: bright, and the mean of its channels is not.
	assert branding.ink("#ffcd11") == "#1c1c1c"
	# A blue of similar mean, and dark.
	assert branding.ink("#1100ff") == "#ffffff"
	assert "luminance(accent) > 0.45" in THEME_JS.read_text()


def test_the_block_outranks_the_stylesheet_it_has_to_beat(branding):
	"""`head_html` lands before the framework's own CSS, and espresso declares
	these tokens at `:root`. Equal specificity, later file — so a plain `:root`
	block here is a colour that silently does not apply."""
	assert ":root:root {" in branding.css("#0f62fe")


def test_the_block_only_ever_writes_custom_properties(branding):
	"""Everything between the braces is a `--token`, or the settings tab is a
	stylesheet a customer can put `display: none` in."""
	body = branding.css("#0f62fe").split("{", 1)[1].split("}")[0]
	for line in body.strip().splitlines():
		assert line.strip().startswith("--"), line


# --------------------------------------------------------------------------- #
# head_html is the customer's
# --------------------------------------------------------------------------- #

def test_the_block_replaces_itself_and_nothing_else(branding, stub_frappe):
	theirs = '<script src="https://plausible.io/js/script.js"></script>'
	stub_frappe.db.singles[("Website Settings", "head_html")] = theirs

	branding.set_accent("#0f62fe")
	after = stub_frappe.db.singles[("Website Settings", "head_html")]
	assert theirs in after
	assert "#0f62fe" in after

	branding.set_accent("#dc2626")
	after = stub_frappe.db.singles[("Website Settings", "head_html")]
	assert theirs in after
	assert "#0f62fe" not in after, "the old block was left behind"
	assert after.count(branding.OPEN) == 1

	branding.set_accent("")
	after = stub_frappe.db.singles[("Website Settings", "head_html")]
	assert after == theirs, "clearing the colour took the customer's snippet"


def test_a_block_written_twice_by_hand_is_still_cleaned_up(branding):
	doubled = branding.css("#0f62fe") + "\nkeep me\n" + branding.css("#dc2626")
	assert branding.without_ours(doubled) == "keep me"


# --------------------------------------------------------------------------- #
# The seam into the settings dialog
# --------------------------------------------------------------------------- #

def _accent_setting(workspace):
	group = next(g for g in workspace.GROUPS if g["key"] == "branding")
	return next(s for s in group["settings"] if s.key == "accent")


def test_the_accent_is_a_setting_with_no_doctype_behind_it(branding, workspace):
	setting = _accent_setting(workspace)
	assert setting.type == "Color"
	assert not setting.targets
	assert setting.default_key == branding.ACCENT_KEY


def test_saving_branding_puts_the_frameworks_pages_back_in_step():
	"""Otherwise the colour is in the app and the sign-in page is still grey."""
	from tests.sources import text

	body = text(ROOT / "apps/oneapp/oneapp/oneapp_core/workspace.py")
	assert "branding.refresh()" in body


def test_a_bad_colour_never_reaches_the_store(branding, workspace, stub_frappe):
	_accent_setting(workspace).write("not a colour")
	assert stub_frappe.db.defaults[branding.ACCENT_KEY] == ""


# --------------------------------------------------------------------------- #
# The app
# --------------------------------------------------------------------------- #

def test_the_boot_payload_carries_what_is_wanted_before_the_first_paint():
	page = (ROOT / "apps/oneapp/oneapp/www/one.py").read_text()
	assert "branding.boot()" in page

	boot = (SPA / "lib/runtime/boot.js").read_text()
	assert "read('brand', {})" in boot


def test_the_tab_icon_follows_the_workspace_rather_than_the_build():
	"""`index.html` names our own favicon, and it is a literal in a built file
	no workspace can reach. The app has to set it from the boot payload or a
	workspace's chosen icon stops at the sign-in page."""
	app = (SPA / "App.vue").read_text()
	assert "icon: brand.favicon" in app


def test_the_splash_image_is_read_by_something():
	"""It was a setting that wrote a field nothing ever looked at."""
	app = (SPA / "App.vue").read_text()
	assert "brand.splash" in app


def test_the_workspace_colour_is_the_floor_a_space_theme_stands_on():
	"""Not a replacement for it, and not ignored by it.

	The pair is the whole design: the workspace is what the product looks like,
	and a space's own theme says where it differs — so clearing a space's theme
	has to land back on the workspace rather than on frappe-ui's grey.
	"""
	source = THEME_JS.read_text()
	assert "export function setBrand" in source
	# The space's word wins, which is what this spread order means.
	assert "{ ...brand, ...(space || {}) }" in source
	# And clearing a space repaints rather than removing everything.
	body = source.split("export function clearTheme")[1].split("}")[0]
	assert "paint()" in body


def test_the_line_under_the_sign_in_page_is_ours():
	"""Frappe's own footer template renders "Built on Frappe" when
	`footer_powered` is empty, and ERPNext's setup fills it with "Powered by
	ERPNext". Both land on the sign-in page — the one page every person in a
	workspace sees before they are anybody, and the last place a supplier's name
	belongs. So we set the field, and the fallback never runs."""
	source = (ROOT / "apps/oneapp/oneapp/oneapp_core/branding.py").read_text()
	assert 'FOOTER = "OneSpace"' in source
	assert '"footer_powered"' in source
	# And it is written on every sync, not only when somebody opens the tab:
	# a workspace nobody has been into is exactly the one still saying ERPNext.
	sync = (ROOT / "apps/oneapp/oneapp/oneapp_core/sync.py").read_text()
	assert "branding.refresh()" in sync.split("def sync_branding")[1].split("\ndef ")[0]
