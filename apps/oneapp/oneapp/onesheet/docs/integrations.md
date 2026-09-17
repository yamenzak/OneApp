# Integrations

## OneCloud (`onestorage`)

A sheet is a `File`, so folders, sharing, links, the bin, quota and the WebDAV
mount all belong to OneCloud. OneWorkbook is the Drive landed on
`place=workbooks`, not a second application over a second store.

`File Version` is shared with OneWriter: both stores answer the same three
questions — what is the head, read it, put this back — so `shared/versions.py`
asks through a small contract and neither module knows about the other.

## ERPNext — the reason this module exists

**In both directions, and neither is a copy.**

**Outward**, `feed.py`: a named range fills a Quotation's line items, an
Invoice's, any child table the record names. The estimator prices the job in
the sheet and the document is filled from it. After `lock`, the document is the
record.

**Inward**, `records.py`: `=RECORD("grand_total") * 0.05` reads the quotation
back. A formula rather than a paste, so it stays right through the third
revision.

That pair is the whole argument for this being in the product rather than being
Excel — the sheet and the record are in the same place, and the numbers travel
both ways without anybody exporting anything. `docs/SHEETS.md` is what RUA's
Google Sheets integration actually did, which is the shape `feed.py` took.

## Frappe

**`File`** through OneCloud. **`on_trash`** so a binned sheet takes its `Sheet
Book` with it. **`Bound Record`** for the keyed binding a document uses too.

`Sheet Book` is granted to **System Manager only**, which is not a Frappe
integration so much as a refusal of one: every path into a workbook's contents
is one of this module's functions, which is what stops "a sheet is a File" from
being true of the identity and false of the contents.

## `frappe/sheets` — vendored, and said so

The grid, the engine and the canvas renderer were **taken whole** rather than
re-solved. `frappe/sheets` is AGPL-3.0 and so is this repository, so the
licences match and the three obligations are met: Frappe's copyright stays at
the top of every vendored file, each says what it was derived from, and none of
it moves to a permissive licence.

`frontend/src/modules/onesheet/lib/VENDORED.md` is what came from where and
what changed. A fork that pretends to be original is one nobody can update.

## OneWriter (`onedoc`)

Two editors, one chrome, one version store. The person who prices the job in
the sheet is the person who writes the letter — the adjacency is most of the
argument for both.

The AI door was settled here first: no branded button, verbs in the menu, and
`shared/lib/ai/verbs.js` holds the words so three editors cannot drift.

## The engine (`onespace`)

* **`shared/paper.py`** describes the page `printing.py` lays a rectangle on.
* **The desk** — OneWorkbook is a window with its own tile, mark colour and
  corner.
* **`collab.py`** — a colleague in the workbook watches a plan arrive.

## OneLegal

Nothing of its own beyond what OneCloud says about where bytes live.

## OneAI

`ai.md`. One feature, and it is the only surface in the product where a model's
answer is not text.
