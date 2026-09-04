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

from .kinds import ACTIVE, KIND_FIELD, OPENED_FIELD, STATUS_FIELD, TRASHED

# Frappe's own root folder. Every file is somewhere under it.
ROOT = "Home"

HOME = "home"
RECENTS = "recents"
FAVOURITES = "favourites"
SHARED = "shared"
TRASH = "trash"

PLACES = (HOME, RECENTS, FAVOURITES, SHARED, TRASH)

# Where each place looks and how it is ordered. `order` is the reader's default;
# a column header still overrides it.
ORDER = {
    HOME: f"is_folder desc, file_name asc",
    RECENTS: f"{OPENED_FIELD} desc",
    FAVOURITES: "modified desc",
    SHARED: "modified desc",
    TRASH: "custom_trashed_on desc",
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


def _place_filters(place: str, folder: str = "", kind: str = "") -> tuple[dict, list]:
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

    if kind:
        filters[KIND_FIELD] = kind

    return filters, or_filters
