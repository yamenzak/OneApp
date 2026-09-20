# Following the framework — the audit, the blueprint and the move

You were right, and the first version of this document was wrong because it was
written against a checkout seven days stale. Pulling changed the answer.

`HEAD` was `6f32555`, 2026-09-13. `origin/develop` is 344 files and 43,355
insertions ahead of it — **one week of upstream**. In that tree is a directory
that did not exist in ours:

    ui/
      package.json      "@framework/ui" — "Shared client components and
                        utilities for Frappe apps"
      src/components/   FormLayout, Fields, ListView, Filter, SortBy,
                        ColumnSettings, QuickFilter, ConditionBuilder, Grid,
                        Link, TableMultiSelect, ActivityTimeline, DataImport,
                        FileUpload, Notifications, Composer, InviteUser
      src/experimental/List/   List.vue, columnTracks.ts, useColumnResize.ts,
                               useRowSelection.ts, ListBulkBar.vue
      island/           the mount contract, and thirteen decision records

It is Vue 3, TypeScript, tested, and it is a **library for apps** — not desk
furniture. Its peer dependencies are `vue >= 3.3`, `vue-router`, `tailwindcss`,
and `frappe-ui >= 1.0.0-beta.63`. Two of its ~300 files touch `window.frappe`.

This is the layer we spent nine arcs writing. It now ships in the framework.

## 0. The stages

| | | |
|--:|---|---|
| 1 | This document — the audit's terms of reference and the blueprint | done |
| 2 | Catch the bench up: frappe, erpnext, hrms, and `frappe-ui` to beta.63+ | |
| 3 | The full audit — `docs/FRAMEWORK-UI.md`, written while reading | |
| 4 | `frappe.watch` — what landed upstream since we last looked | |
| 5 | The borrowing guards — a test that fails when we rebuild something | |
| 6 | One screen on `@framework/ui`, beside its current self | |
| 7 | The record page: `FormLayout` replaces `components/screen/record` | |
| 8 | The list: `experimental/List` replaces `RecordTable` and the bodies | |
| 9 | Fields, filters, conditions, the timeline | |
| 10 | The shell reads `Workspace`, `Dock`, `Desktop Icon`, `Custom Sidebar` | |
| 11 | `Module Profile` and the whitelabel | |
| 12 | Islands — the same screens hosted in the desk, where that is wanted | |

## 1. The framework's own answer: one library, two hosts

`ui/island/decisions/0008-one-host-loop-two-hosts.md` settles the argument we
were having, because Frappe already had it:

> Desk was the first host of an island. A frappe-ui app, such as CRM or
> Insights, is the second. The loop between a name and a mounted island is the
> same for both. […] That loop lives once, in `ui/island/host.js`. Each host is
> a thin wrapper over it.

And it explicitly rejects tying an island to the desk:

> It works only on a desk page. A frappe-ui app is its own SPA, served from its
> own route, with no desk bundle on it.

So "desk or SPA" is no longer the expensive decision. **The components are the
same either way.** A screen written on `@framework/ui` runs in our SPA today and
can be mounted into a desk page tomorrow by exporting a `mount`, with the same
code. Thirteen decision records describe how an app bundles, builds, styles and
claims its islands; `0012-a-desk-page-can-be-an-island.md` and
`0013-framework-builds-page-islands.md` are the two to read first.

This is why the move is worth making and why it is not a rewrite: we are not
choosing a host, we are adopting a component library, and the host question
becomes reversible afterwards instead of before.

## 2. The inventory — ours against theirs

Measured, not guessed. The SPA is 109,114 lines of `.vue` and `.js` excluding
tests.

| ours | lines | theirs |
|---|--:|---|
| `screen/record/`, `RecordForm`, `FormSections` | 5,637 | `FormLayout`, `buildLayoutFromMeta`, `fieldsToLayout`, `resolveLayout` |
| `screen/fields/FieldControl.vue` and the map | 1,992 | `Fields/` — 23 field components and `registerFieldType` |
| `screen/bodies/RecordTable.vue` — tracks, resize, pinning, selection | 4,196 | `experimental/List` — `columnTracks.ts`, `useColumnResize.ts`, `useRowSelection.ts`, `ListBulkBar.vue` |
| `lib/screen/narrowing.js` and the filter UI | part of 9,352 | `Filter`, `QuickFilter`, `SortBy`, `ColumnSettings` |
| `oneforms/showing.py` — the condition grammar | 260 | `evaluateDependsOn`, `ConditionBuilder` |
| `ChildTable.vue` and this week's `RowsField.vue` | ~900 | `useChildRowModel`, `TableField`, `Grid` |
| `shared/lib/runtime/format.js` | ~400 | `formatField`, `formatCurrency`, `getNumberFormatInfo`, `getFormatDefaults` |
| `lib/screen/meta` | part of 9,352 | `useDoctypeMeta` |
| the record timeline | part of 5,637 | `ActivityTimeline`, with a socket live-update layer |
| the uploader | part of `onestorage` | `FileUpload`, headless engine plus component |

That is **roughly 22,000 lines with a direct counterpart**, and theirs is
typed, tested, and maintained by the people who own the schema it reads.

## 3. What stays ours whatever happens

About 58,000 lines have no counterpart and will not get one, because they are
products rather than views over a schema:

* **`onesheet`, 35,130 lines** — one canvas, one selection, one history. A
  third of the SPA. Nothing in `@framework/ui` is a spreadsheet.
* **`onestorage`, `onedoc`, `onemail`, `oneai`, `oneforms`** — a file manager, a
  collaborative editor, a mail reader, an assistant, a page a stranger opens.
* **The window shell and the dock's *behaviour*** — `lib/desk/geometry.js`,
  `windows.js`, `pip.js`. The desk has a `Dock` doctype for what is *in* a dock;
  it has nothing for a floating, resizable window over a record.
* **The tenancy boundary** — `finding.placed`, the space manifest's grants, and
  the rule that a form is only ever over a doctype a reader's spaces already
  show them. No library has our permission model because no library has our
  tenancy.

The honest framing: **we are replacing our view layer with theirs and keeping
our product.** Not moving the product into their admin tool.

## 4. The audit — stage 3, and what it produces

You asked for a full audit that ends in "a powerful documentation and blueprint
to follow and guard". That is `docs/FRAMEWORK-UI.md`, written while reading
rather than after, in this order:

1. **`ui/island/decisions/*`** — thirteen records, shortest first. They are the
   architecture, written by the people who chose it, and they say what was
   rejected as well as what was taken.
2. **`ui/src/components/FormLayout`** — 40 files. The registry, the layout
   builder, the child-row model, `evaluateDependsOn`, the number formatting.
   This is the one to understand completely; everything else composes with it.
3. **`ui/src/components/Fields`** — 23 components and `fieldTypes.ts`. Read
   `registerFieldType` carefully: it is the seam where our own field types
   (a space narrowing, an `@me` sentinel) join theirs.
4. **`ui/src/experimental/List` and `components/ListView`** — and note the word
   *experimental*, which is a real risk to record rather than skip.
5. **`Filter`, `QuickFilter`, `SortBy`, `ColumnSettings`, `ConditionBuilder`.**
6. **The `frappe` client object** — `frappe.call`, `frappe.model`, `frappe.perm`,
   `frappe.datetime`, `frappe.format`, `frappe.msgprint`, `frappe.show_alert`,
   `frappe.confirm`, `frappe.prompt`, `frappe.ui.Dialog`, `frappe.realtime`.
   Which of these have a non-desk equivalent in `@framework/ui` or `frappe-ui`,
   and which are desk-only. The distinction decides what an island may call.
7. **Desk pages** — `frappe/public/js/frappe/views/`, `frappe.ui.Page`,
   `frappe.pages`, and `frappe/utils/island.py` for how a page island resolves.
8. **ERPNext and HRMS** — not for their UI, which is desk-classic, but for the
   three things they do that we will have to: `Customize Form` and property
   setters as the per-tenant layer, the naming-series and fixtures patterns, and
   how a module declares its workspaces and onboarding. Their client scripts are
   what an island replaces, so read them as the *before*.

Each section answers the same four questions, and the document is useless
without them: what it is, what it replaces of ours, what it cannot do that ours
does, and what it costs to adopt.

## 5. The guards — stage 5

A blueprint nobody checks is a blueprint that decays, and this repository's own
answer to that is a test. Three:

* **`tests/test_borrowing.py`** — a named list of framework capabilities and the
  file in our tree that must *not* reimplement them. Starts at ten entries from
  §2 and grows when the audit finds another. It is a list rather than a
  heuristic because "is this a reimplementation" is a judgement, and a list
  somebody has to edit deliberately is how this repo already holds judgements
  (`test_module_docs.py`, `test_no_desk.py`).
* **`tests/test_framework_version.py`** — the `frappe-ui` floor and the recorded
  upstream sha, failing when `@framework/ui`'s peer range moves past what we
  have. We are on `frappe-ui ^1.0.0-beta.55` and it wants `>= 1.0.0-beta.63`;
  that gap is stage 2 and this test is what stops it reopening.
* **An eslint rule** that refuses a raw `fetch`, a hand-rolled date format, or a
  new field control outside `registerFieldType` — the same shape as the
  `<Button>` rule that already exists and that this session found nine
  violations of.

## 6. `frappe.watch` — stage 4

`scripts/frappe_watch.py`, and it should exist before stage 6 rather than after,
because it is what makes the rest of this repeatable:

* reads the recorded sha from `docs/FRAMEWORK-UI.md`'s front matter;
* diffs it against `origin/develop` for new doctypes, new hooks, new whitelisted
  methods, new `@framework/ui` exports and new island decision records;
* prints them grouped, and fails a test when the recorded sha is more than a
  chosen distance behind.

It would have told us about `ui/` the week it landed. `Dock` and `Desktop Icon`
shipped upstream while we were building both, and nobody knew either way — that
is the cost this script exists to stop, and it is the highest-value item on the
list for the least work.

## 7. The move — stages 6 to 12

**Stage 6 is one screen, beside its current self.** Not a migration: a route
`/one/next/<space>/<screen>` that draws the same screen with `FormLayout` and
`experimental/List`, while the old one stays at its own URL. Both seeded, both
shot, both looked at. The screen is OneProject's task list, because it is a
plain list over a plain doctype and the least interesting thing we have — which
is what a first port should be.

**Stages 7 to 9 are the engine, in the order the dependency graph allows.** The
record page first, because `FormLayout` is the piece everything composes with.
Then the list. Then fields, filters, conditions and the timeline, which are
leaves. Each stage deletes the file it replaces in the same commit — a port that
leaves both is a port that never finishes, which `docs/CLEANUP.md` §12 already
learned once.

**Stage 10 moves the manifest's storage, not its meaning.** `Workspace` carries
`links`, `shortcuts`, `charts`, `number_cards`, `roles`, `restrict_to_domain`,
`for_user`, `is_hidden`, `parent_page`; `Dock` and `Dock Item` carry a dock;
`Desktop Icon` carries `logo_url` and `icon_type`, which is the custom-SVG
registry; `Custom Sidebar` carries a rail. Reading `spaces/*.py` out of those
doctypes means a tenant rearranges their own dock in a UI Frappe maintains, and
it deletes our manifest storage without touching a screen.

**Stage 11 is configuration, not an arc.** `User.block_modules`, `Module Profile`
and `Block Module` are the "tenants should not see infrastructure doctypes"
half, and `NavBar Settings.app_logo` plus a `Website Theme` is most of the rest.

**Stage 12 is optional and comes last.** Once a screen is an island, hosting it
in a desk page is an export and a registration. Do it where the desk's furniture
is worth more than ours — the operator console is the candidate — and nowhere
else. It is last because it is the only part that is not reversible cheaply, and
because by then we will know from stages 6 to 9 whether it is wanted at all.

## 8. The two risks worth naming

**`experimental/List` is called experimental.** It is the piece we would lean on
hardest and the piece most likely to change shape under us. Stage 6 exists
partly to measure that: port one list, then watch it for a month with
`frappe.watch` before stage 8 commits the rest.

**The e2e suite does not shrink; it changes hands.** 75 specs, 840 tests,
fifty-one minutes. Every one of them asserts on our `data-slot` hooks, and
`@framework/ui` has its own. Each ported screen re-selects its spec, and the
suite is red in between. Budget it per stage rather than discovering it at
stage 7.

## What this does not do

**It does not move the product into `/app`.** That was the question asked and
the framework's own answer — one library, two hosts — makes it the wrong
question. The host stays ours, becomes reversible, and stops being what the
argument is about.

**It does not price the whole thing.** Stage 6 is one screen and exists to
produce the number. Nobody should price 22,000 lines from a document, and the
first version of this one is a standing reminder of what happens when a plan is
written from a stale checkout rather than from the tree.

**It does not touch the control plane's rule.** `docs/ONEADMIN.md` §"No desk"
is about credentials and every tenant's billing on one site, and nothing in this
plan weakens it. If stage 12 ever puts the operator console on a desk page, that
argument has to be answered first and separately.
