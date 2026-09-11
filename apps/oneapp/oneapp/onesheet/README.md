# OneSheet

Spreadsheets, over the file table every attachment already lives in. An
estimator prices a job in one, a named range in it fills the quotation's line
items, and the quotation's own numbers come back into the sheet as formulas
rather than as figures somebody retyped.

Who opens it: the person doing the arithmetic. The whole reason this is in the
product rather than being Excel is that last paragraph — the sheet and the
record are in the same place, and the numbers travel both ways without anybody
exporting anything.

`docs/SHEETS.md` is why this is built at all: every Python formula engine is
copyleft, what RUA's Google Sheets integration actually did, and the seven
stages. `frontend/src/modules/onesheet/lib/VENDORED.md` is what was taken from
`frappe/sheets` and what was changed. This file is the module.

---

## 1. The model

**A sheet is a `File`.** Same decision as a document and for the same return:
identity, folder, share, expiring link, bin, storage meter and the binding to a
record all arrived free. What is written here is the only thing a `File` cannot
hold, which is a grid.

| | |
|---|---|
| **File** (kind `Sheet`) | The sheet's identity. |
| **Sheet Book** | The workbook, as one blob. Granted to System Manager only — every path in goes through this module. |
| **File Version** | An earlier draft, shared with documents. |
| **Bound Record** | A record the workbook reads, keyed — the same rows a document uses. |
| **Sheet Feed** | The outward leg: which named range fills which child table of which record, and whether it has been locked. |

Two decisions run through every layer and nothing makes sense without them.

**The browser evaluates formulas and the server stores what it computed.** The
saved workbook carries `sheet` (what was typed, `=A2*B2*C2`) beside `values`
(what it came to, `6480`), and nothing on this side ever reads the first. A
print format, a read-back and a CSV all want the number and none of them has a
browser. `values` is *ours* — Frappe's payload has no such slice, because
nothing on their server ever needs one.

**A workbook is one blob, not a table of cells.** That is a reversal: the first
build stored a row per cell so a read-back could be a query. The grid is
Frappe's now, vendored whole, and it loads and saves the workbook entire — so a
second store the browser never reads would be a second thing to keep in step
for no reader. `codec.py` is how Python reads the one that is left.

---

## 2. The layers

Server, in import order:

    refs          A1 notation, and nothing else — no Frappe, no database
    codec         what is inside the blob a browser saves
    book          opening a workbook and saving one — the editor's two calls
    reading       reading a rectangle out of one
    writing       making a sheet, copying one, cleaning up after one
    templates     a sheet somebody starts from
    export        the one moment a sheet has to be bytes
    printing      a sheet on paper, Google's model rather than a print format
    feed          a named range fills a document's child table
    records       what `RECORD()` in a cell resolves to
    intelligence  an instruction as a plan of changes the grid applies

Browser, at `frontend/src/modules/onesheet/`: `Sheet.vue` is the host page and
`components/editor/` is the editor — vendored from `frappe/sheets` and split
into composables since. `lib/` holds the engine, the canvas renderer, the
services, and the two files that are ours by origin rather than adaptation:
`aiPlan.js` and the record-field resolver.

---

## 3. The decisions that cost something

### `refs.py` depends on nothing

Reference arithmetic is where a spreadsheet is most easily and most quietly
wrong — `Z` to `AA`, a range whose corners arrive the wrong way round, a row
zero. A module with no Frappe, no database and no document in it is one a test
can hammer, and that is the only reason it is a separate file.

Columns are 1-based. The temptation to make them 0-based dies the first time a
stack trace has to be read next to a screenshot of the grid.

### A named range is the contract, and everything outside it is private

`feed.py` is the stage everything else exists for, and its shape is RUA's
because RUA's was right: the named range is what a document reads, its first
row names the columns, a header may carry its unit, and the rows become child
rows. Everything outside that rectangle is the estimator's working — lookup
tables, scratch columns, a note to themselves — and none of it is anybody
else's business. That is what makes a spreadsheet usable *as a spreadsheet*
rather than as a form with gridlines.

And after the feed is locked, the document is the record. A rate edited at six
o'clock must not move a number somebody agreed to.

### `RECORD()` reads the other way, and it is a formula not a paste

An estimator's workbook that says `=RECORD("grand_total") * 0.05` stays right
through the third revision; a number read off the quotation and typed in was
right on the day. Three forms, keyed by source, because a formula that names
its source survives a second record being added above it.

### The permission is the File's, and `Sheet Book` has none of its own

Every read checks `File`. `Sheet Book` is granted to System Manager only, and
every path in is one of this module's functions — which is what stops "a sheet
is a File" from being true of the identity and false of the contents.

### Printing is Google's model, not Frappe's

You do not print the grid you are looking at; you choose what goes on the page
and then look at it. A print format walks a doctype and a sheet has none — what
a sheet has is a rectangle of values, and `printing.py` turns that into a table
on a page `shared/paper.py` has already described.

### The editor is vendored, and the fork is documented rather than hidden

`frappe/sheets` is AGPL-3.0 and so is this repo, so the grid, the engine and
the canvas renderer were taken whole rather than re-solved. `VENDORED.md` says
what came from where and what changed, and every vendored file carries Frappe's
copyright at the top. The obligation is not optional and neither is the
honesty: a fork that pretends to be original is one nobody can update.

### A model answers with a plan, and the grid applies it

This is the one AI surface in the product where the answer is not text, and it
follows directly from the first decision above. A server that wrote
`=SUM(D2:D20)` into a cell would be writing a workbook whose stored `values`
disagree with its `sheet`, and there is no browser on that side to recompute
it.

So `sheet.plan` answers with four operations — `tab`, `set`, `format`, `name` —
validated here against the workbook that actually exists, and applied in the
browser through `setCell`, `applyToRange` and `pushEditOp`: the same calls the
toolbar uses, so one Undo takes the whole plan back and a colleague in the
workbook watches it arrive.

The checking is where the value is, because a plan is a small JSON object that
looks fine and can wreck a workbook. A tab that is not there is dropped; a tab
the plan itself created two steps earlier is allowed. A style key nothing
declares is dropped *from* the step rather than taking the step with it. A plan
bigger than the store holds is refused whole, because half a plan applied is a
workbook nobody asked for.

The writing verbs are deliberately absent: improve and proofread are about
prose and a grid has none. What a model reads is a *sample* of the workbook as
values rather than formulas — a model reading `=C2*D2` cannot tell a broken
reference from a working one.

---

## 4. What is not built

In the order it blocks.

1. **xlsx export.** CSV is one tab at a time, which is what a CSV is. A
   customer who wants the workbook — tabs, formats, formulas — wants xlsx, and
   that is `docs/SHEETS.md` stage 6.
2. **Charts that survive a template load.** A template's sheets come across as
   tabs; its charts, pivots and named ranges do not, and the editor says so
   rather than dropping them quietly.
3. **A formula engine on the server.** Everything in §1 follows from not having
   one, and the licence survey in `docs/SHEETS.md` is why. If that ever
   changes, the `values` slice is the thing that stops being necessary.
4. **Conditional formatting in the plan vocabulary.** The four operations a
   model may ask for do not include it; the toolbar does.
5. **A records rail a phone can use.** The rail is `w-80` beside a `flex-1`
   editor, which is right on a desktop and wrong at 412px: the grid gets 92px
   and every cell sits under the rail. The phone's answer is a rail that takes
   the window the way Mail's reader does, and until it exists the two browser
   tests that need both halves on screen skip on mobile. The document editor
   has the same shape and the same gap.
