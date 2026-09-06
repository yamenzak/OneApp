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
| `spaceview/` | One screen and everything a reader can do on it. Twenty-odd modules from `meta` (what a doctype's metadata says a screen may show) down to `run` (running a declared action) — the package docstring is the map, and `tests/test_spaceview_layers.py` reads it back and holds the import order to it. The whitelisted paths the SPA calls are re-exported from the package, so they are `spaceview.rows` and not `spaceview.records.rows`. |
| `email/mailbox/` | Reading and writing one person's mail. `scope` → `flags` → `query` → `reading` → `filing` → `sending` → `drafts` → `composing`. |
| `importer/` | Bringing another Frappe site's records across. `source` → `mapping` → `writing` → `running` → `checking` → `screen`. |
| `docs/` | The prose a `File` could not hold. `body` (opening one, saving one, and the store contract `versions.py` reads) → `text` (the `.txt` and `.md` beside them, edited as their own bytes) → `export` (one self-contained HTML file, which is also the `file_url` the framework insists on) → `writing`. See `docs/WRITER.md`. |
| `email/` (the rest) | `addresses`, `connect`, `folders`, `inbound`, `outbound`, `people`, `rules`, `threading`. Inbound arrives from a Cloudflare Worker; there is no IMAP server behind an address we route. |

The single modules, roughly by how often they are touched:

* `versions.py` — earlier drafts of a file's body, for a workbook and a
  document alike, because a version of either is the same five columns. The
  snapshot policy and the tiered nightly thinning are Frappe's; the op log
  behind theirs is not taken, because our save is total.
* `link_preview.py` — what is behind a URL somebody typed into a cell.
  Vendored from Frappe for its SSRF guards and off unless an operator turns it
  on, per bench.
* `workspace.py` — the settings a workspace owns, and the allowlist the write
  path checks against. Adding a setting is a change here and nowhere else.
* `tabs.py` — which tabs the settings dialog has and who each one is for. The
  half that was missing: four groups came from `workspace.GROUPS` with a role
  check, and ten more were written into `SettingsShell.vue` and drawn for
  everybody, so the dialog could only be offered to admins. An audience is a
  predicate rather than a role, because "holds an address" is one and no role
  says it.
* `me.py` — what a person may change about *themselves*: their name, their
  password, their own language and time zone, and where they are signed in.
  Same two rules as `workspace.py` — the spec is the allowlist, and every write
  names `frappe.session.user` rather than taking a user.
* `sync.py` — the manifest the control plane sends, cached and applied. What a
  space *is*, on this site.
* `printing.py`, `naming.py`, `docflow.py`, `collab.py`, `showcase.py`,
  `dashboard.py`, `board.py`, `fieldtypes.py`, `theming.py` — one subject each,
  all of them thin wrappers over something Frappe already has. The rule
  throughout: use the framework's model, add the surface. `board.py` is the
  newest and the clearest example: Frappe keeps a board's arrangement on a
  Kanban Board doctype, and here the same four facts are a *view*, because a
  view is what this product already had for "how one person looks at a screen".
* `branding.py` — the workspace's own colour, and the two places a colour has to
  land. The only setting with no Frappe field behind it, and the only thing here
  that writes CSS: the app gets the accent in the boot payload, and the pages the
  framework renders for itself get it as a `<style>` block in
  `Website Settings.head_html`, because espresso and frappe-ui read the same
  tokens. `theming.py` validates the value; `lib/shell/theme.js` expands it.
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
* `ai/` — one call to a model, everything that follows from declaring one, and
  the loop above it. `features` (the `@ai_feature` decorator and its registry) →
  `settings` (the workspace's answers, and the ceilings an operator may lower) →
  `meter` (units the provider reported, never estimated) → `gateway`
  (hold → call → settle, through Cloudflare AI Gateway). Then the three that
  make a conversation possible: `tools` (a Python signature described to a model
  as JSON Schema), `transcript` (one message shape, and the two provider shapes
  it becomes) and `conversation` (ask, run what came back, ask again — within a
  turn count and a credit budget). The last three are adapted from
  `frappe/flow_client`; the model they call is ours, because Flow's own is a
  provider row a tenant could edit.
* `chat/` — the workspace assistant, which is one `@ai_feature` that loops.
  `toolbox` (what it may read, every tool a wrapper over an endpoint the SPA
  already calls, so the assistant sees exactly what its asker could click to) →
  `context` (where the question was asked from: the space bound onto the tools
  and out of their schemas, the screen and record said once in the system
  prompt, both resolved through the same checks a click goes through) →
  `session` (a conversation on disk, and as the transcript a provider is sent) →
  `assistant` (the declaration, the system prompt, and four endpoints). Nothing
  here can write. See `docs/ONESPACE.md` §10.
* `storage/`, `plans/` — R2, and the one bespoke
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
| `cloudflare/` | `api` is the one client and the one place a token is chosen — an account-wide `cf_admin_token` that never leaves the control plane, with the narrow ones winning where they are set. Then `dns`, `kv`, `r2`, `workers` (the inbound email worker and its KV namespace) and `email` (Email Routing on the zone, and the catch-all). `worker/` holds the bundle the control plane uploads, generated from `workers/email-inbound/` and guarded by `tests/test_worker_bundle.py`. |
| `press/`, `cloudflare/` (the rest) | Frappe Cloud and Cloudflare. Both degrade rather than raise: an unreachable dependency greys out a panel, it does not take down the page that would explain why. |
| `spaces/` | The space manifests themselves — `rua`, `books`. Data, read by the sync. |

## The SPAs, `apps/*/frontend/src`

Both are built from `scripts/gen_frontend.py`. **Anything with `Generated by
scripts/gen_frontend.py` at the top is written by that script** — edit
`scripts/spa/`, not the copy, and `tests/test_frontend_guards.py` fails if the
two disagree.

| | |
|---|---|
| `lib/runtime/` | The layer under everything, and the only part both SPAs share byte for byte: `resource` (every call), `errors`, `notify`, `socket`, `sound`, `boot`, `brand`. Generated. |
| `lib/shell/` | What the chrome knows: `session` and `user`, `nav` and `sidebar`, `breakpoint`, `theme` and `appearance`, `icons`, `shortcuts`, `notifications`, `settings` (the dialog's open state) and `mail` (the rail's folders). |
| `lib/screen/` | What a screen's rows and fields *mean*: `fields` (every fieldtype), `cells`, `cards`, `format`, `list`, `rules`, `docstate`, `viewTypes`, `surfaces`, `tree`, `recurrence`, `diary`, `childColumns`. |
| `lib/files/` | One file into the workspace: `attach` (the one door), `directUpload` (the big ones, straight at R2), `files` (what a `File` row is, and `routeFor` — whether clicking one opens an editor or the previewer) and `download`. |
| `lib/workspace/` | Hand-written, and the one place a server call is named: `settings`, `screen`, `record`, `layouts`, `mail`, `drive`, `sheets`, `docs`, `versions`, `importing`, `printing`, assembled into one `workspace` object because every caller says `workspace.screenRows(...)`. |
| `lib/sheets/` | The spreadsheet itself, and mostly **not ours**. `engine/`, `canvas/` and `utils/` are Frappe's, vendored whole from `frappe/sheets` and unmodified — the formula evaluator and its dependency graph, number formats, fill series, merges, spills, validation, conditional formats, pivots, charts, sort and filter, the clipboard, named ranges, the undo stack, and the canvas renderer that draws all of it. `VENDORED.md` is the licence position and the list of what we changed; `tests/vendored.py` is what the guards read. Ours in that tree: `store.js` (loading and saving, against `oneapp_core/sheets`, and the `values` slice their payload has no reason to carry), `headless.js` (a workbook built with no grid on screen, for the Drive's import), `xlsx-file.js` (ExcelJS behind their SheetJS-shaped mapper) and `services/` (`versions.js` and `linkPreview.js`, which fill in the two features whose server halves were not ported when the editor was vendored). |
| `pages/` | One per route. `ScreenHost` is the big one — it resolves a screen and hosts whichever body the view type asks for. |
| `components/screen/` | Everything a screen draws, in four families. `bodies/` is how the rows are shown — `ListBody` (which is also the report), `BoardBody`, `CardsBody`, `DashboardBody`, `CalendarBody`, `GanttBody`, `TreeBody` and the cells, footer and selection bar they share. `record/` is one record open — `RecordView`, its pane, drawer, showcase, tabs and dialogs. `fields/` is one value drawn or edited — `FieldControl`, `LinkPicker`, `StateBadge`, the pickers. `views/` is which screen and how it is filtered — `ScreenHeader`, the filters, the column picker, the switcher. |
| `components/docs/`, `components/versions/` | A document open, and the earlier drafts of one. `DocEditor` is frappe-ui's `RichTextKit` with the surround around it — the save loop, the outline derived from the headings on every transaction, the page setup, the word count — and `PlainText` is the other editor behind the same route, for a `.txt` or `.md` whose bytes are the file. `VersionPanel` is one component for a document and a sheet, because `oneapp_core/versions.py` is one module for both. See `docs/WRITER.md`. |
| `components/mail/`, `components/notifications/`, `components/drive/`, `components/sheets/` | The four surfaces that are not screens. `drive/` is the file manager and the picker every attach surface opens; its `FileRow` is also what a record's Files tab draws, because the two are one query apart. `sheets/` is the editor — `editor/`, which is Frappe's page vendored and reseamed (`lib/sheets/VENDORED.md`), hosted by a four-line `pages/Sheet.vue` that adds no chrome of its own because the editor brings four rows of it. Its `index.vue` is the largest file in the repository and is meant to stay one file: twenty composables have already come out of it and what is left is one canvas, one selection and one history, whose functions each read a dozen of the others — the stylesheet is out, in `editor.css`, because CSS has no closure to share — plus `ImportSheet`, `FeedNote` and `FillFromSheet`, which is the one piece of it that appears somewhere else: a control on every editable child table, because a spreadsheet that cannot feed a document is a spreadsheet. Everything left at the root of `components/` is the shell — the rail, the bottom bar, the account menu — or a primitive more than one side uses: `Resizer`, `FadedScroll`, `EmptyState`, `UsageBar`, and `SharePanel`, which is the body of the share dialog for a record and for a file alike. |
| `composables/` | State pulled out of a page, and what makes `ScreenHost` a shell rather than a program. `useScreenAsked` is what the reader has asked of a screen — the filters, the sort, the columns, the card settings, and whether any of it is unsaved; `useRows` the records that came back for it; `useBulkActions` everything done to the ticked ones; `useRowWrites` the three writes a body makes without opening a record; `useScreenLayout` where an unsaved change goes when you keep it. Beside them: `useRecordSurface` (which record is open, and whether it is a pane or the page), `useCreating` (the three doors that make a new one), `useSavedViews`, `usePeek`, `useListFollow`, `useDrive`, `useUploads`, `useNewFile` (the New menu, shared by the Drive and a record's Files tab), `useOutline` (a document's headings, shared by the rail and the phone's dropdown), `useCrumbs` and `useSorting`. A composable called at the top of `<script setup>` runs *immediately*, so everything it reads must be declared above the call — `tests/test_composables.py` enforces exactly that — written after one extraction read a `const` declared below its call, which is a `ReferenceError`, a blank page, and 152 specs timing out at once. |
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
| `affected.py` | Which browser specs a change can break, so half an hour is not the price of one line. `dev.sh e2e` runs what it prints; `tests/test_affected.py` holds it to the one asymmetry it rests on — narrow on evidence, and answer `all` on silence. |
| `check_settings.py` | Every declared settings type against the Frappe fieldtype it actually writes. Needs a bench. |
| `i18n_pot.py`, `i18n.py` | The catalogue. The first re-extracts every msgid and needs a site; the second answers what is still owed and writes the `.po` files, and needs nothing. `docs/LANGUAGE.md` is the why. |

## Where a change goes

* **A new setting a workspace owns** → `oneapp_core/workspace.py`, then the tab
  in `oneapp_core/tabs.py`'s list and the panel in `components/settings/`. Three
  files, and `tests/test_settings_tabs.py` holds them together: a tab with no
  panel draws nothing, an icon named only in Python draws nothing either, and a
  declared `type` no control can draw falls through to a text box in silence.
  A setting with no Frappe field to write takes `default_key=` instead of
  `targets=`; `branding.py`'s accent is the one that does.
* **A new thing that is a person's own rather than the workspace's** →
  `oneapp_core/me.py`, whose spec is the allowlist and whose every write names
  `frappe.session.user`.
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
* **A new sentence a customer reads** → inside `__()` in the browser or `_()`
  on the server, and nowhere else. `tests/test_i18n.py` reads both halves;
  `python3 scripts/i18n.py sync` then lists it as owed in Arabic and German.

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
* **A guard finds a file by name, not by path.** `tests/where.py` resolves
  `RecordView.vue` or `cards.js` wherever it has been grouped — a guard that
  cannot open its file stops checking rather than failing.
