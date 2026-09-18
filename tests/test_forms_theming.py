"""Six settings, compiled into the stylesheet that already exists.

`docs/ONEFORMS.md` §14, stage 13. §12 gave a customer `custom_css` and OneCode's
editor, which is the right door for the one person in the building who writes
CSS and no door at all for the person who wants their logo at the top.

Three claims:

  * **It is not a second mechanism.** A theme is a block inside `custom_css`
    between two markers, so the public page learns nothing and the two halves
    cannot disagree about which one the browser applies.
  * **Written by hand still wins.** The theme owns its block and nothing else;
    the block goes first, so a hand-written rule after it overrides — which is
    the order somebody would expect from having written the second one.
  * **Every value is checked**, and the interesting refusals follow for free: a
    font is a *system* stack because `check_css` refuses `@import` and refuses
    `url()` to another site, so a form a stranger opens fetches nothing from
    anywhere.
"""

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
SOURCE = ROOT / "apps/oneapp/oneapp/oneforms/theming.py"
PANEL = ROOT / "apps/oneapp/frontend/src/modules/oneforms/components/LookPanel.vue"
BUILDER = ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/FormBuilder.vue"


@pytest.fixture
def theming(stub_frappe):
	from oneapp.oneforms import theming

	return theming


# ------------------------------------------------------------------ the values

def test_a_colour_is_a_hex_triple_and_nothing_else(theming):
	"""A colour that could be `red` could be `url(…)` a version later, and the
	panel is a colour picker."""
	assert theming.check({"accent": "#2563EB"})["accent"] == "#2563eb"
	assert theming.check({"accent": "#abc"})["accent"] == "#abc"
	for said in ("red", "rgb(1,2,3)", "url(//x)", "#12345", "#gggggg"):
		with pytest.raises(Exception) as refused:
			theming.check({"accent": said})
		assert "accent" in str(refused.value)


def test_a_font_is_one_of_the_ones_already_on_the_machine(theming):
	"""Not a limitation worked around. A web font needs an `@import` or a
	`url()`, and `check_css` refuses both — so a form a stranger opens fetches
	nothing from anywhere, which is worth keeping."""
	assert theming.check({"font": "serif"})["font"] == "serif"
	with pytest.raises(Exception):
		theming.check({"font": "Comic Sans"})
	for stack in theming.FONTS.values():
		assert "http" not in stack and "url(" not in stack


def test_a_size_is_a_number_in_a_range(theming):
	"""A corner of 400 is a circle and a width of 4000 is a form nobody can
	read across."""
	assert theming.check({"corner": "12"})["corner"] == 12
	assert theming.check({"width": 640})["width"] == 640
	for said in ({"corner": 400}, {"width": 40}, {"width": 4000}, {"corner": "lots"}):
		with pytest.raises(Exception):
			theming.check(said)


def test_a_mark_is_a_file_on_this_site(theming):
	"""`check_css` would refuse an absolute URL when the block reached it.
	Refusing here means the refusal names the setting rather than the
	stylesheet."""
	assert theming.check({"mark": "/files/logo.png"})["mark"] == "/files/logo.png"
	for said in ("https://elsewhere/logo.png", "//elsewhere/logo.png",
	             "/files/a\").png", "/files/a)b.png"):
		with pytest.raises(Exception):
			theming.check({"mark": said})


def test_nothing_set_compiles_to_nothing(theming):
	assert theming.check({}) == {}
	assert theming.compiled({}) == ""
	assert theming.compiled({"font": ""}) == ""


# --------------------------------------------------------------- the compiling

def test_it_writes_against_the_hooks_rather_than_the_utilities(theming):
	"""Tailwind utilities are not an API — that was §12's finding and it is
	what makes a theme possible at all."""
	css = theming.compiled({"accent": "#2563eb", "paper": "#fffdf6", "width": 640})

	assert '[data-slot="public-form"]' in css
	assert '[data-slot="form-send"]' in css
	assert "max-width: 640px" in css
	# Nothing reaching for a class the next reflow renames.
	assert ".bg-" not in css and ".text-" not in css


def test_the_page_colour_reaches_the_wrapper_rather_than_the_document(theming):
	"""Measured in the browser on the first theme: the page's own wrapper
	carries a background utility and paints over `body`, so a rule on `body` is
	a rule nobody sees."""
	css = theming.compiled({"page": "#f0fdfa"})

	assert '[data-slot="form-page"]' in css
	assert "body {" not in css

	page = (ROOT / "apps/oneapp/frontend/src/modules/oneforms/pages/PublicForm.vue").read_text()
	assert 'data-slot="form-page"' in page


def test_a_mark_is_drawn_above_the_heading_rather_than_instead_of_it(theming):
	"""A logo that replaced the title would be a form whose name only exists as
	a picture."""
	css = theming.compiled({"mark": "/files/logo.png"})
	assert '[data-slot="form-title"]::before' in css
	assert "url(/files/logo.png)" in css


# ------------------------------------------------------- living with a person

def test_the_block_is_replaced_and_the_rest_is_kept(theming):
	"""The whole argument for one field rather than two."""
	mine = "h1 { letter-spacing: -.01em }"
	once = theming.into(mine, {"accent": "#2563eb"})
	assert mine in once and theming.OPENS in once

	twice = theming.into(once, {"accent": "#111111"})
	assert mine in twice
	assert "#2563eb" not in twice and "#111111" in twice
	assert twice.count(theming.OPENS) == 1


def test_the_theme_goes_first_so_a_hand_written_rule_wins(theming):
	written = theming.into("h1 { color: red }", {"ink": "#000000"})
	assert written.index(theming.OPENS) < written.index("h1 { color: red }")


def test_clearing_it_takes_the_block_out_and_leaves_the_rest(theming):
	"""Its own button in the panel, because "undo the theme" is one decision
	rather than six empty fields."""
	mine = "h1 { letter-spacing: -.01em }"
	once = theming.into(mine, {"accent": "#2563eb"})
	assert theming.into(once, {}) == mine


def test_half_a_marker_does_not_eat_the_file(theming):
	"""Somebody editing in OneCode may delete one of them, and the answer is to
	treat what is left as theirs rather than to throw it away."""
	broken = f"{theming.OPENS}\nbody {{ color: red }}\nh1 {{ color: blue }}"
	assert theming.without(broken) == ""

	assert theming.without("h1 { color: blue }") == "h1 { color: blue }"
	assert theming.without("") == ""


# ------------------------------------------------------------------- the doors

def test_the_compiled_block_goes_through_the_same_check_as_a_written_one():
	"""A compiler with its own door would be a door."""
	service = (ROOT / "apps/oneapp/oneapp/oneforms/service.py").read_text()
	look = service.split("def look")[1]
	assert "check_css(theming.into" in look
	assert "_admin()" in look


def test_the_panel_reopens_on_what_is_stored_rather_than_on_the_css():
	"""A stylesheet cannot be read back into a colour picker, which is why the
	six settings are kept beside the CSS they compiled to."""
	service = (ROOT / "apps/oneapp/oneapp/oneforms/service.py").read_text()
	assert 'THEME = "custom_onespace_theme"' in service
	assert '"theme":' in service.split("def read")[1].split("\n@")[0]
	assert "custom_onespace_theme" in (ROOT / "apps/oneapp/oneapp/install.py").read_text()


def test_both_doors_are_in_the_builder():
	"""One for somebody who writes CSS and one for somebody who does not, and
	they write the same field."""
	builder = BUILDER.read_text()
	assert 'data-slot="builder-look"' in builder
	assert 'data-slot="builder-style"' in builder
	assert "LookPanel" in builder and "CodeDialog" in builder
