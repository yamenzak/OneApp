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
License v3, and this repository is MIT. The standing rule in `CLAUDE.md` holds
without exception here: read it for patterns, paste nothing.

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
* The link is `File Link` — a secret, an expiry, a revoked flag and a count.
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

### Stage 1 — A file is somewhere, not just attached to something

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

### Stage 2 — The reader

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

Server side, one module — `oneapp_core/drive.py` — with the reader shaped like
`mailbox`'s: a scope, a query, and the actions. `sync.granted_doctypes()` has no
part in it; a file is not a doctype screen.

### Stage 3 — Preview, and the link that outlives a session

Six previewers, the same six Drive has, because they are the six that cover a
workspace's files: image, PDF, video, audio, text, and a fallback that offers the
download. Video and audio need range requests, which means a streaming endpoint
rather than a presigned redirect — our `download` already redirects, and a
`<video>` element following a 302 to a presigned URL works, so this may be free.

**A public link** is `Drive Token`'s idea done our way: a row naming a file, an
expiry, and a secret in the URL. Not `is_private = 0` — that is a site-wide flag
with no expiry and no audit, and "share this one drawing with the consultant
until Friday" is the actual request.

### Stage 4 — Every attach surface becomes a picker

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

### Stage 5 — Sharing, favourites, recents, trash

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

### Stage 6 — The storage screen

The quota is enforced and invisible. A screen in Settings with what is stored,
by kind, by biggest, by folder, and what the plan allows — reading
`storage/quota.py`, which already computes all of it.

### Stage 7 — What we deliberately do not take

* **Drive's own editors.** `Documents` and `Slides` are a word processor and a
  presentation tool. That is a product, not a feature, and the same argument
  `docs/EMAIL.md` makes about Frappe Mail applies unchanged.
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
