"""The places in the rail, as filters on one table.

Home, Recents, Favourites, Shared, Templates, Trash. Every one of them is the
same query with a different `where` and a different order — there is no second
store behind any of them, which is the whole reason the rail is cheap.

The one that is not a filter is Shared, and it is worth saying why: a file is
shared with somebody through `DocShare`, and `get_list` already joins that in
for every reader. So "shared with me" is "not mine, and I can see it", which is
a filter on `owner` over a query that was already permission-scoped.
"""

import frappe
from frappe import _

from .kinds import ACTIVE, KIND_FIELD, OPENED_FIELD, STATUS_FIELD, TEMPLATE_FIELD, TRASHED

# Frappe's own root folder. Every file is somewhere under it.
ROOT = "Home"

HOME = "home"
RECENTS = "recents"
FAVOURITES = "favourites"
SHARED = "shared"

# Everything flagged as one to start from, of either kind. A rail entry rather
# than a folder: a template is a flag on a file and the file stays wherever its
# owner put it, so "the templates" is a filter and a folder would be a second
# place to keep them in step with.
TEMPLATES = "templates"

TRASH = "trash"

# Not in the rail. Every file this person can see, wherever it sits — which is
# what a picker wants and what the rail never should: a flat list of a
# workspace's files is a list of its attachments, and the folders are the only
# thing that makes the drive legible. The picker is the opposite case. It is
# already scoped to one field on one record, the person knows what they are
# looking for, and making them walk into `Home/Attachments` to find the file
# they uploaded yesterday is a folder tree used as an obstacle.
ALL = "all"

# Also not in the rail, and the one that proves the whole design: what a record
# has filed against it is this same query with `attached_to_doctype` set. The
# Drive and a record's Files tab are two `where` clauses over one table, so the
# tab draws the Drive's own rows rather than a second list that looks like them.
RECORD = "record"

# The same query, walked rather than filtered. `record` answers "what is filed
# against *this* one"; this is the tree over all of them — a directory per kind
# of record, and one per record inside it — which is what a mounted
# `doctype:Quotation` already presents over WebDAV. The Drive draws the same
# tree from the same resolver, because a rail place and a mount that disagree
# about what a record has on it would be two answers to one question.
#
# Not a filter, so it has no entry in `ORDER` and no clause in
# `_place_filters`: `reading.listing` hands it to `scopes.py` instead. It is in
# `PLACES` because that is the list the endpoint validates against, and a place
# the client may ask for has to be in it.
RECORDS = "records"

PLACES = (HOME, RECENTS, FAVOURITES, SHARED, TEMPLATES, TRASH, ALL, RECORD,
          RECORDS)

# Where each place looks and how it is ordered. `order` is the reader's default;
# a column header still overrides it.
ORDER = {
    HOME: f"is_folder desc, file_name asc",
    RECENTS: f"{OPENED_FIELD} desc",
    FAVOURITES: "modified desc",
    SHARED: "modified desc",
    TEMPLATES: "file_name asc",
    TRASH: "custom_trashed_on desc",
    ALL: "modified desc",
    RECORD: "creation desc",
    RECORDS: "creation desc",
}


# What a reader may order by, and the expression each one means.
#
# An allowlist and not the string the client sent, because `order_by` reaches
# `get_list` and `get_list` puts it in the query: a whitelisted GET that takes
# arbitrary SQL there is a read of any table on the site. Nothing sent this
# until the Drive grew a sort control, which is exactly when a dormant hole
# stops being dormant.
#
# A folder is always first whatever the key is. A file manager that mixes them
# is a file manager where a folder is somewhere in the middle of page two, and
# nobody has ever wanted that.
SORTABLE = {
    "name": "file_name",
    "modified": "modified",
    "size": "file_size",
    "kind": KIND_FIELD,
}

FOLDERS_FIRST = "is_folder desc"


def ordering(place: str, key: str, descending: bool) -> str:
    """One of `SORTABLE`, or the place's own default when the key is not one."""
    field = SORTABLE.get(key or "")
    if not field:
        return ORDER.get(place) or "modified desc"
    return f"{FOLDERS_FIRST}, {field} {'desc' if descending else 'asc'}"


def _visible() -> dict:
    """The filter every place starts from: files that are not in the bin.

    `["in", [Active, ""]]` rather than `= Active`, because a file uploaded
    before this module existed has no status and is not thereby deleted. That is
    also why nothing backfills the column — its absence already means Active,
    and a write over every File on a site to say so would be a migration that
    changes nothing.
    """
    return {STATUS_FIELD: ["in", [ACTIVE, "", None]]}


def _place_filters(place: str, folder: str = "", kind: str = "",
                   attached_to: tuple[str, str] = ("", "")) -> tuple[dict, list]:
    """One place, as `(filters, or_filters)`.

    Both halves come back together and a caller may not take one: `or_filters`
    on its own widens a query rather than narrowing it, which is how a scoped
    list becomes every row on the site.
    """
    filters = {}
    or_filters = []

    if place == TRASH:
        filters[STATUS_FIELD] = TRASHED
    else:
        filters.update(_visible())

    if place == HOME:
        # A folder is a place, and the top of the drive is what sits in `Home`.
        filters["folder"] = folder or ["in", ["", "Home", None]]
        # `Home` is the drive, not a thing inside it. Its own `folder` is
        # empty, so without this the root lists itself and clicking it is a
        # loop back to where you already are.
        filters["name"] = ["!=", ROOT]
        if not folder:
            # And not the attachments, which since §E1 have no folder at all:
            # they belong to a record and live in the Records tree. Without
            # this clause, dropping Frappe's `Home/Attachments` bucket would
            # put every attachment in the workspace at the top of the drive,
            # which is worse than the bucket was.
            #
            # Only at the root. A file that is both attached and filed into a
            # folder somebody made shows in that folder, which is the whole of
            # what "it can have both" means.
            #
            # `is not set` and not `in ["", None]`: a NULL never matches
            # anything inside an SQL `IN`, so that spelling would have hidden
            # every file that is *not* attached — which is all of them at the
            # root, and is what it did.
            filters["attached_to_doctype"] = ["is", "not set"]
    elif place == FAVOURITES:
        filters["_liked_by"] = ["like", f"%{frappe.session.user}%"]
    elif place == SHARED:
        # Reachable and not mine. What makes it reachable is `DocShare`, which
        # `get_list` has already applied by the time this filter is read.
        filters["owner"] = ["!=", frappe.session.user]
    elif place == RECENTS:
        filters[OPENED_FIELD] = ["is", "set"]
    elif place == TEMPLATES:
        filters[TEMPLATE_FIELD] = 1
    elif place == ALL:
        # No folder clause at all. The only thing excluded is the root itself,
        # for the same reason Home excludes it: it is the drive, not a file.
        filters["name"] = ["!=", ROOT]
    elif place == RECORD:
        doctype, docname = attached_to
        # An unaddressed record place would be every attachment on the site,
        # which is the one way this filter could be dangerous. `get_list` would
        # still scope it to what the reader may see; that is not a reason to
        # ask a question this broad by accident.
        if not doctype or not docname:
            frappe.throw(_("Which record's files?"))
        filters["attached_to_doctype"] = doctype
        filters["attached_to_name"] = docname

    if kind:
        filters[KIND_FIELD] = kind

    return filters, or_filters


def _searching(search: str, filters: dict, or_filters: list):
    """Narrow a place to what matches — by name, and by what a document says.

    A file manager searches filenames because a filename is all it has. A
    document has more: `Doc Body.html` is what the editor rendered, written on
    every save, so "the one where we agreed retention was five per cent" is a
    question this can answer without an index, an extension or a second store.

    `get_all` here and `get_list` in the caller, deliberately. This query only
    produces candidate names; the reader's own permission is applied by the
    `File` query those names go into, which is the only place it could be
    applied correctly — `Doc Body` is a body, and who may read a body is
    settled by the file it belongs to.

    Both halves go in as `or_filters` rather than as a second query, because
    one file can match on its name and on its text, and merging two paged
    result sets is how a list starts skipping rows.
    """
    like = f"%{search}%"
    hits = frappe.get_all(
        "Doc Body", filters={"html": ["like", like]}, pluck="doc", limit=200
    )
    if not hits:
        filters["file_name"] = ["like", like]
        return or_filters

    # A dict rather than the `[doctype, field, op, value]` list form. The list
    # form makes Frappe join the doctype in again, and a file that matches on
    # both its name and its text then comes back twice — which the caller pages
    # and the reader sees as the same document listed under itself.
    return {"file_name": ["like", like], "name": ["in", hits]}
