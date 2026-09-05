"""Opening a workbook and saving one — the two calls the editor makes.

The grid is Frappe's (`frontend/src/lib/sheets/VENDORED.md`) and it speaks a
small, blunt protocol: hand me the whole workbook, and take the whole workbook
back. `get_sheet` and `save_sheet` are that protocol, named as the editor names
them, over a `File` rather than over a `Sheet` doctype.

Everything a sheet *is* — its name, owner, folder, share, place in the bin, the
record it hangs off — is the File's, so nothing about identity is written here.
What is written here is the two questions the File cannot answer: what is in the
grid, and may this person change it.

A save is idempotent and total. There is no partial write, no cell endpoint and
no merge: the browser is the only thing that understands the workbook, so the
last save wins by construction rather than by a rule anyone has to remember.
"""

import json

import frappe
from frappe import _

from . import codec

TITLE_MAX = 280


def _mine(sheet: str, level: str = "read"):
    """The File behind a sheet, if this person may have it at that level."""
    doc = frappe.get_doc("File", sheet)
    if doc.get("custom_kind") != "Sheet":
        frappe.throw(_("That file is not a sheet."))
    doc.check_permission(level)
    return doc


def load(sheet: str) -> dict:
    """The workbook as a dict, for server-side readers. No permission check.

    Callers have already settled access — `_mine`, or `r2.serve`, which is the
    one funnel every download and every share link goes through. Kept separate
    from `get_sheet` so a reader that wants three cells does not have to think
    about compression flags or about what the editor happens to need.
    """
    stored = frappe.db.get_value("Sheet Book", sheet, "payload")
    return codec.workbook(stored)


def store(sheet: str, payload: str) -> int:
    """Replace a workbook's stored blob. Returns the new save count."""
    size = codec.size_of(payload)
    if size > codec.MAX_BYTES:
        codec._too_big()

    existing = frappe.db.exists("Sheet Book", sheet)
    if existing:
        head = (frappe.db.get_value("Sheet Book", sheet, "head_seq") or 0) + 1
        frappe.db.set_value("Sheet Book", sheet, {
            "payload": payload, "byte_size": size, "head_seq": head,
        }, update_modified=False)
    else:
        head = 1
        frappe.get_doc({
            "doctype": "Sheet Book", "sheet": sheet, "payload": payload,
            "byte_size": size, "head_seq": head,
        }).insert(ignore_permissions=True)
    return head


@frappe.whitelist(methods=["GET"])
def get_sheet(name: str, compressed: int = 0) -> dict:
    """Everything the editor needs to draw a workbook, in one request.

    `compressed` is the browser saying it can gunzip. When it can, the stored
    envelope goes over the wire untouched — a megabyte and a half rather than
    twenty — and the page decompresses it. When it cannot, we decompress here.
    Either way what arrives is the same JSON.
    """
    doc = _mine(name)
    stored = frappe.db.get_value("Sheet Book", name, "payload")

    return {
        "name": doc.name,
        "title": doc.file_name,
        "folder": doc.folder,
        "owner": doc.owner,
        "attached_to": {
            "doctype": doc.attached_to_doctype or "",
            "docname": doc.attached_to_name or "",
        },
        # Asked rather than assumed, so a control that is drawn and a write
        # that is allowed read the same flag at the same moment.
        "can_write": bool(frappe.has_permission("File", "write", doc=doc)),
        "is_template": bool(doc.get("custom_is_template")),
        "sheets_data": stored if frappe.utils.cint(compressed) else codec.decode(stored),
    }


@frappe.whitelist(methods=["POST"])
def save_sheet(name: str, sheets_data: str, title: str = "") -> dict:
    """Write the workbook back, and rename the file if the title moved.

    The title travels with the save because in this editor it is edited in the
    same header as the grid — there is no separate Save, so there is no other
    moment to send it. It is the File's `file_name`, not a field of our own: a
    sheet renamed here is renamed in the Drive, which is the only behaviour
    that could be right when the two are the same object.
    """
    doc = _mine(name, "write")

    head = store(name, sheets_data)

    clean = (title or "").strip()[:TITLE_MAX]
    if clean and clean != doc.file_name:
        # Through the Drive so a rename is one thing wherever it starts —
        # `custom_kind` survives it, and a name collision in a folder is
        # settled the same way it is when somebody renames from the file list.
        from ..drive import writing as drive

        drive.rename(name, clean)

    # A cell is not a File row, so nothing else marks the sheet as touched —
    # and "the sheet has moved on since these rows were pulled" is read off
    # exactly this timestamp. See `feed._with_freshness`.
    doc.db_set("modified", frappe.utils.now(), update_modified=False)

    return {"name": name, "head_seq": head}


def blank() -> str:
    """The payload of a workbook nobody has typed in yet.

    One empty tab called Sheet1, in the packed shape the editor writes, so a
    freshly made sheet loads through exactly the same path as one that has been
    saved a hundred times.
    """
    empty = {"v": codec.PACK_VERSION, "current": "Sheet1", "sheets": {"Sheet1": {"rows": {}}}}
    return codec.encode(json.dumps({"sheet": empty, "values": empty}))
