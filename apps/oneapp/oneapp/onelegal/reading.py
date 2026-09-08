"""What the browser asks for: the documents, and one document.

Read-only and open to anybody signed in. A person who is being asked to agree
to something has to be able to read it first, and somebody who agreed in March
has to be able to read what they agreed to — so a stored version can be fetched
by name as well.
"""

import frappe
from frappe import _

from . import assemble
from .documents import PARTY


@frappe.whitelist(methods=["GET"])
def catalogue() -> dict:
    """Every document, with its current version and who has to agree to it."""
    return {"party": PARTY, "documents": assemble.documents()}


@frappe.whitelist(methods=["GET"])
def document(key: str, version: str = "") -> dict:
    """One document — the current text, or the exact text of an old version.

    An old version comes from `Legal Document Version`, which is written the
    first time anybody agrees to it. Asking for a version nobody ever agreed to
    is not an error worth an exception: it answers with the current one and says
    which it gave you.
    """
    if version:
        stored = frappe.db.get_value(
            "Legal Document Version", f"{key}-{version}",
            ["title", "version", "revision", "audience", "html"], as_dict=True,
        )
        if stored:
            return {"key": key, "party": PARTY, "historic": True, **stored}

    try:
        return {**assemble.render(key), "historic": False}
    except KeyError:
        frappe.throw(_("There is no such document."))


@frappe.whitelist(methods=["GET"])
def history(key: str = "") -> list[dict]:
    """Every version this workspace has ever agreed to, newest first."""
    filters = {"document": key} if key else {}
    return frappe.get_all(
        "Legal Document Version", filters=filters,
        fields=["name", "document", "title", "version", "revision", "audience"],
        order_by="creation desc",
    )
