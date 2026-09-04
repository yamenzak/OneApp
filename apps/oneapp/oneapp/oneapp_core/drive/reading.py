"""Listing a place, walking to a folder, and what one file is.

Every read here is `get_list`, never `get_all`. That one word is the whole
access model: `get_all` ignores permissions, and a file manager built on it
would hand every reader every file on the site — including the attachments on
records they cannot open, which is where most of a workspace's files live.
"""

import frappe
from frappe import _

from oneapp.oneapp_core.email import people

from .kinds import KIND_FIELD, KINDS, OPENED_FIELD, STATUS_FIELD, TRASHED_FIELD
from .query import HOME, ORDER, PLACES, ROOT, TRASH, _place_filters, _visible

PAGE = 50

# What a row needs to draw: a name, a kind, a size, who and when. Not the
# content and not the R2 key — one is the point of the preview endpoint and the
# other is ours.
FIELDS = [
    "name", "file_name", "file_url", "is_folder", "folder", "file_size",
    "is_private", "owner", "modified", "creation", "attached_to_doctype",
    "attached_to_name", "_liked_by",
    KIND_FIELD, STATUS_FIELD, TRASHED_FIELD, OPENED_FIELD,
]

# How deep a breadcrumb walks before giving up. `File.folder` is a Link and
# Frappe does not stop you pointing one at its own descendant.
DEPTH = 20


@frappe.whitelist(methods=["GET"])
def listing(place: str = HOME, folder: str = "", kind: str = "",
            search: str = "", start: int = 0, limit: int = PAGE,
            order_by: str = "") -> dict:
    """One page of one place."""
    place = place if place in PLACES else HOME
    if kind and kind not in KINDS:
        kind = ""

    filters, or_filters = _place_filters(place, folder, kind)
    if search:
        filters["file_name"] = ["like", f"%{search}%"]

    limit = max(1, min(int(limit or PAGE), PAGE))
    start = max(0, int(start or 0))

    rows = frappe.get_list(
        "File",
        filters=filters,
        or_filters=or_filters,
        fields=FIELDS,
        order_by=order_by or ORDER.get(place) or "modified desc",
        limit_start=start,
        limit_page_length=limit + 1,
    )

    more = len(rows) > limit
    rows = rows[:limit]
    _shape(rows)

    return {
        "files": rows,
        "more": more,
        "place": place,
        "folder": folder,
        "path": path(folder) if folder else [],
        "can_write": place != TRASH,
    }


def _shape(rows: list[dict]) -> None:
    """Everything a row needs that is not a column, in one query for the page."""
    owners = people.profiles([(row.get("owner") or "", "") for row in rows])
    me = frappe.session.user
    for row in rows:
        row["owner_person"] = owners.get((row.get("owner") or "").lower()) or {}
        liked = frappe.parse_json(row.pop("_liked_by", None) or "[]")
        row["liked"] = me in liked
        # Frappe stores `Home/Attachments` and the like; a reader wants the
        # last part, and the breadcrumb carries the rest.
        row["folder_label"] = (row.get("folder") or "").rsplit("/", 1)[-1]


@frappe.whitelist(methods=["GET"])
def path(folder: str) -> list[dict]:
    """The breadcrumb to a folder, top first.

    Walked at read time rather than stored: a folder tree is a handful of rows
    deep and a stored path is a thing to rewrite on every move.
    """
    trail = []
    seen = set()
    current = folder
    # Stops at `Home`, which is the drive itself: the page draws that crumb as
    # "Files", and a trail that repeated it would read `Files / Home / …`.
    while current and current != ROOT and current not in seen and len(seen) < DEPTH:
        seen.add(current)
        row = frappe.db.get_value(
            "File", current, ["name", "file_name", "folder"], as_dict=True
        )
        if not row:
            break
        trail.append({"name": row.name, "label": row.file_name or row.name})
        current = row.folder

    trail.reverse()
    return trail


@frappe.whitelist(methods=["GET"])
def details(name: str) -> dict:
    """One file, and the fact that opening it is what makes it recent.

    Stamped here rather than by the preview endpoint, because a person who
    opened the details pane has looked at the file whether or not the bytes
    were fetched — and because the preview is a redirect, which is the one
    place there is no request to hang this on.
    """
    doc = frappe.get_doc("File", name)
    doc.check_permission("read")

    doc.db_set(OPENED_FIELD, frappe.utils.now_datetime(), update_modified=False)

    row = {field: doc.get(field) for field in FIELDS if field != "_liked_by"}
    liked = frappe.parse_json(doc.get("_liked_by") or "[]")
    row["liked"] = frappe.session.user in liked
    row["owner_person"] = people.profiles([(doc.owner or "", "")]).get(
        (doc.owner or "").lower()
    ) or {}
    row["path"] = path(doc.folder) if doc.folder else []
    return row


@frappe.whitelist(methods=["GET"])
def storage() -> dict:
    """What is stored, by kind, and what the plan allows.

    The quota was enforced at upload time and shown nowhere, which is the worst
    of both: a refusal with no way to see it coming.
    """
    from oneapp.oneapp_core.storage import quota

    # The breakdown is what this reader may see; the total beside it is the
    # workspace's real usage, which is a number off the control plane and
    # counts files nobody in particular can open. They are deliberately two
    # figures and the screen says so — a breakdown that summed to the meter
    # would be a breakdown that leaked what it could not show.
    rows = frappe.get_list(
        "File",
        filters={"is_folder": 0, **_visible()},
        fields=["file_size", KIND_FIELD],
        limit_page_length=0,
    )

    by_kind = {}
    for row in rows:
        kind = row.get(KIND_FIELD) or "Other"
        by_kind[kind] = by_kind.get(kind, 0) + (row.get("file_size") or 0)

    return {
        "by_kind": [
            {"kind": kind, "bytes": size, "label": quota.format_bytes(size)}
            for kind, size in sorted(by_kind.items(), key=lambda pair: -pair[1])
        ],
        "visible": sum(by_kind.values()),
        "files": len(rows),
        "workspace": quota.usage_summary(),
    }
