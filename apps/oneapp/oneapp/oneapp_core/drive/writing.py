"""Making folders, and everything that moves or removes a file.

The one that matters is the bin. Frappe deletes a `File` and its object
together, so before this the only undo for a misplaced click was a backup —
which is not an undo, it is a support ticket. Trashing sets a column; the object
survives until a scheduled sweep decides it has been thirty days.

Everything here checks `write` on the document, not `read`. `get_list` decides
who may see a file; `check_permission` decides who may change one, and they are
different questions with different answers on a file somebody shared read-only.
"""

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime

from .kinds import ACTIVE, KIND_FIELD, STATUS_FIELD, TRASHED, TRASHED_FIELD, kind_of

# How long the bin keeps something. Long enough to notice, short enough that a
# workspace is not paying to store what it threw away in the spring.
KEEP_DAYS = 30

# How deep a folder may nest. A guard against a cycle rather than a product
# rule: `File.folder` is a Link and nothing stops one pointing into its own
# subtree, which would make the breadcrumb walk forever.
DEPTH = 20


def _mine(name: str):
    """One file, if this person may change it."""
    doc = frappe.get_doc("File", name)
    doc.check_permission("write")
    return doc


@frappe.whitelist(methods=["POST"])
def make_folder(file_name: str, folder: str = "") -> dict:
    """A new folder, inside another or at the top."""
    title = (file_name or "").strip()
    if not title:
        frappe.throw(_("A folder needs a name."))
    if "/" in title:
        # Frappe builds `Home/Attachments`-style names out of this, so a slash
        # in one is a folder that cannot be found again.
        frappe.throw(_("A folder name cannot contain a slash."))

    parent = folder or "Home"
    if folder:
        _mine(folder)

    try:
        doc = frappe.get_doc({
            "doctype": "File",
            "file_name": title,
            "is_folder": 1,
            "folder": parent,
            KIND_FIELD: kind_of(title, is_folder=True),
            STATUS_FIELD: ACTIVE,
        }).insert()
    except frappe.DuplicateEntryError:
        # Frappe names a folder `Home/Drawings`, so two folders with one name
        # in one parent are one primary key. Its own message names a doctype
        # and an id the person never typed; this names what they did.
        frappe.throw(_("There is already a folder called “{0}” here.").format(title))

    return {"ok": True, "name": doc.name, "label": doc.file_name}


@frappe.whitelist(methods=["POST"])
def rename(name: str, file_name: str) -> dict:
    """Rename a file or a folder.

    The kind is re-derived, because renaming `notes` to `notes.pdf` is somebody
    saying what the file is — and a kind that only ever reflected the name at
    upload time would be a filter that quietly lies after the first rename.
    """
    title = (file_name or "").strip()
    if not title:
        frappe.throw(_("A name cannot be empty."))

    doc = _mine(name)
    doc.file_name = title
    doc.set(KIND_FIELD, kind_of(title, doc.is_folder))
    doc.save()
    return {"ok": True, "name": doc.name, "label": doc.file_name,
            "kind": doc.get(KIND_FIELD)}


@frappe.whitelist(methods=["POST"])
def move(names: str | list, folder: str = "") -> dict:
    """Put files into a folder, or back at the top.

    A folder cannot be moved into itself or into anything under it. Frappe will
    happily store that and the breadcrumb walk is what discovers it, one
    reader at a time.
    """
    names = frappe.parse_json(names) if isinstance(names, str) else names
    names = [one for one in (names or []) if one]
    if not names:
        return {"ok": True, "moved": 0}

    target = folder or "Home"
    if folder:
        _mine(folder)
        inside = set(_upward(folder))
        for name in names:
            if name == folder or name in inside:
                frappe.throw(_("A folder cannot be moved inside itself."))

    for name in names:
        doc = _mine(name)
        doc.folder = target
        doc.save()

    return {"ok": True, "moved": len(names), "folder": folder}


def _upward(folder: str) -> list[str]:
    """Every folder above this one, so a move can refuse a cycle."""
    trail, seen, current = [], set(), folder
    while current and current not in seen and len(seen) < DEPTH:
        seen.add(current)
        parent = frappe.db.get_value("File", current, "folder")
        if not parent:
            break
        trail.append(parent)
        current = parent
    return trail


@frappe.whitelist(methods=["POST"])
def trash(names: str | list) -> dict:
    """Throw files away, reversibly.

    A folder takes what is in it, because "delete this folder" said out loud
    means the folder and its contents — and a folder emptied of everything but
    the row is a folder that reappears empty.
    """
    names = frappe.parse_json(names) if isinstance(names, str) else names
    when = now_datetime()
    count = 0

    for name in [one for one in (names or []) if one]:
        for target in _subtree(name):
            doc = _mine(target)
            doc.db_set(STATUS_FIELD, TRASHED, update_modified=False)
            doc.db_set(TRASHED_FIELD, when, update_modified=False)
            count += 1

    return {"ok": True, "trashed": count, "keep_days": KEEP_DAYS}


@frappe.whitelist(methods=["POST"])
def restore(names: str | list) -> dict:
    """Take files back out of the bin.

    Back where they were, which is what `folder` still says — nothing cleared
    it, precisely so that this is possible. A file whose folder was itself
    thrown away comes back to the top rather than into the bin.
    """
    names = frappe.parse_json(names) if isinstance(names, str) else names
    count = 0

    for name in [one for one in (names or []) if one]:
        for target in _subtree(name, status=TRASHED):
            doc = _mine(target)
            parent = doc.folder
            if parent and frappe.db.get_value("File", parent, STATUS_FIELD) == TRASHED:
                doc.db_set("folder", "Home", update_modified=False)
            doc.db_set(STATUS_FIELD, ACTIVE, update_modified=False)
            doc.db_set(TRASHED_FIELD, None, update_modified=False)
            count += 1

    return {"ok": True, "restored": count}


def _subtree(name: str, status: str = "") -> list[str]:
    """A file and everything under it, if it is a folder.

    Breadth-first with a depth cap, for the same reason the breadcrumb has one.
    """
    found = [name]
    frontier = [name]
    for _level in range(DEPTH):
        if not frontier:
            break
        filters = {"folder": ["in", frontier]}
        if status:
            filters[STATUS_FIELD] = status
        children = frappe.get_all("File", filters=filters, pluck="name")
        children = [one for one in children if one not in found]
        found.extend(children)
        frontier = children
    return found


@frappe.whitelist(methods=["POST"])
def empty_trash(names: str | list = "") -> dict:
    """Delete for real — the row and the object together.

    Named separately from `trash` and reached from its own screen, because this
    is the one that does not come back and a person should have arrived at it
    on purpose.
    """
    names = frappe.parse_json(names) if isinstance(names, str) else names
    names = [one for one in (names or []) if one]

    if not names:
        names = frappe.get_list(
            "File", filters={STATUS_FIELD: TRASHED}, pluck="name",
            limit_page_length=0,
        )

    gone = 0
    for name in names:
        doc = _mine(name)
        if doc.get(STATUS_FIELD) != TRASHED:
            # Only from the bin. Otherwise this endpoint is a delete button
            # with no confirmation anywhere in front of it.
            continue
        frappe.delete_doc("File", name, delete_permanently=True)
        gone += 1

    return {"ok": True, "deleted": gone}


def sweep_trash():
    """Empty what has been in the bin past `KEEP_DAYS`. A scheduled job.

    `delete_doc` rather than a bulk SQL delete, because the `File` override's
    `on_trash` is what removes the R2 object — a row deleted around it is an
    object nobody will ever find again, still being paid for.
    """
    cutoff = add_days(now_datetime(), -KEEP_DAYS)
    stale = frappe.get_all(
        "File",
        filters={STATUS_FIELD: TRASHED, TRASHED_FIELD: ["<", cutoff]},
        pluck="name",
        limit_page_length=200,
    )

    for name in stale:
        try:
            frappe.delete_doc("File", name, delete_permanently=True,
                              ignore_permissions=True)
        except Exception:
            # One undeletable file — a link somewhere else, a missing object —
            # must not stop the sweep for the rest.
            frappe.log_error(title=f"Drive: could not empty {name}")

    return len(stale)
