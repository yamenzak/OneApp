# Where things are

Two Frappe apps and two SPAs. `docs/ONESPACE.md` is the product, `docs/ONEADMIN.md`
is the platform, and both explain *why*. This is the map: which directory owns
what, and where a change goes.

## The two apps

`apps/oneapp` is installed on every **tenant** site. It holds the customer's
data and everything they see.

`apps/oneapp_control` is installed on the **control plane** only. It holds who
the customers are, what they are entitled to, what they owe, and the machinery
that creates and destroys their sites. A tenant site never imports it; it
reaches the control plane over HTTP through `oneapp_core/control_client.py`.

The seam is worth stating plainly, because most confusion about this repo is
confusion about which side of it something is on: **the control plane holds
intent, the tenant site holds data.** The plan a workspace is on lives on the
control plane. The invoices that workspace issues to *its* customers live on
the tenant site.

## The tenant app, `oneapp/oneapp_core`

Four packages carry most of the weight. Each is layered internally — a strict
import order written into its `__init__` docstring, so a module may use the ones
above it and never below — and each has a test that keeps it that way.

| | |
|---|---|
| `spaceview/` | One screen and everything a reader can do on it. Nineteen modules from `meta` (what a doctype's metadata says a screen may show) down to `run` (running a declared action). The whitelisted paths the SPA calls are re-exported from the package, so they are `spaceview.rows` and not `spaceview.records.rows`. |
| `email/mailbox/` | Reading and writing one person's mail. `scope` → `flags` → `query` → `reading` → `filing` → `sending` → `drafts` → `composing`. |
| `importer/` | Bringing another Frappe site's records across. `source` → `mapping` → `writing` → `running` → `checking` → `screen`. |
| `email/` (the rest) | `addresses`, `connect`, `folders`, `inbound`, `outbound`, `people`, `rules`, `threading`. Inbound arrives from a Cloudflare Worker; there is no IMAP server behind an address we route. |

The single modules, roughly by how often they are touched:

* `workspace.py` — the settings a workspace owns, and the allowlist the write
  path checks against. Adding a setting is a change here and nowhere else.
* `sync.py` — the manifest the control plane sends, cached and applied. What a
  space *is*, on this site.
* `printing.py`, `naming.py`, `docflow.py`, `collab.py`, `showcase.py`,
  `dashboard.py`, `fieldtypes.py`, `theming.py` — one subject each, all of them
  thin wrappers over something Frappe already has. The rule throughout: use the
  framework's model, add the surface.
* `notifications.py` — the feed, and the follow machinery Frappe half has.
* `alerts.py` — rules that tell somebody when a record changes. Frappe's own
  `Notification`, gated to the workspace's doctypes and narrowed to one
  sentence; the condition is compiled from three controls rather than typed,
  because Frappe evaluates it as code.
* `jobs.py`, `backup.py`, `expiry.py`, `retention.py`, `site.py` — the scheduled
  half. Every job here is accounted for by `tests/test_site_role.py`.
* `drive/` — every file in the workspace, over Frappe's own `File` table. Five
  layers: `kinds` (what a file is, decided on insert), `query` (the places in
  the rail, as filters), `reading`, `writing`, `sharing` (a link that outlives a
  session, which is the one thing `DocShare` cannot do — sharing with a
  colleague *is* `DocShare` and lives there too). A file attached to a record has
  `attached_to_doctype` and a file in a folder has `folder`; it can have both,
  which is why the Drive and a record's Files tab are two queries and not two
  stores.
* `sheets/` — spreadsheets, over that same `File` table. A sheet *is* a File
  with `custom_kind = 'Sheet'`, so its name, owner, folder, share, bin and
  binding to a record are the Drive's and are not written twice; what is
  written here is the grid, which a File cannot hold. Seven layers: `refs` (A1
  notation, no Frappe), `codec` (what is inside the blob a browser saves),
  `book` (the two calls the editor makes — open a workbook, save one),
  `reading` (a rectangle out of one), `writing` (making a sheet, copying one,
  cleaning up after one), `templates`, `export` (one tab as CSV, and the URL a
  sheet's `file_url` honestly points at) and `feed` — the read-back, where a
  named rectangle fills a document's child table, and the `Sheet Feed` row that
  remembers it did. That row's permission is the *document's*, which is the one
  place in this package the guarding question is not "may you have this File".
  A workbook is **one `Sheet Book` row**, not a row per cell: the grid is
  Frappe's and loads and saves it whole. It carries what was typed beside what
  that came to, and nothing on this side reads the first — the browser
  evaluates formulas, the server stores what it computed. See
  `docs/SHEETS.md` §8.
* `ai/`, `storage/`, `plans/` — the metered gateway, R2, and the one bespoke
  migration plan. In `storage/`, `file.py` is the `File` override that moves an
  uploaded attachment to R2 and `direct.py` is the path a large file takes
  instead: the browser PUTs it straight at the bucket and only tells us where it
  put it. `quota.check_room` is what both ask before allowing it.

## The control plane, `oneapp_control`

| | |
|---|---|
| `api/admin/` | Everything the operator console can do, by subject: `tenants`, `fleet`, `sites`, `billing`, `ai`, `screens`, `lifecycle`, over two shared layers `guard` and `press`. |
| `api/customer.py` | What a workspace can do about itself — its plan, its credits, its invoices. |
| `entitlements/` | Which spaces exist, what each grants, and the operator console's own manifest. |
| `provisioning/` | Creating a site: the steps, and the standby pool that makes it feel instant. |
| `billing/`, `credits/` | Stripe, the ledger, and what a call costs. |
| `lifecycle/` | The dunning ladder, cold storage, and the sweep that drives them. |
| `press/`, `cloudflare/` | Frappe Cloud and Cloudflare. Both degrade rather than raise: an unreachable dependency greys out a panel, it does not take down the page that would explain why. |
| `spaces/` | The space manifests themselves — `rua`, `books`. Data, read by the sync. |

## The SPAs, `apps/*/frontend/src`

Both are built from `scripts/gen_frontend.py`. **Anything with `Generated by
scripts/gen_frontend.py` at the top is written by that script** — edit
`scripts/spa/`, not the copy, and `tests/test_frontend_guards.py` fails if the
two disagree.

| | |
|---|---|
| `lib/` | Generated: the runtime. `resource` (every call), `fields` (every fieldtype), `icons`, `socket`, `notify`, `theme`. |
| `lib/workspace/` | Hand-written, and the one place a server call is named: `settings`, `screen`, `record`, `layouts`, `mail`, `drive`, `sheets`, `importing`, `printing`, assembled into one `workspace` object because every caller says `workspace.screenRows(...)`. |
| `lib/sheets/` | The spreadsheet itself, and mostly **not ours**. `engine/`, `canvas/` and `utils/` are Frappe's, vendored whole from `frappe/sheets` and unmodified — the formula evaluator and its dependency graph, number formats, fill series, merges, spills, validation, conditional formats, pivots, charts, sort and filter, the clipboard, named ranges, the undo stack, and the canvas renderer that draws all of it. `VENDORED.md` is the licence position and the list of what we changed; `tests/vendored.py` is what the guards read. Ours in that tree: `store.js` (loading and saving, against `oneapp_core/sheets`, and the `values` slice their payload has no reason to carry), `headless.js` (a workbook built with no grid on screen, for the Drive's import), `xlsx-file.js` (ExcelJS behind their SheetJS-shaped mapper) and `services/` (the two features whose server halves are not ported, shaped so they can be). |
| `pages/` | One per route. `ScreenHost` is the big one — it resolves a screen and hosts whichever body the view type asks for. |
| `components/screen/` | Everything a screen draws, in four families. `bodies/` is how the rows are shown — `ListBody`, `BoardBody`, `CardsBody`, `DashboardBody` and the cells, footer and selection bar they share. `record/` is one record open — `RecordView`, its pane, drawer, showcase, tabs and dialogs. `fields/` is one value drawn or edited — `FieldControl`, `LinkPicker`, `StateBadge`, the pickers. `views/` is which screen and how it is filtered — `ScreenHeader`, the filters, the column picker, the switcher. |
| `components/mail/`, `components/notifications/`, `components/drive/`, `components/sheets/` | The four surfaces that are not screens. `drive/` is the file manager and the picker every attach surface opens; its `FileRow` is also what a record's Files tab draws, because the two are one query apart. `sheets/` is the editor — `editor/`, which is Frappe's page vendored and reseamed (`lib/sheets/VENDORED.md`), hosted by a four-line `pages/Sheet.vue` that adds no chrome of its own because the editor brings four rows of it — plus `ImportSheet`, `FeedNote` and `FillFromSheet`, which is the one piece of it that appears somewhere else: a control on every editable child table, because a spreadsheet that cannot feed a document is a spreadsheet. Everything left at the root of `components/` is the shell — the rail, the bottom bar, the account menu — or a primitive more than one side uses: `Resizer`, `FadedScroll`, `EmptyState`, `UsageBar`, and `SharePanel`, which is the body of the share dialog for a record and for a file alike. |
| `composables/` | State pulled out of a page. `useRows` owns the records a screen lists and everything about having fetched them; `useRecordSurface` the one that is open and whether it is a pane or the page; `useCreating` the three doors that make a new one; `useSavedViews` the named layouts; `usePeek` a record opened from inside another; `useListFollow` the realtime refetch; `useDrive` the file list, its selection and the eight things that change it; `useCrumbs` and `useSorting` the header's derived state. A composable called at the top of `<script setup>` runs *immediately*, so everything it reads must be declared above the call — `tests/test_composables.py` enforces exactly that — written after one extraction read a `const` declared below its call, which is a `ReferenceError`, a blank page, and 152 specs timing out at once. |
| `screens/` | Bespoke screens a manifest names by component, rather than rendering from metadata. |
| `ui.js` | The barrel. Every frappe-ui component comes through it, so what is allowed is one reviewable list. |

## The generators, `scripts/`

Two things in this repository are written rather than typed: the doctype JSONs
and the shared SPA setup. Each generator is now an assembly file over a package
of content, so a change lands in one subject-sized module instead of a
three-thousand-line one.

| | |
|---|---|
| `gen_doctypes.py` | Turns declarations into JSON, plus the fieldtype map and the capability list that follow from them. |
| `doctypes/` | The declarations: `spec` (the `f`/`section`/`column` vocabulary), then `fleet`, `catalogue`, `ai`, `spaces`, `records`, `importing`. A `doctype()` call registers by side effect, which is why `__init__` imports every module. |
| `gen_frontend.py` | Decides which generated file gets which content, and which bundle gets which files. |
| `spa/` | The content: `spec` (routes, brand, pinned versions), `ui` (the barrel), `runtime`, `shell`, `screens`, `build`, `browser`, `fields`. |
| `field_types.py`, `app_icons.py`, `ai_capabilities.py` | Data both generators read. |
| `check_frontend.py`, `check_frappe_ui.py` | The CI side: a generated copy edited by hand, and a frappe-ui pin gone stale. |

## Where a change goes

* **A new setting a workspace owns** → `oneapp_core/workspace.py`, then the tab
  in `components/settings/`.
* **A new thing a reader can do to a record** → a layer in `spaceview/`, then a
  call in `lib/workspace/record.js`.
* **A new operator action** → a module in `api/admin/`, then `screens/ops/`.
* **A new fieldtype** → `scripts/field_types.py`, which is checked against
  Frappe's own list; `scripts/spa/fields.py` follows from it.
* **A new doctype** → the right module in `scripts/doctypes/`. It must also get
  a customer or operator surface, or `tests/test_no_desk.py` fails — there is no
  desk.
* **A new scheduled job** → `hooks.py`, and `tests/test_site_role.py` wants it
  accounted for.

## The rules the tests keep

Worth knowing before you fight one:

* **No desk.** Every tenant doctype needs a surface in OneSpace; every control
  doctype needs one in OneAdmin.
* **The manifest is the allowlist.** A screen cannot reach a doctype its space
  did not grant, and permission is Frappe's rather than ours.
* **The barrel is the component list.** Nothing imports frappe-ui directly.
* **Generated files are generated.** Edit the generator.
* **A package's layers point one way.** `spaceview`, `mailbox`, `importer` and
  `admin` each fail the suite on an import from below.
* **A guard finds a component by name, not by path.** `tests/components.py`
  resolves `RecordView.vue` wherever it has been grouped — a guard that cannot
  open its file stops checking rather than failing.
