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
that is what a window is for.

**Two OneCloud windows cascade rather than share a corner.** Record previews
share one box because you only ever look at one; two folders open at once is
the reason file managers have windows at all — dragging between them is the
gesture. Each gets its own dock tile, which is why there are no tabs inside
the window: this product's tab bar is the dock, and it already draws a face
per thing.

Four zones, top to bottom.

### The path bar

`← → ↑` then the breadcrumb then search. Every breadcrumb segment is a
control: press the name to go there, press the chevron after it to jump to a
sibling without going there first. Search is scoped to where you are and says
so — "Search in Wallpapers" — with one press to widen it to everywhere.

### The command bar

Verbs, labelled while there is room, then icons, then `More`. **It changes
with the selection**, which is the whole reason it is a bar and not a fixed
row:

* nothing selected — `New ▾` · `Upload ▾` · `Sort ▾` · `View ▾` · `Details`
* something selected — `Open ▾` · `Download` · `Share ▾` · `Rename` · `Move` ·
  `Delete` · `More ▾`
* several selected — the same, minus `Rename`, plus the count

`New ▾` is the one menu worth writing out, because it is where three features
that are currently in three different corners belong together:

    New folder
    ─────────────
    Upload files…
    Upload a folder…
    ─────────────
    Document            (OneWriter)
    Workbook            (OneWorkbook)
    Code file           (OneCode)
    From a template…
    ─────────────
    Connect a folder…   (a mount)

### The body

Rail, then the list or grid, then the details pane.

**The rail is grouped rather than flat.** Ten entries in one column is a list
you read; four groups of two or three is a list you recognise.

    Home · Recent · Favourites · Shared with me
    MADE HERE      Documents · Workbooks · Code · Templates
    RECORDS        the doctype/record tree
    FOLDERS        your own tree, a level at a time
    CONNECTED      mounts, with a dot for whether the host answered
    ───────────────────────────────────────────────
    Storage        a bar, not a sentence

**A row of kind pills sits above the list**: All · Images · Videos ·
Documents · Sheets · Code · Other. This is the "show me every image" the board
asks for and it is one query — `listing(kind=…)`, which already exists. Pills
and not tabs, so there is one tab metaphor in the product and it is the dock.

**The details pane** is the best idea on the board and we half have it:
`FilePane` already previews. What it gains is the rest of the card —

    [ preview ]
    House.png
    [ Share ]  [ Open with ▾ ]
    DETAILS     type · size · where · dimensions
    ACTIVITY    who changed what, from versions
    RELATED     the record this belongs to, the folder beside it

— because "who touched this" and "what is this attached to" are the two
questions a file in a *workspace* raises that a file on a disk does not.

### The status bar

`10 items · 1 selected · 234 MB` at the start, the list/grid toggle at the
end. The count is a fact about what you are looking at and belongs under it,
which is where every file manager has put it for thirty years — not floating
at the bottom right of the list, which is where ours is.

### And the small things that make it feel like a file manager

Right-click anywhere: `Open` · `Open with ▸` — `Download` — `Rename` —
`Share ▸` — `Organise ▸` (move, copy, favourite) — `Details` — `Move to bin`.
Type a letter to jump to the first thing starting with it. `Space` for the
details pane, `Enter` to open, `F2` to rename, `Delete` to bin. Drag onto a
folder in the list or onto one in the rail's tree. Drop from the desktop
anywhere in the body.

## 4. What is not built

In the order it blocks:

1. **The window.** It is a route today, so it replaces the space rather than
   sitting over it. `docs/DESKTOP.md` stage 6.
2. **A folder inside a record's room**, and everything that follows from a
   room being writable. `docs/DRIVE.md` §13.
3. **The command bar, the kind pills and the status bar** — the arrangement
   above. The verbs all exist; they are spread over a header, a menu and a
   footer.
4. **The details pane's Activity and Related.** Versions and `attached_to_*`
   are both in hand.
5. **The Files tab becomes this**, so there is one file list in the product.
