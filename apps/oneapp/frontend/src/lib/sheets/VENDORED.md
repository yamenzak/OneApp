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

**Nothing inside `engine/`, `canvas/` or `utils/` except the header block.**
That is deliberate: their own unit suite comes with them and runs unmodified
(`yarn test`), so an upstream fix can be pulled in by re-copying a file rather
than by re-deriving a patch.

**The editor is modified**, and every change is one of three kinds.

*Seams* — files that were theirs and are now ours, each with its reason at the
top of it:

| File | Why |
|---|---|
| `store.js` | Their `usePersistence`, against `oneapp.oneapp_core.sheets` rather than `sheets.api`, because a sheet of ours is a `File` in the Drive. Adds a `values` slice their payload has no reason to carry. |
| `headless.js` | A workbook built with no grid on screen, for the Drive's import. |
| `xlsx-file.js` | ExcelJS where upstream calls SheetJS. Their pure `engine/xlsx-io.js` mapper is untouched behind it. |
| `services/versions.js`, `services/linkPreview.js` | Two features whose server halves are not ported, shaped so they can be. |
| `../../components/sheets/editor/usePersistence.js` | The five refs and five functions `index.vue` expects, over `store.js`. |
| `../../components/sheets/editor/useCollaboration.js` | Inert. Yjs wants a second Node process. |
| `../../components/sheets/editor/shortcutRegistry.js` | frappe-ui 1.0 replaced `{key, ctrl}` with `'Mod+S'`. |

*Version differences* — the editor targets frappe-ui `1.0.0-beta.3` and this
repository is on `beta.55`. Thirteen components they register globally are
imported per file here; `FeatherIcon` is `Icon` with `lucide-*` names;
`Autocomplete` is `Select`; the command palette is the seven-part family that
replaced it; `{group, items}` is `{group, options}`; `Dialog`'s `:options` are
props with the body in the default slot; `Popover`'s `#target`/`#body` are
`#trigger`/default; `placement` is `side` and `align`. None of these is an
error at build time — a renamed prop is a menu that opens on "No options" and a
dialog that opens empty.

*Removals* — the share dialog (a sheet is a `File`, and two share models for
one object is the bug), AI Assist, the version-history trigger, Frappe's brand
mark, and a second copy of the signed-in person's avatar.

`docs/SHEETS.md` §8 is the long form.

## What we did not take

* `collab/` — Yjs over a separate Node process (`@hocuspocus/server` + Redis).
  Live collaboration is not built; see `docs/SHEETS.md`.
* `utils/sentry.js`, `sheets/ai/` — we have our own AI gateway and no Sentry.
* `pages/SheetEditor/ShareDialog.vue` and their trash — a sheet is a `File`, so
  sharing, the bin and expiring links are the Drive's already.
