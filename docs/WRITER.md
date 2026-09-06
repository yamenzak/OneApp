# Documents

The prose half of what a workspace writes. A scope of works, a method
statement, a letter, a set of minutes — the things a business writes that are
not a record and not a spreadsheet, and that until now left the workspace to be
written and came back as a `.docx` attachment nobody could search.

`docs/SHEETS.md` settled the model this is built on and `docs/DRIVE.md` settled
the one under that; this is short because most of it was already decided.

## 1. What we may take, and what it costs

`frappe/writer` is AGPL-3.0 — its `hooks.py` says `app_license = "agpl-3.0"`
and its README says the same. So is this repository. Code may be taken, and
taking it carries three obligations that are not optional: keep Frappe's
copyright notice, say at the top of the file what it was derived from, and
never move that file back to a permissive licence.

What that licence actually bought here is smaller than it looks, and the reason
is worth writing down: **frappe-ui's editor is most of Frappe Writer.**
`RichTextKit` is tiptap with tables, task lists, colour, alignment, text
styles, typography, headings with stable ids, slash commands and an image
uploader already configured. Writer adds a page around it. So does this — a
different page, because ours hangs off a `File` and theirs hangs off Drive's.

## 2. A document is a `File`

The same decision a sheet is built on, for the same reasons. There is no
`Document` entity: the `File` row is the document's name, its owner, the folder
it is in, who it is shared with, whether it is in the bin, and the record it
hangs off. All of that is built, and none of it is built again here.

Two things are added:

| | |
|---|---|
| `Doc Body` | One row per document, keyed by the File. `content` is ProseMirror JSON and is the source of truth. `html` is what the editor rendered that to, written on the same save. `settings` is how the page is set — width, typeface, spacing, and whether it is locked against accidental typing. |
| kind `Doc` | A declared kind, like `Sheet`, because nothing about "Scope of works" says what it is. It sits beside `Document` rather than inside it, and the near-collision is deliberate: a `.docx` somebody uploaded and a document somebody wrote here are different things to open, to weigh and to search. |

Both representations are needed and only one is authoritative. The editor reads
back `content`; everything that is not the editor reads `html` — search, the
preview, print, export, a mail body — so that none of them needs a ProseMirror
implementation in Python to find out what the document says. The browser has
both in hand at the moment it saves, so both go up in one request.

## 3. What is not taken, and why

**The collaboration.** Frappe Writer's editing model is peer-to-peer Yjs: a
`WebrtcProvider` against `wss://signal.frappe.cloud`, an IndexedDB copy in each
browser, and a base64 CRDT update as the stored column. It is good, and taking
it means running a signalling server per shard and storing a CRDT nobody on our
side can read. `docs/SHEETS.md` argued that case for the grid and the argument
is unchanged: a shard is one GIL-bound Python process, and a second runtime is
the thing we keep declining to add.

So a document is saved whole by one writer at a time, the way a workbook is —
and the header says when it last landed rather than who else is typing. What
that costs is real: two people editing the same paragraph at the same moment,
last save wins. What it buys is that a document is a column anybody can read,
a version is a snapshot rather than a replay, and nothing new runs beside the
web server.

**Anchored comments.** Writer's are a second Yjs document (`ycomments`) with a
floating-card layer over the prose. A record already has a comment thread and a
document is a file, so the cheap version — comment on the *file* — is one
`SharePanel` away and is not built either. Anchored-to-a-paragraph is a real
feature and a later one.

**Their `.docx` export.** It is the `docx` npm package plus a mapper. What
leaves here is one self-contained HTML file, because every word processor opens
HTML and nothing has to be kept in step with a schema.

## 4. What is built

* **A document, made from the Drive's New menu**, in the folder you are looking
  at, and opened.
* **The editor** — `/one/docs/:name`, frappe-ui's `RichTextKit`, a toolbar
  composed from frappe-ui's own menu items rather than drawn as buttons, an
  outline rail derived from the headings on every transaction, a word count,
  and page setup (width, typeface, line spacing, lock).
* **Autosave**, debounced to the pause between sentences, with a save on the
  way out of the page and the state said in the header rather than in a toast.
* **Version history**, the same panel and the same module a sheet has — see §5.
* **Search over what a document says.** `Doc Body.html` is matched beside the
  filename, so "the one where we agreed retention was five per cent" is a
  question the file manager can answer without an index or a second store.
* **`.txt`, `.md` and `.csv` made in the Drive** and edited as themselves — the
  same bytes, the same key, replaced in place. A markdown file round-tripped
  through ProseMirror comes back reflowed and is no longer the thing anybody
  committed, so it never goes near the prose editor.
* **Export**: print through the browser, one self-contained HTML file, and
  Markdown through Frappe's own `html2text`.
* **Everything a file already had** — folders, sharing, an expiring link, the
  bin, the storage meter, attaching it to a record.

## 5. Versions, and why they are shared with sheets

`File Version` and `oneapp_core/versions.py` serve a workbook and a document
alike, because a version of either turned out to be the same five columns: a
blob, its file, when, who, and whether somebody named it. The store says how to
write its own kind of blob back and how a reader wants it read; nothing else in
the module knows what a version contains.

The policy is Frappe's, from `frappe/sheets`' `sheets/versioning/`:

* snapshot the first time a file is saved, so the panel is never empty;
* then every 25 saves, or after 30 seconds of editing — so a burst of autosaves
  is one version and an afternoon is a readable list;
* always on an explicit "save this version";
* never prune what somebody named;
* thin the automatic ones nightly on a tiered schedule — everything for a day,
  hourly for a week, daily for a month, weekly for three, then nothing — so a
  year of editing is a bounded number of blobs rather than an unbounded one.

Their op log is not taken. It exists because their save is incremental; ours is
total, so a version *is* a snapshot and there is nothing to replay. The two
places that cost something are the sheet editor's cell-history popover and its
changed-cell outlines, both of which the vendored editor already treats as
optional.

## 6. Where the code is

    oneapp_core/docs/body     opening a document and saving one
    oneapp_core/docs/text     the plain-text files beside them
    oneapp_core/docs/export   a document as one HTML file
    oneapp_core/docs/writing  making one, copying one, throwing one away
    oneapp_core/docs/templates one to start from, which is a flag on a file
    oneapp_core/versions.py   earlier drafts, for both kinds

    components/docs/          the editor, the outline, page setup, plain text
    components/versions/      the history panel, shared with the sheet
    lib/workspace/docs.js     the calls
    composables/useNewFile.js the New menu, shared with the record's Files tab
    lib/files/files.js        routeFor — whether a click opens an editor
    pages/Doc.vue             which of the two editors this file wants

## 7. Where the editor is reached from

Three seams, and all three are the same two calls the Drive already makes.

**A long-text or text-editor field** on any record carries an expand button
beside its label. It opens the field's value in the document editor as a
dialog, and Save writes it back to the field — the same editor, so a scope of
works typed into a Project reads the way it will print.

**A record's Files tab** carries the Drive's own New menu, pointed at the
record: a document or a sheet made there is attached to it rather than filed in
a folder, which is what makes "the project's scope of works" a query rather
than a feature. `composables/useNewFile.js` is that menu, once, for both
surfaces.

**Templates** appear in both menus. A template is a document with
`custom_is_template` on it — the same flag and the same listing a sheet
template has, deliberately: a person who has made one already knows how to make
the other. The editor's menu is where a document becomes one.

## 8. What is not built yet

* **Live collaboration**, per §3.
* **Anchored comments**, per §3.
* **A document as a print format.** A quotation's covering letter is prose with
  fields in it, and the two halves — a document, and Frappe's Jinja print
  formats — do not meet yet.
