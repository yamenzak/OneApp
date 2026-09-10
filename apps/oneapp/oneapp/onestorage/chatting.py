"""The conversation about a file, as opposed to the one inside it.

A sheet has notes on cells and a document will have them on paragraphs. This
is the other thing people want, and it is not the same thing: "are these the
March rates or April's?", asked about the whole workbook, by somebody who does
not want to attach it to a cell because it is not about a cell.

Frappe's `Comment`, with `reference_doctype` of `File`. Three reasons and the
third is the one that decided it:

  * the storage, the permission rule and the bookkeeping already exist, which
    is the same argument `onespace/collab.py` makes about `DocShare`;
  * a comment on a file then turns up in the same notification feed and the
    same activity timeline as a comment on a record, rather than in a second
    feed nobody checks;
  * **`Comment.after_insert` calls `notify_mentions`.** An `@` in a note is a
    notification to that person, with a link back, for nothing — and writing
    our own store would have meant writing that too, worse.

What is ours is the gate. `Comment` is granted to System Manager and our
members are Website Users by design, so the insert is `ignore_permissions`
behind a check on the *file*, which is the permission that actually decides.
The same shape `spaceview.comment` uses for a record.
"""

import frappe
from frappe import _

# How many come back. A file's conversation is not a mailing list; the ones
# that matter are the recent ones, and a workbook with more than this has a
# different problem.
PAGE = 100

# Characters in one note. The same cap the record surface uses — this is a
# remark about a file, not the file.
MAX_CHARS = 5000


def _readable(file: str):
    """The file, if this person may open it. The permission check for both."""
    doc = frappe.get_doc("File", file)
    doc.check_permission("read")
    return doc


@frappe.whitelist(methods=["GET"])
def notes(file: str) -> dict:
    """Everything said about this file, oldest first.

    Oldest first, unlike the record timeline: that is a feed of events and
    reads newest-first like any feed, and this is a conversation, which reads
    in the order it was had.
    """
    _readable(file)

    rows = frappe.get_all(
        "Comment",
        filters={"reference_doctype": "File", "reference_name": file,
                 "comment_type": "Comment"},
        fields=["name", "content", "comment_email", "comment_by", "creation"],
        order_by="creation asc",
        limit_page_length=PAGE,
    )
    return {
        "notes": [
            {
                "name": row["name"],
                "content": row["content"],
                "by": row["comment_email"],
                "name_of": row["comment_by"] or row["comment_email"],
                "at": str(row["creation"]),
                "mine": row["comment_email"] == frappe.session.user,
            }
            for row in rows
        ],
        "count": frappe.db.count("Comment", {
            "reference_doctype": "File", "reference_name": file,
            "comment_type": "Comment",
        }),
    }


@frappe.whitelist(methods=["POST"])
def say(file: str, content: str) -> dict:
    """Add a note to a file.

    `read`, not `write`. Somebody a sheet was shared with read-only is exactly
    the person who has something to say about it and cannot change it, and
    refusing them the remark would leave them nowhere to put it.
    """
    _readable(file)

    content = (content or "").strip()
    if not content:
        frappe.throw(_("A note needs something in it."))

    added = frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Comment",
        "reference_doctype": "File",
        "reference_name": file,
        "content": content[:MAX_CHARS],
        "comment_email": frappe.session.user,
        "comment_by": frappe.utils.get_fullname(frappe.session.user),
    }).insert(ignore_permissions=True)

    return {
        "name": added.name,
        "content": added.content,
        "by": added.comment_email,
        "name_of": added.comment_by or added.comment_email,
        "at": str(added.creation),
        "mine": True,
    }


@frappe.whitelist(methods=["POST"])
def unsay(name: str) -> dict:
    """Take a note back.

    Yours only, and not on a `write` check on the file: being able to change a
    workbook is not the same as being able to delete what somebody said about
    it, and a conversation an editor can quietly edit is not a record of
    anything.
    """
    row = frappe.get_doc("Comment", name)
    if row.reference_doctype != "File" or row.comment_email != frappe.session.user:
        frappe.throw(_("That is not yours to remove."), frappe.PermissionError)

    _readable(row.reference_name)
    frappe.delete_doc("Comment", name, ignore_permissions=True)
    return {"ok": True, "removed": name}
