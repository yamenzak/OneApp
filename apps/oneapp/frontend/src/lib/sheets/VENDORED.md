# Vendored from frappe/sheets

`engine/`, `canvas/` and `utils/` in this directory are Frappe's, taken whole
from [frappe/sheets](https://github.com/frappe/sheets) at `3f9e37b5776f`. They
are the spreadsheet itself: the formula evaluator and its dependency graph, the
number-format grammar, fill series, smart fill, merges, spills, validation,
conditional formats, pivots, charts, sort and filter, the clipboard, named
ranges, the undo stack — and the canvas renderer that draws all of it.

They arrive with three obligations, none of them optional:

* **Frappe's copyright notice stays.** Every file carries it, and the upstream
  path it came from, in its first four lines. Do not strip that block, and do
  not move a file without updating the path in it.
* **They stay AGPL-3.0.** OneSpace is AGPL-3.0, which is why this was allowed at
  all. No file here may be moved to a permissive licence, ours or anyone's.
* **What we changed is written down.** See below.

## Why vendored rather than depended on

`frappe/sheets` publishes no library. The engine and the renderer are internal
modules of an app, imported by relative path from a Vue page that assumes its
own routes, its own `Sheet` doctype and its own collaboration server. Taking the
two layers that have no dependencies at all — neither `engine/` nor `canvas/`
imports anything outside this tree — is the only way to have them.

## What we changed

Nothing inside `engine/`, `canvas/` or `utils/` except the header block. That is
deliberate: their own test suite comes with them and runs unmodified (`yarn
test`), so an upstream fix can be pulled in by re-copying a file rather than by
re-deriving a patch.

Everything OneSpace-shaped lives *outside* these three directories:

* `../../components/sheets/` and `../../pages/Sheet.vue` — our chrome, our
  routes, our theme tokens.
* `store.js` here — the save payload and the load, against
  `oneapp.oneapp_core.sheets` rather than `sheets.api`, because a sheet of ours
  is a `File` in the Drive and not a `Sheet` doctype.

## What we did not take

* `collab/` — Yjs over a separate Node process (`@hocuspocus/server` + Redis).
  Live collaboration is not built; see `docs/SHEETS.md`.
* `utils/sentry.js`, `sheets/ai/` — we have our own AI gateway and no Sentry.
* `pages/SheetEditor/ShareDialog.vue` and their trash — a sheet is a `File`, so
  sharing, the bin and expiring links are the Drive's already.
