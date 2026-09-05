"""A sheet as bytes, for the one moment it has to be a file.

Everywhere else a sheet is rows: the grid reads `Sheet Cell`, the read-back
reads a named rectangle, a print format reads `value`. Nobody needs bytes until
somebody wants to mail one, and then they want a spreadsheet rather than our
table.

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

from . import refs
from .reading import _mine

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
    missing, and every reader of an exported sheet wants the numbers. `raw` is
    for the grid and stays there.
    """
    doc = _mine(name, "read")
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
    if not tab:
        first = frappe.get_all(
            "Sheet Tab", filters={"sheet": sheet}, fields=["tab_name"],
            order_by="position asc", limit=1,
        )
        tab = first[0]["tab_name"] if first else "Sheet1"

    cells = frappe.get_all(
        "Sheet Cell", filters={"sheet": sheet, "tab": tab},
        fields=["ref", "value"], limit_page_length=0,
    )

    grid, rows, columns = {}, 0, 0
    for cell in cells:
        try:
            row, column = refs.parse(cell["ref"])
        except refs.BadRef:
            continue
        grid[(row, column)] = cell["value"] or ""
        rows, columns = max(rows, row), max(columns, column)

    return grid, (rows, columns)
