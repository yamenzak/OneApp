# Building a space

A space is configuration before it is code.

It declares which doctypes it grants and which screens it puts in front of a
customer. OneSpace renders those screens from the *tenant site's own metadata* —
what each field is called, what a Select offers, whether this user may write it —
so most spaces need no frontend code at all, and a new one is a registration plus
its doctypes with no OneSpace release.

The escape hatch is there for the rest.

---

## What a space is made of

| | Where | What it does |
|---|---|---|
| Registration | `OneSpace Space` in OneAdmin | Name, icon, availability, and the role that gates it |
| Manifest | `OneSpace Space Doctype` | Which doctypes the role may touch, and how much |
| Screens | `OneSpace Space Screen` | What the customer sees |
| AI features | `@ai_feature` in app code | See `docs/AI.md` |

Availability is the lever: **General** reaches every workspace, **Restricted**
only those granted it individually on their own page. A space with no screens is
an entitlement with no interface — a real thing to be, since it still grants its
roles and doctypes to whatever else is using them.

## A screen

```
screen        invoices            slug in the URL; a bookmark points at it
label         Invoices            the space's navigation
icon          lucide-receipt
document_type Sales Invoice       what the list shows
fields        customer,status,grand_total
filters       {"status": "Open"}  always applied
order_by      modified desc
view_types    list,board          how it may be looked at; the first is default
view_settings {"board": {...}}    what a type needs beyond columns and filters
component                         escape hatch — see below
```

Only `fields` is worth writing down about the columns, and it is **a default
rather than a ceiling**: it decides which columns a screen opens with, and the
column picker offers every field the doctype has. Someone who wants the due date
on their list gets it without a deploy. Labels, types, Select options and
required-ness come from the tenant site, so a relabelled field is relabelled on
every workspace without a sync. A field the manifest names and a site does not
have is skipped rather than fatal — one manifest serves sites on different
versions. Naming none at all falls back to the doctype's own list fields.

Screens are edited in OneAdmin under **Settings → Space screens**. Their order
there is the order of the space's navigation, in the sidebar and in the phone's
bottom bar alike.

A screen in the sidebar **expands** when there is more than one way to open it:
the view types it declares, then the named views somebody saved on it, under a
"Views" heading. Two groups rather than one run of items, because they answer
different questions — "as a board or as a list" and "which slice of it" — and
picking a view leaves the view type exactly where it was. A screen with one
view type and no saved views has nothing to expand, and gets no chevron.

The sidebar asks for a space's layouts once (`spaceview.space_layouts`) rather
than fetching a spec per screen to draw a menu. On a phone there is no sidebar,
and the same views are in the switcher in the breadcrumb line.

## Two rules make a screen safe to hand a customer

**A screen is an allowlist, twice over.** It can only be reached through a space
the workspace is entitled to, and can only name a doctype that space's manifest
already granted — checked against the DocPerms actually written, not against the
manifest as sent. A screen pointing outside its space is refused rather than left to
come back as an empty list, which reads like there is no data.

**A write is bounded by the doctype the space granted, not by the manifest's field
list.** Reads and writes go through the view rather than a generic document API,
so a screen cannot reach a doctype outside its app's grant. Within that doctype
the bound is Frappe's own: `has_permission(write)` decides, `read_only` fields
are not editable, a field above this user's permlevel is never offered, and
Frappe's bookkeeping never is. The manifest's `fields` used to narrow this too;
it no longer does, because the record now shows the whole doctype and a control
that looks editable and is silently discarded is worse than one that is absent.

Both are exercised against a real site, and the logic behind them is pinned in
`tests/test_screens.py`.

## When a list is not enough

Register a component under `spaceCode/view` in
`spaces/oneapp/frontend/src/spaces/index.js`:

```js
export const APP_COMPONENTS = {
  'crm/pipeline': () => import('./crm/Pipeline.vue'),
}
```

Set `component` on the view to `crm/pipeline` and everything else on it is
ignored: the component receives `spaceCode` and `view` as props, and the rest of
the screen is the space's business rather than ours. Lazy, so a space nobody opened
costs nothing to load. Keyed by app so two spaces can each have an `overview`.

Use it for a dashboard, a wizard, a calendar — anything a list of records and one
of those records open cannot be. Reach for it second: the generic path already
handles most of what a space is, and every screen written by hand is a screen that
has to be maintained by hand.

## What a screen carries without being asked

None of this is written into a manifest. It comes off the doctype the screen
already names, so a space gets it by existing.

* **Every fieldtype has a control.** The map is generated from Frappe's own
  `data_fieldtypes` (`scripts/field_types.py`), so a fieldtype Frappe adds fails
  a test here rather than rendering as a text box that writes a string into a
  Currency column. Colour, signature, geolocation, barcode and icon have no
  frappe-ui counterpart: they are shown, never offered.
* **A link is a record, everywhere.** The same three things a row's title
  column shows — a face, a name, and the id beneath it where the name is not
  already the id — render in a list cell and in the picker's menu, because a
  link *is* a record and reading one and choosing one should not look like two
  different things. The list resolves a page's ids in one query per column, so
  the cells cost nothing extra; a target this person may not read falls back to
  the id, which is the truthful thing to show.

  The picker searches on the server (`spaceview.link_options`), bounded by the
  screen the same way its rows are, matching the id, the title and the
  doctype's own `search_fields`, and honouring the field's `link_filters`.
  Client-side filtering is off deliberately: the server already decided what
  matched, and a second literal substring pass drops rows a person can see are
  right.

  **Create is in the menu** where the target doctype is one the space granted
  and this user may create — Frappe's own quick entry, which is the fields the
  doctype marks `allow_in_quick_entry` plus anything mandatory. What was typed
  into the search becomes the new record's name, and the record is adopted as
  the value, because choosing it was the point. Elsewhere there is simply no
  Create row. A filter never offers one: nobody makes a record in order to
  filter by it.
* **Field icons.** One per fieldtype, in the list header and beside the record.
* **Badge colours.** From the doctype's own `DocType State` rows where it
  declares them, and otherwise from Frappe's word lists — so "Open" is the same
  colour here as in the desk.
* **Title, image and naming.** `title_field` names the record, `image_field`
  gives it an avatar, and the naming rule is reported so a screen knows whether
  a new record names itself.
* **Comments, history and likes.** Frappe keeps all three on every doctype.
  History is rendered in the screen's own labels, not the database's field
  names, and only for fields the screen shows.
* **A title column.** The doctype's `image_field` as an avatar (falling back to
  initials from the id), its `title_field` as the name, and the id underneath in
  subtle text. Always the first column, because a row needs a name before it
  needs anything else.
* **A row's age, its comments and a heart**, at the end of every list. All three
  come off the document — the count is parsed from `_comments`, which itself
  never leaves the server — so they cost no extra query. The heart in the
  toolbar filters to what this person liked.
* **Sortable headers.** Clicking one sorts by that column and shows the
  direction beside its name; clicking again reverses it.
* **A trail that says where you are.** A house for the space, the screen, and
  then the thing you are looking at — the view, or the record when one is
  open. Frappe CRM's shape, and its argument: the rail already names the
  space, so the house carries it as a tooltip and the line spends its width on
  what changes. The house goes to the space's first screen until a space home
  is a page of its own.

  The last crumb is the **view switcher**: the view type when nothing is
  saved, the layout's name when one is open, and a menu of every view of that
  screen either way.

  A record takes the last place from the view, and reads the way a record
  reads everywhere else — a face, a name, and the id beside it where the name
  is not already the id. It is in the URL (`?record=…`), so it is a link
  somebody can send and a place a reload comes back to; opening it fetches the
  record rather than reading the list row, which is what makes a field nobody
  put on the list show its value on the form.
* **An icon says what it does.** Every control that renders as a picture and
  nothing else carries a tooltip — frappe-ui's, through `Button`'s own
  `tooltip` prop, which builds one internally. `label` is the *accessible*
  name and reaches a screen reader alone; the gear beside a list is one click
  from changing what the list shows, and sighted people were left guessing.
  `tests/test_frontend_guards.py` fails the build on an icon-only button with
  no tooltip, and on any other kind of tooltip: a `title` attribute is not one
  (undelayed, unstyleable, and inert on a touch screen), and neither is a
  hand-rolled hover card. A button that is only *sometimes* an icon is exempt,
  because it shows its label wherever there is a pointer to hover with.
* **Columns are one model.** Which, in what order, how wide, and whether one
  stays put while the rest scroll — all chosen in the picker and remembered.
  Nothing is pinned by default. The title field renders with its avatar and id
  wherever it sits, and activity (`__activity`) is a column like any other, so
  a person who does not want a row's age and comment count can drop it.
* **Selection.** Checkboxes on every row and a select-all in the header, with a
  bar for what to do with a selection. The title opens a record, because
  frappe-ui's List hands the row click to the checkbox — which is how Frappe's
  own list behaves too.
* **Grouping.** By any column, chosen in the picker. Rows are sorted by the
  group first, so a group arrives whole rather than as the same heading three
  times.
* **A quick filter box per field**, above the list. Which fields get one is
  Frappe's own answer — `in_standard_filter` plus the title field — so no
  manifest repeats it, and every list gets an ID box. Each typed box carries
  Frappe's `=` / `≈` toggle for exact against contains.
* **Filters, in Frappe's own vocabulary.** A filter is
  `[fieldname, operator, value]`, and which operators a field offers comes from
  Frappe's own per-fieldtype table: a Select gets Equals / Not Equals / In /
  Not In / Is, a Date also gets Between, Timespan and the comparisons under
  Frappe's names for them ("On or Before" rather than "<="). The value control
  follows the pair — a link picker, a choice, a list, two dates, Frappe's
  relative-date words, or Set / Not Set.
* **Saved views, as named layouts.** Everything the controls can change travels
  together under a name in `OneSpace Saved View` — there is no half of it that is
  remembered and half that is not:

  | | |
  | --- | --- |
  | which columns, and in what order | `columns` |
  | how wide each one is | `columns[].width` |
  | which edge a column is pinned to, if any | `columns[].pin` |
  | which column the rows are grouped under | `group_by` |
  | every filter, from the quick boxes and the panel alike | `filters` |
  | the sort field and its direction | `order_by` |
  | how big a page is | `page_length` |
  | whether it is filtered to what you liked | `favourites` |
  | its name, and whose it is | `label`, `user` | This follows the shape of Frappe's own `List Filter`
  doctype: a layout belongs to one person, or — with its user left empty — to
  the whole workspace. Which one is open is in the URL, so a view is a link
  somebody can send. The Save button still writes the person's own unnamed
  default, which is what "keep this how I left it" means.

  **A view carries an icon**, chosen when it is named or renamed — a menu of
  five names is a list to read, and a menu of five icons is a list to
  recognise. Two kinds, and the reason for both is the build: one of a curated
  lucide set (Tailwind only emits CSS for class names it saw in the source, so
  a name chosen at runtime renders as nothing), or **any emoji**, which is
  text and so needs no build step at all. Frappe CRM tolerates an emoji here
  for legacy reasons; for us it is the more capable of the two. The server
  checks the same two rules, because the value reaches the DOM as a class
  name.

  **A record is a pane beside the list, and a page on a phone.** It was a
  modal dialog, and a dialog is the wrong shape for it: a record is something
  you read *against* the list — mark this one done, glance at the next, come
  back — and a modal takes the list away and the page out of the accessibility
  tree with it. The pane's width is dragged and remembered in the browser,
  because how wide somebody likes it is a property of the screen they are
  sitting at rather than of their account. On a phone there is no room to keep
  both, so the pane draws itself as a page; the screen host does not know which
  it is.

  **Making a record is still a dialog**, which is the one place a modal is the
  right answer: nothing behind it to refer to yet, a short decision, and
  cancelling leaves nothing behind. It posts only what was typed into it —
  Frappe's defaults are words like `Today` and `__user` that only the server
  can turn into values, so a form that posts them back writes the word.

  **An open record is the last thing in the trail**, and it reads the way a
  record reads everywhere else: one face, the name, the id beneath it. Beside
  the name is the status — "where does this stand" is the second thing anybody
  asks about a record. Which field that is comes from the manifest's
  `status_field`; the colours do not, because the doctype already declares them
  as Document States and the list cell already reads those. A screen that names
  no status field gets no badge rather than an empty one.

  **The switcher is where a view is managed**, and the only place. Each view
  in it opens a submenu of its own: open it, put the unsaved change on screen
  into it, rename it, share it, make it what the screen opens with, delete it.
  Before this the menu managed only the view you were already in, so renaming
  any other one meant opening it first — and putting a change into a view you
  were not looking at was not offered at all.

  **A shared view you would rather not see can be hidden**, per person. Not
  deleted: a shared view belongs to the workspace and somebody else may be
  living in it, so hiding writes a row of your own rather than touching theirs.
  Your own views are not hideable — you made them, and deleting is what you
  want. They come back all at once, because a hidden view is not in the menu
  and a menu is the wrong place to pick one out of.

  **Where an unsaved change goes depends on where you are.** In a named view
  you may write, Save writes into that view; anywhere else it writes this
  person's own unnamed default for the screen. CRM draws the same line, and
  the alternative is worse in both directions — a Save that silently makes a
  private copy of a shared view, or one that quietly rewrites a view other
  people are using. Discard puts back whichever of the two you were looking
  at.

  A layout narrows what the screen offers and can never widen it, shared or not
  — see ADR-13 — and every filter in one is re-checked against the screen on
  the way out, not only when it was saved. The same bounds apply to an unsaved
  change, which is why the controls can show their answer before anything is
  saved.

  Only a workspace admin writes a shared layout (`OneSpace Workspace Owner`, or
  support arriving as a System Manager) — the same shape as Frappe's
  `_can_edit_global_filter`, with our own role in it. Nobody edits anybody
  else's private layout, admin or not.
* **The same columns at every width.** A view means one thing on a phone and on
  a desktop; the table scrolls sideways rather than being narrowed to a
  different set of columns. That is only safe because the columns are the
  reader's own choice — Frappe CRM draws the same conclusion.

## The list is a data grid, not a long page

The screen is a **pane**: the route marks itself `meta: { pane: true }`, the
shell turns its own page scrolling off, and the list fills what is left. One
element inside it scrolls in both directions, with the column header sticky at
its top.

That shape is the answer to a question worth stating, because the obvious
layout gets it wrong: **where does the horizontal scrollbar go?** On a page that
scrolls, a wide table puts its scrollbar at the bottom of the *table* — so on
two hundred rows you have to scroll down past everything to discover you could
have scrolled sideways. Fixing the pane's height puts that scrollbar at the
bottom of the window, where it is always visible.

One scroller rather than two nested ones, and that is not a detail: a separate
horizontal wrapper around a vertical one leaves the header outside the vertical
scrollbar's gutter, so the header sits a scrollbar's width out of true with the
rows beneath it. Sharing one container gives them nothing to disagree about.
`tests/test_frontend_guards.py` fails the build on the two-wrapper shape.

Three more things carry the idea:

* **An edge tells you there is more.** The side with content beyond it gets a
  soft wash, and loses it at the end. A `ResizeObserver` drives it rather than a
  render hook — the first version measured before layout, so a table that opened
  too wide said nothing until something else made it scroll.
* **Pinned columns** stay put while the rest scrolls, so the row's identity is
  still there when you are eight columns to the right. Which columns pin is the
  reader's choice, saved with the view.
* **The footer** is Frappe CRM's: a page size (20 / 50 / 100 / 500, remembered
  in the view), a Load more that appends, and "48 of 1,240" where the total is
  what matches rather than what was sent.

  The count is **its own request**, made after the rows and never awaited with
  them. A `COUNT(*)` over a filter with no index behind it is a full scan, and
  folding it into the page would put that scan in front of every list anybody
  opens; the footer reads "48" for a moment instead. It goes through `get_list`
  rather than `db.count` so it sees the same permissions and User Permissions
  the rows did — a count larger than the list it labels is worse than no count.

Rows are **windowed past two hundred** (frappe-ui's `ListRows virtual`), which
is where Load more starts to make a page you can feel. Below that the plain
path is simpler and behaves better with a keyboard.

## One radius language

frappe-ui's own components draw four corner sizes and mean something different
by each, so these SPAs use the same four and nothing else:

| Token | | Where |
| --- | --- | --- |
| `rounded-4` | 8px | a control — the size Button md and every input draw |
| `rounded-6` | 12px | a panel — a card, a dialog's inset block, a floating bar |
| `rounded-7` | 16px | a dialog, which is frappe-ui's own and never ours to set |
| `rounded-full` | | a circle — an avatar, a colour swatch, a count |

`rounded-s-none` / `rounded-e-none` join a box to the button welded to it, so an
input group reads as one control rather than two that happen to touch.

Two rules in `tests/test_design_tokens.py` hold it: no radius outside that list
may appear anywhere in either SPA, and an outlined block — anything carrying
`border border-outline-*` — is a panel and is drawn at `rounded-6`. Both were
written because the drift had already happened: cards on the account pages at
8px sat beside cards on the launcher at 12px, and a grey band behind a list
header ran into a square corner.

## Every DocField flag, and what we do with it

A DocField carries more than a type and a label, and each of these is set once
on the doctype and honoured on every screen pointing at it — nothing below is
ever written into a manifest.

| Flag | What OneSpace does with it |
| --- | --- |
| `label`, `fieldtype`, `options`, `description`, `placeholder`, `precision`, `non_negative`, `default` | The control and how it reads |
| `reqd`, `read_only`, `permlevel` | Whether it is offered, and to whom |
| `in_list_view` | Which columns a screen opens with, when the manifest names none |
| `in_standard_filter` | Which fields get a quick-filter box |
| `link_filters` | What the link picker may offer |
| `in_preview` | The card on hover over a link to this doctype |
| `allow_in_quick_entry` | What creating one from a link picker asks for |
| `bold` | The cell is drawn heavier |
| `columns` | Where the column's width starts — Frappe's grid units, 96px each |
| `hide_days`, `hide_seconds` | Which parts of a Duration are worth reading |
| `set_only_once` | Editable on a new record, read-only afterwards |
| `fetch_from` | Said under the box: "From Customer", so a field that fills itself explains why |
| `title_field`, `image_field`, `search_fields` | How a record is named, faced and told apart — in the title column, in a link cell and in the picker alike |
| `states` | Badge colours, the same ones the desk draws |

Deliberately not honoured, and worth saying why:

* **`depends_on` and its siblings.** They are JavaScript, evaluated against the
  document. Running them means an expression evaluator in the SPA, and a
  half-implemented one hides a field that should be visible — which is worse
  than showing one that could have been hidden. The server still enforces
  `mandatory_depends_on` on save, so nothing is written that Frappe would
  refuse.
* **`in_global_search`, `search_index`, `unique`, `no_copy`, `print_hide`.**
  Each is about something a screen does not do yet: search across doctypes,
  index tuning, duplication, printing. Frappe enforces `unique` on save
  regardless.
* **`translatable`.** Labels come through `_()` already; translating stored
  *values* is a data question rather than a rendering one.
* **`is_virtual`.** Frappe computes it; a screen reads it like any other field.

## The record form is the whole form

Frappe's desk opens a Quick Entry dialog for a new record and asks for
`allow_in_quick_entry` fields alone, with a link out to the full form. OneSpace
shows the whole form for a new record and uses the quick-entry set only where
space is genuinely tight — creating a record from inside a link picker, without
leaving the form you were already filling in.

That is a deliberate difference. A dialog that asks for four fields and hides
eleven leaves people to discover the rest later, and the desk's answer to that
is a second screen to navigate to. One form has neither problem.

## What the generic screen does not do yet

Worth knowing before designing around it:

* **One view type.** A screen may declare `list,board,calendar`; only the list
  is built, and a type nothing can draw is dropped rather than refused — so the
  screen renders as a list today and gains the rest without a manifest edit.
  Rows are shaped for a list and only for a list; see ADR-15 for why the
  shaping is not written ahead of the view that needs it.
* **No child tables.** A doctype with rows inside it shows its top-level fields
  only.
* **No free-text search across the whole set.** Filters, the quick boxes and
  sort narrow a list; there is no "search everything" box.
* **A child table cannot be filtered.** It is rows rather than a value, so
  Frappe needs a four-part filter naming the child doctype and a three-part one
  names a column that is not there. Shown, never filtered.
* **Drag to resize a column.** The width box is in the picker; dragging the
  border is not built. frappe-ui's List takes fixed grid tracks and ships no
  resize of its own.

None of these block a first app; all of them are worth knowing about before
designing one around a list of five thousand invoices.
