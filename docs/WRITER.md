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

`File Version` and `shared/versions.py` serve a workbook and a document
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

    onedoc/body     opening a document and saving one
    onedoc/text     the plain-text files beside them
    onedoc/export   a document as one HTML file
    onedoc/writing  making one, copying one, throwing one away
    onedoc/templates one to start from, which is a flag on a file
    shared/versions.py   earlier drafts, for both kinds

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

* **Live collaboration**, per §3. A deliberate park, not a gap: it is Yjs and a
  Node process, which changes what a shard is.
* **Anchored comments**, per §3. Parked with it, for the same reason.
* **A document as a *selectable* print format.** Most of what this was asking
  for is built and is described in §9: a document can be written about a
  record and can carry that record's fields. What is still missing is the last
  step of the plumbing — a bound document standing in the Print dialog's
  format list beside `Standard`, so printing the quotation prints the covering
  letter. Today the letter prints itself, from its own page.

## 9. A document written about records

A quotation's covering letter is prose with the quotation's numbers in it.
Typed out, those numbers are a second copy that goes stale the first time
somebody changes the quotation, and the person who finds out is the customer,
holding a letter whose total disagrees with the schedule stapled behind it.

**A file reads a set of records, and the attachment is not one of them.** This
was the other way around for exactly one iteration — a document's binding was
its attachment — which is elegant and wrong twice. A covering letter names the
quotation *and* its customer *and* the project, and an attachment holds one;
a template is for a *kind* rather than a record, and an attachment cannot say
that at all. So `Bound Record` rows are what a file reads and `attached_to_*`
goes back to meaning where the file is filed. The two still meet at the one
moment it helps: a letter created from a quotation gets its first source
seeded from that attachment, so nobody says it twice.

**A source has a key, and a token names `key.field`.** The key is what makes a
record swappable — starting from a template fills in the records and the prose
does not change — and what lets one letter hold two projects. The first source
is called `record`, which is what a bare token means; after that a key is the
scrubbed doctype, then `quotation_2`. Twelve to a file: past that a document
is a report, and a report is a screen.

**A field is a node, not text.** `RecordField` is an inline atom holding a
source and a fieldname, rendered as
`<span data-record-source="quotation" data-record-field="grand_total">د.إ 144,235.00</span>`.
An atom because putting a cursor inside a formatted number and deleting a
comma would produce a figure the record never said, which is the failure the
whole thing exists to prevent. The last answer is written into the markup
rather than fetched on render, because three readers have no app behind them:
the HTML export, a mail client, and the editor in the moment before the
resolve lands.

**A child table is a block, not a phrase.** `RecordTable` is the other node: a
real table in the prose, `binding.rows` behind it, holding only which columns
it draws. Its rows and its column *labels* are not stored in the body at all —
`fields.sanitise` empties both on every read — so a schedule is built from
what this reader resolved, never from what the last one did. The export builds
its own `<table>` from the same answer, through `fields.draw`.

**What may be named is narrow, and that is the point.** A token is a string a
person typed, so the endpoint behind it takes a doctype and a fieldname from a
browser. `binding.offer` cuts it to the doctype's own fields, minus layout and
table types that have no value, minus permlevels this person cannot read,
minus `Password` — everything else on that list would render as nonsense; that
one would render as a secret in a document somebody prints. `binding.tables`
narrows a child table's columns the same way, against the *child* doctype.

**The stored text is a cache, and the server overwrites it on the way out.**
That is the permission rule, and the first version got it wrong: the last
answer used to be served exactly as stored, so a field behind a permlevel one
person could resolve became readable by everyone who could open the document.
`fields.sanitise` now runs on every read — `get_doc`, the export, the print
page — and replaces every token's text with what *this* reader resolves, or
with nothing. What is on disk is never what is shown. The one deliberate way a
value crosses that line is "Fix the fields", which is the same act as typing
it.

**The rail is where the records live.** A strip could say "About Q-9"; it
could not hold three records and their fields without being a menu inside a
menu. So `RecordPanel.vue` is a rail: each source a section you open and
browse, its fields as phrases and its child tables as blocks, a click inserting
either at the cursor. Adding one is two steps — which kind, then which record
— because the second list cannot exist until the first is answered.

**A template is a starter, not a form.** Starting from one no longer asks for
a record first. `copy_sources` carries the template's *slots* — the kinds,
with the records left empty — onto the new document, and the rail prompts for
each with a Waiting badge beside it. Which is the point: the person filling in
the quotation the template named usually also wants the customer it did not.

**Live while it is a draft, frozen when it leaves.** A bound document resolves
every time it is opened and again whenever somebody presses Refresh, and the
rail's footer says when — a document open since this morning shows this
morning's total, and saying so is the difference between a reader who
refreshes and one who quotes a stale number down the phone. Export freezes:
`fields.fill` asks once more, `fields.freeze` turns every token into the words
it says, and both the HTML and the ProseMirror JSON are flattened together,
because freezing one and not the other means the token comes back the moment
somebody opens the document. Freezing leaves a *block* alone: writing a
schedule into the prose is a larger thing than fixing a number and is not what
anybody presses this for.

Nothing is pushed. A record changing does not reach into the documents that
mention it, and it should not: a document is read far less often than a record
is edited, and a write fan-out over every mention would be the wrong shape for
a workspace with four thousand files in it.

`docs/SHEETS.md` §9 is the same question answered for a workbook, where the
constraint is harder and the answer is the same.

**And a third surface, where the answer is the opposite.** The mail composer
mounts the same `RecordPanel.vue`, and what a click puts in is not a token
but the *words the field says* — see `docs/EMAIL.md` Stage 8. A message that
has been sent cannot be read again, so there is nothing to keep live and
nothing to refresh; the panel takes `live: false` and drops both the Refresh
button and the "Read at". Two other things follow from a draft not being a
`File`. Its sources are not `Bound Record` rows — there is no row to hang one
off — so an empty `name` hands the list back to the host, which adds, fills
and drops them itself and passes them down as a prop; and the key is only the
rail's own handle, where a document's is a name its prose holds forever.

What is shared is what was worth sharing: which records, what each one
offers, and the two steps that add another.
