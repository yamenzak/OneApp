"""A document somebody starts from.

The same feature `sheets/templates.py` is, in the same shape and for the same
reason: a template is a file with a flag on it. Managing them is managing files
— no second screen, no second permission model, and a template shared with a
colleague is `DocShare` like everything else. The Drive's Templates rail entry
is that same flag read as a place.

One shape rather than two is the point. A person who has made a sheet template
already knows how to make a document one, and the Drive's New menu offers both
from the same list.
"""

import frappe
from frappe import _

from ..onestorage import kinds

#: One name for the flag, in `drive/kinds.py` beside the other columns this
#: product adds to `File` — a sheet template and a document template are the
#: same column and the Drive's Templates place reads it too.
TEMPLATE_FIELD = kinds.TEMPLATE_FIELD


@frappe.whitelist(methods=["GET"])
def listing() -> list[dict]:
    """Every document template this person can see.

    `get_list` and not `get_all`: a template is a File, a File may be shared or
    not, and the Drive's whole access model is that one word.
    """
    return frappe.get_list(
        "File",
        filters={
            "custom_kind": kinds.DOC,
            TEMPLATE_FIELD: 1,
            "custom_status": ["in", ["Active", "", None]],
        },
        fields=["name", "file_name", "folder", "modified", "owner"],
        # Newest first, because the New menu shows six of these and
        # alphabetical order hides the one somebody just made behind five
        # they have not touched in a year.
        order_by="modified desc",
        limit_page_length=100,
    )


@frappe.whitelist(methods=["POST"])
def set_template(doc: str, on: str | int = 1) -> dict:
    """Mark a document as one to start from, or stop.

    `write` and not `share`: making a template is a statement about your own
    file. Whether anybody else can *see* it is the share, which is separate and
    already exists.
    """
    row = frappe.get_doc("File", doc)
    if row.get(kinds.KIND_FIELD) != kinds.DOC:
        frappe.throw(_("That file is not a document."))
    row.check_permission("write")

    wanted = 1 if frappe.utils.sbool(on) else 0
    row.db_set(TEMPLATE_FIELD, wanted, update_modified=False)
    return {"name": doc, "is_template": bool(wanted)}
