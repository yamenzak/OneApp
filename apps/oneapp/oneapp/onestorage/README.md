# OneCloud

Every file in the workspace, in one place — and the same rows a record's
attachment is, a mail attachment is, and a spreadsheet is. There is no second
store anywhere in this product, and almost everything below follows from that.

A person opens it from the dock's cloud tile. What they get is a file manager:
a rail of places, a folder tree, a path, a list or a grid, and a pane showing
whatever they are looking at.

The server half is `oneapp/onestorage/`; the browser half is
`frontend/src/modules/onestorage/`. `docs/DRIVE.md` is the arc — what Frappe
Drive is, what we took, and the stages. This is the module: the model, the
decisions, and the shape of the thing on screen.

## 1. The model

Four facts, and the first is the one to keep hold of:

**A file is a Frappe `File`.** Not a row of ours pointing at one. Four custom
columns carry what the framework does not have — `custom_kind`,
`custom_status`, `custom_trashed_on`, `custom_opened` — and that is the whole
of the schema.

**A folder is a `File` with `is_folder`,** parented by `File.folder`, which is
what the framework already does and the desk already uses.

**A file attached to a record has `attached_to_doctype`; a file in a folder
has `folder`; a file can have both.** This is the sentence the Files tab, the
Records tree and the Drive are all three built on: they are queries over one
table rather than stores to keep in step.

**A place is a filter, not a table.** Home, Recents, Favourites, Shared, the
bin, Templates, Documents, Workbooks, Code — every one is the same query with
a different `where`. That is why the rail is cheap, and why a tenth place
would be a filter rather than a feature.

The layers, in import order, are listed in the package docstring; the ones
worth knowing by name are `query` (the places), `reading` (listing, paths,
details), `writing` (folders, rename, move, bin), `sharing` (a link that
outlives a session), `remote` (a folder on somebody else's host) and `dav`
(the other direction).

## 2. The decisions that cost something

**The bin sets a column.** Frappe deletes a `File` and its object together, so
the only undo was a backup, which is not an undo — it is a support ticket.
Trashing marks; a sweep decides at thirty days.

**An attachment has no folder.** Frappe files every attachment into one
`Home/Attachments` bucket, so a workspace with four thousand quotations has
four thousand files in a folder nobody browses. `file.set_folder_name` leaves
them folderless and Home excludes them, because the Records tree reaches them
by the address they already have.

**The Records tree has no rows in its first two levels.** A directory per
record would be a `File` per record: renaming a record would become moving a
folder, deleting one a cascade. The doctype and record levels are made out of
the attachment rows at the moment somebody asks — `reading._records` for the
Drive, `scopes.children` for a mount, one resolver so a rail place and a
WebDAV mount cannot disagree about what a record has on it.

**A mount is read-only through the Drive.** The Drive reads a host; it does
not write to one. Browsed live and never copied, so there is no sync to be
wrong.

**Sharing is `DocShare` plus a link, and not a permission table of our own.**
Two systems deciding one question is two systems that will disagree — the same
refusal `spaceview` and `email/inbound` make.

## 3. The shape on screen

OneCloud is a window on the desk (`docs/DESKTOP.md` stage 6). Not a page: a
file manager is the thing people keep open beside what they are doing, and
that is what a window is for. Its route stays as the maximised case, so a deep
link still works.

**Four windows, one component.** A document is a `File` and a workbook is a
`File`, so OneWriter is not a second application over a second store — it is
this one landed on `place=documents`, and OneWorkbook and OneCode are the same
over `workbooks` and `code`. Each has its own dock tile, its own mark colour
and its own corner. `lib/window.js` holds the list. Which is also why there
are no tabs inside a window: this product's tab bar is the dock, and it
already draws a face per thing.

**Two OneCloud windows cascade rather than share a corner.** Record previews
share one box because you only ever look at one; two folders open at once is
the reason file managers have windows at all — dragging between them is the
gesture.

**Two bands above the list, and that was the hardest part to get right.** The
first build had four: a path, a command bar, a row of kind pills and a search
box, and then, 180 pixels down, the first file. Every reference on the board
draws two. So search moved into the path and the pills moved onto the command
bar's trailing end, where only the one in force wears its word — seven
labelled pills are 480 pixels and there are about 300, which is how the first
attempt pushed the view toggles off the end of the window.

### The path bar

`↑` then the breadcrumb, then search at the trailing end. Search is scoped to
where you are and says so — "Search Workbooks" — and on Home, which has no
list to narrow, typing here takes you to All files carrying what you typed.

### The command bar

Verbs, labelled while there is room, then icons. **It changes with the
selection**, which is the whole reason it is a bar and not a fixed row:

* nothing selected — `New ▾` · `Upload` · `Sort ▾`
* something selected — `Open` · `Download` · `Share` · `Rename` · `Move` ·
  `Move to the bin` · `More ▾` · `✕`

Then, always at the trailing end: the kind pills, the list/grid toggle and
`Details`. The pills are gone in a room that already *is* a kind — asking for
the images among the documents is the empty set every time — and the last two
are gone on Home, which has no one list to lay out or pick a row of.

`New ▾` is the one menu worth writing out, because it is where three features
that used to be in three different corners belong together:

    Upload files
    New folder
    ── Write ──────
    Document            (OneWriter)
    Text file
    Markdown file
    ── Calculate ──
    Blank sheet
    Import a spreadsheet
    ── Build ──────
    Code                (OneCode)
    ── Elsewhere ──
    Connect a folder
    Share over WebDAV

### The rail

**Grouped, and shorter than it was.** It had ten flat entries, three of which
— Documents, Workbooks, Code — were the same filter as three of the kind pills
an inch to the right, and one of which (Templates) is something you pick from
the New menu rather than a room you stand in.

    Home · All files · Recent · Favourites · Shared with me
    Records        the doctype/record tree
    FOLDERS        your own tree, six of them and the rest one press away
    CONNECTED      mounts, with a dot for whether the host answered
    ───────────────────────────────────────────────
    Bin
    Storage        a bar, not a sentence

`places.js` keeps two lists and says why. `PLACES` is the vocabulary the
endpoint answers, so `?place=workbooks` is still a link that works; `RAIL` is
a claim that you go there often enough to deserve a seat. A guard refuses a
rail entry that types its own value rather than looking one up.

The editors' windows draw no rail at all. There is one place inside OneWriter,
and a rail there would be a column of doors out of the room you just opened.

### Home

What OneCloud opens on. It opened on All files, which on a real workspace is
fifty rows of folders in alphabetical order — a directory listing, which is a
thing you consult and not a thing you land on.

Three bands: **Pinned** as tiles, because a favourite is somebody saying "this
one" out loud and it is the only such statement we have, and because a folder
is something you aim a pointer at rather than compare; **Recent**, which is
the answer nine times in ten; and **Shared with you**, which draws nothing at
all where nobody has shared anything.

Each band is `fileSource` over one of the places the rail used to spend an
entry on — no second store, no new endpoint, and the skeleton and the empty
state are the frame's. `start` is the one place the rail offers and `listing`
does not, and the parity guard says so and refuses a second.

### The list and the grid

`DataList` over `fileSource`, folders first, with the column heads banded like
a screen's. Three things it stopped saying:

* **"Folder" under every folder.** The mark is an amber folder and the heading
  above says FOLDERS. Frappe's own mark was a flat `#525252` silhouette with
  square corners, drawn for a card and used by us at sixteen pixels, where a
  list of twelve folders read as a column of black boxes — so `Folder.svg` and
  `Folder-shared.svg` are ours, two-toned and rounded.
* **The Owner column, where there is one owner.** A workspace one person uses
  answered "Administrator" on every row of every folder for ever, which in a
  window is 144 pixels taken off the only column anybody reads.
* **The kind, in a room that is one kind.** "Doc" under fifty names in
  OneWriter is the third telling after the window's title and the file's own
  mark. The grid keeps its line, because there it carries the size.

The grid's select-all wears its own words. In the list it is the head of a
column and the column says what it ticks; on its own above a wall of cards it
was a lone checkbox nobody presses.

### The details pane

`FilePane`, beside the list rather than over it, and an `ⓘ` toggle in its own
header that swaps the preview for the facts: kind, size, where, the record it
is on, who owns it, when it arrived and when it last changed, and who can see
it where that is not just you. Nothing is fetched — every one of those is
already on the row that drew the list.

A toggle rather than a band under the body, because the body is sometimes an
editor that wants the whole pane, and `v-show` rather than `v-if`, so looking
at the facts never unmounts an editor with unsaved work in it.

### The status bar

`10 items · 1 selected · 234 MB` at the start, and what this place refuses at
the end. The count is a fact about what you are looking at and belongs under
it, which is where every file manager has put it for thirty years.

### And the small things that make it feel like a file manager

Right-click anywhere for the row's own menu. Drag onto a folder in the list or
onto one in the rail's tree. Drop from the desktop anywhere in the body.

## 4. What is not built

In the order it blocks:

1. **Activity and Related in the details pane.** The facts are there; who
   changed what (from versions) and a way *to* the record a file is on are
   not. The second is not a lookup but a question about spaces: which screen
   to open a Quotation on is something OneCloud, which is not inside a space,
   cannot answer on its own.
2. **Keyboard.** Type a letter to jump to the first thing starting with it,
   `Space` for the details pane, `Enter` to open, `F2` to rename, `Delete` to
   bin. None of it is wired.
3. **Open with ▸.** A `.xlsx` can go to OneWorkbook or be downloaded, and the
   pane offers one of those.
4. **The phone.** `docs/DESKTOP.md` stage 7 — a window is a full-screen sheet
   there and the rail is a dropdown, which is the least this could be rather
   than the answer.
