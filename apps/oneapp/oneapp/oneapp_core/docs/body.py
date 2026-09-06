"""Opening a document and saving one — the two calls the editor makes.

Reseamed from `frappe/writer` (AGPL-3.0, © Frappe Technologies Pvt. Ltd. and
contributors), whose `writer/api/docs.py` and `Writer Document.save_doc` these
are the same two calls as. Both projects are AGPL-3.0 and this file stays that
way.

The protocol is the one `sheets/book.py` already speaks, for the same reason:
the browser holds the whole document and hands the whole document back. There
is no paragraph endpoint and no merge. What is different from Frappe's is that
theirs saves a base64 CRDT update, because their editing model is peer-to-peer
Yjs over a signalling server they host; ours saves ProseMirror JSON, because a
shard runs one Python process and `docs/SHEETS.md` already argued why a second
runtime is not worth what it buys.

Two blobs go in on every save and only one of them is authoritative. `content`
is the JSON the editor reads back. `html` is what the editor rendered it to,
sent alongside, and it exists so that search, the preview, print, export and a
mail body do not each need a ProseMirror implementation in Python to find out
what the document says.
"""

import json

import frappe
from frappe import _

from ..drive import kinds

TITLE_MAX = 280

#: A cap on one document. Big enough for a hundred-page contract with images
#: as data URIs, small enough that loading one is not what takes the site down.
MAX_BYTES = 8 * 1024 * 1024

BLANK = {"type": "doc", "content": [{"type": "paragraph"}]}

DEFAULT_SETTINGS = {"width": "page", "font": "", "spacing": "normal", "locked": False}


def _mine(doc: str, level: str = "read"):
    """The File behind a document, if this person may have it at that level."""
    row = frappe.get_doc("File", doc)
    if row.get(kinds.KIND_FIELD) != kinds.DOC:
        frappe.throw(_("That file is not a document."))
    row.check_permission(level)
    return row


def blank() -> str:
    return json.dumps(BLANK)


# --------------------------------------------------------------------------- #
# The store contract `versions.py` reads
# --------------------------------------------------------------------------- #

def head_of(doc: str) -> dict:
    row = frappe.db.get_value(
        "Doc Body", doc, ["content", "head_seq"], as_dict=True
    )
    return {"payload": (row or {}).get("content") or blank(),
            "head_seq": (row or {}).get("head_seq") or 0}


def may_read(doc: str) -> None:
    _mine(doc)


def may_write(doc: str) -> None:
    _mine(doc, "write")


def put(doc: str, payload: str) -> int:
    """Write a document back wholesale. What restoring a version calls.

    The HTML is re-derived from the JSON here, badly — a restore is the one
    moment no browser is holding the document, and a stale `html` beside a
    restored `content` would mean a search hit on a paragraph the document no
    longer has. `text.py` does the same job for the same reason.
    """
    return store(doc, payload, html_of(payload))


# --------------------------------------------------------------------------- #
# Reading and writing
# --------------------------------------------------------------------------- #

def readable(payload: str) -> str:
    """A stored document as the editor reads it, which is unchanged."""
    return payload


def copy(payload: str, title: str, folder: str = "") -> dict:
    """A new document holding this prose. What "make a copy" of a version is."""
    from . import writing

    made = writing.make(title=title, folder=folder)
    store(made["name"], payload, html_of(payload))
    return made


def load(doc: str) -> dict:
    """One document's stored body. No permission check — callers have settled it."""
    row = frappe.db.get_value(
        "Doc Body", doc, ["content", "html", "settings", "head_seq"], as_dict=True
    )
    if not row:
        return {"content": blank(), "html": "", "settings": dict(DEFAULT_SETTINGS),
                "head_seq": 0}
    return {
        "content": row.content or blank(),
        "html": row.html or "",
        "settings": _settings(row.settings),
        "head_seq": row.head_seq or 0,
    }


def _settings(stored) -> dict:
    try:
        given = json.loads(stored) if isinstance(stored, str) else (stored or {})
    except ValueError:
        given = {}
    return {**DEFAULT_SETTINGS, **(given if isinstance(given, dict) else {})}


def store(doc: str, content: str, html: str = "", settings: dict | None = None) -> int:
    """Replace a document's body. Returns the new save count."""
    size = len((content or "").encode("utf-8")) + len((html or "").encode("utf-8"))
    if size > MAX_BYTES:
        frappe.throw(_("That document is too big to save. Split it in two."))

    fields = {"content": content, "html": html, "byte_size": size}
    if settings is not None:
        fields["settings"] = json.dumps(settings)

    if frappe.db.exists("Doc Body", doc):
        head = (frappe.db.get_value("Doc Body", doc, "head_seq") or 0) + 1
        frappe.db.set_value("Doc Body", doc, {**fields, "head_seq": head},
                            update_modified=False)
    else:
        head = 1
        frappe.get_doc({
            "doctype": "Doc Body", "doc": doc, "head_seq": head,
            "settings": json.dumps(settings or DEFAULT_SETTINGS), **fields,
        }).insert(ignore_permissions=True)

    # Onto the File as well, because a document is a file and every place a
    # file's weight is read reads it there — the Drive's list, the storage
    # screen, the meter. A document has no object behind it, so without this it
    # weighs nothing and a workspace of five hundred of them says so.
    frappe.db.set_value("File", doc, "file_size", size, update_modified=False)

    return head


def html_of(content: str) -> str:
    """The text of a ProseMirror document, as rough HTML.

    Not a renderer. The browser sends real HTML on every save and that is what
    is stored; this is the fallback for the two moments no browser is involved
    — a restore, and a document made from a template — and its whole job is
    that the stored `html` never describes a body that has been replaced. What
    it loses is formatting, which search does not read and the editor does not
    load.
    """
    try:
        node = json.loads(content or "{}")
    except ValueError:
        return ""

    lines = []

    def walk(one):
        if not isinstance(one, dict):
            return
        if one.get("type") == "text":
            lines.append(frappe.utils.escape_html(one.get("text") or ""))
            return
        kids = one.get("content") or []
        before = len(lines)
        for kid in kids:
            walk(kid)
        if one.get("type") in ("paragraph", "heading", "listItem") and len(lines) > before:
            lines.insert(before, "<p>")
            lines.append("</p>")

    walk(node)
    return "".join(lines)


# --------------------------------------------------------------------------- #
# What the editor calls
# --------------------------------------------------------------------------- #

@frappe.whitelist(methods=["GET"])
def get_doc(name: str) -> dict:
    """Everything the editor needs to draw a document, in one request."""
    row = _mine(name)
    held = load(name)

    return {
        "name": row.name,
        "title": row.file_name,
        "folder": row.folder,
        "owner": row.owner,
        "modified": str(row.modified),
        "attached_to": {
            "doctype": row.attached_to_doctype or "",
            "docname": row.attached_to_name or "",
        },
        # Asked rather than assumed, so a control that is drawn and a write
        # that is allowed read the same flag at the same moment.
        "can_write": bool(frappe.has_permission("File", "write", doc=row)),
        "content": held["content"],
        "settings": held["settings"],
        "head_seq": held["head_seq"],
    }


@frappe.whitelist(methods=["POST"])
def save_doc(name: str, content: str, html: str = "", title: str = "",
             settings: str = "") -> dict:
    """Write the document back, rename the file if the title moved, and offer a
    version.

    The title travels with the save for the reason it does in a sheet: it is
    edited in the same header as the prose, so there is no other moment to send
    it, and it is the File's `file_name` rather than a field of our own — a
    document renamed here is renamed in the Drive, which is the only behaviour
    that could be right when the two are one object.
    """
    row = _mine(name, "write")

    chosen = None
    if settings:
        try:
            chosen = _settings(settings)
        except ValueError:
            chosen = None

    head = store(name, content, html, chosen)

    clean = (title or "").strip()[:TITLE_MAX]
    if clean and clean != row.file_name:
        from ..drive import writing as drive

        drive.rename(name, clean)

    row.db_set("modified", frappe.utils.now(), update_modified=False)

    from .. import versions

    kept = versions.keep(name, versions.DOC)

    return {"name": name, "head_seq": head, "version": kept}
