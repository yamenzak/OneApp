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

**Nothing inside `canvas/` or `utils/` except the header block, and one thing
inside `engine/`.** The rule is deliberate: their own unit suite comes with
them and runs unmodified (`yarn test`), so an upstream fix can be pulled in by
re-copying a file rather than by re-deriving a patch.

The exception is `RECORD()` — a cell that reads a field off a record
(`docs/SHEETS.md`, `oneapp/onesheet/records.py`). It is three hunks:

| File | What |
|---|---|
| `engine/formula.js` | A `RECORD` entry in `FUNCTIONS`, its hint, and `setRecordResolver` — a module-level hook the function reads through. The entry hands the hook the arguments as they were written, so which of the three forms a call is stays in one file. |
| `engine/formula.js` | A `RECORDROW` entry beside it, and its hint: one cell of a child table, because this engine has no spill and a schedule is written as a block of cells. |
| `engine/sheet.js` | `RECORDROW` and `RECORD` added to `VOLATILE_RE`, so a cell reading a record is not memoised across a refresh. `RECORDROW` goes *first*: alternation is first-match, and at `RECORDROW(` the shorter name matches and then fails on `\s*\(` without backtracking into a longer sibling — so a block of child rows would be memoised and never re-read. |

Both are additive: nothing upstream behaves differently, and re-copying
either file loses the feature rather than breaking the file. The hook is
module-level rather than a seventh parameter threaded through `evaluate` and
`createParser` because the cache behind it is keyed by *record* — two
workbooks open on the same quotation want the same number — and because the
parameter would have touched both files far more deeply than this does.

The resolver itself is ours and is not in `engine/`:
`services/recordFields.js`. It exists because the engine is synchronous and
must stay that way; it collects every record a workbook names, fetches them
in one request, and recomputes once.

**The editor is modified**, and every change is one of three kinds.

*Seams* — files that were theirs and are now ours, each with its reason at the
top of it:

| File | Why |
|---|---|
| `store.js` | Their `usePersistence`, against `oneapp.onesheet` rather than `sheets.api`, because a sheet of ours is a `File` in the Drive. Adds a `values` slice their payload has no reason to carry. |
| `headless.js` | A workbook built with no grid on screen, for the Drive's import. |
| `xlsx-file.js` | ExcelJS where upstream calls SheetJS. Their pure `engine/xlsx-io.js` mapper is untouched behind it. |
| `services/versions.js` | Their version panel, over `shared/versions.py` — one module shared with documents (`docs/WRITER.md` §5). `cellHistory` and `cellDiff` stay empty: they read an op log, which exists because their save is incremental and ours is total, and the editor already treats what they feed as optional. |
| `services/linkPreview.js` | Their hover card, over `onespace/link_preview.py` — which is their endpoint, vendored whole for its SSRF guards, off unless an operator turns it on. |
| `../../components/sheets/editor/usePersistence.js` | The five refs and five functions `index.vue` expects, over `store.js`. |
| `../../components/sheets/editor/useCollaboration.js` | Inert. Yjs wants a second Node process. |
| `../../components/sheets/editor/shortcutRegistry.js` | frappe-ui 1.0 replaced `{key, ctrl}` with `'Mod+S'`. |
| `../../components/sheets/editor/useTemplateInsert.js` | A template's tabs added to the open workbook. No upstream counterpart. |
| `../../components/sheets/editor/editor.css`, `editor.global.css` | Their `<style>` blocks, lifted into files of their own. Same rules, same scoping — `<style scoped src>` still bounds them to the component. |

*Version differences* — the editor targets frappe-ui `1.0.0-beta.3` and this
repository is on `beta.55`. Thirteen components they register globally are
imported per file here; `FeatherIcon` is `Icon` with `lucide-*` names;
`Autocomplete` is `Select`; the command palette is the seven-part family that
replaced it; `{group, items}` is `{group, options}`; `Dialog`'s `:options` are
props with the body in the default slot; `Popover`'s `#target`/`#body` are
`#trigger`/default; `placement` is `side` and `align`. None of these is an
error at build time — a renamed prop is a menu that opens on "No options" and a
dialog that opens empty.

*Additions* — five, and each is a line or two.

The topbar's `File ⌄` dropdown is a three-dot button at the *end* of the bar.
Same options, same groups, same component — what moved is the trigger and
where it sits, so that it matches the document editor's. The two are one
suite and their menus hold nearly the same verbs; a labelled dropdown at one
end and an icon at the other made finding one teach you nothing about
finding the other.

`onCommit` skips data validation for a value beginning `=`. What arrives
there is the text somebody typed, because the commit runs before the
recompute — so a `number` rule read a word and a `list` rule read something
in no list, and every formula in a validated column was refused. Google
Sheets validates the result; this engine has no result at that point, and
refusing every formula is worse than checking none. The result *is* checked
where it lands: `onesheet/rules.check` reads the computed slice at the pull.
Upstream never hit this because nothing upstream seeds a rule over a column
people write formulas into.

`_flashProtected` shows the blocked
range's own `description` where it has one, falling back to their sentence
where it does not. Upstream never writes a description, so upstream had
nothing to show; `sheets/feed.py` writes one on the headings of a sheet that
feeds a child table, and it names where to work instead. "This range is
protected" with no idea what to do next is the same as no message.

`isGuest` reads `getSessionUser()` rather than
`window.frappe.session.user`. That global belongs to Frappe's own desk page
and to their standalone `www/sheets.html`; this SPA is neither and never
sets it, so the check answered "Guest" for every signed-in person — and
`canCollaborate` is derived from it, which is how live editing stayed
switched off on a page that was otherwise fully wired. The helper beside it,
`lib/utils/session.js`, already knew to fall back to the `user_id` cookie;
this one line did not use it. Found by two browsers refusing to see each
other, and by nothing else — no suite and no build can see it.

`isInitialLoad` is declared beside the collaboration hookup rather than
beside `onMounted`, and is passed in as `ready`. Collaboration must not
start before `get_sheet` has answered: the first person into a room seeds it
from what their engine holds, and what this editor holds three hundred
milliseconds after mount is an empty grid — which would then be the workbook
handed to everybody else. An immediate watcher reads the ref during setup,
and a `const` read above its own declaration throws rather than reading
undefined, so the declaration had to move.

*Removals* — the share dialog (a sheet is a `File`, and two share models for
one object is the bug), AI Assist, the version-history trigger, Frappe's brand
mark, and a second copy of the signed-in person's avatar.

`docs/SHEETS.md` §8 is the long form.

## `collab/`, and what changed under it

`lib/collab/ydoc.js` and `lib/collab/cells-binding.js` are theirs, taken
whole but for one import path and one added function. The Y.Doc shape, the
patched `setCell`, the origin tags and `drainLocalTouches` are all Frappe's
and all right.

`applyRemote` is ours, on the binding: a write into the engine through the
*unpatched* setter, so it neither goes back out to the room nor counts as one
of this client's touches for undo. `useCollaboration` calls it once, when a
late joiner has been handed the room's state and has to make its engine agree
with it — including about the cells the room no longer has, which is the one
thing a Yjs update cannot tell an engine that loaded a stale copy.

What we did **not** take is their transport. `frappe-provider.js` publishes
each Yjs update through a whitelisted method — an HTTP POST into a Python
worker per flush — and `hocuspocus-client.js` is the alternative, a separate
Node service. Ours is `shared/lib/live/`, over the socketio process the bench
already runs. `docs/COLLABORATION.md` §1 is the argument and the measurement.

`useCollaboration.js` is theirs in shape and ours in two places: identity
comes from the relay's roster rather than from awareness, because awareness
is client-asserted and a peer must not be able to claim to be somebody else;
and there is one transport rather than two behind a `collab_v2` flag.

## What we did not take
* `utils/sentry.js`, `sheets/ai/` — we have our own AI gateway and no Sentry.
* `pages/SheetEditor/ShareDialog.vue` and their trash — a sheet is a `File`, so
  sharing, the bin and expiring links are the Drive's already.
