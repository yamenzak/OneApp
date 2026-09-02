# OneSpace

The product a customer uses. A workspace is a Frappe site with ERPNext on it,
and OneSpace is the only way anybody sees it — no desk, for customers or for us.

This document is the whole tenant side: what a space is, how a screen is drawn,
what bounds it, and what the product already does without being told to.
The platform behind it — tenancy, billing, provisioning, the lifecycle — is
`ONEADMIN.md`.

---

## 1. The shape of it

```
Account ──┬── Workspace (a Frappe site)   plan, credits, people
          └── Workspace                    billed separately
                 │
                 ├── Space   an entitlement + a role + screens
                 ├── Space
                 └── Account   billing, people, roles, domain
```

**One account, many workspaces.** The same person signing up for their company
and later for something at home is normal, not an edge case. Every customer
endpoint therefore takes a workspace name and **verifies ownership before doing
anything else** — enforced once in `require_workspace()`, and asserted by a test
that reads the source, because an endpoint that skips it is a cross-tenant read.

**The SPA is served from the Frappe app**, built by Vite into
`oneapp/public/frontend` and routed at `/one`. Not edge-hosted: each site serves
the frontend matching its own backend, so a rolling migration can never point a
new frontend at an un-migrated site. Auth is Frappe's own same-origin `sid`
cookie — no CORS, no token exchange.

---

## 2. A space is configuration before it is code

A space declares which doctypes it grants and which screens it puts in front of
a customer. OneSpace renders those screens from **the tenant site's own
metadata** — what each field is called, what a Select offers, whether this user
may write it — so most spaces need no frontend code at all and a new one is a
registration plus its doctypes, with no OneSpace release.

| | Where | What it does |
|---|---|---|
| Registration | `OneSpace Space` in OneAdmin | Name, icon, availability, the role that gates it |
| Manifest | `OneSpace Space Doctype` | Which doctypes the role may touch, and how much |
| Screens | `OneSpace Space Screen` | What the customer sees |
| AI features | `@ai_feature` in app code | §9 |

**General** reaches every workspace; **Restricted** only those granted it
individually. A space with no screens is an entitlement with no interface — a
real thing to be, since it still grants its roles and doctypes.

### A screen

```
screen        invoices            slug in the URL; a bookmark points at it
label         Invoices            the space's navigation
icon          lucide-receipt
document_type Sales Invoice       what the list shows
fields        customer,status,grand_total
filters       {"status": "Open"}  always applied
order_by      modified desc
view_types    list,board,grid,dashboard    the first is the default
view_settings {"board": {...}}    per type, what it needs beyond columns
status_field  status              the badge, and the board's columns
naming_series ACME-INV-.YYYY.-.#####       a fixture, applied once
print_formats [{...}]             a fixture, applied once
component                         escape hatch
```

`fields` is **a default, not a ceiling**: it decides which columns a screen
opens with, and the column picker offers every field the doctype has. Someone
who wants the due date on their list gets it without a deploy. Labels, types,
Select options and required-ness come from the tenant site, so a relabelled
field is relabelled everywhere without a sync. A field a site does not have is
skipped rather than fatal — one manifest serves sites on different versions.

Screens are edited in OneAdmin under **Settings → Space screens**, and their
order there is the order of the space's navigation.

### The escape hatch

Register a component under `spaceCode/screen` in `spaces/index.js`, set
`component` on the screen, and everything else on it is ignored. Lazy, so a
space nobody opened costs nothing. Use it for a wizard or a bespoke page —
second, not first: every screen written by hand is a screen maintained by hand.

---

## 3. Two rules make a screen safe to hand a customer

**A screen is an allowlist.** It can only be reached through a space the
workspace is entitled to, and can only name a doctype that space's manifest
already granted — checked against the DocPerms actually written, not against the
manifest as sent. A screen pointing outside its space is refused rather than
returning an empty list, which reads like there is no data.

**Reads and writes go through the view, never a generic document API.** Within
the granted doctype the bound is Frappe's own: `has_permission(write)` decides,
`read_only` fields are not editable, a field above this user's permlevel is
never offered, and Frappe's bookkeeping never is.

The manifest's `fields` used to narrow writes too and no longer does. A field
you do not want a customer to edit needs `read_only` or a permlevel **on the
doctype** — not merely absence from the manifest.

**A space must grant every doctype its editable Links point at.** This is the
first thing that bites when writing one. A Link renders a picker, the picker is
`frappe.get_list` over the target *as the person asking*, and our roles hold
only what the manifest granted — so a Link pointing outside it comes back
empty. Not refused, not an error: an empty menu on a field the form may well
mark required. A Sales Invoice screen needs Customer and Item in the manifest,
at least to read, or the two fields somebody fills in first are both blank.

It cannot be found by using the operator console, because an operator is a
System Manager and reads everything. `tests/test_manifests.py` checks it
against the declarations instead, with an exemption table naming the handful of
framework doctypes that are reachable without a grant and why.

### A person may narrow a screen, never widen one

A saved view hands the browser three things that reach the query layer. So:

* **Filters are ANDed** with the screen's own. A saved `status = Closed` on a
  screen filtered to `status = Open` returns nothing rather than quietly
  returning the screen's rows.
* **The operator is a named part**, checked against Frappe's own per-fieldtype
  table — inverted from its deny list into an allow list, because a deny list
  gives a fieldtype nobody thought about every operator.
* **A value has to be the shape its operator takes.** `between` is exactly two,
  `in` is a bounded list, everything else is a scalar. A list arriving where a
  scalar belongs is dropped, never reinterpreted.
* **Columns intersect** and keep their order; naming `owner` drops it rather
  than adding it.
* **`order_by` is rebuilt from parts** — a fieldname and a direction, each
  checked. The string that arrived never reaches the query layer.
* **The same bounds apply before anything is saved**, which is why the controls
  can show their answer immediately.

Everything is re-checked **on the way out**, not only when it was saved — the
row is a doctype an operator can write directly.

A saved view can be **shared** (its user left empty, the shape Frappe's own
`List Filter` uses). Writing one needs workspace admin; opening one needs
nothing, because it is bounded when read. Nobody edits anybody else's private
layout, admin or not.

> A whitelisted method's **type annotations are part of the contract**. Frappe
> validates arguments against them and answers a mismatch with a 417 before the
> body runs — which is how every save from the browser was silently refused
> while every unit test passed. `tests/test_screens.py` reads the annotations
> and checks them against what the SPA sends.

---

## 4. What a screen carries without being asked

None of this is in a manifest. It comes off the doctype, so a space gets it by
existing.

* **Every fieldtype has a control**, generated from Frappe's own
  `data_fieldtypes`, so a fieldtype Frappe adds fails a test rather than
  rendering as a text box that writes a string into a Currency column.
* **A link is a record, everywhere** — a face, a name, the id beneath — in a
  list cell, a picker menu and a hover card alike. The picker searches on the
  server, bounded by the screen, honouring `link_filters` and the doctype's
  `search_fields`. Create is in the menu where the target doctype is one the
  space granted and this user may create.
* **Title, image and naming.** `title_field` names the record, `image_field`
  gives it a face, and the naming rule says whether a new record names itself.
* **Badge colours** from the doctype's own Document States, so "Open" is the
  same colour here as in the desk.
* **Comments, history and likes**, which Frappe keeps on every doctype.
* **Quick filter boxes** for `in_standard_filter` fields plus the title field,
  each with Frappe's `=` / `≈` toggle.
* **Sortable headers**, an ID box on every list, a row's age, its comment count
  and a heart.
* **Assignment** — Frappe's `_assign` plus a ToDo, so the record turns up in
  that person's own list. Read permission is enough to assign: a reader who can
  see a record and cannot ask a colleague to look at it sends an email instead.
* **Every DocField flag** that says something: `reqd`, `read_only`, `permlevel`,
  `in_list_view`, `in_standard_filter`, `link_filters`, `in_preview`,
  `allow_in_quick_entry`, `bold`, `columns`, `hide_days`/`hide_seconds`,
  `set_only_once`, `fetch_from`, `states`, `precision`, `non_negative`.
* **`depends_on`, `mandatory_depends_on`, `read_only_depends_on`** — parsed by a
  small grammar rather than evaluated. The desk runs those strings as
  JavaScript; the string is a database row anyone with a Property Setter can
  write, and `new Function` on one turns "can customise a form" into "can run
  code in every reader's browser". Anything outside the grammar is treated as no
  rule rather than guessed at.

Deliberately not honoured: `in_global_search`, `search_index`, `unique`,
`no_copy`, `print_hide` — each about something a screen does not do yet.
`unique` is still enforced by Frappe on save.

---

## 5. The four bodies

A view type is *how you look*; a saved view is *which slice*. Both are in the
URL (`type` and `layout`) and **every saved view is filed under the type it was
made in** — a board's views carry a column field, a list's carry widths and
pinning, and neither means anything in the other's switcher.

Switching type **carries the row question and drops the drawing**: filters, sort
and favourites follow you; columns, widths, pinning and grouping do not. A link
opened cold carries nothing and gets that type's own default, which is what a
link should mean.

### List — a data grid, not a long page

The screen is a pane: page scrolling off, one element scrolling both axes, the
column header sticky at its top. That answers the question the obvious layout
gets wrong — on a scrolling page a wide table puts its scrollbar at the bottom
of the *table*, so on two hundred rows you scroll down past everything to
discover you could have scrolled sideways.

One scroller, not two nested: a separate horizontal wrapper leaves the header a
scrollbar's width out of true with its rows. A guard fails the build on the
two-wrapper shape.

Pinned columns, an edge wash that says there is more, a footer of page size /
Load more / "48 of 1,240", and windowing past two hundred rows. The count is
**its own request**, never awaited with the rows: a `COUNT(*)` over an unindexed
filter is a full scan, and folding it in would put that scan in front of every
list. It goes through `get_list` so it sees the same permissions the rows did.

`RecordTable` draws both this and the grid inside a record — one place to be
wrong about tracks, sticky headers, pinning and windowing.

### Board — the same list, drawn as columns

Same rows, same filters, same order, placed in the column a field names. Which
field is the reader's, narrowest last: the screen's `status_field`, the
manifest's `view_settings`, the saved view.

Two fieldtypes make columns and they make them differently. A **Select** becomes
its own options, in the doctype's order, empty ones included — an empty column
is where you drop something. A **Link** becomes the values actually on the page:
a board by assignee in a workspace of four hundred people is four hundred
columns and 397 of them are empty. Nothing else — a Date wants a calendar.

Moving a card writes one field through the same `save` a form uses, so
permissions, `read_only` and `fetch_from` all apply. The list is re-read
afterwards rather than trusted.

### Grid — the same cards, not bucketed

`lib/cards.js` owns what a card *says*; the two bodies are two ways of putting
those on a page. A grid needs no field, so it is offered wherever declared.

**Where the doctype has an `image_field`, the grid is a gallery**: the picture
*is* the card and everything else sits over it in a gradient to black. Decided
by the doctype, not by a setting. A board does not do this — a board column is
18rem wide and a column of squares is a board you scroll all afternoon.

### Dashboard — the first that draws no records

Declared, never coded:

```json
"view_settings": {"dashboard": {"widgets": [
  {"kind": "number", "label": "Open", "aggregate": "count",
   "filters": {"status": "Open"}, "width": 3},
  {"kind": "donut", "label": "By status", "group_by": "status", "width": 6},
  {"kind": "line",  "label": "Raised", "group_by": "date",
   "grain": "month", "width": 6}
]}}
```

Nine kinds, one per chart frappe-ui ships. Five aggregates. Widths in twelfths.

Everything about it follows from one decision: **every widget is one
`frappe.get_list`, as the person asking.** No raw SQL, no `ignore_permissions`,
and the screen's own filters underneath every one — so a dashboard cannot count
a row its reader may not see, and answers differently for two people with
different User Permissions, without a second permission model existing.

A bad widget is dropped **whole**, never narrowed to its valid parts: a chart of
*something else* is worse than no chart, because a reader cannot tell.

One real limit: Frappe refuses a SQL function in `group_by`, so a widget grouped
down a date column fetches and buckets in Python, capped at 5,000 rows. Fine at
a chart's scale, not at a report's — which is why the cap is stated.

---

## 6. The record

**A pane beside the list on a desktop, a page on a phone.** It was a modal, and
a modal is the wrong shape: a record is something you read *against* the list —
mark this done, glance at the next, come back. The pane's width is dragged and
remembered in the browser.

Four tabs:

| | |
|---|---|
| **Details** | The doctype's own form. Tab, Section and Column Breaks read the way the desk reads them, collapsing below the breakpoint. |
| **Activity** | One timeline: what was said, what changed, and when it started, newest first. Merged in the browser from two queries; every entry carries a glyph from a closed set, because a column of identical avatars makes a comment and a field change look alike. |
| **Files** | Frappe's own File rows, so an Attach field's file and a dropped file are one list. |
| **Meta** | The desk's sidebar: the face and name, then the four things you do to a record *about other people* — assign, attach, tag, share — then who made it and when, then its id. |

**Making a record is a dialog**, the one place a modal is right: nothing behind
it to refer to, a short decision, cancelling leaves nothing. It shows the whole
form rather than Frappe's quick-entry subset — a dialog that asks for four
fields and hides eleven leaves people to discover the rest later.

**Renaming is Frappe's rename**, through `update_document_title`, and only where
`allow_rename` plus write permission say so. The id is a foreign key in every
Link field, `_assign`, Comment, File, ToDo, Version and Document Follow row; an
`UPDATE ... SET name` would leave a workspace full of links to a record that no
longer exists. Renaming the *title* is not this — that is an ordinary save.

**A child table is a grid**, using the child doctype's own `in_list_view`
fields: edited in place, tickable, drag to reorder with `idx` rewritten, numbers
right-aligned, required columns marked in the header. None of it is declared.

**Two permission questions, not one.** A field above the read levels is not
offered anywhere; a field above the write levels is shown and never editable.

**Docstatus and workflow are one row of buttons.** They are one thing in
Frappe — a `Workflow State` carries a `doc_status`, so approving something is
what submits it — so the header asks the server one question, *what can be done
to this now*, and renders the list that comes back without knowing which
mechanism produced it. A submittable doctype with no workflow offers Submit,
then Cancel, then Amend. A doctype with one offers that workflow's transitions
instead, filtered by the reader's roles and each transition's own condition, and
the plain Submit is not offered beside them: a workflow **owns** the transition,
and two buttons that mean the same thing would disagree about who may press
them. Amend is `copy_doc` honouring `no_copy`, and the framework's own naming
turns `amended_from` into `-1`.

Three rules shape that row, and none of them names an action:

* **A step forward is a button; a step that cancels is behind three dots**, in
  red, and asks before it runs. Which is which comes off the next state's own
  `doc_status`, never the word on the button — "Reject" and "Return to draft"
  are the same word to a reader and different things to the ledger. So a
  submitted document is a badge and a menu: unwinding a ledger entry should
  not sit one mis-click from the thing you came here to do.
* **The first step forward is green.** It is what the record is waiting for.
* **Save and the actions share one slot.** Save is offered only while the form
  holds something the server has not seen, the actions only while it does not.
  Submitting what is on the server while the form holds something else is how a
  document gets submitted that nobody has read.

A submitted record is editable only in the fields marked `allow_on_submit`; a
cancelled one is not editable at all.

**Where a record stands is beside its name**, not among the buttons — in the
trail on a desktop, in the pane's own header on a phone, and as a badge either
way. Up to two of them: the screen's `status_field`, which is the doctype's own
word (*Overdue*, *Paid*), and the framework's, which is the workflow's state or
Draft / Submitted / Cancelled. De-duped where they are the same field. Both
carry a glyph derived from the words the same way the list cell's does, through
one `StateBadge` — a status that has an icon in the list and none in the trail
is a difference nobody reports and everybody notices.

`Workflow Document State.allow_edit` is enforced on the way *in*, not only
drawn: the desk enforces it in the browser, which means the API under it does
not, and ours is the only surface there is.

**There is no workflow builder.** A workflow is part of what an app *is*, like
its doctypes and its print formats, so it is shipped by whoever owns the
doctype. The runtime honours whatever it finds.

**Realtime.** A list follows `list_update` (coalesced, because a bulk import
publishes hundreds a second). A record joins Frappe's two rooms, so the header
shows who else has it open, and when somebody else saves it the pane *says so*
rather than doing anything — the reader may be halfway through typing, and
replacing what is on screen is the one thing worse than being out of date.

---

## 7. Roles, permissions and collaboration

**We ignore the roles ERPNext ships with.** A customer never sees ERPNext, so a
role named for its org chart describes nothing they recognise. OneSpace defines
its own: **Recommended** ones generated per space from the manifest, and
**Custom** ones the workspace builds, drawn from the same allowlist.

The manifest is the single source of truth — one list drives the DocPerms we
generate, what an entitlement grants and revokes, and what a custom role may
draw from. A doctype absent from every manifest is reachable by nobody without
anyone remembering to exclude it.

**Our roles are `desk_access = 0` at creation.** Frappe derives `user_type` from
that flag on every User save, so every workspace member is a Website User by
design. Two consequences worth carrying:

* Query Report and the report builder are gone; reporting is something we build.
* Frappe's own "assignable users" filter (`user_type = "System User"`) selects
  *nobody* here, so our picker asks the question our own way: who holds a role
  we granted.

**The workspace owner is not a System Manager.** They own the workspace, not the
site — `site_config` holds the HMAC secret, and a System Manager could sign
requests as their own tenant. Everything they need is a whitelisted method run
elevated behind one role check.

### Tags, sharing, following

All three are Frappe's stores, and each was half-built until it was used.

**Tags** are `_user_tags` (a comma-joined column added on demand — being on the
row is what makes a tag filterable and pageable with no join) plus `Tag Link`
and a `Tag` master. Ours is where they appear: a Tags column in the picker, on
every card whether or not anybody added the column, and in the Meta panel as the
control. The picker offers the **workspace's whole vocabulary**, not this
doctype's: offering only tags already used here is how one word becomes three
spellings of it.

**Sharing** is `DocShare`, and the part that matters is what reads it — Frappe's
`db_query` folds shares into the permission condition of *every* `get_list`, so
a shared record becomes visible with nothing else written anywhere. Three levels
(view / edit / share) rather than four checkboxes. `share` rides with Write and
above, never with Read: Read is the level that may not give away what it was
given. A share still cannot widen a screen — `record()` re-reads through the
screen's filters.

**Following** is `Document Follow`, which Frappe uses only for a digest email.
Our own producer writes the in-app notification: `on_version` reports field
*labels*, never values, and `on_comment` excludes anybody already mentioned.

### Notifications

**The feed is Frappe's `Notification Log`, not a doctype of ours.** It is
already per-user, already permissioned, already swept at 180 days, already
emailed by preference, already deduped — and already being written by assignment
and @mention on every tenant since the day those shipped, with nowhere to see
one. Writing our own would mean re-implementing all of that in order to *stop*
receiving what we already get.

A notification's **route is derived, not stored**: `Notification Log.app` cannot
carry a Space, so OneSpace resolves the destination at read time from
`document_type` through the manifest, picking a space this reader may open. One
that cannot be resolved is still shown and simply does not link — the truthful
rendering.

**The control plane does not write into tenants; the tenant pulls.** Workspace
notices ride the sync that already runs every fifteen minutes, keyed so a
re-drain cannot duplicate. The honest cost: a billing notice can be up to
fifteen minutes late in-app. The email is immediate.

Push is a seam (`push.send`) and not a feature. It stays that way until the
EU-jurisdiction question is settled — Web Push with VAPID keys we own is the
answer when it is.

---

## 8. Printing and naming

Both are Frappe's whole stack, reached from OneSpace's settings. **We built the
surfaces, not the mechanics**: every write goes through Frappe's own
`Print Format`, `Letter Head`, `Print Settings` and `Document Naming Settings`,
and every render through `PrintFormatGenerator` and `frappe.get_print`.

A print format is not a template we render — it is a document the *framework*
renders, resolving the letter head, applying the print style, honouring the page
size and running the per-fieldtype renderers. A second renderer would be a
second set of those decisions, drifting, and drifting for an invoice means a
customer's letter head in the wrong place on the copy that went to their
auditor. So the builder writes Frappe's own `format_data` and stops — which is
also what makes a format drawn here print identically from a scheduled email.

Where it lives: **Settings → Printing** is the paper (size, font, engine,
margins); **Settings → Print formats** is what is drawn on it, plus letter
heads; **the record header → Print** is a picker and a preview.

**Naming** tells apart the two kinds Frappe's own page never distinguishes: a
`naming_series` field, whose prefixes are a business decision stored as a
Property Setter, and a doctype named by its own `autoname` like `EV.#####`,
which shows its series read-only and still moves its counter.

The full contract — the layout schema, the two gates, the fixtures a manifest
may ship — is in `PRINTING.md`. That and `WORKSPACE-SETTINGS.md` are the two
files that survived the consolidation, because they are **reference tables a
test reads** rather than explanations: one holds the `format_data` schema, the
other the field-by-field record of what was moved into workspace settings and
what stayed ours. Everything else that used to be in `docs/` is here or in
`ONEADMIN.md`.

---

## 9. AI in a workspace

The AI tab in workspace settings is **not written anywhere** — it is the feature
registry rendered. Each `@ai_feature` an app declares becomes a row; its model
picker is filtered to models matching the capability it declared.

A workspace can add to the prompt and read back what it added. It cannot read
ours: `settings.spec()` builds its rows field by field and `feature.system` is
not one of them. The model receives ours first, then theirs, because
instructions later in a system prompt qualify what came before.

A feature marked `tenant_can_disable=False` is one where AI *is* the process
rather than an assistant beside it; those keep running when a workspace turns AI
off, because the alternative is a broken workflow with no error to point at.

Credits, metering and markup are the platform's — `ONEADMIN.md` §7.

---

## 10. Workspace settings

A tenant site is a real Frappe site, so the name and logo on its sign-in page,
who may sign in, and what a date looks like all already exist — behind a desk
its owner never sees. Those are the customer's.

`oneapp_core/workspace.py` is **one object serving as both the spec the SPA
renders and the allowlist the write path checks**, so a setting is writable
exactly when it is visible and there is no code path for anything else.

| Group | Holds |
|---|---|
| Branding | Name, logo, favicon, the sign-in page |
| Sign in | Which methods, session policy, password strength, invite-only |
| Printing | Page size, font, PDF engine, margins, letter head on or off |
| Regional | Timezone, date and number format, currency, first day of week |
| Books | Company and chart of accounts, without ERPNext's wizard |
| Print formats | The format list, the builder, letter heads |
| Naming | Series and counters per doctype |
| AI | The feature registry, rendered |
| People / Roles | Members, seats, and the workspace's own role builder |

What stays ours is the platform: the scheduler, backups, file size limits (a
billed quota), guest uploads, telemetry, the mail footer and tracebacks. A
workspace that can stop its own scheduler stops its own email, backups and syncs
and cannot see why — and we get the ticket. A test fails the build if anything
on the platform's side appears in the spec.

---

## 11. The UI rules

**The frappe-ui API is read, not remembered.** Every UI defect in this project
so far was the same mistake: giving a component a prop, a slot or an option it
does not declare. Vue turns an unknown prop into a fallthrough attribute and
never renders an unknown slot. Nothing throws, nothing logs, the page loads —
and the thing is missing. Eight page headers were empty, eight lists rendered
zero rows beside a correct count, nine alerts dropped their text.

So `tests/frappe_ui_api.py` reads the declarations out of the installed package,
and the guards compare them against what we write: unknown props, unknown slots,
content with nowhere to go, missing required props, values outside a union,
unknown call options, deprecated components, a local component shadowing one,
markup pretending to be a component, and a POST to a GET-only method.

Two more the same suite holds:

* **Icon-only controls carry a tooltip** — frappe-ui's, through `Button`'s own
  prop. `label` is the *accessible* name and reaches a screen reader alone; a
  `title` attribute is not a tooltip (undelayed, unstyleable, inert on touch).
* **Colours come from semantic tokens.** `text-blue-600` is a fixed colour that
  stays a light-mode blue on a dark background.

**One radius language**, four sizes and nothing else: `rounded-4` a control,
`rounded-6` a panel, `rounded-7` a dialog (frappe-ui's own, never ours to set),
`rounded-full` a circle. An outlined block is a panel and is drawn at
`rounded-6`. Both rules exist because the drift had already happened.

**Tailwind emits CSS only for class names it can see in the source.** A class
built at runtime renders as nothing, which is why the span map, the icon set and
the theme classes are written out — and why a test asserts every class in either
SPA actually emits CSS.

**`AppShell` is the only component allowed to compose the layout primitives.**
`DesktopShell` and `MobileShell` have different slots, so something has to
choose — and a surface choosing for itself is how one account comes to look like
two products on the same tablet.

We are on frappe-ui `1.0.0-beta.55`, and npm's `latest` still points at the
`0.1.x` line. That is why v0 API shapes keep appearing in examples online. The
guards compare against the version actually installed.

---

## 12. What the generic screen does not do yet

Worth knowing before designing around it.

* **A workflow builder.** Workflows run; there is no screen for drawing one.
* **Notification rules and email templates.** The feed and the digest exist; the
  rules that would produce "email the owner when this goes overdue" do not.
* **Data import and export.** No CSV either way.
* **Customize Form.** We write Property Setters for naming and default print
  formats; there is no UI for adding a field or relabelling one.
* **User Permission.** Enforced on every path, and there is nowhere to grant
  one.
* **Bulk edit.** Selection does delete and declared actions only.
* **Calendar and map views**, which a manifest may already declare — a type
  nothing can draw is dropped rather than refused, so the screen renders as a
  list and gains the calendar without a manifest edit.
* **Free-text search across a whole doctype**, drag-to-resize a column, and
  filtering on a child table (Frappe needs a four-part filter there and a
  three-part one names a column that is not present).

Also, deliberately: **Assignment is not shown in the list.** The activity column
is a fixed 176px track already holding an age, a count and a heart. If
assignment should be readable in a list the honest answer is a column of its
own, filterable like any other.
