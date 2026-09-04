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
"""

import frappe

from .kinds import (
    KIND_FIELD, KINDS, OPENED_FIELD, STATUS_FIELD, TRASHED_FIELD,
    ACTIVE, TRASHED, kind_of, on_insert,
)
from .query import PLACES, _place_filters, _visible
from .reading import PAGE, listing, path, storage
from .writing import (
    empty_trash, make_folder, move, rename, restore, sweep_trash, trash,
)

__all__ = [
    "ACTIVE",
    "KINDS",
    "KIND_FIELD",
    "OPENED_FIELD",
    "PAGE",
    "PLACES",
    "STATUS_FIELD",
    "TRASHED",
    "TRASHED_FIELD",
    "_place_filters",
    "_visible",
    "empty_trash",
    "kind_of",
    "listing",
    "make_folder",
    "move",
    "on_insert",
    "path",
    "rename",
    "restore",
    "storage",
    "sweep_trash",
    "trash",
]
