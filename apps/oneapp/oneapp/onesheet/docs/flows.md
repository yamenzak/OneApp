# Flows

The layers, in import order, and the order is the dependency:

    refs          A1 notation, and nothing else — no Frappe, no database
    codec         what is inside the blob a browser saves
    book          opening a workbook and saving one — the editor's two calls
    reading       reading a rectangle out of one
    writing       making a sheet, copying one, cleaning up after one
    templates     a sheet somebody starts from
    export        the one moment a sheet has to be bytes
    printing      a sheet on paper, Google's model rather than a print format
    feed          a named range fills a document's child table
    records       what RECORD() in a cell resolves to
    intelligence  an instruction as a plan of changes the grid applies

## `refs.py` depends on nothing, and that is the point

Reference arithmetic is where a spreadsheet is most easily and most quietly
wrong — `Z` to `AA`, a range whose corners arrive the wrong way round, a row
zero. A module with no Frappe, no database and no document in it is one a test
can hammer, and that is the only reason it is a separate file.

Columns are **1-based**. The temptation to make them 0-based dies the first
time a stack trace has to be read next to a screenshot of the grid.

## Opening and saving — `book.py`

`get_sheet` returns the blob; `save_sheet` takes it back whole. Two calls, and
the editor makes no others.

## Reading a rectangle — `reading.py`

`named_ranges` lists what a workbook offers. `read_range` returns the values in
one — the `values` slice, never the `sheet` slice, because there is no browser
on this side to recompute a formula.

## The feed, which is the stage everything else exists for — `feed.py`

1. `preview(sheet, range, into)` shows what would land.
2. **The first row names the columns**, and a header may carry its unit.
3. `pull` writes the rows into the record's child table. `filled` and `skipped`
   record what happened.
4. `lock` ends it. **After the feed is locked, the document is the record** — a
   rate edited at six o'clock must not move a number somebody agreed to.
   `unlock` exists and is a decision somebody makes.

`start_from` goes the other way: a sheet begun from a record. `bound_to` and
`feeds` are the listings.

The shape is RUA's because RUA's was right.

## Reading the record back — `records.py`

`record_fields` is what `RECORD()` resolves against. The workbook reads the
quotation while the quotation reads the workbook, and neither is a copy.

## Printing — `printing.py`

**Google's model, not Frappe's.** You do not print the grid you are looking at;
you choose what goes on the page and then look at it. A print format walks a
doctype and a sheet has none — what a sheet has is a rectangle of values, and
this turns that into a table on a page `shared/paper.py` has already described.

## Exporting — `export.py`

The one moment a sheet has to be bytes. `download` renders the `values` slice.

## Asking a model — `intelligence.py`

See `ai.md`. The short version: the answer is a **plan**, not text, and the
grid applies it.
