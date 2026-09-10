"""A sheet somebody starts from.

A template is a sheet with a flag on it, and "new from template" copies its
rows. That is the whole feature, and it is small because a sheet is a `File`:
managing them is managing files — no second screen, no second permission model,
and a template shared with a colleague is `DocShare` like everything else. The
Drive's Templates rail entry is that same flag read as a place, so a template
stays wherever its owner filed it rather than being moved to a folder.

RUA did this against somebody else's API — `create_sheet_from_template` was a
Google Drive `files.copy` with polling and a permissions grant afterwards, and
about a hundred lines of error handling for the ways that fails over a network.
Ours is an insert.
"""

import frappe
from frappe import _

from ..onestorage import kinds
from ..shared.binding import BOUND_FIELD

#: One name for the flag, in `drive/kinds.py` beside the other columns this
#: product adds to `File` — a sheet template and a document template are the
#: same column and the Drive's Templates place reads it too.
TEMPLATE_FIELD = kinds.TEMPLATE_FIELD


@frappe.whitelist(methods=["GET"])
def listing() -> list[dict]:
    """Every template this person can see.

    `get_list` and not `get_all`: a template is a File, a File may be shared or
    not, and the Drive's whole access model is that one word.
    """
    return frappe.get_list(
        "File",
        filters={
            kinds.KIND_FIELD: kinds.SHEET,
            TEMPLATE_FIELD: 1,
            "custom_status": ["in", ["Active", "", None]],
        },
        # The record kind this template is for, if it is for one — the same
        # column a document template carries, read by the picker so it can
        # ask which record before making the workbook.
        fields=["name", "file_name", "folder", "modified", "owner",
                f"{BOUND_FIELD} as bound_doctype"],
        # Newest first, because the New menu shows six of these and
        # alphabetical order hides the one somebody just made behind five
        # they have not touched in a year.
        order_by="modified desc",
        limit_page_length=100,
    )


@frappe.whitelist(methods=["POST"])
def set_template(sheet: str, on: str | int = 1) -> dict:
    """Mark a sheet as one to start from, or stop.

    `write` and not `share`: making a template is a statement about your own
    file. Whether anybody else can *see* it is the share, which is separate and
    already exists.
    """
    doc = frappe.get_doc("File", sheet)
    if doc.get("custom_kind") != "Sheet":
        frappe.throw(_("That file is not a sheet."))
    doc.check_permission("write")

    wanted = 1 if frappe.utils.sbool(on) else 0
    doc.db_set(TEMPLATE_FIELD, wanted, update_modified=False)
    return {"name": sheet, "is_template": bool(wanted)}
