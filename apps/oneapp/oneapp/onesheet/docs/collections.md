# Collections

**A sheet is a `File`.** Same decision as a document and for the same return:
identity, folder, share, expiring link, bin, storage meter and the binding to a
record all arrived free. What is written here is the only thing a `File` cannot
hold, which is a grid.

## Owned

| Doctype | What it is |
| --- | --- |
| `Sheet Book` | The workbook, as one blob. `sheet` (the File), `payload`, `byte_size`, `head_seq`. **Granted to System Manager only** — every path in goes through one of this module's functions. |
| `Sheet Feed` | The outward leg: which named range fills which child table of which record, and whether it has been locked. `reference_doctype`, `reference_name`, `into`, `sheet`, `sheet_title`, `label`, `filled`, `skipped`, `status`, `pulled_on`, `pulled_by`, `locked_on`, `locked_by`. |

## Borrowed

| Doctype | From | What it is here |
| --- | --- | --- |
| `File` (kind `Sheet`) | Frappe core, via OneCloud | The sheet's identity, and the only permission that decides anything. |
| `File Version` | OneCloud | An earlier draft, shared with documents. |
| `Bound Record` | The engine | A record the workbook reads, keyed — the same rows a document uses. |

## The blob, and what is inside it

**A workbook is one blob, not a table of cells.** That is a reversal: the first
build stored a row per cell so a read-back could be a query. The grid is
Frappe's now, vendored whole, and it loads and saves the workbook entire — so a
second store the browser never reads would be a second thing to keep in step
for no reader. `codec.py` is how Python reads the one that is left.

**The browser evaluates formulas and the server stores what it computed.** The
saved workbook carries `sheet` (what was typed, `=A2*B2*C2`) beside `values`
(what it came to, `6480`), and **nothing on this side ever reads the first**.

`values` is *ours*. Frappe's payload has no such slice, because nothing on
their server ever needs one. A print format, a read-back and a CSV all want the
number and none of them has a browser.

## The two that are contracts rather than storage

**A named range is what a document may read**, and everything outside it is the
estimator's working — lookup tables, scratch columns, a note to themselves.
That rectangle is the whole interface between a workbook and a record, and it
is what makes a spreadsheet usable *as a spreadsheet* rather than as a form
with gridlines.

**`RECORD()` is a formula, not a paste.** `=RECORD("grand_total") * 0.05` stays
right through the third revision; a number read off the quotation and typed in
was right on the day. Three forms, keyed by source, because a formula that
names its source survives a second record being added above it.
