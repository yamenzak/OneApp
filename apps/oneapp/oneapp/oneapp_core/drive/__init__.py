"""Every file in the workspace, in one place.

Attachments were a per-surface afterthought: an uploader on the record's Meta
tab, a second in the composer, a third behind every Attach field, and no screen
anywhere that could answer "what is this workspace storing". This is the one
place, and every other surface becomes a view onto it.

## It is `File`, not a new model

There is no Drive entity. A file here is Frappe's own `File` row — the same one
`storage/file.py` already overrides to put content in R2, the same one an
attachment already is. Four columns are added and nothing else:

    custom_kind        Folder / Image / PDF / Video / Audio / Document / Other
    custom_status      Active / Trashed
    custom_trashed_on  when, so trash can empty itself
    custom_opened      last opened, which is what Recents orders by

Folders are `File.is_folder` with `File.folder` as the parent, which the
framework already has and the desk already uses.

That one decision is what makes the rest cheap. **A file attached to a record
has `attached_to_doctype`; a file in a folder has `folder`; a file can have
both** — so the Drive and a record's Files tab are two queries over one table
rather than two stores to keep in step.

## Who may see one

`DocShare`, `File.is_private`, and the framework's own rule that access to an
attachment follows the document it hangs off. Not a permission table of our own:
this product has refused that in `spaceview`, in `email/inbound` and in
`spaceview/mail`, each time because two systems deciding the same question is
two systems that will disagree. Every read here goes through `get_list`, which
applies all three.

The layers, in import order:

    kinds     what a file is, from its mime type
    query     the places — home, recents, favourites, shared, trash — as filters
    reading   listing a place, the path to a folder, one file's details
    writing   folders, renaming, moving, trashing, restoring, emptying
    sharing   a link that outlives a session, which is the one thing
              `DocShare` cannot be
"""

import frappe

from .kinds import (
    KIND_FIELD, KINDS, OPENED_FIELD, STATUS_FIELD, TRASHED_FIELD,
    ACTIVE, TRASHED, kind_of, on_insert,
)
from .query import ALL, PLACES, RECORD, _place_filters, _visible
from .reading import PAGE, details, listing, path, storage
from .writing import (
    attach, empty_trash, make_folder, move, rename, restore, set_favourite,
    sweep_trash, trash,
)
from .sharing import (
    DEFAULT_DAYS, MAX_DAYS, SECRET_BYTES, colleagues, links, make_link, open_link, people,
    revoke, share_with, sweep_links, unshare_with,
)

__all__ = [
    "ACTIVE",
    "ALL",
    "attach",
    "colleagues",
    "DEFAULT_DAYS",
    "details",
    "empty_trash",
    "KIND_FIELD",
    "kind_of",
    "KINDS",
    "links",
    "listing",
    "make_folder",
    "make_link",
    "MAX_DAYS",
    "move",
    "on_insert",
    "open_link",
    "OPENED_FIELD",
    "PAGE",
    "path",
    "people",
    "PLACES",
    "RECORD",
    "rename",
    "restore",
    "revoke",
    "SECRET_BYTES",
    "set_favourite",
    "share_with",
    "STATUS_FIELD",
    "storage",
    "sweep_links",
    "sweep_trash",
    "trash",
    "TRASHED",
    "TRASHED_FIELD",
    "unshare_with",
    "_place_filters",
    "_visible",
]
