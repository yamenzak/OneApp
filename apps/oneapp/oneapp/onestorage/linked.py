"""A file a stranger can open — and, if the link says so, edit.

`sharing.py` built the read-only half: a row naming one file, 32 bytes of
secret in the URL, and a date. This is the other half, and it is the piece in
`docs/COLLABORATION.md` with a real security surface, which is why it is last
and why it is a module of its own rather than a flag on the endpoints the
signed-in editors use.

## Why not reuse `get_sheet` and `save_doc`

Because a guest has no permission and Frappe will not let one be granted. A
`has_permission` hook is the obvious mechanism and it does not work here:
`has_controller_permissions` says so in its own docstring — a controller can
deny and cannot grant. The alternatives are all worse: `ignore_permissions`
on the ordinary endpoints widens them for everybody, and a real `User` per
link is an account nobody asked for.

So the link's endpoints are their own narrow surface. Everything in this file
resolves a secret first and touches exactly the one file that secret names.
Nothing here takes a doctype, a filter or a fieldname from the caller.

## What a guest deliberately does not get

**The record rail.** A workbook's `RECORD()` formulas and a document's tokens
read the *workspace's* data, and the endpoints behind them are permission
checked and would refuse a guest anyway. Rather than let that surface as a
grid of errors, the payloads here carry no sources at all — a shared file is
the file, not a window onto the ledger behind it.

**A name.** A guest's edits are attributed to the link, because that is the
truth: the workspace gave a URL to somebody and does not know who is holding
it. Whoever made the link is the accountable party and the label they typed
is what the version history shows.

**Anything else in the workspace.** No listing, no folder, no other file, no
comments, no sharing. Three endpoints, and each one starts with the secret.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from . import kinds

# What a guest may send in one save. The signed-in path has no explicit cap
# because a person who can write the file can already fill it; a stranger
# with a URL is a different proposition, and a workbook this size is already
# far past anything a browser draws comfortably.
MAX_PAYLOAD = 12 * 1024 * 1024


def _link(secret: str):
    """The link this secret names, if it is still good.

    Every refusal is the same sentence for the reason `sharing.open_link`
    gives: a refusal that explains itself tells a stranger whether the secret
    was nearly right.
    """
    name = frappe.db.get_value("File Link", {"secret": secret}, "name") if secret else None
    link = frappe.get_doc("File Link", name) if name else None

    if not link or link.revoked or not link.expires_on:
        frappe.throw(_("This link is not available."), frappe.PermissionError)
    if get_datetime(link.expires_on) < now_datetime():
        frappe.throw(_("This link is not available."), frappe.PermissionError)
    return link


def _writable(secret: str):
    link = _link(secret)
    if (link.level or "read") != "write":
        frappe.throw(_("This link is read only."), frappe.PermissionError)
    return link


def _file(link):
    return frappe.get_doc("File", link.file)


def _shape(link, row) -> dict:
    """What the page needs to decide which editor to draw, and nothing else."""
    level = link.level or "read"
    return {
        "kind": row.get(kinds.KIND_FIELD) or "",
        "name": row.name,
        "title": row.file_name,
        "label": link.label or row.file_name,
        "level": level,
        # Named the way the signed-in payloads name it, so an editor that
        # asks "may I write?" gets its answer from the same key whichever
        # door it came in through.
        "can_write": level == "write",
        "expires_on": str(link.expires_on) if link.expires_on else "",
        # The editors read this to draw "saved a minute ago". Everything else
        # `get_doc` and `get_sheet` carry — the folder, the owner, whether it
        # is a template, what record it is attached to — is a fact about the
        # workspace's filing, and a link is not a window onto that.
        "modified": str(row.modified),
        # There is no rail through a link, and the editors read this to know
        # it. A `RECORD()` formula and a document token reach the workspace's
        # own data; a shared file is the file, not a window onto the ledger
        # behind it.
        "sources": [],
    }


@frappe.whitelist(allow_guest=True, methods=["GET"])
def follow(secret: str) -> dict:
    """What is at the end of this link.

    Answered before the content, so the page can mount the right editor — and
    so a link to something neither editor can draw (a PDF, a photograph) is
    told to go and download it instead, which is what `open_link` already
    does and has always done.
    """
    link = _link(secret)
    row = _file(link)

    said = _shape(link, row)
    said["editable"] = said["kind"] in (kinds.SHEET, kinds.DOC)
    return said


@frappe.whitelist(allow_guest=True, methods=["GET"])
def open_file(secret: str, compressed: int = 0) -> dict:
    """The workbook or the document behind this link.

    Counted the way `open_link` counts a download: the row is the audit trail
    and the count is what it exists for. `frappe.local.flags.commit` because
    this is a GET and Frappe rolls back a request that did not change state
    by its method.
    """
    link = _link(secret)
    row = _file(link)
    kind = row.get(kinds.KIND_FIELD)

    link.db_set("opened", (link.opened or 0) + 1, update_modified=False)
    link.db_set("last_opened", now_datetime(), update_modified=False)
    frappe.local.flags.commit = True

    said = _shape(link, row)

    if kind == kinds.SHEET:
        from ..onesheet import book, codec

        stored = frappe.db.get_value("Sheet Book", row.name, "payload")
        said["sheets_data"] = (
            stored if frappe.utils.cint(compressed) else codec.decode(stored)
        )
        said["head_seq"] = book.head_of(row.name).get("head_seq")
    elif kind == kinds.DOC:
        from ..onedoc import body

        held = body.load(row.name)
        # The *stored* content, not `fields.sanitise`'s rewrite of it. There
        # is nothing to resolve for a guest and nothing they may read — a
        # token in a shared document keeps whatever answer it last had, which
        # is the same thing the export does.
        said["content"] = held["content"]
        said["settings"] = held["settings"]
        said["head_seq"] = held["head_seq"]
    else:
        frappe.throw(_("This link is not one you can open here."))

    return said


@frappe.whitelist(allow_guest=True, methods=["POST"])
def save_file(secret: str, payload: str, html: str = "") -> dict:
    """Write it back.

    No title, which the signed-in editors send with their save: a stranger
    renaming somebody's file in their Drive is not part of what "edit this"
    meant.

    `html` is the document's second stored form — what the search and the
    export read — and it is markup from somebody with no account, so it goes
    through `sanitize_html` on the way in. That is the mail reader's rule
    applied to the one other place this product takes HTML from outside.
    """
    link = _writable(secret)
    row = _file(link)

    if payload and len(payload) > MAX_PAYLOAD:
        frappe.throw(_("That is too big to save through a link."))

    kind = row.get(kinds.KIND_FIELD)
    if kind == kinds.SHEET:
        from ..onesheet import book

        head = book.store(row.name, payload)
        which = "Sheet"
    elif kind == kinds.DOC:
        from ..onedoc import body

        # Imported here rather than at the top: it is Frappe's, it is only
        # wanted on this one branch, and the module has to import cleanly
        # against the suite's stub.
        from frappe.utils.html_utils import sanitize_html

        head = body.store(row.name, payload, sanitize_html(html or ""), None)
        which = "Doc"
    else:
        frappe.throw(_("This link is not one you can save through."))

    row.db_set("modified", frappe.utils.now(), update_modified=False)

    # A version, attributed to the link rather than to nobody. "Who changed
    # this" cannot name a person — the workspace handed out a URL — so it
    # names the URL and whoever made it.
    from ..shared import versions

    kept = versions.keep(row.name, which,
                         title=_("Through the link {0}").format(link.label or link.name))

    return {"name": row.name, "head_seq": head, "version": kept}
