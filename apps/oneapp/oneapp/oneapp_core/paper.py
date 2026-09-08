"""How a page is set, for everything of ours that gets printed.

Not Frappe's print stack. That one takes a doctype and a name and walks a print
format — see `printing.py`, which is records and only records. A document and a
sheet have no doctype to print: what they have is content and a page it has to
sit on, and this is that page.

What it is, precisely: page size, orientation, margins and a letter head, turned
into CSS. The browser paginates. That is the whole design decision and it is
worth saying why, because "render a PDF on the server" is the obvious
alternative and it is wrong here twice over — it wants a headless browser in
every container, and it produces a file where what somebody asked for was a
document they could still read on screen.

So: `@page` carries the size and the margins, `page-break-*` carries the rules,
and the letter head repeats on every sheet by the one mechanism every engine
honours — a `<thead>`. `position: running()` is the specified answer and Chrome
has never implemented it; `position: fixed` repeats in Chrome and not in
Firefox. A table header repeats in both, has since Netscape, and is what every
invoice on the web is still built out of.

Shared by `docs/export.py` and `sheets/export.py` because a page is a page: an
A4 with a 20mm margin and the company's letter head on it is the same object
whether the words on it are prose or a column of numbers.
"""

import frappe

#: Page sizes, in millimetres, portrait. The same five `printing.PAGE_SIZES`
#: offers, so a workspace that set Legal for its invoices is not offered a
#: different list for its documents.
SIZES = {
    "A4": (210, 297),
    "Letter": (216, 279),
    "Legal": (216, 356),
    "A3": (297, 420),
    "A5": (148, 210),
}

DEFAULT_SIZE = "A4"

#: Margins, in millimetres, as the three presets a person actually picks
#: between. A number in a box is offered too — `margin_mm` — because somebody
#: printing onto pre-printed stationery has a measurement rather than a
#: preference.
MARGINS = {"narrow": 12, "normal": 20, "wide": 30}
DEFAULT_MARGIN = "normal"

ORIENTATIONS = ("portrait", "landscape")


def setup_of(settings: dict | None) -> dict:
    """One document's page setup, with every gap filled.

    Read from whatever the editor stored, which is a free-form JSON column and
    may be from a version of this product that did not have half these keys.
    Nothing here throws: a page setup that refuses to resolve is a document
    that will not print.
    """
    settings = settings or {}
    size = settings.get("page_size")
    if size not in SIZES:
        size = DEFAULT_SIZE

    orientation = settings.get("orientation")
    if orientation not in ORIENTATIONS:
        orientation = "portrait"

    margin = settings.get("margin")
    if isinstance(margin, (int, float)):
        millimetres = max(0, min(60, float(margin)))
    else:
        millimetres = MARGINS.get(margin, MARGINS[DEFAULT_MARGIN])

    return {
        # Pageless is the default, and that is a real choice rather than an
        # absence: a document written to be read on a screen has no pages, and
        # making somebody turn pages off would be making them undo a decision
        # nobody asked them to make.
        "paged": bool(settings.get("paged")),
        "page_size": size,
        "orientation": orientation,
        "margin": millimetres,
        "letter_head": settings.get("letter_head") or "",
    }


def size_mm(setup: dict) -> tuple[float, float]:
    """Width and height in millimetres, the way round it is being printed."""
    width, height = SIZES.get(setup["page_size"], SIZES[DEFAULT_SIZE])
    return (height, width) if setup["orientation"] == "landscape" else (width, height)


def page_css(setup: dict) -> str:
    """The `@page` rule, the rules that keep content whole, and the on-screen
    sheet that matches them.

    `size` in millimetres rather than by name, because `size: A4 landscape` is
    honoured by fewer engines than two numbers are — and because a custom size
    would need the numbers anyway.

    The screen half matters more than it looks. This file is opened and read as
    often as it is printed, and a page set to A5 that fills a laptop window
    until the moment somebody prints it is a page that lied. So on screen the
    body *is* the sheet: the page's width, the page's margins, and a grey desk
    behind it.
    """
    width, height = size_mm(setup)
    margin = setup["margin"]
    return (
        f"@page {{ size: {width}mm {height}mm; margin: {margin}mm; }}\n"
        "@media screen {\n"
        "  body { background: #eef0f3; }\n"
        f"  body {{ width: {width}mm; max-width: 100%; margin: 24px auto;\n"
        f"    padding: {margin}mm; background: #fff;\n"
        "    box-shadow: 0 1px 3px rgb(0 0 0 / 12%); }\n"
        "}\n"
        "@media print {\n"
        "  html, body { width: auto; margin: 0; padding: 0; max-width: none;\n"
        "    background: none; box-shadow: none; }\n"
        # A heading with its paragraph, a row with its table, an image whole.
        # The three that a reader notices when they are missing.
        "  h1, h2, h3, h4 { break-after: avoid-page; }\n"
        "  tr, img, blockquote, pre { break-inside: avoid-page; }\n"
        "}\n"
    )


def letter_head_html(name: str) -> str:
    """One letter head's markup, or "" — including for a name that is gone.

    A letter head somebody deleted is not an error worth refusing to print
    over. It is a document that prints without one, which is what it looked
    like before they added it.
    """
    if not name:
        return ""
    row = frappe.db.get_value(
        "Letter Head", name, ["content", "disabled"], as_dict=True
    )
    if not row or row.disabled:
        return ""
    return row.content or ""


def repeated(setup: dict, body: str) -> str:
    """`body`, wrapped so the letter head repeats on every printed page.

    A `<thead>`, and the docstring at the top of this module is why. The table
    is one column and carries no borders of its own, so it is a layout wrapper
    and nothing a reader can see.
    """
    head = letter_head_html(setup.get("letter_head") or "")
    if not head:
        return body

    return (
        '<table class="paper"><thead><tr><td>'
        f'<div class="letterhead">{head}</div>'
        "</td></tr></thead><tbody><tr><td>"
        f"{body}"
        "</td></tr></tbody></table>"
    )


#: The wrapper's own styling. Separate from `page_css` because a caller that
#: has no letter head still wants the page rules.
PAPER_CSS = (
    "table.paper { width: 100%; border-collapse: collapse; }\n"
    "table.paper > thead > tr > td, table.paper > tbody > tr > td {\n"
    "  padding: 0; border: 0; }\n"
    ".letterhead { padding-bottom: 12px; margin-bottom: 16px;\n"
    "  border-bottom: 1px solid #d9dde2; }\n"
)
