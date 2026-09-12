# Files

Every file in the product, in one place, with one way of looking at it: a Drive.

Today attachments are a per-surface afterthought — a `FileUploader` on the
record's Meta tab, a second in the composer, a third behind every Attach field —
and no screen anywhere shows a workspace what it is storing. This is the plan for
replacing all of that with one file manager, and for making every other
attachment surface a view onto it.

Written as a study before any of it is built. §1 is the licence position, because
it decides what "move the UI" can mean. §2–4 are what Frappe Drive actually is,
read out of the repository. §5 is what we already have. §6 is the plan.

---

## 1. What we may take, and what we may not

**`frappe/drive` is AGPL-3.0.** Its `LICENSE` is the GNU Affero General Public
License v3. **This was written while this repository was MIT**, and the rule
then was to read Drive for patterns and paste nothing — which is what the Drive
that shipped did, and why none of it is derived. The repository is AGPL-3.0 now
(see `docs/SHEETS.md` §1), so the prohibition has lifted; what is below is the
history of a decision, not a live constraint.

That rule is easy to get wrong on this particular job, because Drive is built
with frappe-ui and the request was to "move the UI". Two different things wear
that name:

* **frappe-ui itself is MIT**, and we already depend on it. Every component Drive
  draws with — `ListView`, `Dropdown`, `FileUploader`, `Dialog` — is available to
  us directly and always was.
* **Drive's own `.vue` files are AGPL.** `GridView.vue`, `Sidebar.vue`,
  `FileRender.vue` and the rest are Drive's source, not frappe-ui's, whatever
  they are assembled from.

So what moves is the **shape**: the sidebar of Home / Recents / Favourites /
Shared / Trash, the list-and-grid toggle, the breadcrumb path, the drag-to-move,
the preview overlay per file kind, the upload tracker in the corner. Those are
ideas, and ideas are not what a licence covers. The code is ours to write.

Where a behaviour is subtle enough that a paragraph is the honest way to carry it
across, this document is where that paragraph goes.

## 2. What Frappe Drive is, structurally

The most useful finding, and the one that makes this whole plan cheaper than it
looks:

**Drive is built on Frappe's core `File` doctype.** There is no `Drive File`
entity any more — there was, and `patches/integrate_with_framework.py` migrated
away from it. What Drive adds is:

* an override class registered as `override_doctype_class` on `File`;
* seven custom fields on `File` — `team`, `mime_type`, `status`
  (Active/Trashed/Removed), `file_modified`, and a `content_doctype` /
  `content_docname` pair for files whose contents are a document rather than
  bytes;
* a `user_has_permission` hook on `File`;
* eleven small doctypes beside it, none of which is the file itself.

That is the same architecture we already have. `storage/file.py` is a `File`
override registered exactly the same way, and `install.create_custom_fields`
already adds `File.r2_key`. We are not adopting a new model; we are extending the
one both products already share.

### The doctypes beside it

| | |
|---|---|
| `Drive Permission` | user × entity × {read, write, comment, share, upload}, inherited down the folder tree |
| `Drive Team` | a container with its own bucket, prefix, quota and members |
| `Drive Team Member` | user × access level (0 guest, 1 user, 2 admin) |
| `Drive Favourite` | user × entity |
| `Drive Entity Log` | user × entity × last interaction — this is what "Recents" reads |
| `Drive Entity Activity Log` | who did what to a file, field by field |
| `Drive Notification` | share and mention notices |
| `Drive Token` | a time-boxed grant for one file, for links that outlive a session |
| `Drive Disk Settings` | S3 credentials, bucket, thumbnail prefix, preview size |

### The API

`drive/api/` is eleven modules. The ones that matter to us:

* **`files.py`** — chunked `upload_file`, `create_folder`, `create_link`,
  `get_file_content` with a `trigger_download` flag, `stream_file_content` for
  media, `download_folder` which streams a zip, plus `rename`, `move`,
  `remove_or_restore`, `delete_entities`, `set_favourite`, `search`.
* **`list.py`** — `files`, `shared`, `favourites`, `recents`, `trash`, and
  **`get_attachments(doctype, docname)`**. That last one is Drive already doing
  what this request asks for: a document's attachments, listed through the Drive
  reader.
* **`permissions.py`** — `get_user_access`, `get_team_access`, `filter_access`.
* **`s3.py`, `storage.py`** — the object store and the quota.

### The frontend

Sixteen pages and forty components. The pages are the feature list: `Folder`,
`File`, `Shared`, `Favourites`, `Recents`, `Trash`, `Team`, `Teams`,
`Notifications`, **`Attachments`**, plus `Documents` and `Slides` for Drive's own
editors. `FileTypePreview/` holds six previewers — image, PDF, video, audio,
text, MS Office.

## 3. The one place we must not follow

Drive's access model is a **parallel permission system**. `Drive Permission` is
its own table of user × entity × verb, inherited up the folder tree by
`generate_upward_path`, with `Drive Team` membership as a second source and an
`access_level` integer as a third.

This product has refused that everywhere it has come up, and said so each time:

* `spaceview` — "Permission is Frappe's, not ours … This reports what the user
  may do so the UI can hide what it must; it does not decide it."
* `inbound._share` — "a permission system of our own beside it would be two
  systems disagreeing about the same row."
* `spaceview/mail.py` — the record's correspondence is read with `get_list`
  precisely so that the framework decides.

Drive itself half-concedes the point: `get_user_access` has a `is_site_file`
branch that defers to `ff_has_permission` for files that came from the framework
rather than from Drive. That branch exists because two systems were disagreeing.

**So we take Drive's model of a file and not its model of who may read one.**
Ours is `DocShare` — which the record surface, the search and the list already
respect — plus the space manifest, plus `File.is_private`. A folder's grant is a
`DocShare` on the folder; inheritance is a query up `folder`, not a second
table.

The one thing genuinely missing from the framework is a **link that outlives a
session**, which is what `Drive Token` is for. That is a real gap and worth
copying as an idea: one row, a file, an expiry, and no session.

## 4. What we already have

* **`storage/r2.py`** — R2 through boto3, `object_key`, `upload`, `delete`,
  `presigned_url`, and a `download` endpoint whose permission check is the whole
  point of it existing. Objects are never publicly reachable.
* **`storage/file.py`** — the `File` override, moving content to R2 on insert and
  falling back to the filesystem when R2 is unconfigured.
* **`storage/quota.py`** — enforced at upload time rather than after the fact.
* **`File.r2_key`** — already a custom field, for the reason `docs/` records:
  a rename or a key-scheme change cannot orphan objects we can no longer find.
  It is also what makes a restore survivable: `onespace/restore.reconcile` is
  the set difference between these keys and what the bucket actually holds, in
  both directions — objects no row claims are deleted, and rows whose object is
  gone are counted and said out loud.
* **`spaceview/surround.py`** — `attachments`, `remove_attachment`, and the
  gallery filters.
* **The surfaces that would become views**: `RecordFiles.vue` (the record's Files
  tab), `AttachmentGallery.vue` (the declared gallery fieldtype),
  `FieldControl.vue`'s `FileUploader` branch for `Attach` and `Attach Image`,
  `RecordMeta.vue`'s image uploader, and `MailComposer.vue`'s attach button.

Five upload surfaces, no browser, and nothing that can answer "what is in this
workspace's storage".

## 5. What is missing, precisely

Against Drive, and in the order a person would notice:

1. **No file manager at all.** No folders, no tree, no browsing.
2. **No preview.** A PDF or an image opens by downloading it.
3. **No picker.** Every attach surface can upload and cannot choose something
   already here, so the same drawing is uploaded four times.
4. **No recents, favourites, or trash.** A deleted attachment is gone.
5. **No search over files.**
6. **No sharing of a file as a file** — only whatever the record it hangs off
   grants.
7. **No public link.** `is_private` is a flag with no surface.
8. **No storage screen.** The quota is enforced and never shown.

## 6. The plan

Seven stages. Each is shippable and none needs the next; the order is what makes
the next one cheaper, and the first two are what everything else is a view onto.

**Stages 1 to 6 are built.** What the stages below said, and what the building of
them changed:

* The picker asks for a place that is not in the rail. `place=all` is every file
  the reader can see, flat, with no folder clause — because almost every file in
  a workspace is an attachment living in `Home/Attachments`, and a picker over
  the root folder shows an empty drive. The rail keeps its five places, where
  folders are what makes the drive legible; the picker is the opposite case.
* Picking a file that is already attached somewhere writes a **second** `File`
  row pointing at the same object, rather than moving the first. The file being
  picked is usually already attached to something else, which is generally why it
  was worth picking.
* The link is `File Link` — a secret, an expiry, a revoked flag, a count and a
  level. Where it *goes* is decided by the kind: a workbook or a document opens
  at `/one/link/<secret>` in the editor it belongs in, at the level the link
  says; anything else is bytes through `open_link`. `docs/COLLABORATION.md` §5.
  Guest-callable, so the secret is the whole of the authentication: every refusal
  says the same sentence, because a message that distinguished expired from wrong
  would tell a stranger whether the secret was right. Revoking marks rather than
  deletes, and the sweep drops rows thirty days *after* they expire, because "it
  stopped working last Tuesday" is asked in the week after it stops working.
* Sharing replaces the preview rather than stacking on it. Two open modals nest
  and the outer goes `aria-hidden` under the inner.
* Both the preview and the link go through **one** function, `r2.serve`. Serving
  a presigned redirect unconditionally is correct only on a site that has a
  bucket, and on one that does not — development, and anybody self-hosting before
  they buy storage — the preview fetched the download route and rendered the
  error page as the file's contents. A `.txt` whose preview reads
  "Redirecting..." is what that looked like.
* A record's Files tab is the Drive filtered to one record — the same `FileRow`
  over the same query with `attached_to_doctype` set, which is what §6 said it
  should be and the proof that the two surfaces are one. Taking a file off a
  record now goes to the bin rather than deleting the row: a misplaced click on
  the wrong record's tab was previously unrecoverable, and the bin exists so
  that it is not.
* The share dialog's body is one component, `SharePanel`, rendered by both the
  record surface and the Drive. A record and a file are shared by the same three
  questions; two copies would be two places to fix "can edit" in. What differs
  is three calls, and they arrive as functions.
* Sharing a file with somebody outside the workspace is refused by the same
  bound the assignment picker uses. It matters more on a `File` than on a
  record, because a file is the thing people actually send.
* A settings panel is a flex item sized by its content, and `min-w-0` only says
  it *may* shrink. Nothing stopped one growing past the dialog, which then
  clipped the right of every line in it — header included. `w-0` on the panel
  makes the free space its whole width. Latent for every panel wide enough to
  hit it; the storage screen was the first.

Two shapes the reader had to change to hold Stage 5:

* `FileRow` put the whole row inside a `Button`. A button inside a button is
  neither valid nor reachable by a keyboard, so nothing could be added beside
  the name until the row became a container with the name inside it.
* Its controls are drawn always rather than on hover. A phone has no hover, so a
  heart that appears on `group-hover` does not exist on half the devices this
  runs on.

**Where this has got to.** Stages 1 to 6 are built and live. Stage 7 is still
deliberately absent. The stages below are the plan as written, ticked where the
code caught up with it.

### Stage 1 — A file is somewhere, not just attached to something  ✅

Folders, on `File`'s own `folder` field, which the framework already has and
Frappe's desk already uses. Custom fields to match Drive's, minus the ones its
parallel model needs:

    File.custom_kind        Folder / Image / PDF / Video / Audio / Document / Other
    File.custom_status      Active / Trashed        (Drive's `status`, one fewer)
    File.custom_trashed_on  when, so trash can empty itself on a schedule
    File.custom_opened      last time somebody opened it — Recents, without a doctype

`custom_kind` is derived from the mime type on insert. It is a stored column
rather than a computed one for the reason every list in this product stores its
grouping key: a filter over four thousand files cannot be a Python `next()` over
a mime map.

Every existing attachment stays exactly where it is. A file attached to a record
has `attached_to_doctype`; a file in a folder has `folder`; a file can have both,
and that is the whole trick — **the Drive and the record's Files tab are two
queries over one table.**

### Stage 2 — The reader  ✅

`pages/Drive.vue` and `components/drive/`. The layout is the one every file
manager has had for thirty years and the reason to keep it is that nobody has to
learn it: a rail of places, a path, and a list or a grid.

* **The rail**: Home, Recents, Favourites, Shared with me, Trash, and the storage
  bar at the bottom.
* **The body**: list or grid, the toggle remembered per person like the record
  surface's pane-or-page. The list is `ListBody`'s own shape — this product
  already has a virtualized, resizable, sortable list and a second one would be a
  second one.
* **The path**: breadcrumbs that are links, so a folder is a place with a URL.
* **Selection and drag**: the selection bar we already have; drag onto a folder
  to move.

Server side, one module — `onestorage.py` — with the reader shaped like
`mailbox`'s: a scope, a query, and the actions. `sync.granted_doctypes()` has no
part in it; a file is not a doctype screen.

### Stage 3 — Preview, and the link that outlives a session  ✅

Six previewers, the same six Drive has, because they are the six that cover a
workspace's files: image, PDF, video, audio, text, and a fallback that offers the
download. Video and audio need range requests, which means a streaming endpoint
rather than a presigned redirect — our `download` already redirects, and a
`<video>` element following a 302 to a presigned URL works, so this may be free.

**A public link** is `Drive Token`'s idea done our way: a row naming a file, an
expiry, and a secret in the URL. Not `is_private = 0` — that is a site-wide flag
with no expiry and no audit, and "share this one drawing with the consultant
until Friday" is the actual request.

### Stage 4 — Every attach surface becomes a picker  ✅

The stage the request is really about, and it is small once Stage 2 exists.

One component, `FilePicker.vue`, with two tabs: **Upload** and **Choose from
Drive**. Upload writes into the Drive and then picks the result, so there is one
path and one place files end up. It replaces:

* `FieldControl.vue`'s `FileUploader` for `Attach` and `Attach Image` — the image
  case filters the picker to `custom_kind = "Image"`;
* `RecordMeta.vue`'s cover-image uploader;
* `AttachmentGallery.vue`'s add button;
* `MailComposer.vue`'s attach button — which is exactly "upload or pick from
  Drive", and where the request named it.

`RecordFiles.vue` becomes the Drive's list component filtered to
`attached_to_doctype`/`attached_to_name` — Drive's own `get_attachments` is the
same idea, and it is the proof that the two surfaces are one.

### Stage 5 — Sharing, favourites, recents, trash  ✅

* **Sharing** is `DocShare` on the `File`, drawn with the share control the
  record surface already has. A folder shared is every file under it, resolved by
  a query up `folder` at read time rather than by writing a row per descendant.
* **Favourites** is `_liked_by`, which the framework has on every doctype and
  this product already draws as a heart.
* **Recents** is `File.custom_opened`, stamped by the reader. One column, no
  doctype — Drive's `Drive Entity Log` is a row per user per file, and a
  workspace's own file list does not need per-person recency badly enough to pay
  for that.
* **Trash** is `custom_status`, with a scheduled sweep that empties past thirty
  days and deletes the R2 object then rather than on the click. A deleted
  attachment coming back is the single most-missed thing on this list.

### Stage 6 — The storage screen  ✅

Built, as `settings/StorageSettings.vue` over `storage/quota.py`: what is
stored, by kind and by biggest, and what the plan allows. The quota was
enforced and invisible; it is enforced and readable now.

### Stage 7 — What we deliberately do not take

* **`Slides`.** A presentation tool is a product, not a feature, and the same
  argument `docs/EMAIL.md` makes about Frappe Mail applies unchanged.
  `Documents` was on this line too and is built — see `docs/WRITER.md`, which
  also explains why the word processor turned out to be cheap and the
  presentation tool did not.
* **Teams.** `Drive Team` is Drive's answer to multi-tenancy and we have one: the
  workspace *is* the team, and a second container inside it is a second
  hierarchy for somebody to get lost in.
* **Drive's notification doctype.** We have a feed and a bell.

## 7. Order, and the one thing to decide first

Stages 1 and 2 are the whole of the risk, and they are mostly the reader. Stage 4
is what the request asks for and is a fortnight after Stage 2 rather than a
fortnight on its own.

The decision worth making before any code: **does a file in the Drive belong to a
person or to the workspace?** Drive answers "to a team, with a personal folder
beside it", and that shape is why `Drive Team` and `Drive Permission` exist. The
cheaper answer, and the one that matches everything else here, is that a file
belongs to the workspace and `DocShare` narrows it — which makes "my files" a
filter on `owner` rather than a second tree. Everything in §6 assumes the second
answer; the first would add a stage and a doctype.

## 8. Getting the bytes in

Written after the stages above were built, because the way in turned out to be
the part nobody had specified. Two paths, and which one a file takes is decided
by its size alone.

**Under 8 MB** it is one `multipart/form-data` POST to Frappe's own upload
endpoint, exactly as before: the request handler holds it in memory, writes it
to disk, inserts a `File`, and `storage/file.py` then reads it back and pushes
it to R2. Four copies of the bytes, which for a photograph nobody notices.

**Over 8 MB** it never comes here at all. The browser asks
`storage/direct.begin` for somewhere to put it, gets presigned URLs for an R2
multipart upload, PUTs the parts straight at Cloudflare three at a time, and
calls `storage/direct.finish`, which completes the upload and makes the `File`
row with `r2_key` already set. Frappe Drive proxies every byte through Python
and we deliberately do not: a two-gigabyte video through a worker meets the
request-body limit, the gunicorn timeout or the proxy's own ceiling, whichever
comes first, and none of the three fails in a way anybody can act on.

Four things the direct path has to get right, and all four are in
`storage/direct.py` with the reasoning beside them: the quota is checked before
anything is signed, so a full workspace is a refusal in the browser rather than
an upload thrown away at the end; an HMAC over the key, the upload id and the
session user means nobody can finish somebody else's upload; a row the quota
hook refuses takes its object with it, so a refused upload is never a billed
one; and the size written on the row is what R2 says it holds, not what the
browser claimed.

`begin` answers `{"direct": false}` — rather than throwing — whenever the path
does not apply: no bucket, no boto3, the control plane, a small file. The
browser reads that as "post it the ordinary way", so a development site with no
R2 keys works exactly as it did.

### The one configuration line that has to exist

**The bucket's CORS policy must expose `ETag`.** A multipart upload is completed
by sending each part's ETag back, and a response header the browser cannot read
does not exist as far as JavaScript is concerned — so without it every byte
uploads correctly and the upload fails on the last call, which is the most
expensive way a missing config line can fail. `r2.ensure_cors()` writes the
policy; it is a bucket-level operation, not a per-site one, so it is run once per
shard rather than on a schedule. See `docs/ONEADMIN.md`.

### Every attach surface takes the same route

`lib/files/attach.js` is one function — `putFile(file, {attachTo, folder})` — that
tries the direct path and falls back to the POST. The Drive's queue calls it and
so does the picker, which is what makes a large file attachable to a record and
not only droppable into the Drive. Before that the picker used frappe-ui's
`FileUploader`, which posts the whole body, so a 200 MB video went into the
Drive fine and failed the moment somebody attached one to a quotation.

The one surface still posting is an image pasted into a rich-text field, which
goes through the editor's own upload hook. A pasted image is a screenshot, and
the threshold is eight megabytes.

## 9. The one dialog

`FilePicker` is every attach surface in the product: the Attach and Attach Image
fieldtypes, the attachment gallery, a record's Files tab, its identity image,
the mail composer, and the sheet importer. Three sources, and the reasoning for
which three is in the component's own header — it is Frappe's own dialog minus
Link and Google Drive.

* **Library** — every file this person can see, flat and searchable, `place=all`
  rather than the root folder because almost every file in a workspace is an
  attachment living in `Home/Attachments`. First, because the file somebody
  wants is usually one that is already here.
* **This device** — a drop zone and a chooser, through `lib/files/attach.js`.
* **Camera** — `getUserMedia` with a live preview, a shutter and a front/back
  toggle, falling back to a `capture` input when the page is not on a secure
  origin or permission is refused. Frappe's desk has had this since
  `frappe/public/js/frappe/ui/capture.js`; every surface we built to replace the
  desk quietly did not.

Two props narrow it. `kind` is the Drive's own taxonomy, which is what an Attach
Image field wants. `extensions` is narrower and sometimes the only useful
filter — a spreadsheet and a Word document are both `Document`, and only one of
them can be imported as a sheet.

**`attached-to` is what makes a file belong to the record.** Omit it and the
file is made, the field gets its URL, and the row is loose in the Drive: absent
from the record's Files tab, absent from its attachment count, orphaned the
moment somebody clears the field. That is exactly how the Attach fieldtype
shipped — every other caller passed it and the one people use most did not — and
`test_frontend_guards.py::test_a_picker_on_a_record_attaches_to_it` now refuses
a picker on a record that omits it.

## 10. What the storage meter counts

`quota.current_usage` is the number every refusal and every meter reads, and it
counts **objects, not rows**.

The distinction is the whole of it. Attaching a file the workspace already has
does not upload it again — `File.create_attachment_copy` writes a second row
over the same object, which is what the picker's Library tab does and what an
attachment on a second record is. Summing `file_size` over rows billed that
drawing once per record it appeared on. Rows are grouped by `r2_key`, or by
`file_url` where the file is on local disk and Frappe's own duplicate check
already reuses the path.

Two other things now weigh what they weigh. A **sheet** carries its stored
workbook's size on its `File` row, written when it saves; before that every
sheet was zero bytes in a list whose job is to say how big things are. And the
**bin** is reported on the storage screen — how much it holds, and that each
file leaves for good thirty days after it went there — because a binned file
correctly still counts, and deleting a gigabyte while the meter does not move is
indistinguishable from a bug unless something says so.

---

## 11. A folder on somebody else's server

An authority does not email a GTFS feed; it puts it on SFTP and tells you the
folder. Neither does a bank, a laboratory or half of construction. So the
Drive takes a mount: **a `Remote Folder` is a protocol, a host, a credential
and a base path**, and once it exists it is a place in the rail with the same
list, the same breadcrumb, the same preview pane and the same Copy as
everything else. `apps/oneapp/oneapp/onestorage/remote.py` is the whole of it.

### Five protocols, two dependencies

| | What it is for | What it costs us |
|---|---|---|
| **SFTP** | What a transport authority runs, and most of the rest | `paramiko` |
| **FTPS**, **FTP** | Older authorities. Plain FTP sends the password in the clear and is offered because some of them still run nothing else | `ftplib`, stdlib |
| **SMB** | The office share — a site office, a finance department | `smbprotocol`, which is SMB2/3; `pysmb` is SMB1-era and vendors have switched SMB1 off |
| **WebDAV** | Nextcloud, ownCloud, SharePoint, every NAS | nothing — it is HTTP, so `requests` and sixty lines of `ElementTree` |

Two of the five needed a dependency and three did not, which is the whole
reason to write the adapters rather than take a "remote filesystem" library:
the abstraction those sell is the part that is four functions long.

Two shapes differ from the rest and both are on the `base_path`. **SMB has a
share**, which is not a directory you can list your way into, so the first
segment is it: `/drawings/2026` is the 2026 folder of the `drawings` share,
and a mount pointed at `/` is refused rather than left to fail on its first
browse. **WebDAV has a scheme**, and https is assumed — a host written
`http://nas.local` reaches a box on the local network without a second
dropdown entry that ninety-nine mounts in a hundred would not want.

The DAV listing is parsed on the local name of each element rather than on a
prefix, because `D:`, `d:` and `lp1:` are all in the wild and a prefix match
returns nothing for whichever server chose differently — which shows up as a
mount that lists empty rather than one that fails, and is the worst way for
this to be wrong.

### Nothing is copied

The rows a mount returns are not `File` rows and nothing writes one. Browsing
is live: the request opens a connection, lists the directory, and hands back
rows in the shape the Drive's own list already draws.

The alternative — sync the listing into `File` rows on a cron — fails three
ways at once, and each on its own is enough. The rows go stale between syncs,
which is the one thing a drop folder cannot be. They count against a storage
quota that measures bytes *we* are paying to keep. And deleting one would be
ambiguous in a way no confirmation dialog can fix.

The cost is real and is paid in one place: no cross-mount search, no favourite
on a remote file, no share of a single remote file, and a mount that is down is
a folder that says so rather than a folder that looks empty. Every one of those
refusals is a sentence rather than a stack trace — `remote.deny`, called from
`writing.py` and `sharing.py`, and a test reads the list back.

### What a remote file is called

`remote://<mount>/<path>`. It travels everywhere a `File` name does: it is a
row's `name`, the URL's `?folder=`, and what `r2.download` takes. Nothing
stores one, so the day the format changes there is no migration.

`..` is refused on every path, resolved nowhere. Resolving is the version that
looks right and is not — `normpath` over a symlink gives an answer the host
disagrees with, and the base path is the entire boundary.

### Who may open one

`Remote Folder` is System Manager: a row here is a credential, and a workspace
where anybody can type one has an exfiltration feature rather than a file
manager. Sharing works anyway and needed no code — `share` is in the perms, so
a manager gives a colleague a `DocShare` on the mount and `has_permission`
answers yes. The mount is the unit of sharing, because a single remote file has
no row to hang a share on.

### Connecting one proves it, and so does editing one

`connect_folder` inserts the row, opens the connection, lists the base path,
and **deletes the row again if either fails**. A credential form that saves
whatever you typed is the form every FTP integration has, and it is why "is the
feed running" is a question nobody can answer until a Monday morning. A mount
in the rail is a mount that answered at least once; a mount that stopped
answering is red there, with the host's own words on it, and a paused one is
grey.

`update_folder` runs the same `_prove` and **puts the old settings back when
the new ones do not work**, saying so. A typo in a hostname should cost you the
typo, not the connection that was working before you made it. Neither path can
write Connected without having connected, because both call one function.

The form is the same dialog as Connect, opened on a mount from its own folder
view — Connection settings, beside Pause and Disconnect. Two things it will not
do. It will not rename a mount: the name is its id and the first segment of
every `remote://` path under it, so renaming one renames every link anybody
saved. And it will not show a credential: `folder_settings` sends
`has_secret` and `has_private_key` rather than either value, the fields read
"Unchanged", and a blank one on save means leave it alone — because the form
cannot tell "leave it" from "clear it", and clearing a working credential by
opening a form and saving it is the worse of the two mistakes.

### What it replaced

OneMobility carried a host, a folder, a username, a password and forty lines of
paramiko on `Transit Source`, which made the feed reader the only part of the
product that could see an authority's SFTP server — and meant a person holding
the credentials had to be given a Transit Source form to type them into. A
source now names a mount and a path inside it, `sources._over_folder` is six
lines over `remote.newest`, and the folder a feed reads is a folder somebody
can *look at* in the file manager before wondering why the poll found nothing.
`oneapp/patches/sftp_sources_become_mounts.py` moves the existing ones, one
mount per host and username, paused until somebody checks them.

---

## 12. The other direction: a Drive folder served over WebDAV

§11 mounts somebody else's server here. This serves ours to them — a folder in
the Drive appears in Finder, in Windows Explorer, in Nextcloud's
external-storage list, and the files in it are the same `File` rows every
other surface draws. `apps/oneapp/oneapp/onestorage/dav.py`.

### Why WebDAV and not SFTP

Asked as a pair and answered separately, because they are only a pair from the
client's side.

**WebDAV is HTTP.** It rides the port the site already answers on, inside the
process already running, behind the proxy that already has the certificate.
Nothing new to deploy, nothing new to watch, no port to open.

**SFTP is a subsystem of SSH.** Serving it means a daemon, a listening port, a
host key, key rotation, and something keeping the daemon alive — a second
runtime. This product has refused one twice (`docs/COLLABORATION.md` §1 is the
last time), a shard is one GIL-bound Python process, and a tenant on Frappe
Cloud has nowhere to put a listener on port 22 in any case. It is not a
afternoon's work behind the same door; it is a different kind of thing.

So: WebDAV, which every operating system mounts natively, and no SFTP server.

### Getting a request at all

Frappe's dispatcher answers `/api/...` for any method, routes GET, HEAD and
POST to the website, and **raises NotFound for everything else** — so PROPFIND
on a path of ours 404s before any code of ours runs. The way in is
`before_request`, which runs after `frappe.connect()` and before both
`validate_auth()` and that dispatch: the hook builds a whole response and
raises it as an `HTTPException` whose `get_response` hands it back, which is
the one shape `application()` returns without re-rendering.

Two consequences, both load-bearing and both tested:

* **The route authenticates itself.** No session, no CSRF, no `validate_auth`.
  That is what a WebDAV client wants — it sends HTTP Basic and nothing else —
  and it means every check here is ours.
* **Frappe rolls back after any exception, including the one we return with.**
  So every handler that writes commits first. A handler that forgot would
  answer `201 Created` and change nothing, which is the worst shape available:
  the client believes the file arrived.

A third thing had to be fought for. Frappe replaces `WWW-Authenticate` with an
OAuth Bearer challenge on any 401 once resource metadata is enabled, and a
client told to use Bearer never shows a password box — the share simply cannot
be mounted. `frappe.local.response_headers` is applied after that, so the
Basic challenge is set twice and the second one wins.

### What a key is

A **`Drive Access`**: a generated username, a generated secret, scoped to one
folder, read-only by default, optionally expiring. Not the account password
and not an API key, because it needs all four of those properties and an API
key has none of them. It **acts as the person who made it**, so `get_list`
does the permission work and a key can never reach a file its owner could not.

The secret is a SHA-256 digest in the row — 32 bytes of `token_urlsafe`, so
there is nothing to brute-force and no reason for a reversible copy. The
plaintext exists once, in the dialog that made it, which is why that dialog
says so and offers three copy buttons.

Revoking is a row, not a password reset, and a revoked key is kept: `last_used`
is what answers "what was this, and when did anything last touch it".

### What it does and does not do

Every verb a file manager sends: OPTIONS, PROPFIND (depth 0 and 1), GET, HEAD,
PUT, MKCOL, DELETE, MOVE, COPY, PROPPATCH, LOCK, UNLOCK. A DELETE goes to the
**bin**, not to a delete — thirty days, the same as everywhere else, and this
is the last place to make a stray keypress final. A PUT goes through
`File.before_insert`, so it counts against the quota like every other upload.

Not done, and each for a reason: ranged GET; `Depth: infinity` on PROPFIND,
which the RFC lets a server refuse and which would otherwise be one request
that walks a whole Drive; and a deep COPY, which is a quota question per file
and is refused rather than half-done.

### The bytes, and the ceiling that is not ours

A PUT goes **straight into the bucket**. `direct.land` puts the object and
makes the `File` row already pointing at the key — the same landing the
browser's multipart upload uses at the end of its handshake. The alternative,
and what this did first, was `File.insert(content=…)`: Frappe writes the bytes
to the site's local disk, `OneSpaceFile.after_insert` reads them back, uploads
them to R2 and deletes the copy. Four passes over a drawing set on a request
worker, for nothing.

Two consequences worth naming. **An overwrite writes over the object the row
already owns**, so every link into it survives — a share URL, an `img src` in
a document — and only the difference in size is charged; unless another `File`
points at the same object, which is what attaching a Drive file to a record
writes, and then the new bytes get a new key so the other rows keep theirs.
**A COPY is a copy inside the bucket**, `copy_object` rather than a download
and an upload, which matters because COPY-then-DELETE is how Finder moves a
file between two shares.

What remains is a size ceiling, and it is the framework's rather than this
module's. `init_request` sets `request.max_content_length` from the site's
`max_file_size` and then calls `make_form_dict`, which reads the whole body —
both *before* the first `before_request` hook. By the time any code here runs
the body is already in memory or already refused, and Frappe exposes no WSGI
middleware seam to put a streaming reader in front of it. So a streaming PUT
is not reachable from app code; only the disk round-trip was.

The refusal is at least made legible. Werkzeug's 413 is an HTML error page
that a file manager displays as nothing, so an `after_request` hook
(`dav.explain_refusal`) rewrites it, on `/dav` paths only, into a plain-text
sentence naming the file's size, the ceiling, and the two ways past it:
upload through the Drive in a browser, which signs a multipart upload and
sends the parts at Cloudflare without passing through Python at all, or raise
`max_file_size` in the site configuration — which raises it for every upload
on the site, not just this share.

**Locks are answered and not enforced.** A lock is a promise that no other
writer will touch the file, and this runs in several processes behind a load
balancer with no shared lock manager; a lock table would make the promise and
break it. Finder and Office refuse to write to a share that 501s LOCK, so the
honest choice is between answering without enforcing and having no writing
from a Mac. Every small DAV server picks the first.
