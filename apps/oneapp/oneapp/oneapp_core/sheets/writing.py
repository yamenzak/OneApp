"""Making a sheet, and changing one.

Every write checks `write` on the File, for the same reason every read checks
`read` on it: a sheet's permission is its File's, and `Sheet Cell` has none of
its own.

The one thing worth understanding before editing this file is that **a cell edit
is a batch**. A person typing in one cell changes one cell; a person pasting a
column changes four hundred, and every one of them is a row. So the endpoint
takes a list and writes it in as few statements as it can — one existence query
for the batch, then inserts and updates. A loop of `frappe.get_doc().save()`
over four hundred cells is four hundred round trips and about a minute.
"""

import json

import frappe
from frappe import _

from . import export, refs
from .reading import MAX_CELLS, _mine

# Blank is not a value; it is the absence of one. A cell cleared by a person is
# a row deleted rather than a row holding "", so an empty sheet is an empty
# table and the cell count means what it says.
EMPTY = ("", None)


@frappe.whitelist(methods=["POST"])
def make(title: str = "", folder: str = "", doctype: str = "", docname: str = "",
         template: str = "") -> dict:
    """A new sheet, which is a new `File` of kind Sheet.

    `doctype`/`docname` attach it to a record, using the same two columns every
    attachment in the product uses — which is what makes "the quotation's
    estimator" a query rather than a feature.
    """
    title = (title or "").strip() or "Untitled sheet"

    if doctype and docname and not frappe.has_permission(doctype, "write", doc=docname):
        frappe.throw(_("You cannot change that record."), frappe.PermissionError)

    doc = frappe.get_doc({
        "doctype": "File",
        "file_name": title,
        "is_folder": 0,
        "folder": folder or "Home",
        "is_private": 1,
        "attached_to_doctype": doctype or None,
        "attached_to_name": docname or None,
        # Nothing about the name says this is a sheet, so `kinds.on_insert`
        # cannot work it out and is told instead.
        "custom_kind": "Sheet",
        "custom_status": "Active",
        # A sheet's bytes do not exist until somebody exports it, so there is
        # no object and no key — see `docs/SHEETS.md` §5 Stage 1. `File`
        # refuses a row whose URL names nothing, and its own exception for a
        # produced file is a `/api/method/` URL, so a sheet's URL is the
        # exporter. Bare here and completed below, because the row has no name
        # until the insert returns.
        "file_url": export.ROUTE,
    }).insert()

    doc.db_set("file_url", export.url_for(doc.name), update_modified=False)

    if template:
        copy_into(doc.name, template)
    else:
        add_tab(doc.name, "Sheet1")

    return {"name": doc.name, "title": doc.file_name, "url": f"/one/sheets/{doc.name}"}


@frappe.whitelist(methods=["POST"])
def write_cells(sheet: str, cells: str | list) -> dict:
    """Write a batch of cells, and delete the ones that were cleared.

    `cells` is `[{tab, ref, raw, value, kind, format_json}, …]` — what the
    browser computed, not what it wants computed. The server stores `raw` and
    `value` side by side and never looks at `raw` again; see `docs/SHEETS.md`
    §1 and §3 for why that is the design rather than a shortcut.
    """
    doc = _mine(sheet, "write")
    rows = frappe.parse_json(cells) if isinstance(cells, str) else cells
    if not isinstance(rows, list):
        frappe.throw(_("Cells arrive as a list."))

    # Existing rows for exactly the cells in this batch, in one query. The
    # alternative is a `get_value` per cell, which is what made pasting slow.
    wanted = {}
    for row in rows:
        tab = (row.get("tab") or "Sheet1").strip()
        ref = (row.get("ref") or "").strip().upper()
        refs.parse(ref)          # refuses anything that is not a cell
        wanted[(tab, ref)] = row

    existing = {
        (row["tab"], row["ref"]): row["name"]
        for row in frappe.get_all(
            "Sheet Cell",
            filters={"sheet": sheet, "ref": ["in", [ref for _t, ref in wanted]]},
            fields=["name", "tab", "ref"], limit_page_length=0,
        )
        if (row["tab"], row["ref"]) in wanted
    }

    written, cleared = 0, 0
    for (tab, ref), row in wanted.items():
        raw = row.get("raw")
        value = row.get("value")
        blank = raw in EMPTY and value in EMPTY

        if blank:
            if (tab, ref) in existing:
                frappe.delete_doc("Sheet Cell", existing[(tab, ref)],
                                  ignore_permissions=True, force=True)
                cleared += 1
            continue

        payload = {
            "raw": None if raw is None else str(raw),
            "value": None if value is None else str(value),
            "kind": row.get("kind") or "",
            "format_json": _format(row.get("format_json")),
        }

        if (tab, ref) in existing:
            frappe.db.set_value("Sheet Cell", existing[(tab, ref)], payload,
                                update_modified=False)
        else:
            _guard_size(sheet)
            frappe.get_doc({
                "doctype": "Sheet Cell", "sheet": sheet, "tab": tab, "ref": ref,
                **payload,
            }).insert(ignore_permissions=True)
        written += 1

    _touch(doc)
    return {"written": written, "cleared": cleared}


def _format(value) -> str | None:
    """A cell's presentation, as a JSON string, or nothing.

    Nothing rather than `{}`: an unformatted cell is the overwhelming majority
    of them, and two bytes each over twenty thousand cells is a table that is
    mostly empty braces.
    """
    if not value:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))


def _guard_size(sheet: str) -> None:
    """Refuse the cell that would take a sheet past its cap.

    Checked on insert only — an update replaces a row and cannot grow the
    table. `docs/SHEETS.md` §7 is the argument for having a cap at all: a row
    per cell is what makes the read-back a query, and it is the wrong shape for
    a million cells, so the limit is chosen rather than discovered.
    """
    if frappe.db.count("Sheet Cell", {"sheet": sheet}) >= MAX_CELLS:
        frappe.throw(
            _("A sheet holds {0:,} cells. This one is full — split it, or move "
              "the working out into a second sheet.").format(MAX_CELLS)
        )


def _touch(doc) -> None:
    """Mark the File modified, so the Drive shows a sheet as recently changed.

    A cell is not a File row, so nothing else would.
    """
    doc.db_set("modified", frappe.utils.now(), update_modified=False)


# --------------------------------------------------------------------------- #
# Tabs
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def add_tab(sheet: str, tab_name: str = "") -> dict:
    """A new tab, named or numbered.

    Numbered when unnamed, and numbered around what is already there: a
    workbook whose second tab was deleted gets `Sheet3` next rather than a
    duplicate `Sheet2`, because the name is a unique key here.
    """
    doc = _mine(sheet, "write")
    existing = [row["tab_name"] for row in frappe.get_all(
        "Sheet Tab", filters={"sheet": sheet}, fields=["tab_name"])]

    name = (tab_name or "").strip() or _next_name(existing)
    if name in existing:
        frappe.throw(_("This sheet already has a tab called {0}.").format(name))

    made = frappe.get_doc({
        "doctype": "Sheet Tab", "sheet": sheet, "tab_name": name,
        "position": len(existing),
    }).insert(ignore_permissions=True)
    _touch(doc)
    return {"name": made.name, "tab_name": name, "position": made.position}


def _next_name(existing: list[str]) -> str:
    number = len(existing) + 1
    while f"Sheet{number}" in existing:
        number += 1
    return f"Sheet{number}"


@frappe.whitelist(methods=["POST"])
def rename_tab(sheet: str, tab: str, tab_name: str) -> dict:
    """Rename a tab, and carry its cells with it.

    `Sheet Cell.tab` is a name and not a link precisely so this is one
    statement rather than a rewrite of every row the tab holds. The cost is
    that the two have to be kept in step here, which is the trade this makes on
    purpose.
    """
    doc = _mine(sheet, "write")
    name = (tab_name or "").strip()
    if not name:
        frappe.throw(_("A tab needs a name."))
    if name == tab:
        return {"tab_name": name}

    taken = frappe.db.exists("Sheet Tab", {"sheet": sheet, "tab_name": name})
    if taken:
        frappe.throw(_("This sheet already has a tab called {0}.").format(name))

    row = frappe.db.exists("Sheet Tab", {"sheet": sheet, "tab_name": tab})
    if row:
        frappe.db.set_value("Sheet Tab", row, "tab_name", name, update_modified=False)

    frappe.db.set_value("Sheet Cell", {"sheet": sheet, "tab": tab}, "tab", name,
                        update_modified=False)
    frappe.db.set_value("Sheet Range", {"sheet": sheet, "tab": tab}, "tab", name,
                        update_modified=False)
    _touch(doc)
    return {"tab_name": name}


@frappe.whitelist(methods=["POST"])
def remove_tab(sheet: str, tab: str) -> dict:
    """Drop a tab and everything on it.

    Never the last one. A workbook with no tabs is a grid with nowhere to type,
    and the empty state for it would be a screen explaining a state nobody
    meant to reach.
    """
    doc = _mine(sheet, "write")
    rows = frappe.get_all("Sheet Tab", filters={"sheet": sheet}, fields=["name", "tab_name"])
    if len(rows) <= 1:
        frappe.throw(_("A sheet keeps at least one tab."))

    for row in rows:
        if row["tab_name"] == tab:
            frappe.delete_doc("Sheet Tab", row["name"], ignore_permissions=True, force=True)

    frappe.db.delete("Sheet Cell", {"sheet": sheet, "tab": tab})
    frappe.db.delete("Sheet Range", {"sheet": sheet, "tab": tab})
    _touch(doc)
    return {"ok": True}


@frappe.whitelist(methods=["POST"])
def set_tab_geometry(sheet: str, tab: str, column_widths: str = "",
                     row_heights: str = "", frozen_rows: int = 0,
                     frozen_columns: int = 0) -> dict:
    """What somebody dragged: column widths, row heights, frozen panes."""
    doc = _mine(sheet, "write")
    row = frappe.db.exists("Sheet Tab", {"sheet": sheet, "tab_name": tab})
    if not row:
        frappe.throw(_("This sheet has no tab called {0}.").format(tab))

    frappe.db.set_value("Sheet Tab", row, {
        "column_widths": column_widths or None,
        "row_heights": row_heights or None,
        "frozen_rows": int(frozen_rows or 0),
        "frozen_columns": int(frozen_columns or 0),
    }, update_modified=False)
    _touch(doc)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Named ranges — the contract, `docs/SHEETS.md` §3
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["POST"])
def set_range(sheet: str, label: str, tab: str, ref: str) -> dict:
    """Name a rectangle, or move the one that has this name."""
    doc = _mine(sheet, "write")
    name = (label or "").strip()
    if not name:
        frappe.throw(_("A range needs a name."))
    refs.parse_range(ref)

    existing = frappe.db.exists("Sheet Range", {"sheet": sheet, "label": name})
    if existing:
        frappe.db.set_value("Sheet Range", existing, {"tab": tab, "ref": ref},
                            update_modified=False)
    else:
        frappe.get_doc({
            "doctype": "Sheet Range", "sheet": sheet, "label": name,
            "tab": tab, "ref": ref,
        }).insert(ignore_permissions=True)
    _touch(doc)
    return {"label": name, "tab": tab, "ref": ref}


@frappe.whitelist(methods=["POST"])
def remove_range(sheet: str, label: str) -> dict:
    """Forget a name. The cells stay; only the contract goes.

    Silent when there is nothing by that name, because the end state is what
    was asked for either way.
    """
    _mine(sheet, "write")
    existing = frappe.db.exists("Sheet Range", {"sheet": sheet, "label": label})
    if existing:
        frappe.delete_doc("Sheet Range", existing, ignore_permissions=True, force=True)
    return {"ok": True}


# --------------------------------------------------------------------------- #
# Copying
# --------------------------------------------------------------------------- #

def copy_into(sheet: str, source: str) -> int:
    """Every tab, cell and range of `source`, into `sheet`.

    What a template is made of — see `templates.py`. Not a `File` copy: a
    sheet's content is rows, so copying one is inserting rows, and the R2
    object a Drive copy would duplicate does not exist.
    """
    frappe.get_doc("File", source).check_permission("read")

    for tab in frappe.get_all(
        "Sheet Tab", filters={"sheet": source},
        fields=["tab_name", "position", "frozen_rows", "frozen_columns",
                "column_widths", "row_heights"],
    ) or [{"tab_name": "Sheet1", "position": 0}]:
        frappe.get_doc({"doctype": "Sheet Tab", "sheet": sheet, **tab}).insert(
            ignore_permissions=True)

    copied = 0
    for cell in frappe.get_all(
        "Sheet Cell", filters={"sheet": source},
        fields=["tab", "ref", "raw", "value", "kind", "format_json"],
        limit_page_length=MAX_CELLS,
    ):
        frappe.get_doc({"doctype": "Sheet Cell", "sheet": sheet, **cell}).insert(
            ignore_permissions=True)
        copied += 1

    for row in frappe.get_all(
        "Sheet Range", filters={"sheet": source}, fields=["label", "tab", "ref"],
    ):
        frappe.get_doc({"doctype": "Sheet Range", "sheet": sheet, **row}).insert(
            ignore_permissions=True)

    return copied


def on_trash(doc, method=None):
    """A sheet's rows go when its File does.

    Registered on `File`, because that is the document being deleted. Without
    it the bin's thirty-day sweep would leave the cells of every sheet anybody
    ever threw away.
    """
    if doc.get("custom_kind") != "Sheet":
        return
    for table in ("Sheet Cell", "Sheet Tab", "Sheet Range"):
        frappe.db.delete(table, {"sheet": doc.name})
