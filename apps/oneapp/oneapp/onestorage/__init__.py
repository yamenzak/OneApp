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
    remote    a folder on an FTP or SFTP host, browsed live and never copied
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
# The object store under all of it: where a file's bytes live, how a big
# upload gets there without passing through the web server, and what one
# workspace is allowed to keep. Part of this module's front door rather than a
# package of its own, because "the Drive" and "where the Drive puts things" are
# one subject and were only ever two directories.
# The conversation *about* a file, which is not the notes inside it. Frappe's
# `Comment` on the `File` row, so an `@` notifies and a remark turns up in the
# same feed as one on a record.
from .chatting import notes, say, unsay
from .direct import abort, begin, finish, sign
# A file a stranger can open, and — if the link says so — edit. Its own module
# and its own three endpoints, because a guest cannot be *granted* a
# permission in Frappe and the alternative was widening the ones everybody
# else uses. See `docs/COLLABORATION.md` §5.
from .linked import MAX_PAYLOAD, follow, open_file, save_file
from .r2 import download, serve
# A folder on somebody else's server, browsed live rather than synced. Its own
# module because it is the one place in this package where a row is not a
# `File` — see the argument at the top of `remote.py`.
from .remote import (
    check_remote, connect_folder, copy_here, disconnect, mounts, set_paused,
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
    "abort",
    "begin",
    "details",
    "download",
    "empty_trash",
    "finish",
    "follow",
    "KIND_FIELD",
    "kind_of",
    "KINDS",
    "links",
    "check_remote",
    "connect_folder",
    "copy_here",
    "disconnect",
    "listing",
    "make_folder",
    "make_link",
    "MAX_PAYLOAD",
    "MAX_DAYS",
    "mounts",
    "move",
    "notes",
    "on_insert",
    "open_file",
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
    "save_file",
    "say",
    "SECRET_BYTES",
    "set_favourite",
    "set_paused",
    "share_with",
    "STATUS_FIELD",
    "serve",
    "sign",
    "storage",
    "sweep_links",
    "sweep_trash",
    "trash",
    "TRASHED",
    "TRASHED_FIELD",
    "unsay",
    "unshare_with",
    "_place_filters",
    "_visible",
]
