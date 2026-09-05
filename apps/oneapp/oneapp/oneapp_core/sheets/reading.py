"""Opening a sheet, and reading a rectangle out of one.

Every read here checks `File` and not `Sheet Cell`. A sheet's permission is its
File's — that is the whole reason a sheet is a File — so a cell has no access
rules of its own and must never be asked for any: `Sheet Cell` is granted to
System Manager only, and every path in is one of these functions.

`frappe.get_doc` then `check_permission`, rather than `get_list` over the cells.
The Drive's rule was "every read is `get_list`" because it lists rows a reader
may or may not see one by one. Here the question is asked once, about the sheet,
and answered before a single cell is fetched.
"""

import frappe
from frappe import _

from . import refs

# What one request will hand back. A sheet is opened whole — a spreadsheet with
# a page control would be a spreadsheet nobody could write a formula across —
# so this is the cap on a sheet, not on a page of one.
MAX_CELLS = refs.MAX_CELLS

FIELDS = ["tab", "ref", "raw", "value", "kind", "format_json"]


def _mine(sheet: str, level: str = "read"):
    """The File behind a sheet, if this person may have it at that level."""
    doc = frappe.get_doc("File", sheet)
    if doc.get("custom_kind") != "Sheet":
        frappe.throw(_("That file is not a sheet."))
    doc.check_permission(level)
    return doc


@frappe.whitelist(methods=["GET"])
def open_sheet(sheet: str) -> dict:
    """Everything needed to draw one: its tabs, its cells, its named ranges.

    One request rather than three. A spreadsheet is useless in pieces — the
    grid cannot draw until it knows the tabs, and a formula cannot resolve
    until it has the cells it points at — so a round trip per part would be
    three waits to see one thing.
    """
    doc = _mine(sheet)

    cells = frappe.get_all(
        "Sheet Cell", filters={"sheet": sheet}, fields=FIELDS,
        limit_page_length=MAX_CELLS + 1,
    )

    return {
        "name": doc.name,
        "title": doc.file_name,
        "folder": doc.folder,
        "attached_to": {
            "doctype": doc.attached_to_doctype or "",
            "docname": doc.attached_to_name or "",
        },
        # Asked rather than assumed, so a control that is drawn and a write
        # that is allowed read the same flag at the same moment.
        "can_write": bool(frappe.has_permission("File", "write", doc=doc)),
        "is_template": bool(doc.get("custom_is_template")),
        "tabs": tabs(sheet),
        "cells": cells,
        "ranges": ranges(sheet),
        "limit": MAX_CELLS,
    }


def tabs(sheet: str) -> list[dict]:
    """The tabs of a sheet, left to right.

    A sheet with no tab rows has one called `Sheet1`. Stored nothing, because a
    workbook always has at least one tab and writing that fact down would be
    writing down a default — and because a sheet made from an import or by a
    read-back should not have to remember to create it.
    """
    found = frappe.get_all(
        "Sheet Tab",
        filters={"sheet": sheet},
        fields=["name", "tab_name", "position", "frozen_rows", "frozen_columns",
                "column_widths", "row_heights"],
        order_by="position asc, creation asc",
    )
    if found:
        return found
    return [{
        "name": "", "tab_name": "Sheet1", "position": 0,
        "frozen_rows": 0, "frozen_columns": 0,
        "column_widths": None, "row_heights": None,
    }]


def ranges(sheet: str) -> list[dict]:
    return frappe.get_all(
        "Sheet Range", filters={"sheet": sheet},
        fields=["name", "label", "tab", "ref"], order_by="label asc",
    )


@frappe.whitelist(methods=["GET"])
def read_range(sheet: str, label: str = "", tab: str = "", ref: str = "") -> dict:
    """A rectangle, as a grid of values.

    Named or literal. The named form is the one that matters: a `Sheet Range`
    is the contract between a sheet and whatever reads it — see
    `docs/SHEETS.md` §3 — and everything outside it is the estimator's working,
    which is nobody else's business.

    `value` and not `raw`, always. The server does not evaluate formulas and
    does not need to: the browser wrote down what each one came to. A caller
    that wanted `=A2*B2` rather than `6480` is a caller doing something else.
    """
    _mine(sheet)

    if label:
        found = frappe.get_all(
            "Sheet Range", filters={"sheet": sheet, "label": label},
            fields=["tab", "ref"], limit_page_length=1,
        )
        if not found:
            frappe.throw(_("This sheet has no range called {0}.").format(label))
        tab, ref = found[0]["tab"], found[0]["ref"]

    if not tab or not ref:
        frappe.throw(_("Which range?"))

    top, left, bottom, right = refs.parse_range(ref)
    rows = frappe.get_all(
        "Sheet Cell",
        filters={"sheet": sheet, "tab": tab},
        fields=["ref", "value", "kind"],
        limit_page_length=MAX_CELLS,
    )
    inside = {
        row["ref"]: row for row in rows if refs.within(row["ref"], ref)
    }

    return {
        "tab": tab,
        "ref": refs.format_range(top, left, bottom, right),
        "values": refs.grid({k: v["value"] for k, v in inside.items()}, ref),
        "kinds": refs.grid({k: v["kind"] for k, v in inside.items()}, ref),
    }
