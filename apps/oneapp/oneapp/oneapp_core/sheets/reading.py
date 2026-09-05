"""Reading a rectangle out of a workbook.

Every read here checks `File` and not `Sheet Book`. A sheet's permission is its
File's — that is the whole reason a sheet is a File — so the workbook has no
access rules of its own and must never be asked for any: `Sheet Book` is granted
to System Manager only, and every path in is one of these functions or
`book.get_sheet`.

`value` and never `raw`. The server does not evaluate formulas and does not need
to: the browser wrote down what each one came to, in the `values` slice, and a
caller that wanted `=A2*B2` rather than `6480` is a caller doing something else.
`codec.values_map` is the whole of that decision.
"""

import frappe
from frappe import _

from . import book, codec, refs
from .book import _mine  # noqa: F401  — the permission gate, re-exported

MAX_CELLS = refs.MAX_CELLS


def tabs(sheet: str) -> list[str]:
    """The tabs of a sheet, left to right. Always at least one."""
    return codec.tab_names(book.load(sheet))


def ranges(sheet: str) -> list[dict]:
    """The named ranges, as `[{label, tab, ref}, …]`, alphabetically.

    Flattened out of the engine's own store, which keys them upper-case and
    keeps the typed capitalisation inside. Everything downstream — the feed,
    the fill control, the preview — wants the label as somebody wrote it.
    """
    entries = codec.named_ranges(book.load(sheet))
    out = [
        {
            "label": row.get("name") or key,
            "tab": row.get("sheet") or "",
            "ref": row.get("range") or "",
        }
        for key, row in entries.items()
    ]
    return sorted(out, key=lambda row: row["label"].lower())


@frappe.whitelist(methods=["GET"])
def read_range(sheet: str, label: str = "", tab: str = "", ref: str = "") -> dict:
    """A rectangle, as a grid of values.

    Named or literal. The named form is the one that matters: a named range is
    the contract between a sheet and whatever reads it — see `docs/SHEETS.md`
    §3 — and everything outside it is the estimator's working, which is nobody
    else's business.
    """
    _mine(sheet)
    return _read(book.load(sheet), label=label, tab=tab, ref=ref)


def _read(loaded: dict, label: str = "", tab: str = "", ref: str = "") -> dict:
    """The same read, for a caller that has the workbook in hand already.

    The feed reads a range and then reads it again to count what it wrote;
    going through `read_range` twice would gunzip and parse the workbook twice
    for one press of a button.
    """
    if label:
        found = codec.named_ranges(loaded).get(str(label).upper())
        if not found:
            frappe.throw(_("This sheet has no range called {0}.").format(label))
        tab, ref = found.get("sheet") or "", found.get("range") or ""

    if not tab or not ref:
        frappe.throw(_("Which range?"))

    top, left, bottom, right = refs.parse_range(ref)
    cells = codec.values_map(loaded, tab)
    inside = {key: value for key, value in cells.items() if refs.within(key, ref)}

    return {
        "tab": tab,
        "ref": refs.format_range(top, left, bottom, right),
        "values": refs.grid(inside, ref),
    }
