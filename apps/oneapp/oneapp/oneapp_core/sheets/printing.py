"""A sheet on paper.

Google's model, because it is the one every person who has printed a
spreadsheet already has: you do not print the grid you are looking at, you
choose what goes on the page and then look at it. Which tabs, what size, which
way round, how much of it fits, whether the lines show, whether the top row
comes back at the top of every page.

Not Frappe's print stack, for the same reason `paper.py` is not: a print format
walks a doctype and a sheet has none. What a sheet has is a rectangle of
values, and this turns that rectangle into a table on a page `paper.py` has
already described.

Values and not formulas, the same call `export.py` makes: a printed `=A2*B2` is
a printed mistake.
"""

import frappe
from frappe import _

from .. import paper
from . import book, codec
from .book import _mine

#: How much of the grid one print can carry. A sheet used down to row ten
#: thousand is a sheet somebody meant to export rather than print, and the
#: honest answer is to say so rather than to build a hundred-page PDF nobody
#: asked for.
MAX_PRINT_CELLS = 40000

#: What "smaller" means. Percentages rather than Google's fit-to-page, which
#: needs a measurement only the browser has — and a browser that has it is a
#: browser already showing the person a print preview they can scale in.
SCALES = (100, 90, 75, 50)


def options_of(given: dict | None) -> dict:
    """One print's options, with every gap filled and every wrong value ignored."""
    given = given or {}
    scale = given.get("scale")
    try:
        scale = int(scale)
    except (TypeError, ValueError):
        scale = 100

    return {
        "which": "all" if given.get("which") == "all" else "current",
        "tab": given.get("tab") or "",
        "scale": scale if scale in SCALES else 100,
        # On by default: a spreadsheet without its lines is a list of numbers
        # nobody can follow across.
        "gridlines": given.get("gridlines") is not False,
        "repeat_head": bool(given.get("repeat_head")),
        "tab_titles": given.get("tab_titles") is not False,
    }


@frappe.whitelist(methods=["POST"])
def printable(name: str, options: str = "", setup: str = "") -> dict:
    """The whole printable page for one sheet, as a string for a frame.

    POST rather than GET because the options are a body rather than a name, and
    a print with eight parameters in a query string is a print that breaks the
    first time somebody names a tab with an ampersand.
    """
    doc = _mine(name, "read")
    chosen = options_of(frappe.parse_json(options) if options else {})
    page = paper.setup_of({**(frappe.parse_json(setup) if setup else {}), "paged": True})

    loaded = book.load(doc.name)
    tabs = codec.tab_names(loaded)
    if chosen["which"] == "current":
        wanted = chosen["tab"] if chosen["tab"] in tabs else codec.current_tab(loaded)
        tabs = [wanted]

    title = doc.file_name or _("Sheet")
    return {"name": doc.name, "title": title,
            "html": _page(title, tabs, loaded, chosen, page)}


def _page(title: str, tabs: list[str], loaded: dict, chosen: dict, page: dict) -> str:
    """The document, head and all."""
    lang = frappe.local.lang or "en"
    blocks = []
    counted = 0

    for index, tab in enumerate(tabs):
        cells = codec.values_map(loaded, tab)
        rows, columns = codec.extent(cells)
        counted += rows * columns
        if counted > MAX_PRINT_CELLS:
            frappe.throw(
                _("That is too much sheet to print. Export it instead, or print one tab.")
            )
        blocks.append(_table(tab, cells, rows, columns, chosen, page,
                             first=index == 0, many=len(tabs) > 1))

    style = _STYLE + _scale_css(chosen["scale"]) + paper.page_css(page) + paper.PAPER_CSS
    if not chosen["gridlines"]:
        style += "table.grid td, table.grid th { border-color: transparent; }\n"

    return (
        "<!doctype html>\n"
        f'<html lang="{lang}"><head><meta charset="utf-8">'
        f"<title>{frappe.utils.escape_html(title)}</title>"
        f"<style>{style}</style></head><body>"
        + "".join(blocks)
        + "</body></html>"
    )


def _table(tab, cells, rows, columns, chosen, page, first: bool, many: bool) -> str:
    """One tab, as a table on a page of its own.

    A new tab starts a new sheet of paper — every one but the first — because
    two tabs sharing a page is two tables somebody has to tell apart, and the
    whole reason they are separate tabs is that they are separate things.

    The letter head goes in this table's own `<thead>` rather than in a wrapper
    of its own the way a document's does. Same mechanism, one fewer table: a
    grid already has a header row that has to repeat, and a `<thead>` inside a
    `<thead>`'s table is one nesting past what print engines agree on.
    """
    break_ = "" if first else " break"
    head = paper.letter_head_html(page.get("letter_head") or "")
    title = _titled(tab, chosen, many)

    if not rows:
        empty = frappe.utils.escape_html(_("Nothing on this tab."))
        return (
            f'<div class="tabblock{break_}">'
            + (f'<div class="letterhead">{head}</div>' if head else "")
            + title
            + f'<p class="empty">{empty}</p></div>'
        )

    header_rows = []
    if head:
        header_rows.append(
            f'<tr class="head"><td colspan="{columns}">'
            f'<div class="letterhead">{head}</div></td></tr>'
        )
    if chosen["repeat_head"]:
        header_rows.append("<tr>" + "".join(
            f"<th>{_cell(cells, column, 1)}</th>"
            for column in range(1, columns + 1)
        ) + "</tr>")

    lines = [
        "<tr>" + "".join(
            f"<td>{_cell(cells, column, row)}</td>"
            for column in range(1, columns + 1)
        ) + "</tr>"
        for row in range(2 if chosen["repeat_head"] else 1, rows + 1)
    ]

    thead = f'<thead>{"".join(header_rows)}</thead>' if header_rows else ""
    return (
        f'<div class="tabblock{break_}">{title}'
        f'<table class="grid">{thead}<tbody>{"".join(lines)}</tbody></table></div>'
    )


def _cell(cells: dict, column: int, row: int) -> str:
    # `_label` is zero-based — `_label(0)` is "A" — and every column
    # index here is the one-based number `codec.extent` counts in.
    value = cells.get(f"{codec._label(column - 1)}{row}", "")
    return frappe.utils.escape_html(str(value if value is not None else ""))


def _titled(tab: str, chosen: dict, many: bool) -> str:
    """The tab's name over it, when there is more than one tab to tell apart."""
    if not (chosen["tab_titles"] and many):
        return ""
    return f'<h2 class="tab">{frappe.utils.escape_html(tab)}</h2>'


def _scale_css(scale: int) -> str:
    """Smaller, by making the type smaller.

    `zoom` rather than `transform: scale()`, which scales the box and not the
    layout — a transformed table prints at its original size with the ink in
    the wrong place. `zoom` is not in any standard and is in every engine,
    including the print paths, which is the only test that matters here.
    """
    if scale == 100:
        return ""
    return f"table.grid {{ zoom: {scale / 100:.2f}; }}\n"


#: Enough style that a printed sheet reads as a spreadsheet. Not our design
#: tokens, for the same reason `docs/export.py` does not use them: this page is
#: rendered where our stylesheet is not.
_STYLE = """
body { font: 12px/1.4 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
       color: #1f2933; }
h2.tab { font-size: 14px; margin: 0 0 8px; color: #52606d; }
p.empty { color: #7b8794; }
table.grid { border-collapse: collapse; }
table.grid td, table.grid th { border: 1px solid #cbd2d9; padding: 3px 6px;
                               text-align: left; vertical-align: top;
                               white-space: pre-wrap; }
table.grid th { background: #f5f7fa; font-weight: 600; }
div.tabblock.break { break-before: page; }
tr.head > td { border: 0; padding: 0; }
@media print {
  table.grid thead { display: table-header-group; }
  table.grid tr { break-inside: avoid-page; }
}
"""
