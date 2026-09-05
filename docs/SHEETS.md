# Sheets

A spreadsheet you can put anywhere: on its own, in a folder, or bound to a
record so the numbers a person works out in a grid become the lines on a
quotation.

Written as a study before any of it is built. §1 is the licence position,
because on this job it decides the architecture and not merely what may be
copied. §2 is what Frappe Sheets actually is, read out of the repository. §3 is
what RUA did with Google Sheets, read out of the old code — it is the only
place in this product with a real, shipped answer to "a spreadsheet feeds a
document", and the shape it found is worth taking. §4 is what we already have.
§5 is the plan.

---

## 1. What we may take, and what it costs

**This repository moved to AGPL-3.0 so that it could take from
`frappe/sheets`.** That was a decision, not a technicality: `frontend/src/engine/`
is 11,154 lines including tests, `formula.js` alone is around 1,400 with a 36 KB
test file, and re-deriving a formula engine, a dependency graph and array spill
semantics is months of work with no product in it.

What the licence asks in return is real and worth stating once. Every file taken
keeps Frappe's copyright notice and says at its top what it came from; nothing
taken can ever move back to a permissive licence; and AGPL §13 binds a *service*
— anybody running a modified copy of this over a network owes its source to the
people using it, and that includes us.

The other half of the licence position is unchanged, because it is about what we
*depend on* rather than what we copy, and it is what decides the architecture.

**Every spreadsheet formula engine for Python is copyleft**, and now that we are
AGPL that is no longer a licence problem — it is a dependency problem, since
GPL-3.0 and EUPL are still not AGPL-3.0 and would each need their own analysis.
Measured, not assumed:

| Package | Licence |
|---|---|
| `formulas` | EUPL-1.1+ |
| `pycel` | GPL-3.0 |
| `koala2` | GPL-3.0 |

**In JavaScript there is a permissive one.** `fast-formula-parser` is MIT: a
Chevrotain grammar plus about three hundred Excel functions. `@formulajs/formulajs`
is MIT too and is the function library without the parser. `hyperformula` is
GPL-3.0-only and is therefore out despite being the best-known option;
`handsontable` is commercial. `univer` is Apache-2.0 and would be permissible —
it is a whole spreadsheet, engine and grid and toolbar together, with its own
design system that is not ours.

So: **a formula is evaluated in the browser, and the server reads what the
browser worked out.** That was forced by licensing when this was written and is
now a choice — and it is still the right one, because §3 shows it is exactly
what RUA's integration did for two years without anybody noticing a limitation.
A server that evaluated formulas would be a second engine to keep in step with
the first, which is the actual cost and it does not go away with the licence.

---

## 2. What Frappe Sheets is, structurally

### The data model

Five doctypes, and the shape of the first one is the whole story:

| Doctype | What it holds |
|---|---|
| `Sheet` | `sheets_data` — a **JSON blob of the entire workbook**: every tab, every cell, every format. Plus `head_seq`, `head_snapshot`, `is_public`, `public_write`, and the same trashed/trashed_on/trashed_by triple our Drive uses. |
| `Sheet Cell` | `parent_sheet`, `sheet_name`, `cell_id`, `raw_value`, `format_json` — one row per cell, beside the blob rather than instead of it. |
| `Sheet Snapshot` | A copy of `sheets_data` at a sequence number, `kind` of auto / milestone / named. |
| `Sheet Op Log` | Per-operation `before_json` / `after_json` with a `summary` and an actor — the undo history, durable. |
| `Sheet Collab State` | `ydoc_state`, a persisted Yjs document. |

The workbook is one JSON document with an operation log beside it. That is a
sound choice for a spreadsheet: a cell edit is small, ordering matters, and the
whole thing is read at once when somebody opens it.

### The collaboration server

`Sheet Collab State` is where the cost is. Live multi-cursor editing is Yjs, and
Yjs needs a server that speaks its protocol — `collab-server/` is a **separate
Node process** depending on `@hocuspocus/server`, `@hocuspocus/extension-redis`
and `@hocuspocus/extension-database`.

For us that is a second service per bench, or one shared service that every
tenant's browser connects to and that therefore has to authenticate and scope
per tenant. Frappe Cloud runs our benches; adding a Node process to them is a
real change to what a shard is, not a dependency line.

### The frontend

`frontend/src/engine/` is the interesting half and the one we may not have:
`formula.js`, `deps.js` (the dependency graph), `spill.js` (array formulas),
`cond-format.js`, `pivot.js`, `sortFilter.js`, `named-ranges.js`, `xlsx-io.js`,
`clipboard.js`, `validation.js`, `protection.js`, `smart-fill.js`. It also
carries `xlsx` for import/export and `echarts` for charts.

---

## 3. What RUA actually did, and why it is the right shape

This is the part worth reading twice, because it is a shipped answer to the
question the request is really asking — *"use them wherever I want"* — and it is
not the answer Frappe Sheets gives.

`rua/google_sheets.py` is 582 lines. What it does:

1. **A project gets a sheet copied from a template** on first save.
   `create_sheet_from_template(template_sheet_id, new_sheet_name)` is a Drive
   `files.copy`. The project stores `google_sheet_id`.
2. **The estimator works in the sheet.** That is where the arithmetic lives:
   width × height × qty × rate, per-row totals, VAT, a grand total. Nobody wrote
   that logic in Python; a person wrote it in cells.
3. **A named range is the contract.** The project stores
   `extraction_named_range`, defaulted from company settings. Everything outside
   that range is the estimator's working — scratch columns, notes, lookup
   tables — and is nobody else's business.
4. **Locking reads the range back.** `get_sheet_data(sheet_id, range)` returns a
   grid, the first row is headers, and the rest become the project's line items.
   Required headers are `Item Name`, `Description`, `Qty`, `Amount`, `Total`,
   `Vat Amount`, `Grand Total`; optional ones are `Width`, `Height`, `Area`,
   `UOM`.
5. **A header carries its unit in brackets.** `Width [mm]` is parsed with
   `re.sub(r"\s*\[.*?\]$", "", h)` for the name and `re.search(r"\[(.*?)\]$", h)`
   for the unit, and the unit is appended to each value on the way in. So one
   template serves millimetres and metres without a second column.
6. **Locked means the doctype is now the record.** After extraction the
   quotation prints and invoices from its own child table. The sheet is history.

Two things follow from this, and they are the load-bearing observations of this
whole study.

**The API returned computed values, never formulas.** `spreadsheets.values.get`
hands back what the sheet worked out. RUA never evaluated an expression, never
built a dependency graph, and never needed one. The spreadsheet was a
*calculator that happened to be shared*, and the integration was a way to read
its answers.

**Which means our licence problem is not a problem.** The browser evaluates and
stores what it computed; the server reads stored values. That is precisely what
Google's API gave RUA, it is what a print format needs, and it needs no
permissive Python engine because it needs no Python engine at all.

`docs/RUA.md` §5 currently says the spreadsheet is "what to delete rather than
port", on the grounds that we have a grid and quotation lines are a child table
with computed columns. That was right about the *quotation*, and wrong about the
*capability*: a child table with three derived columns does not replace a
surface where somebody can write `=IF(C7>50, D7*0.9, D7)` without asking a
developer. This document supersedes that paragraph; §5 of RUA.md should be
amended when the first stage lands.

---

## 4. What we already have

More than is obvious, because the Drive was just built.

**A place for a sheet to live.** `oneapp_core/drive` is folders, favourites,
recents, a bin with a thirty-day promise, `DocShare` for colleagues, an expiring
link for strangers, and a picker that every attach surface in the product now
opens. Every one of those is a query over `File` with a `where` clause.

**A way to bind a thing to a record.** `attached_to_doctype` /
`attached_to_name`, and `place=record` in `drive/query.py` is the record's Files
tab. A sheet attached to a quotation is the same idea with no new machinery.

**Print formats.** Jinja over a document, built in the builder. The output half
of RUA's flow is already ours.

**A screen can declare a view type.** `VIEW_TYPES` in `lib/viewTypes.js` maps a
declared name to a body component, and `calendar` is already sitting there as
`built: false` — the mechanism for "this screen is looked at as a sheet" exists
and has an unbuilt entry in it today.

**A data grid.** `ListBody` is virtualized, resizable, sortable, with pinned
columns and a selection model. It is not a spreadsheet — it edits values and
does not derive them — but the scrolling, the column model and the keyboard
handling are solved problems in this repo.

---

## 5. What is missing, precisely

1. **A cell store.** Nothing in the product holds a grid of values addressed by
   row and column.
2. **A formula engine.** `fast-formula-parser`, MIT, measured at **89 KB
   gzipped** for the full three hundred functions — bundled with esbuild rather
   than guessed at. Loaded only on the routes that draw a sheet, it costs
   nothing to anybody who never opens one.
3. **A grid that edits.** Selection, fill handle, formula bar, references
   highlighted while typing.
4. **A named-range concept**, which is the contract in §3.
5. **The read-back**, which is what turns a sheet into a document's lines.

---

## 6. The plan

Seven stages. The first three are a spreadsheet; the fourth is the one the
request is actually about; the rest are what makes it pleasant.

**Where this has got to.** Stages 1 to 6 are built and live. Stage 7 is still
deliberately absent. What follows is the plan as written, with what actually happened noted
where the two differ, because the differences are the interesting part.

### Stage 1 — A sheet is a file  ✅

**`Sheet` is not a new place.** It is a `File` with `custom_kind = 'Sheet'`, and
its cells live in their own table keyed by that File's name.

That one decision is worth as much here as "it is `File`, not a new model" was
for the Drive, and for the same reason: a sheet immediately has a folder, a
name, an owner, favourites, the bin, `DocShare`, an expiring link, a row in the
picker, and the ability to hang off a record — none of it written twice.

Where it strains, said plainly: a `File` is a row that names some bytes, and a
sheet's bytes do not exist until somebody exports it. So `file_url` points at
our own route rather than at an object, `r2_key` stays empty, and `file_size` is
the cell count's stand-in until an export is taken. The alternative — a `Sheet`
doctype that reimplements placement, sharing and the bin — is three hundred
lines of machinery to avoid one honest exception.

**What the exception turned out to be, exactly.** `File.validate` refuses a row
whose `file_url` names nothing: it must be under `/files/`, `/private/files/`,
or one of `URL_PREFIXES = ("http://", "https://", "/api/method/")` — and the
last of those is the framework's own hatch for a file whose bytes are produced
rather than stored. So the URL is not the viewer route after all; it is
`sheets.download`, the exporter. That is the better answer as well as the
working one: follow a sheet's `file_url` and you get the file the row claims to
be. Pointing it at `/one/sheets/<name>` inserted fine and then threw on the next
save of the row — a rename, a move, a trash — which is the sort of bug that
appears a week later on somebody else's screen.

    Sheet Cell     sheet (Link → File), tab, ref, raw, value, format
    Sheet Tab      sheet, name, position, frozen_rows, frozen_columns
    Sheet Range    sheet, tab, label, ref     ← the contract, §3

**`raw` and `value` are both stored, and that is the point.** `raw` is
`=A2*B2*C2` and `value` is `6480`. The browser writes both; the server reads
`value` and never parses `raw`. A print format, a report and a read-back all
work with no engine on the server — see §1 and §3.

A cell row per cell rather than a JSON blob per workbook, unlike Frappe Sheets.
The reason is the read-back: `Sheet Range` names a rectangle, and pulling it has
to be a query rather than loading a megabyte of JSON and walking it. It also
makes a cell's history Frappe's own version history instead of a second one.

### Stage 2 — The engine, in the browser  ✅

`fast-formula-parser` behind a thin module of ours, so the dependency is
replaceable and the guards can see it.

Measured while writing this, on the arithmetic a RUA quotation actually does:

    A2*B2*C2*D2            → 6480
    SUM(A2:A3)             → 3.5999999999999996
    ROUND(…, 2)            → 6480
    VLOOKUP(1.2,A2:D3,4,0) → 240
    TEXT(1234.5,"#,##0.00")→ 1,234.50
    A2/0                   → #DIV/0!

Two findings from that half hour, both cheap and both the kind that cost a day
when met later:

* **An unknown function throws rather than returning `#NAME?`.** `parse()` on
  `NOTAFUNCTION(1)` raises. Every call has to be wrapped, and a cell whose
  formula we cannot evaluate must show `#NAME?` rather than take the sheet down.
* **Floating point is floating point.** `2.4*3.0` is `7.199999999999999`. A
  currency column needs a declared precision on the way in and on the way out;
  this is the same lesson every accounting system learns and there is no reason
  to learn it twice.

What is ours rather than the library's: the dependency graph (which cells to
recompute when one changes), cycle detection, and the recalculation order.

### Stage 3 — The grid  ✅

A screen at `/one/sheets/<name>`, and the sheet's own body: a formula bar, a
column and row header, selection, a fill handle, and cells.

Not `ListBody`. The two look alike and are not: a list draws rows of a doctype
with typed columns, and a sheet draws an unbounded lattice of untyped cells.
Sharing a component would be sharing the scroller and nothing else.

Three things were learned building it, all of them about the editor rather than
about the grid. There is **one** `<input>`, moved to whichever cell is being
typed in — twenty thousand form controls is a page that never finishes opening.
It is rendered with `v-show` and not `v-if`, because typing a character has to
start an edit *and* focus the input in the same tick: with `v-if` the element
does not exist yet, focus waits for the next tick, and every keystroke before
then lands on a grid that already believes it is editing. And `v-show`'s own
`display: none` has to be cleared imperatively at the same moment, because a
hidden element cannot take focus either. `=A1*A2` typed at speed arrived as
`=`, twice, for two different reasons.

The fill handle named above is not built. Everything else is: selection by
click and by drag, shift-arrows, tab and enter, copy, cut and paste as
tab-separated text (which is what Excel puts on the clipboard), bold, italic,
underline, wrap, alignment, Excel's own number formats, and tabs.

### Stage 4 — A sheet feeds a document  ✅

**The stage the request is about.** Everything before it is a spreadsheet;
this is what makes it part of the product.

* **A range is declared.** `Sheet Range` gives a rectangle a name — RUA's
  `extraction_named_range`, ours.
* **A record's Files tab already lists sheets**, because a sheet is a File.
  Opening one from a quotation opens it bound to that quotation.
* **Pull** reads the named range and writes a child table. The header row names
  the columns; a header may carry its unit in brackets, because RUA proved that
  one template then serves millimetres and metres. The mapping — which header
  fills which field — is a stored mapping and not code, for the same reason
  `importer.py` is an engine and not a script.
* **Pull is idempotent and repeatable until it is locked.** A pull replaces
  the child table rather than appending to it, so pressing it twice cannot
  double a quotation. Locking is what RUA's lock did: after it, the document is
  the record and the sheet is history, and a pull is refused rather than
  quietly overwriting lines somebody has since corrected by hand.

  What makes locking possible is that a pull now leaves a `Sheet Feed` row —
  one per (document, child table), replaced when the table is filled again. It
  holds which sheet, which range, how many rows, which headings were left out,
  when, and by whom. Until it existed a quotation had no memory of where its
  prices came from; a month later nobody could say which estimator those were.

  Two decisions in that row are worth stating. `sheet` is `Data` and not a
  `Link`, because the moment the provenance matters most is when the sheet is
  gone — "these lines came off Padel Pro estimator on the 3rd" is worth keeping
  when the estimator is not, and a link would either block the delete or take
  the record with it. And it is its own doctype rather than columns on the
  document, because the document is somebody else's doctype and this product
  does not add fields to Frappe's Quotation to say where it was filled from.

  The permission on a feed row is the **document's**, not the sheet's. A row
  saying "this quotation was filled from that estimator" is as private as the
  quotation, and no more; and locking is a statement about the quotation, so
  the person entitled to make it is the one who may write it — often not the
  estimator whose sheet fed it.

**The manifest declaration was dropped, on purpose.** The plan had a space
declare which screen may be filled from which range:

    { "screen": "quotations",
      "sheet": { "template": "Quotation Estimator",
                 "range": "LineItems",
                 "into": "items",
                 "map": { "Item Name": "item_name", "Qty": "qty" } } }

What is built instead is a control on *every* editable child table on every
saved record. The declaration is the more disciplined design and it is the
wrong one here: it means a person cannot price a job in a grid and feed it into
a doctype nobody thought of in advance, which is exactly the thing being asked
for. The mapping it would have carried is not needed either — a header matches
a field by fieldname or by label, so a template written to match the doctype
needs no map at all, and one that does not says so in the dialog before the
pull rather than silently dropping a column.

`mapping` is still a parameter on `sheets.pull`, and nothing sends one yet. It
is where a manifest entry would attach if a space ever does want to fix the
binding.

### Stage 5 — Templates  ✅

A sheet with `is_template` on it. "New from template" copies its cells, which is
an insert rather than RUA's Drive `files.copy` against somebody else's API.

A workspace's templates are a folder in the Drive, so managing them is managing
files — no second screen, no second permission model.

Two controls, and no third: **Use as a template** in the sheet's own menu, and
**New sheet** in the Drive is a menu whose first item is a blank grid and whose
rest are the templates. A workspace that has an estimator template starts from
it far more often than from an empty sheet, so making that the same click is
most of the feature.

There is still no template *gallery* — a screen of thumbnails and categories —
and there should not be until a workspace has enough templates for a menu to be
the wrong shape.

### Stage 6 — Import, export, print  ✅

Both ways, and the library is `exceljs` (MIT) rather than the `xlsx` this
planned. SheetJS is the obvious pick and the newest release on npm is 0.18.5,
which carries two advisories fixed only in releases published on the project's
own CDN — an unusual dependency source to take on for a file format `exceljs`
also handles. It is loaded with a dynamic `import` and nowhere else, so the
900KB is paid by whoever presses Import or Download as Excel and by nobody who
merely opens a grid.

What survives a round trip: values, **formulas**, number formats, bold, italic,
underline, alignment, colour, fill, and the tab each cell is on. A shared
formula — Excel's own compression, where `B4:B20` all point at `B3` — comes
back translated per row, which is the one part of reading xlsx that is not
obvious. What does not survive: merged cells, column widths, charts,
validation, conditional formats, images. Those are things this product does not
have, and inventing storage for them on the way through would be storing what
nothing reads.

Importing keeps the original file in the Drive as well as making the sheet,
because for the first few weeks the `.xlsx` is the thing its owner still
trusts. The bytes parsed are the ones already in the browser rather than the
ones just uploaded — `validateFile` is where frappe-ui's uploader hands the
file over, so there is no second round trip.

Print is not a print format. The grid windows its rows, so printing the page
prints whichever forty are in the DOM; printing builds its own document — the
used range as a plain table with each cell's format on it — and hands it to an
iframe, which is the shape `PrintDialog` already uses for a record.

### Stage 7 — What we deliberately do not take, yet

* **Live multi-cursor editing.** It is Yjs and a Node process, per §2. What we
  can have without it is what the record surface already has: presence, and a
  last-writer-wins cell with a realtime nudge. Worth revisiting when somebody
  actually collides; not worth changing what a shard is on day one.
* **Charts and pivots.** `echarts` is already in the SPA for dashboards. A
  pivot is a feature, not a stage; it can wait for somebody to ask.
* **The AI half.** `sheets/ai/` is a whole surface of its own, and our AI lane
  is metered and declared per feature. "Explain this formula" is a good feature
  and it is not what makes a sheet useful.
* **Cell-level protection.** `DocShare` on the File is the access model. Locking
  individual ranges is a real request and a later one.

---

## 7. Order, and the things to decide first

Stages 1 and 2 are the risk, and they are mostly the cell store and the
dependency graph. Stage 4 is what the request asks for and is a fortnight after
Stage 3 rather than a fortnight on its own — which is the same shape the Drive
had, where the picker everybody wanted was small once the reader existed.

Three decisions worth making before any code:

**Is a sheet a File?** §5 Stage 1 assumes yes and gets folders, sharing, the
bin, the picker and record-binding for nothing, at the cost of one honest
exception about bytes. The alternative is a `Sheet` doctype that reimplements
all of it. This is the decision everything else rests on.

**How big may a sheet be?** A cell row per cell is the right shape for the
read-back and the wrong shape for a hundred thousand cells. A cap — ten
thousand cells, say — is a number to pick deliberately now rather than discover
when somebody pastes a CSV. Frappe Sheets sidesteps this with the JSON blob and
pays for it in the read-back; we should pay somewhere and know where.

**Does a formula ever reach the workspace's own data?** `=ONESPACE("Sales
Invoice", "grand_total", …)` is an obvious and dangerous idea: obvious because a
sheet that cannot see the workspace is an island, dangerous because it is a
permission boundary inside a cell, and because it is the one thing that would
force server-side evaluation and therefore §1's licence problem. Not in the
first four stages. Worth designing before Stage 3 fixes the cell model in a way
that forbids it.
