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
view_types    list,board,grid     how it may be looked at; the first is default
view_settings {"board": {...}}    per type, what it needs beyond columns/filters
status_field  status              where a record stands — the badge, and the
                                  board's columns
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

  **A list follows the site, and a record says who else is in it.** Frappe
  publishes `list_update` for every document that changes, so a list left open
  on a second screen stops being a photograph of when it was opened — coalesced,
  because a bulk import publishes hundreds of those a second. A record joins
  Frappe's own two rooms: the one that carries the document's events, and the
  open-document room that says who has it open, which is what the row of faces
  in the header is. When somebody else saves it, the pane says so rather than
  doing anything about it — the reader may be halfway through typing, and
  replacing what is on screen with what is on the server is the one thing worse
  than being out of date.

  **The form is the doctype's form.** Frappe's three layout fields — Tab
  Break, Section Break, Column Break — are read the way the desk reads them, so
  a doctype whose author grouped its fields is grouped the same way here.
  Columns collapse below the breakpoint, because a two-column form in 360px is
  two columns of hyphens.

  **And the doctype's own rules apply as you type.** `depends_on`,
  `mandatory_depends_on` and `read_only_depends_on` decide whether a field is
  shown, required, or editable, against the record as it stands rather than as
  it was saved. The desk runs those strings as JavaScript; this does not, and
  the reason is where the string comes from — a row in a database, editable by
  anyone who can write a Property Setter, and `new Function` on one would turn
  "can customise a form" into "can run code in every reader's browser". So the
  expression is parsed by a small grammar covering what these rules actually
  say, and anything outside it is treated as no rule rather than guessed at.
  The server validates `reqd` and `mandatory_depends_on` again on save, so a
  form that is wrong here produces a worse error message rather than a worse
  record.

  **Two permission questions, not one.** Frappe protects a field by level
  twice: which levels you may read, and which you may write. A field above the
  read levels is not offered anywhere; a field above the write levels is shown
  and never editable — it used to render as a control that looked editable and
  was dropped on save, which is the answer that looks like it worked.

  **A record is a pane beside the list, and a page on a phone.** It was a
  modal dialog, and a dialog is the wrong shape for it: a record is something
  you read *against* the list — mark this one done, glance at the next, come
  back — and a modal takes the list away and the page out of the accessibility
  tree with it. The pane's width is dragged and remembered in the browser,
  because how wide somebody likes it is a property of the screen they are
  sitting at rather than of their account. On a phone there is no room to keep
  both, so the pane draws itself as a page; the screen host does not know which
  it is.

  **The record carries what surrounds it**, in the shape Frappe CRM uses: the
  doctype's own image where it declares an `image_field`, replaced in place
  rather than as a file box halfway down the form; who made it and when it last
  changed, at the foot of the details, because that is what you look for second;
  and the files, which are Frappe's own File rows — so a file uploaded through
  an Attach field and a file dropped on the record are one list rather than two.
  Uploading attaches in the same request, because Frappe's upload endpoint takes
  the doctype and the name.

  Not emails. CRM's record has a tab for them because CRM has an inbox; a space
  has none, and a tab that cannot be filled is worse than one that is not there.

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

## One table, two surfaces

`RecordTable` draws both the screen's list and the grid inside a record. It
owns the tracks, the sticky header, the pinned columns, the one scroller that
handles both axes, the edge that says there is more, and the windowing past a
few hundred rows.

It does not own what a cell contains, what a row click means, where the rows
came from, or whether they can be sorted. Those differ completely between the
two and are the consumer's, through a `#cell` slot and a handful of props.

It exists because they used to differ about the chrome too. All of it was
written in the list and none of it in the grid, so the grid had no widths, no
pinning and no sticky header — and the one piece it did copy, the row inset, it
copied wrongly along with ten other tables. One table means one place to be
wrong, and two guards keep it that way: the scroller may exist in one file, and
both bodies must go through it.

Two things fall out of it that are worth naming:

* **The row inset is derived, not passed.** `list-row-px-3` is right for a
  selectable table and wrong for a static one; the table asks its own
  `selectable` prop and picks. There is nothing left for a caller to get wrong.
* **The child grid is selectable.** `ListRowBase` treats a row as interactive
  when it is a link, a button, or in a selectable list — and only the first two
  change its tag, so a selectable grid row stays a `div` and can still hold
  form controls. That means frappe-ui draws the tick boxes and the select-all,
  and the grid's own checkbox column is gone.

## A child table is a grid, not a second list

A doctype with rows inside it renders them as a grid on the record: the child
doctype's own `in_list_view` fields as columns, edited in place, with the whole
row available in a dialog for the child doctypes that carry twenty fields.

`in_list_view` rather than a picker is the whole design. Frappe CRM ships a
column editor per grid and stores what it chose as client-side state; the
child doctype has already answered that question, once, for every screen that
ever shows it. A manifest repeating it would be a second answer to drift from.

What the grid does beyond drawing rows:

* **Tick rows and remove them together.** By position, not by key — a saved
  child row has a `name` and a new one does not, which is how Frappe tells an
  update from an insert, so half the rows in an edited table have nothing to
  key a selection on. Every operation that moves a row therefore clears the
  selection: a selection held by position through a reorder is a selection of
  different rows.
* **Drag to reorder**, with `idx` rewritten to match. Frappe orders a child
  table by that column and renumbers on save, but the record in the browser is
  what the form reads back — leaving the old numbers would show one order and
  save another. The handle is the row number itself: the number *is* the
  position, so the thing you drag to change it is the thing that says what it
  is.
* **Numbers against the right edge.** Which cells are numbers is
  `NUMERIC_CELLS`, generated from the same fieldtype map that decides how a
  value is drawn — so a Currency and an Int are one question, and a fieldtype
  added to the map lands in a bucket without a second list to remember.
* **A required column says so in its header.** A grid cell has no room for a
  label, so without the marker the only warning that a column may not be left
  blank is the save failing.

None of it is declared anywhere. A doctype with a child table gets all of it.

## The shell: a rail, a sidebar you can shut, and one header

The desktop shell is frappe-ui's `DesktopShell`: a rail of spaces, a sidebar,
and the page. One shell rather than two — the phone switches to `MobileShell`
inside the same component — because Frappe CRM ships a desktop layout and a
mobile layout as separate component trees and the mobile one has already
drifted behind its sibling.

**The sidebar collapses**, and remembers it in this browser. On a laptop
running a data grid, a fixed 224px of chrome sits between the reader and their
columns; `SidebarItem` already knows how to shrink to its icon, so what was
missing was the state and a toggle. It also **resizes**, through the same
`Resizer` the record pane uses — which is the whole reason that component was
pulled out of the pane.

**The header is teleported, and always was.** `DesktopShell` renders a
`PageHeaderTarget` above the scroll region and a page fills it with
`<PageHeader>`; the screen's breadcrumb line has been going through it since
the pane work. There is no header prop threaded through three components to
remove.

## One timeline, and every entry says what it is

A record has three tabs: Details, Activity, Files. Activity is what was said
about it, what changed on it, and when it started — in one column, newest
first, narrowed by a filter rather than navigated to by a tab.

It was two tabs. That meant "who changed this" and "what did they say about it"
were separate places, and answering "what happened on Tuesday" was reading both
and merging them by eye. The only thing that made them separate was that they
come back from two queries; they are merged in the browser, because merging
them on the server would mean paging them together and that is a much larger
change than putting them in one column.

Every entry carries a glyph from a closed set — `ACTIVITY_ICONS`, generated
like the other three — because a column of identical avatars makes a comment
and a field change look like the same event. A test fails on a fourth kind of
entry added without one: `activityIcon` never returns nothing, and a fallback
dot nobody notices is exactly how that would go unseen.

Two smaller things the merge exposed:

* **The record's creation is an entry.** No log holds it — a Version records a
  change and there was nothing before the first one — so it is built from the
  record's own `owner` and `creation`. Without it the oldest thing on a
  timeline is whatever somebody happened to do next.
* **A change to a markup field reads as words.** A Version keeps what was
  stored, so a Text Editor's history was a line of `<p>` tags. Stripped on the
  way out, and only for the fieldtypes that are markup: a Data field holding
  `a < b` holds `a < b`, and running every value through an HTML stripper to
  tidy one fieldtype turns that into `a `.

## Assignment is a thing you do to a record

Frappe's own model, unchanged: `_assign` is a list of user ids on the document,
and `frappe.desk.form.assign_to` keeps a ToDo beside each one so the record
turns up in that person's own list rather than only on their avatar. Both
halves matter, so the framework's functions do the writing and OneSpace only
decides who may ask.

It is not a field. It is not on the doctype, it is not in the form, there is no
column for it — so it sits with the other things you do to a record: a stack of
faces in the record's header, beside the actions and the heart. Read permission
is enough to assign, deliberately: assigning is how work reaches somebody, and
a reader who can see a record and cannot ask a colleague to look at it sends an
email instead. Frappe draws the same line.

The picker offers everybody who can sign in to this workspace — enabled System
Users, which is what the desk's own dialog filters to — bounded by the screen
like every other read, so a guessed space code is not a directory. The set is
sent whole and the difference worked out on the server, and what comes back is
what the document ended up holding rather than what was asked for.

## The board is the same list, drawn as columns

A screen that names a field a board could be made of may offer `board`. It is
the same rows — the same filters, the same order, the same page — placed in the
column that field names.

**Which field is the reader's.** A screen declares the one a board *opens* on:
its `status_field`, or another named in its own `view_settings`. From there
"show me this by assignee instead" is the same kind of question as "sort by this
column", and it is answered the same way — changed in the board's settings,
kept in a saved view, narrowing what the screen offers rather than widening it.
So is what a card says.

Three answers, narrowest last: the screen's status field, the manifest's
`view_settings`, the reader's saved view.

**Two kinds of field make columns, and they make them differently:**

* A **Select** becomes its own options, in the doctype's own order — or
  alphabetically where the DocField says `sort_options`, because that is
  exactly this question and the answer should not differ between two surfaces.
  Every option gets a column whether or not anything is in it, because an empty
  column is where you drop something.
* A **Link** becomes the values actually on the page, drawn as records — a face
  and a name, the same rendering a link cell uses. Not every row of the target
  doctype: a board by assignee in a workspace of four hundred people is four
  hundred columns and 397 of them are empty.

Nothing else. A Date wants a calendar, a Currency wants a chart, and a board of
two hundred one-card columns is not a board. `_view_settings` checks the name is
a column the screen offers; `_board` checks a board can be *made* of it, which
is a question about the fieldtype, and falls back to the status field when it
cannot.

The rest is not configured, and that is deliberate:

* **The colour and the glyph are the doctype's Document States**, the same ones
  the list cell and the record's badge read. A status is one colour everywhere
  or it is not a status.
* **The card is `RecordCard`**, the component the hover card over a link uses —
  a face, a title, the id beneath, then the fields. Which fields is the
  reader's: what they chose, or the columns they have on the list minus the
  title and the field the column itself is. Blank fields are left off, and a
  card carries six at most — past that it is a record rendered badly, and the
  person who wants the seventh wants the record. The mapping from a row to
  what is on its card is `lib/cards.js`, shared with the grid — see below.
* **A value the field no longer offers still gets a column.** A card that
  vanishes because somebody edited the doctype is worse than an extra column.

Moving a card writes one field, through the same `save` a form uses — so
permissions, `read_only`, workflows and `fetch_from` all apply exactly as they
would in the record. The list is re-read afterwards rather than trusted: the
save may have changed more than was sent.

Two rules are enforced rather than documented. A screen that names no field to
column by is not offered a board at all — `spaceview._has_column_field` and
`lib/viewTypes.js` are the same rule, and a test fails when the two disagree —
and the column field is fetched with every row whether or not it is one of the
columns the reader is looking at, the same way a Dynamic Link's companion is.

The board redraws when the rows fetched for it arrive, not when the setting
changes: the rows come back with the board they were fetched for, the same way
they come back with the grouping. Otherwise a board drawn from the old field
while rows arrive for the new one is a board of empty columns.

A phone shows the board and cannot drag on it: HTML5 drag and drop is a pointer
gesture. A status changes there by opening the record, like every other field.

## The grid is the same cards, not bucketed

A board and a grid are one card twice. A board buckets its cards by a field and
lets you drag one from bucket to bucket; the `grid` type lays the same cards out
flat, in the order the list is sorted by, as many across as fit. That is the
whole difference — so `lib/cards.js` owns what a card *says* (the identity, the
fields, that a blank one is left off, the cap) and the two bodies are the two
ways of putting those on a page. `spaceview._cards` is the server's half.
`tests/test_frontend_guards.py::test_a_card_is_mapped_in_one_place` fails if
either body starts answering the question itself.

Which is also why a grid is not "a board with one column". A board answers
"where does each of these stand"; a grid answers "show me these as things
rather than as lines" — a screen of records with pictures, or one whose fields
are too few to be worth a table. Grouping a grid would make it a board, so it
does not group.

Three consequences worth naming:

* **A grid needs no field**, so it is offered wherever a screen declares it —
  unlike the board, which is nothing without something to column by.
* **Each card-shaped type keeps its own `card_fields`.** A board card sits under
  a heading naming the field it is bucketed by, so it leaves that field off; a
  grid card has no such heading and often wants it.
* **A chosen card field is fetched** whether or not it is a column anybody is
  looking at, the same way the board's column field and a Dynamic Link's
  companion are. Without that the card silently drops the field in exactly the
  case somebody went to the trouble of choosing one.

The gear in the footer opens one dialog for both: **Card settings** over a grid,
**Board settings** over a board, where the extra question — which field the
buckets are — appears. Over a list it is still the column picker, because width
and pinning are questions about a table.

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

* **Three view types.** A screen may declare `list,board,calendar,grid,map`; the
  list, the board and the grid are built, and a type nothing can draw is dropped
  rather than refused — so a screen declaring a calendar renders as a list today
  and gains the calendar without a manifest edit. See ADR-15 for why per-type row
  shaping is not written ahead of the view that needs it.
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
