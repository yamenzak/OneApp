"""A sheet as bytes, for the one moment it has to be a file.

Everywhere else a sheet is a workbook: the grid loads it whole, the read-back
reads a named rectangle out of it, a print format reads a value. Nobody needs
bytes until somebody wants to mail one, and then they want a spreadsheet rather
than our column.

CSV, and one tab at a time, because that is what a CSV is. Workbook-shaped
export — every tab, formats, formulas — is xlsx and is Stage 6.

This module also exists for a smaller reason worth writing down, because it
looks like a workaround and is one. `File.validate` refuses a row whose
`file_url` names nothing: it must be under `/files/`, `/private/files/`, or one
of `URL_PREFIXES = ("http://", "https://", "/api/method/")`, and the last of
those is the framework's own escape hatch for a file whose bytes are produced
rather than stored. A sheet's bytes are produced. So a sheet's `file_url` is
this endpoint, which is true rather than convenient: follow it and you get the
file the row claims to be.
"""

import csv
import io

import frappe

from . import book, codec
from .book import _mine

#: The endpoint every sheet's `File.file_url` points at. Bare, because the row
#: is inserted before it has a name — `writing.make` appends `?name=…` the
#: moment the insert returns.
ROUTE = "/api/method/oneapp.oneapp_core.sheets.download"


def url_for(sheet: str) -> str:
    return f"{ROUTE}?name={sheet}"


@frappe.whitelist(methods=["GET"])
def download(name: str, tab: str = "") -> None:
    """Send one tab as a CSV.

    Values and not formulas: a CSV holding `=A2*B2` is a CSV whose numbers are
    missing, and every reader of an exported sheet wants the numbers. What was
    typed is the grid's business and stays there.
    """
    to_response(_mine(name, "read"), tab)


def to_response(doc, tab: str = "") -> None:
    """The same CSV, for a caller that has already settled the permission.

    Two entry points because there are two kinds of reader. This one is
    `storage.r2.serve`, which is the single funnel every download and every
    expiring share link goes through — and which, before this existed, asked a
    sheet for bytes it does not have and answered 500. A shared sheet is a
    shared spreadsheet; what a stranger following the link should get is the
    file, which is this.
    """
    name = doc.name
    grid, used = _grid(name, tab)

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in range(1, used[0] + 1):
        writer.writerow([grid.get((row, column), "") for column in range(1, used[1] + 1)])

    title = doc.file_name or "sheet"
    if not title.lower().endswith(".csv"):
        title = f"{title}.csv"

    # A BOM, because the overwhelming majority of people opening an exported
    # quotation open it in Excel, and Excel reads a CSV without one as Latin-1
    # — which turns every dirham sign and every Arabic name into mojibake.
    frappe.local.response.filename = title
    frappe.local.response.filecontent = ("﻿" + buffer.getvalue()).encode("utf-8")
    frappe.local.response.type = "download"


def _grid(sheet: str, tab: str = "") -> tuple[dict, tuple[int, int]]:
    """Every value on a tab, by (row, column), and the extent of it.

    The extent is the furthest cell anybody wrote, not the tab's nominal size:
    a sheet used down to row 40 exports forty rows however far the grid on
    screen scrolls.
    """
    loaded = book.load(sheet)
    if not tab:
        tab = codec.current_tab(loaded)

    cells = codec.values_map(loaded, tab)
    grid = {}
    for ref, value in cells.items():
        row, column = codec._parse(ref)
        if row:
            grid[(row, column)] = value if value is not None else ""

    return grid, codec.extent(cells)
