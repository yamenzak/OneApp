# Flows

## Uploading

Two paths, and which one is taken is about size rather than about kind.

**Ordinary.** Frappe's own upload, then `file.py`'s override moves the object
to R2 and rewrites the URL.

**Direct.** `direct.py` — the browser PUTs straight at the bucket and only
tells us where it put it. `begin` reserves, `sign` hands back a presigned URL,
`finish` lands the row, `abort` cleans up. `direct.land`, `replace` and
`duplicate` are the same ending for a file that arrived three different ways,
which is why they are one function rather than three.

## Listing — `reading.py`, over `query.py`

`listing(place, folder, …)` resolves a place to a `where` and runs it. A place
is a filter, so adding one is adding a filter.

`path` walks the breadcrumb. `details` is the pane. `storage` is what the quota
bar reads.

**Attachments are folderless and Home excludes them.** Frappe files every
attachment into one `Home/Attachments` bucket, so a workspace with four
thousand quotations has four thousand files in a folder nobody browses.
`file.set_folder_name` leaves them where they are — reachable by the address
they already have, through the Records tree.

## Binning — `writing.py`

**The bin sets a column.** `custom_trashed_on`, and a sweep decides at thirty
days. Frappe deletes a `File` and its object together, so the only undo was a
backup, and a backup is not an undo — it is a support ticket.

## Sharing — `sharing.py`

Two things, and neither is a permission table of ours.

**With a person**: `DocShare`, Frappe's own. `share_with`, `unshare_with`,
`people`, `colleagues`.

**With a link**: a `File Link` with a secret, a level, an expiry and a revoke.
`make_link`, `links`, `revoke`, `open_link`. It outlives a session, which is
the point — a link in a mail still works tomorrow.

Two systems deciding one question is two systems that will disagree, which is
the same refusal `spaceview` and `email/inbound` make.

## Mounting somebody else's host — `remote.py`, `scopes.py`

A `Remote Folder` is a host, a protocol and a credential. `connect_folder`,
`check_remote`, `set_paused`, `disconnect`, `copy_here`.

**Browsed live and never copied**, so there is no sync to be wrong, and
**read-only through the Drive**: it reads a host, it does not write to one.
`copy_here` is the explicit way across.

## The other direction — `dav.py`

WebDAV out, so a person can mount the workspace's Drive in Finder or VS Code.
`share_folder` makes a `Drive Access`; `shares` lists; `revoke_share` ends one.
`scopes.children` is what a mount walks, and it is the same resolver the
Records tree uses.

## Opening something linked — `linked.py`

`follow`, `open_file`, `save_file` — the path a record's Files tab takes.

**Nothing here takes a doctype, a filter or a fieldname from the caller.** That
sentence is this module's doctrine and `onecode/manifest.py` inherits it: the
caller names a file, and what may be done with it is worked out from the file.

## Previewing — `walk.py`, `thumbnails.py`

`preview` renders what can be rendered; `thumbnail` caches the small version.
Both are reads of a file the caller already named.
