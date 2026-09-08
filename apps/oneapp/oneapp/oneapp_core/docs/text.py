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

import os

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


def own_object(doc) -> bool:
	"""Make sure this row's bytes are its own, and not another row's.

	Frappe deduplicates a `File` by content hash — twice, in two places, with
	two different switches. `File.validate_duplicate_entry` has a flag; the
	check inside `File.save_file` has an `ignore_existing_file_check`
	*parameter* that `validate` does not pass, so there is no way to turn it
	off from outside. Both point the new row at an object that already exists.

	For an upload that is exactly right: two people attaching the same drawing
	should not be billed for it twice. For a file created empty to be typed
	into it is ruinous, because every one of them starts as the same single
	newline — eight new files, one object, and the first edit to any of them
	rewriting all eight, since `save_text` writes back through `file_url`.

	So the row is given an object named after itself, which is the one name
	nothing else can claim. Deliberately the same shape `storage/r2.object_key`
	already uses, and for the same reason.

	R2-backed rows are left alone: their key already carries `File.name`, so
	two of them cannot share one however identical their bytes.
	"""
	# Imported here rather than at the top: `frappe.utils` is a package on a
	# bench and a flat module in the unit suite's stub, so a module-level
	# `from frappe.utils.file_manager import …` fails every test in this file
	# for a helper only one code path calls.
	from frappe.utils import get_files_path
	from frappe.utils.file_manager import get_content_hash

	if doc.get("r2_key") or not (doc.file_url or "").startswith(("/files/", "/private/files/")):
		return False

	mine = f"/private/files/" if doc.is_private else "/files/"
	stem, dot, extension = (doc.file_name or "").rpartition(".")
	unique = f"{stem or doc.file_name}-{doc.name}{dot}{extension}"
	if doc.file_url == mine + unique:
		return False

	content = doc.get_content()
	if isinstance(content, str):
		content = content.encode("utf-8")

	folder = get_files_path(is_private=doc.is_private)
	os.makedirs(folder, exist_ok=True)
	with open(os.path.join(folder, unique), "wb") as handle:
		handle.write(content)

	doc.db_set("file_url", mine + unique, update_modified=False)
	doc.db_set("content_hash", get_content_hash(content), update_modified=False)
	doc.file_url = mine + unique
	return True


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

    # A copy has by definition the same bytes as its source, so it is handed
    # the source's object — and the first edit to the copy would rewrite the
    # thing it was copied from.
    own_object(copy)

    return {"name": copy.name, "title": copy.file_name, "url": f"/one/docs/{copy.name}"}
