"""A `.txt` or `.md` file, read and written in place.

The other half of "new file" in the Drive. A document of kind `Doc` keeps its
prose in a column; these keep theirs in R2, as the bytes anybody who downloads
the file gets — which is the whole point of them. Somebody who writes a README
here expects the thing they download to be that README, not an export of it.

So editing one is read the object, write the object back under the same key.
There is no second store and no `Doc Body` row: the file *is* the content, and
the version history hangs off nothing here for the same reason — a text file's
earlier drafts would be a third store for a fourth shape, and the one that
matters is the one you can download.
"""

import frappe
from frappe import _

from .. import languages
from ..drive import kinds
from ..storage import r2

#: What may be opened as text rather than downloaded: the three `make_text`
#: creates, the ones a person routinely wants to fix a line of without leaving
#: the workspace, and every language OneCode knows. One editor reads all of
#: them — a `.txt` is the same bytes in the same box as a `.py`, minus the
#: colouring — so a second list of "and also code" would be the same list
#: written twice.
EDITABLE = ("txt", "md", "markdown", "csv", "log") + languages.EXTENSIONS

#: A text file bigger than this is not something to open in a browser text
#: box; it is a download. Two megabytes is a very long README.
MAX_BYTES = 2 * 1024 * 1024


def is_text(file_name: str) -> bool:
    name = (file_name or "").rsplit("?", 1)[0]
    return "." in name and name.rsplit(".", 1)[-1].lower() in EDITABLE


def _mine(name: str, level: str = "read"):
    row = frappe.get_doc("File", name)
    if not is_text(row.file_name):
        frappe.throw(_("That file is not text."))
    row.check_permission(level)
    return row


@frappe.whitelist(methods=["GET"])
def get_text(name: str) -> dict:
    """One text file's content, for the editor to show as text."""
    row = _mine(name)

    if (row.file_size or 0) > MAX_BYTES:
        frappe.throw(_("That file is too big to open here. Download it instead."))

    extension = (row.file_name or "").rsplit(".", 1)[-1].lower()

    content = row.get_content()
    if isinstance(content, bytes):
        try:
            content = content.decode("utf-8")
        except UnicodeDecodeError:
            frappe.throw(_("That file is not text this can show."))

    return {
        "name": row.name,
        "title": row.file_name,
        "folder": row.folder,
        "owner": row.owner,
        "modified": str(row.modified),
        "can_write": bool(frappe.has_permission("File", "write", doc=row)),
        "content": content or "",
        # Three answers about one thing, because three readers want different
        # ones: the extension is what the file *is* and is what tells `Doc.vue`
        # this is not prose; `highlight` is CodeMirror's key and is empty for
        # most of them; `language_label` is what a person is shown.
        "language": extension,
        "highlight": languages.highlight_for(extension),
        "language_label": languages.label_for(extension),
        "is_code": languages.is_code(row.file_name),
    }


@frappe.whitelist(methods=["POST"])
def save_text(name: str, content: str = "", title: str = "") -> dict:
    """Write a text file back, under the key it already has.

    Under the same key deliberately: a new key would leave the old object
    behind, unreferenced and still billed, and every link anybody had shared
    would point at the previous draft.
    """
    row = _mine(name, "write")

    raw = (content or "").encode("utf-8")
    if len(raw) > MAX_BYTES:
        frappe.throw(_("That is more text than this file can hold."))

    if row.get("r2_key") and r2.is_configured():
        r2.upload(row, raw)
    else:
        _write_local(row, raw)

    row.db_set("file_size", len(raw), update_modified=False)
    row.db_set("modified", frappe.utils.now(), update_modified=False)

    clean = (title or "").strip()
    if clean and clean != row.file_name:
        from ..drive import writing as drive

        drive.rename(name, clean)

    return {"name": name, "size": len(raw)}


def _write_local(row, raw: bytes) -> None:
    """The no-R2 path, which is every developer's site and no customer's."""
    path = row.get_full_path()
    with open(path, "wb") as handle:
        handle.write(raw)


def duplicate(source, title: str = ""):
    """A copy of a text file, object and all.

    `File`'s own insert does the copying: handed content, it writes a new
    object, and `storage/file.py` moves it to R2 the way it does for an upload.
    """
    content = source.get_content()
    if isinstance(content, str):
        content = content.encode("utf-8")

    copy = frappe.get_doc({
        "doctype": "File",
        "file_name": (title or f"{source.file_name} copy"),
        "is_folder": 0,
        "folder": source.folder,
        "is_private": source.is_private,
        "content": content,
        "custom_status": kinds.ACTIVE,
    }).insert()

    return {"name": copy.name, "title": copy.file_name, "url": f"/one/docs/{copy.name}"}
