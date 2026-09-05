"""Making a sheet, copying one, and cleaning up after one.

Changing a sheet is not here. There is no cell endpoint, no tab endpoint and no
range endpoint any more: the browser holds the whole workbook and
`book.save_sheet` takes the whole workbook back. That is a real loss of
granularity and it buys something worth more — one writer, so a save cannot
race a rename or half-land a paste, and no second store for the grid to drift
away from. `book.py` says the rest.

What remains here is the three moments a sheet is a *file* rather than a grid:
it comes into existence, it is copied from a template, and it is thrown away.
"""

import frappe
from frappe import _

from . import book, export


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

    book.store(doc.name, copy_of(template) if template else book.blank())

    return {"name": doc.name, "title": doc.file_name, "url": f"/one/sheets/{doc.name}"}


def copy_of(source: str) -> str:
    """One sheet's stored workbook, for another sheet to start from.

    What a template is — see `templates.py`. Not a `File` copy: a sheet's
    content is this column, and the R2 object a Drive copy would duplicate does
    not exist.
    """
    frappe.get_doc("File", source).check_permission("read")
    return frappe.db.get_value("Sheet Book", source, "payload") or book.blank()


def on_trash(doc, method=None):
    """A sheet's workbook goes when its File does.

    Registered on `File`, because that is the document being deleted. Without
    it the bin's thirty-day sweep would leave the workbook of every sheet
    anybody ever threw away.
    """
    if doc.get("custom_kind") != "Sheet":
        return
    frappe.db.delete("Sheet Book", {"sheet": doc.name})

    # `Sheet Feed` deliberately survives. "These lines came off Padel Pro
    # estimator on the 3rd" is worth keeping precisely when the estimator is
    # not — which is why `Sheet Feed.sheet` is `Data` rather than a `Link`.
