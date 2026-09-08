"""Paper: page size, margins, orientation and a letter head that repeats.

Documents and sheets both print, and neither goes near Frappe's print stack —
that one walks a doctype through a print format, and a document has no doctype.
What they share is `shared/paper.py`: a page setup resolved from whatever
the editor stored, turned into `@page` and the two or three rules that keep a
heading with its paragraph.

Three things are worth holding.

**Pageless is the default and has to stay one.** Every document written before
any of this existed answers `paged: False` and prints exactly the file it
printed before, and so does one whose settings are a corrupt string.

**The letter head repeats by `<thead>`.** `position: running()` is the
specified answer and Chrome has never implemented it; `position: fixed` repeats
in Chrome and not in Firefox. A table header repeats in both, so a page that
carries a letter head is a table and the test says so.

**The two catalogues agree.** The sizes and margins the dialog offers are the
sizes and margins the server resolves, because a page that looks A4 on screen
and prints Letter is a page that lied.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "apps/oneapp/oneapp/shared/paper.py"
PAPER_JS = ROOT / "apps/oneapp/frontend/src/shared/lib/paper/setup.js"
PAGINATE_JS = ROOT / "apps/oneapp/frontend/src/shared/lib/paper/paginate.js"


@pytest.fixture
def paper(stub_frappe):
	from oneapp.shared import paper as module

	return module


# --------------------------------------------------------------------------- #
# Pageless is the default
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("given", [None, {}, {"width": "page"}, {"paged": False}])
def test_pageless_unless_asked(paper, given):
	assert paper.setup_of(given)["paged"] is False


def test_every_gap_is_filled(paper):
	setup = paper.setup_of({"paged": True})
	assert setup["page_size"] == "A4"
	assert setup["orientation"] == "portrait"
	assert setup["margin"] == paper.MARGINS["normal"]
	assert setup["letter_head"] == ""


def test_nonsense_resolves_rather_than_throws(paper):
	setup = paper.setup_of(
		{"paged": True, "page_size": "Foolscap", "orientation": "sideways", "margin": "huge"}
	)
	assert (setup["page_size"], setup["orientation"]) == ("A4", "portrait")
	assert setup["margin"] == paper.MARGINS["normal"]


def test_a_measured_margin_is_taken_and_clamped(paper):
	assert paper.setup_of({"margin": 5})["margin"] == 5
	assert paper.setup_of({"margin": 500})["margin"] == 60
	assert paper.setup_of({"margin": -3})["margin"] == 0


# --------------------------------------------------------------------------- #
# The page, as CSS
# --------------------------------------------------------------------------- #

def test_landscape_swaps_the_page_round(paper):
	portrait = paper.setup_of({"paged": True, "page_size": "A4"})
	landscape = paper.setup_of({"paged": True, "page_size": "A4", "orientation": "landscape"})
	assert paper.size_mm(portrait) == (210, 297)
	assert paper.size_mm(landscape) == (297, 210)


def test_page_rule_carries_millimetres_not_a_name(paper):
	css = paper.page_css(paper.setup_of({"paged": True, "margin": "wide"}))
	assert "@page { size: 210mm 297mm; margin: 30mm; }" in css
	# `size: A4 landscape` is honoured by fewer engines than two numbers are.
	assert "size: A4" not in css


def test_print_rules_keep_a_heading_with_its_paragraph(paper):
	css = paper.page_css(paper.setup_of({"paged": True}))
	assert "break-after: avoid-page" in css
	assert "break-inside: avoid-page" in css


def test_the_screen_sheet_is_the_page_it_will_print(paper):
	css = paper.page_css(paper.setup_of({"paged": True, "page_size": "A5", "margin": "narrow"}))
	screen = css[css.index("@media screen") : css.index("@media print")]
	assert "width: 148mm" in screen
	assert "padding: 12mm" in screen


# --------------------------------------------------------------------------- #
# The letter head repeats
# --------------------------------------------------------------------------- #

def test_no_letter_head_leaves_the_body_alone(paper):
	setup = paper.setup_of({"paged": True})
	assert paper.repeated(setup, "<p>hello</p>") == "<p>hello</p>"


def test_a_letter_head_becomes_a_table_header(paper, monkeypatch):
	monkeypatch.setattr(paper, "letter_head_html", lambda name: "<h4>Mock House</h4>")
	out = paper.repeated(paper.setup_of({"paged": True, "letter_head": "House"}), "<p>hi</p>")
	assert out.startswith('<table class="paper"><thead>')
	assert "<h4>Mock House</h4>" in out
	assert "<tbody><tr><td><p>hi</p></td></tr></tbody>" in out


def test_a_deleted_letter_head_prints_without_one(paper, monkeypatch):
	monkeypatch.setattr(paper.frappe.db, "get_value", lambda *a, **k: None)
	assert paper.letter_head_html("Gone") == ""


def test_a_disabled_letter_head_prints_without_one(paper, monkeypatch):
	monkeypatch.setattr(
		paper.frappe.db, "get_value",
		lambda *a, **k: type("Row", (), {"content": "<b>x</b>", "disabled": 1})(),
	)
	assert paper.letter_head_html("Retired") == ""


def test_the_wrapper_draws_nothing_of_its_own(paper):
	# A layout table, not a visible one: no borders, no padding of its own.
	assert "border: 0" in paper.PAPER_CSS
	assert "padding: 0" in paper.PAPER_CSS


# --------------------------------------------------------------------------- #
# The two catalogues agree
# --------------------------------------------------------------------------- #

def _js_sizes() -> dict:
	source = PAPER_JS.read_text()
	block = source[source.index("export const PAGE_SIZES") : source.index("export const ORIENTATIONS")]
	return {
		name: (int(width), int(height))
		for name, width, height in re.findall(r"(\w+): \{ label: [^,]+, mm: \[(\d+), (\d+)\] \}", block)
	}


def _js_margins() -> dict:
	source = PAPER_JS.read_text()
	block = source[source.index("export const MARGINS") : source.index("export function paperSetup")]
	return {name: int(mm) for name, mm in re.findall(r"(\w+): \{ label: [^,]+, mm: (\d+) \}", block)}


def test_the_editor_offers_the_sizes_the_server_resolves(paper):
	assert _js_sizes() == paper.SIZES


def test_the_editor_offers_the_margins_the_server_resolves(paper):
	assert _js_margins() == paper.MARGINS


def test_the_editor_offers_both_orientations(paper):
	source = PAPER_JS.read_text()
	block = source[source.index("export const ORIENTATIONS") : source.index("export const MARGINS")]
	assert set(re.findall(r"^\s*(\w+): \{", block, re.M)) == set(paper.ORIENTATIONS)


# --------------------------------------------------------------------------- #
# A sheet on paper
# --------------------------------------------------------------------------- #

@pytest.fixture
def sheet_printing(stub_frappe):
	from oneapp.onesheet import printing as module

	return module


def test_sheet_print_defaults_to_this_tab_with_lines_on(sheet_printing):
	chosen = sheet_printing.options_of(None)
	assert chosen["which"] == "current"
	# A spreadsheet without its lines is a list of numbers nobody can follow.
	assert chosen["gridlines"] is True
	assert chosen["scale"] == 100
	assert chosen["repeat_head"] is False


def test_a_scale_we_do_not_offer_becomes_full_size(sheet_printing):
	assert sheet_printing.options_of({"scale": 33})["scale"] == 100
	assert sheet_printing.options_of({"scale": "75"})["scale"] == 75
	assert sheet_printing.options_of({"scale": None})["scale"] == 100


def test_gridlines_are_turned_off_only_by_saying_so(sheet_printing):
	assert sheet_printing.options_of({"gridlines": False})["gridlines"] is False
	assert sheet_printing.options_of({})["gridlines"] is True


def test_scaling_uses_zoom_not_transform(sheet_printing):
	# `transform: scale()` moves the box and not the layout, so a transformed
	# table prints full size with the ink in the wrong place.
	css = sheet_printing._scale_css(75)
	assert "zoom: 0.75" in css
	assert "transform" not in css
	assert sheet_printing._scale_css(100) == ""


def test_a_second_tab_starts_a_second_sheet_of_paper(paper, sheet_printing):
	setup = paper.setup_of({"paged": True})
	chosen = sheet_printing.options_of({})
	cells = {"A1": "Total", "A2": "9"}
	first = sheet_printing._table("One", cells, 2, 1, chosen, setup, first=True, many=True)
	second = sheet_printing._table("Two", cells, 2, 1, chosen, setup, first=False, many=True)
	assert 'class="tabblock"' in first
	assert 'class="tabblock break"' in second


def test_the_repeating_row_is_a_thead_and_the_rest_is_not(paper, sheet_printing):
	setup = paper.setup_of({"paged": True})
	cells = {"A1": "Name", "B1": "Due", "A2": "Rua", "B2": "Friday"}
	with_head = sheet_printing._table(
		"S", cells, 2, 2, sheet_printing.options_of({"repeat_head": True}),
		setup, first=True, many=False,
	)
	assert "<thead><tr><th>Name</th><th>Due</th></tr></thead>" in with_head
	# The row that repeats is not also a body row.
	assert with_head.count("Name") == 1

	without = sheet_printing._table(
		"S", cells, 2, 2, sheet_printing.options_of({}), setup, first=True, many=False,
	)
	assert "<thead>" not in without
	assert "<td>Name</td>" in without


def test_a_letter_head_rides_in_the_same_thead(paper, sheet_printing, monkeypatch):
	monkeypatch.setattr(sheet_printing.paper, "letter_head_html", lambda name: "<b>House</b>")
	out = sheet_printing._table(
		"S", {"A1": "9"}, 1, 1, sheet_printing.options_of({}),
		paper.setup_of({"paged": True, "letter_head": "House"}),
		first=True, many=False,
	)
	# One table, one thead — a thead inside a thead's table is one nesting past
	# what print engines agree on.
	assert out.count("<thead>") == 1
	assert '<div class="letterhead"><b>House</b></div>' in out


def test_cells_are_escaped(sheet_printing):
	assert sheet_printing._cell({"A1": "<script>"}, 1, 1) == "&lt;script&gt;"
	assert sheet_printing._cell({}, 1, 1) == ""


# --------------------------------------------------------------------------- #
# The editor and the printer are set in the same type
# --------------------------------------------------------------------------- #

@pytest.fixture
def typography(stub_frappe):
	from oneapp.onedoc import typography as module

	return module


def _js_faces() -> dict:
	source = PAPER_JS.read_text()
	block = source[source.index("export const FACES") : source.index("export const LEADING")]
	return dict(re.findall(r"(\w+|''): '([^']*)',", block))


def _js_leading() -> dict:
	source = PAPER_JS.read_text()
	line = source[source.index("export const LEADING") :].split("\n")[0]
	return {name: float(value) for name, value in re.findall(r"(\w+): ([\d.]+)", line)}


def test_the_sheet_is_set_in_the_face_the_page_prints_in(typography):
	# Not Inter. A paged document is measured on screen and printed by a
	# different renderer, and a web font the exported file cannot carry is a
	# document that repaginates on the way to the printer.
	faces = _js_faces()
	assert faces["''"] == typography.FONT_STACK
	assert faces["serif"] == typography.SERIF_STACK
	assert faces["mono"] == typography.MONO_STACK
	assert "Inter" not in typography.FONT_STACK


def test_the_two_agree_on_what_line_spacing_means(typography):
	assert _js_leading() == typography.LEADING


def test_every_face_the_dialog_offers_is_one_the_export_knows(typography):
	source = ROOT / "apps/oneapp/frontend/src/modules/onedoc/components/toolbar.js"
	block = source.read_text()
	block = block[block.index("export const FONTS") : block.index("export const SPACINGS")]
	offered = set(re.findall(r"^\s*'?(\w*)'?: \{", block, re.M))
	assert offered == set(typography.FACES)


def test_the_type_scale_is_written_out_rather_than_a_class(typography):
	# The exported file is opened where Tailwind is not, so `prose-sm` has to
	# arrive as declarations rather than as a class name.
	css = typography.sheet({})
	assert "prose" not in css
	assert "font-size: 14px" in css
	assert "line-height: 1.7142857" in css


def test_a_document_carries_its_own_face_and_leading(typography):
	css = typography.sheet({"font": "serif", "spacing": "loose"})
	assert typography.SERIF_STACK in css
	assert "line-height: 2" in css


# --------------------------------------------------------------------------- #
# Where the pages break
# --------------------------------------------------------------------------- #

def test_the_push_is_a_stylesheet_rather_than_an_inline_style():
	"""The one that cost an afternoon.

	Setting `style.marginTop` on a paragraph inside the editable looks like it
	works and then silently undoes itself: ProseMirror watches the editable for
	mutations it did not make and redraws the node from state, taking the
	margin with it. A rule in a `<style>` element outside the editable is not a
	mutation of the editable at all.
	"""
	source = PAGINATE_JS.read_text()
	assert "nth-child" in source
	assert "rules.textContent" in source
	code = "\n".join(
		line for line in source.splitlines()
		if not line.lstrip().startswith(("*", "/*", "//"))
	)
	assert "style.margin" not in code


def test_a_heading_is_never_the_last_thing_on_a_page():
	source = PAGINATE_JS.read_text()
	assert "ORPHANS" in source
	assert set(re.findall(r"'(H\d)'", source)) == {"H1", "H2", "H3", "H4", "H5", "H6"}
