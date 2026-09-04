"""The places in the rail, as filters on one table.

Home, Recents, Favourites, Shared, Trash. Every one of them is the same query
with a different `where` and a different order — there is no second store behind
any of them, which is the whole reason the rail is cheap.

The one that is not a filter is Shared, and it is worth saying why: a file is
shared with somebody through `DocShare`, and `get_list` already joins that in
for every reader. So "shared with me" is "not mine, and I can see it", which is
a filter on `owner` over a query that was already permission-scoped.
"""

import frappe
from frappe import _

from .kinds import ACTIVE, KIND_FIELD, OPENED_FIELD, STATUS_FIELD, TRASHED

# Frappe's own root folder. Every file is somewhere under it.
ROOT = "Home"

HOME = "home"
RECENTS = "recents"
FAVOURITES = "favourites"
SHARED = "shared"
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

PLACES = (HOME, RECENTS, FAVOURITES, SHARED, TRASH, ALL, RECORD)

# Where each place looks and how it is ordered. `order` is the reader's default;
# a column header still overrides it.
ORDER = {
    HOME: f"is_folder desc, file_name asc",
    RECENTS: f"{OPENED_FIELD} desc",
    FAVOURITES: "modified desc",
    SHARED: "modified desc",
    TRASH: "custom_trashed_on desc",
    ALL: "modified desc",
    RECORD: "creation desc",
}


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
        # Frappe's own attachments land in `Home/Attachments`, which is a
        # folder like any other and shows as one.
        filters["folder"] = folder or ["in", ["", "Home", None]]
        # `Home` is the drive, not a thing inside it. Its own `folder` is
        # empty, so without this the root lists itself and clicking it is a
        # loop back to where you already are.
        filters["name"] = ["!=", ROOT]
    elif place == FAVOURITES:
        filters["_liked_by"] = ["like", f"%{frappe.session.user}%"]
    elif place == SHARED:
        # Reachable and not mine. What makes it reachable is `DocShare`, which
        # `get_list` has already applied by the time this filter is read.
        filters["owner"] = ["!=", frappe.session.user]
    elif place == RECENTS:
        filters[OPENED_FIELD] = ["is", "set"]
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
