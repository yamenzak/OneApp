"""Listing a place, walking to a folder, and what one file is.

Every read here is `get_list`, never `get_all`. That one word is the whole
access model: `get_all` ignores permissions, and a file manager built on it
would hand every reader every file on the site — including the attachments on
records they cannot open, which is where most of a workspace's files live.
"""

import frappe
from frappe import _

from oneapp.onespace.ai import written
from oneapp.onemail import people

from . import remote
from .kinds import KIND_FIELD, KINDS, OPENED_FIELD, STATUS_FIELD, TRASHED, TRASHED_FIELD
from .writing import KEEP_DAYS
from .query import (
    HOME, ORDER, PLACES, RECORD, RECORDS, ROOT, SORTABLE, TRASH, _place_filters,
    _searching, _visible, ordering,
)

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

# How many rows the storage screen shows in each of its two "where is it"
# lists. Enough to find the thing that is costing money, short enough to read.
BIGGEST = 10

# How deep a breadcrumb walks before giving up. `File.folder` is a Link and
# Frappe does not stop you pointing one at its own descendant.
DEPTH = 20


@frappe.whitelist(methods=["GET"])
def listing(place: str = HOME, folder: str = "", kind: str = "",
            search: str = "", start: int = 0, limit: int = PAGE,
            sort: str = "", descending: int = 0,
            doctype: str = "", docname: str = "") -> dict:
    """One page of one place."""
    # A folder on somebody else's server is browsed live and has no rows in
    # this table — see `remote.py`. The branch is here rather than inside
    # `_place_filters` because there is no filter to build: the answer comes
    # from an FTP socket, and putting a `remote://` name into `filters` would
    # be a `File` query for a name no `File` has ever had.
    if remote.is_remote(folder):
        return remote.listing(folder, search, start, limit, sort,
                              bool(int(descending or 0)))

    place = place if place in PLACES else HOME
    if kind and kind not in KINDS:
        kind = ""

    # A tree rather than a filter, so it is walked rather than `where`d — and
    # walked by the same resolver a mounted `doctype:Quotation` uses, because a
    # rail place and a mount that disagreed about what a record has on it would
    # be two answers to one question. `folder` under this place is the path:
    # empty, `Quotation`, `Quotation/QTN-0001`.
    if place == RECORDS:
        return _records(folder, search, start, limit)

    filters, or_filters = _place_filters(place, folder, kind, (doctype, docname))
    if search:
        or_filters = _searching(search, filters, or_filters)

    limit = max(1, min(int(limit or PAGE), PAGE))
    start = max(0, int(start or 0))

    rows = frappe.get_list(
        "File",
        filters=filters,
        or_filters=or_filters,
        fields=FIELDS,
        # A key the reader picked, resolved against an allowlist — never the
        # string they sent. See `ordering`.
        order_by=ordering(place, sort, bool(int(descending or 0))),
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
        # Echoed so the control can draw the order that is actually in force,
        # which is the place's own default until somebody picks one.
        "sort": sort if sort in SORTABLE else "",
        "descending": bool(int(descending or 0)),
        # What the caller asked for, echoed so a tab that scopes itself can
        # tell its own answer from a stale one that arrived after it moved on.
        "attached_to": {"doctype": doctype, "docname": docname} if place == RECORD else None,
    }


def _records(folder: str, search: str, start: int, limit: int) -> dict:
    """The Records tree: kinds of record, then records, then their files.

    Nothing here is a folder. A directory per record would be a `File` row per
    record — four thousand quotations is four thousand rows, renaming a record
    becomes moving a folder and deleting one becomes a cascade — which is the
    decision `docs/UNIFICATION.md` §E1 records and `query.py`'s own docstring
    rests on: there is no second store.

    So the first two levels are made out of the attachment rows themselves, at
    the moment they are asked for, and only the third level is `File` rows. The
    shape they come back in is a folder's, because what draws them is the
    Drive's own row and a row that looked different would be a second component
    to keep in step.
    """
    from . import scopes

    parts = [one for one in (folder or "").split("/") if one]
    limit = max(1, min(int(limit or PAGE), PAGE))
    start = max(0, int(start or 0))

    if len(parts) >= 2:
        # A record's own files, which is `record` by another name — same
        # filter, same rows, same `_shape`.
        found = listing(place=RECORD, search=search, start=start, limit=limit,
                        doctype=parts[0], docname=parts[1])
        found["place"] = RECORDS
        found["folder"] = folder
        found["path"] = _records_path(parts)
        return found

    if parts:
        nodes = scopes.children(
            scopes.Node(label=parts[0], is_folder=True, doctype=parts[0])
        )
        rows = [{"name": f"{parts[0]}/{one.label}", "file_name": one.label}
                for one in nodes]
    else:
        rows = [{"name": one, "file_name": one} for one in _kinds_with_files()]

    if search:
        needle = search.lower()
        rows = [one for one in rows if needle in one["file_name"].lower()]

    page = rows[start:start + limit + 1]
    more = len(page) > limit

    return {
        "files": [_as_folder(one) for one in page[:limit]],
        "more": more,
        "place": RECORDS,
        "folder": folder,
        "path": _records_path(parts),
        # A directory made out of a query has nothing to make *in* it. The New
        # menu and the dropzone read this, and a record's files are attached
        # from the record rather than uploaded into a place.
        "can_write": False,
        "sort": "",
        "descending": False,
        "attached_to": None,
    }


def _kinds_with_files() -> list[str]:
    """The kinds of record that have a file on them, and only those.

    Over the attachment rows rather than over the doctype list: a directory per
    doctype on the site is two hundred directories, almost all of them empty,
    and the thing being listed is the files.
    """
    rows = frappe.get_list(
        "File",
        filters={"attached_to_doctype": ["is", "set"], **_visible()},
        fields=["attached_to_doctype"],
        group_by="attached_to_doctype",
        order_by="attached_to_doctype asc",
        limit_page_length=0,
    )
    return [one["attached_to_doctype"] for one in rows if one.get("attached_to_doctype")]


def _as_folder(one: dict) -> dict:
    """A row the Drive draws as a folder, with nothing behind it."""
    return {
        **one,
        "is_folder": 1,
        "file_size": 0,
        "folder": "",
        "owner": "",
        "modified": None,
        "creation": None,
        "_liked_by": None,
        "file_url": "",
        "is_private": 1,
        KIND_FIELD: "Folder",
        STATUS_FIELD: "",
        TRASHED_FIELD: None,
        OPENED_FIELD: None,
        "attached_to_doctype": "",
        "attached_to_name": "",
        "who": None,
        "liked": False,
        "kind": "Folder",
    }


def _records_path(parts: list[str]) -> list[dict]:
    """`Records / Quotation / QTN-0001`, built from the path rather than walked.

    There is nothing to walk: the levels are a doctype and a record name, and
    both are in the path already.
    """
    trail = []
    for depth, one in enumerate(parts[:2]):
        trail.append({"name": "/".join(parts[:depth + 1]), "label": one})
    return trail


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

    # Which of these a model made. On `file_url` because that is the thing a
    # model produced — the row is a File either way, and renaming one does not
    # make its picture somebody's drawing. One query for the page, and none at
    # all on a site where nothing has ever been marked. See `ai/written.py`.
    marks = written.across("File", [row["name"] for row in rows], "file_url")
    for row in rows:
        if row["name"] in marks:
            row["_ai"] = marks[row["name"]]


@frappe.whitelist(methods=["GET"])
def path(folder: str) -> list[dict]:
    """The breadcrumb to a folder, top first.

    Walked at read time rather than stored: a folder tree is a handful of rows
    deep and a stored path is a thing to rewrite on every move.
    """
    if remote.is_remote(folder):
        return remote.crumbs(folder)

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
    # Nothing to stamp and no row to stamp it on. A remote file is not in
    # Recents for the same reason it is not in Favourites: Recents is a column
    # on a row, and this file has none.
    if remote.is_remote(name):
        return remote.details(name)

    doc = frappe.get_doc("File", name)
    doc.check_permission("read")

    doc.db_set(OPENED_FIELD, frappe.utils.now_datetime(), update_modified=False)
    # And kept. Frappe commits a request only when its HTTP method is one that
    # changes server state — `frappe/app.py` — so a write inside a `GET` is
    # rolled back at the end of it and nothing says so. `flags.commit` is the
    # framework's own way to say this one does write, and without it Recents
    # was permanently empty on a route that answered 200 every time.
    frappe.local.flags.commit = True

    row = {field: doc.get(field) for field in FIELDS if field != "_liked_by"}
    liked = frappe.parse_json(doc.get("_liked_by") or "[]")
    row["liked"] = frappe.session.user in liked
    row["owner_person"] = people.profiles([(doc.owner or "", "")]).get(
        (doc.owner or "").lower()
    ) or {}
    row["path"] = path(doc.folder) if doc.folder else []
    return row


def _one_row_per_object(rows: list[dict]) -> list[dict]:
    """One row per stored object, the way the meter counts them.

    A drawing attached to twenty records is twenty `File` rows over one object:
    Frappe reuses the `file_url` rather than writing a second copy, and an R2
    upload reuses the key. `quota.current_usage` groups by exactly that, so a
    breakdown that summed `file_size` over rows was counting the same bytes
    twenty times — and on this fixture said 737 MB under a meter reading 85.6,
    with a sentence above it claiming the meter was the *larger* of the two.

    The largest row wins, which is what the meter's `MAX(file_size)` does, and
    the key is compared exactly — the meter groups on `BINARY` for the same
    reason, because `PHOTO.JPG` and `PHOTO.jpg` are two objects everywhere
    except in a case-insensitive collation. A folder therefore holds an object
    once even where two rows point at it from two places; the object is stored
    once, so it weighs once, somewhere.
    """
    by_object = {}
    for row in rows:
        key = row.get("r2_key") or row.get("file_url") or row["name"]
        held = by_object.get(key)
        if not held or (row.get("file_size") or 0) > (held.get("file_size") or 0):
            by_object[key] = row
    return list(by_object.values())


@frappe.whitelist(methods=["GET"])
def storage() -> dict:
    """What is stored, by kind, and what the plan allows.

    The quota was enforced at upload time and shown nowhere, which is the worst
    of both: a refusal with no way to see it coming.
    """
    from oneapp.onestorage import quota

    # The breakdown is what this reader may see; the total beside it is the
    # workspace's real usage, which is a number off the control plane and
    # counts files nobody in particular can open. They are deliberately two
    # figures and the screen says so — a breakdown that summed to the meter
    # would be a breakdown that leaked what it could not show.
    rows = frappe.get_list(
        "File",
        filters={"is_folder": 0, **_visible()},
        fields=["name", "file_name", "file_size", "folder", "r2_key", "file_url",
                KIND_FIELD],
        limit_page_length=0,
    )
    rows = _one_row_per_object(rows)

    by_kind, by_folder = {}, {}
    for row in rows:
        size = row.get("file_size") or 0
        by_kind[row.get(KIND_FIELD) or "Other"] = (
            by_kind.get(row.get(KIND_FIELD) or "Other", 0) + size
        )
        # `Home/Attachments` reads as "Attachments" here. The breakdown is a
        # question about where the weight is, and the answer is a place a
        # person recognises rather than a path.
        where = (row.get("folder") or ROOT).rsplit("/", 1)[-1]
        by_folder[where] = by_folder.get(where, 0) + size

    # What the bin is still holding. The single most confusing thing about a
    # storage meter is deleting a gigabyte and watching the number not move —
    # which is correct, because the object survives thirty days so the delete
    # can be undone, and is indistinguishable from a bug unless it is said.
    binned = frappe.get_list(
        "File",
        filters={"is_folder": 0, STATUS_FIELD: TRASHED},
        fields=["file_size"],
        limit_page_length=0,
    )

    return {
        "bin": {
            "files": len(binned),
            "bytes": sum(row.get("file_size") or 0 for row in binned),
            "label": quota.format_bytes(sum(row.get("file_size") or 0 for row in binned)),
            "days": KEEP_DAYS,
        },
        "by_kind": [
            {"kind": kind, "bytes": size, "label": quota.format_bytes(size)}
            for kind, size in sorted(by_kind.items(), key=lambda pair: -pair[1])
        ],
        "by_folder": [
            {"folder": where, "bytes": size, "label": quota.format_bytes(size)}
            for where, size in sorted(by_folder.items(), key=lambda pair: -pair[1])[:BIGGEST]
        ],
        # The other half of "why am I out of room". A breakdown by kind says
        # "photographs"; this says which photograph, which is the one somebody
        # can actually act on.
        "biggest": [
            {
                "name": row["name"],
                "file_name": row.get("file_name") or row["name"],
                "bytes": row.get("file_size") or 0,
                "label": quota.format_bytes(row.get("file_size") or 0),
                "kind": row.get(KIND_FIELD) or "Other",
                "folder": (row.get("folder") or ROOT).rsplit("/", 1)[-1],
            }
            for row in sorted(rows, key=lambda one: -(one.get("file_size") or 0))[:BIGGEST]
        ],
        "visible": sum(by_kind.values()),
        # Laboured here rather than in the browser because the meter beside it
        # is laboured here: two formatters over one quantity read as two
        # numbers, and this one said "86 MB" under a meter saying "85.8 MB".
        "visible_label": quota.format_bytes(sum(by_kind.values())),
        "files": len(rows),
        "workspace": quota.usage_summary(),
    }
