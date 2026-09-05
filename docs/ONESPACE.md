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

### A space's own look

Every space is drawn with the same components, and that is the right default: a
person who learns one has learned the rest. But a space is somebody's
*application* — a contractor's job book, a clinic's day, an operator's console —
and eleven of them in one unchanging grey read as one program with a dropdown at
the top rather than as the eleven things they are.

So a space may declare a **theme**, on its registration, in four words:

```json
{"mode": "dark", "accent": "#e50914", "ground": "#0d0d0f", "radius": "sharp"}
```

| | What it moves |
|---|---|
| `mode` | `light` or `dark`, for the whole app while this space is open |
| `accent` | The solid buttons, the tab indicator, the progress fill, the links — and the ink that goes on them |
| `ground` | The page, the rail and sidebar, the surfaces that step up from it, and the hairlines |
| `radius` | `sharp` or `soft` — the corner scale, not the components |

Two of those do a little more than they look like they do, and both are there
because the first version did not.

**An accent brings its own ink.** frappe-ui puts `--ink-base` on every solid
button, and in dark mode that is a near-black — right under a deep red, and an
unreadable label on Caterpillar yellow. So the browser decides it from the
accent's own luminance rather than a space declaring it: bright takes near-black,
dark takes white. It is the only ink a theme moves, and it is allowed because it
is the ink *on* a colour the space chose rather than text on a page.

**A ground owns its hairlines.** frappe-ui's `--outline-gray-1` to `-3` are a
fixed step off *its* dark grey. A space declaring a much darker ground got them
at full strength against a page they were never measured on, which is a screen
ruled into boxes when it should read as one surface. They are derived from the
ground now, and *away* from it — lighter on a dark ground, darker on a light one,
because a border lifted toward white is a border that vanishes in light mode.

Four, and no more, on purpose. The alternative — a manifest that may set any CSS
variable — is a stylesheet in a database, and the first space to reach for one
would put its own text colour on our own surface colour and ship a screen nobody
can read. These are *intents*: `lib/theme.js` owns which variables each one
moves, so the mapping is corrected in one place when frappe-ui renames a token,
and the neutral scale that carries every row hover and hairline in the product
is deliberately not on the list.

A theme is checked where the session is built (`oneapp_core/theming.py`), field
by field — a good accent and a bad radius keeps the accent — so a hex with a typo
renders the default look rather than a broken one, and the space arrives already
themed with no light frame flashing before it. It is put on `<html>` rather than
on the screen's container, which is the only place that reaches a dropdown or a
dialog teleported to `document.body`. Leaving the space puts the document back
as it was found, the reader's own light-or-dark preference included: a theme
overrules it for as long as it is on screen and never overwrites it.

What a theme **cannot** do is redesign a component. The rail and the sidebar
follow it — their surface is the ground's own step, the active item is an
elevation, the corners are the radius scale — so a themed space's navigation
looks like that space. Where the rail sits, how tall an item is and what is in
it are the shell's, and changing those changes them for everybody. The line is
between a component's *palette*, which a space owns, and its *shape*, which the
product does.

RUA's is the worked example — see `docs/RUA.md`.

### A screen

```
screen        invoices            slug in the URL; a bookmark points at it
label         Invoices            the space's navigation
icon          lucide-receipt
document_type Sales Invoice       what the list shows
fields        customer,status,grand_total
filters       {"status": "Open"}  always applied
order_by      modified desc
view_types    list,report,board,grid,dashboard,calendar,gantt,tree   the first is the default
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
  each with Frappe's `=` / `≈` toggle once there is something in it. The row
  measures itself and draws what fits at a readable width; the rest are one
  chevron away, because what decides whether five boxes fit is the pane, not
  the viewport, and opening a record halves it.
* **Sortable headers**, an ID box on every list, a row's age, its comment count
  and a heart. A face on the title only where the doctype declares an image
  field: initials off the title are fifty-nine identical grey B's down a screen
  of "Backlog item 01".
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

## 5. The bodies

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

A column carries four answers, all the reader's and all saved with the view:
where it sits, which edge it sticks to, **which edge its values sit against**,
and how wide. Alignment is logical — `start` and `end`, never left and right —
because this product draws Arabic beside English in one list, and a column
aligned "left" in a right-to-left screen is aligned to the wrong side of the
words in it. The default is a fourth value rather than a fifth option: *the
fieldtype decides*, which is a number against the end and everything else at
the start. The header takes the alignment with the cells; a right-aligned
column under a left-aligned heading reads as two columns.

Pinned columns, an edge wash that says there is more, a footer of Load more and
"48 of 1,240" — which is also the page-size control, because how many are shown
and how many to fetch are one question — and windowing past two hundred rows.
The count is
**its own request**, never awaited with the rows: a `COUNT(*)` over an unindexed
filter is a full scan, and folding it in would put that scan in front of every
list. It goes through `get_list` so it sees the same permissions the rows did.

`RecordTable` draws both this and the grid inside a record — one place to be
wrong about tracks, sticky headers, pinning and windowing.

**Export.** Beside the count, because it is a question about the same thing:
how much of this am I looking at, and can I have it. What comes out is what is
on screen — this reader's columns in their order, narrowed by the saved view
and by whatever is unsaved above it — and a selection exports exactly the rows
that were ticked. The same `_resolve` → saved view → overrides chain the rows go
through, so an export can never reach further than the list it came from.

**How many of each.** Frappe's list sidebar, as a menu — this product's sidebar
is the space's own navigation, and a second one beside the list would undo the
thing that makes every screen here read the same. Pick a field, see its values
with counts, click one to narrow to it. Only a Select, a Link or a Check: a
Data field has as many values as rows and a date has more. Counted **under the
filters already on**, which is what makes it a shortcut rather than a second
opinion — a tally of everything shown over a list of twelve is a menu of
numbers that do not match the screen. Clicking a value writes an ordinary
`[field, =, value]` into the filter panel, where it can be seen and removed:
a list narrowed by something invisible is a list that looks broken. Twenty
values, and it says so when there are more.

**Bulk operations.** A selection can be changed, assigned, exported or deleted.
The change is one field to one value — Frappe's own shape, and the right one: a
dialog offering several fields at once is a record form applied to forty
records, and what makes a bulk change safe is that it is small and legible.
Assignment is separate because `_assign` is not a field, and it *adds* rather
than replacing: one record's assignment is a list somebody is looking at and
editing whole, a selection's is not on screen at all, and replacing forty with
one name takes work off thirty-nine people by accident.

Each record is saved on its own, inside its own savepoint, and what could not
take the change comes back **named**. A submitted document, a validation rule,
a row this person may read and not write — all facts about that record, and a
bulk change that silently skipped nine of forty would be worse than one that
failed. Capped at the same hundred a bulk delete is: past that this is a script
somebody should be writing rather than a button. `spaceview/bulk.py`.

The file is built on the server (`spaceview/export.py`) rather than joined
together in the browser, for one reason: quoting. A subject with a comma in it
becomes two columns and every row after it is off by one, silently, and this
product's own correspondence register is full of them. Python's `csv` has been
right about that for twenty years. Values are the ones **stored** rather than
the ones drawn — a CSV is data, and a Link cell drawn as "Ada Sinclair" has to
come back as the id for the file to be worth anything downstream. It carries a
byte-order mark, without which Excel on Windows reads UTF-8 as the system
codepage and turns every Arabic subject into mojibake. Capped at 5,000 rows, and
the toast says so when it bites: a spreadsheet that quietly stops is the worst
thing to hand somebody who is about to add it up.

### Report — the same list, opened as a worksheet

A report *is* the list, plus two things: cells you can type into, and a row of
totals under them.

They are a separate view type rather than a switch on the list because of the
**click**. A list row opens the record; a report cell takes the cursor. One
click cannot mean both, and Frappe answered it the same way. `ListBody` draws
them both — a report is a mode of the list, not a second table — and the title
cell still opens the record, which is the way back.

**Inline edit** is `FieldControl`, the same control the record form draws, and
the write is the same `saveRecord` — so the doctype's rules, its permissions and
its `fetch_from` all still happen, and the list re-reads afterwards because the
save may have changed more than was sent. A cell is editable where the server
already said the field is (`editable` carries fieldtype, `read_only` and
permlevel) and the row is not submitted. Escape abandons; Enter and leaving the
cell commit; a value that did not change sends nothing, because a version on a
record saying nothing happened is worse than no version.

**The totals** are an aggregate over the whole filter, asked for separately from
the rows the way the count is. Over the filter and not the page is the only
thing that makes them worth showing: a total of the hundred rows that happen to
be loaded, under a footer reading "100 of 1,240", is a number nobody can use and
everybody would read as the total. Currency and Float only — a sum of
percentages is a number with a percent sign on it, and an Int column is as often
an id or a priority as it is a count. No switch: the row appears where it means
something and nowhere else, which is why the plain list pays nothing for it.

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

### Calendar — the first that is not a page

```json
"view_settings": {"calendar": {"start_field": "starts_on", "end_field": "ends_on"}}
```

`start_field` is the whole declaration; `end_field` is optional and is what
makes a record a span rather than a moment. Both must be a Date or a Datetime,
checked against the doctype like a board's column field is, and a start that is
not drops the calendar the way a missing status drops a board. There is no
screen-level date field to fall back on: `status_field` is on the screen
because a badge reads it too, and nothing but this reads a date.

The Date-versus-Datetime distinction is the one thing a manifest does not have
to say — a Date has no time and is therefore a whole day, which the fieldtype
already settled.

**The range is the request, not a page.** Every other body draws the page it
was handed; a calendar says which days it is showing and the shell fetches
those (`since`/`until` beside `start` and `limit`, applied to the screen's own
field — the browser sends two dates and cannot name a column). A month drawn
from whichever hundred rows sorted first has holes in it, and the holes move as
you page. It is deliberately not part of a saved view either: a view carrying
"March" is a view that shows nothing in April.

The grid is frappe-ui's `experimental/Calendar` — month, week and day, with the
event spans, the popover and the keyboard already in it, and it is what Frappe
Suite's own calendar draws with. Read-only here: it can drag, resize and create,
and every one of those writes a field that this screen already writes properly
through the record. Clicking an event opens that record.

### Gantt — the same two dates, drawn as lengths

```json
"view_settings": {"gantt": {"progress_field": "percent_complete"}}
```

The declaration is the calendar's, and that is deliberate: `gantt` falls back
to `view_settings.calendar` for its pair, so a screen offering both is placing
its records by the same two dates and is never made to say so twice. Name
`start_field` and `end_field` under `gantt` only where the two genuinely
differ.

What changes is that **both ends are compulsory here**. A record with a start
and no end is a moment, and a chart of moments is a column of dots — so a
screen with no `end_field` is offered a calendar and not a Gantt, and a record
missing one date is simply absent from the chart while its neighbours draw.
`progress_field` is optional, is a Percent, Int or Float, and fills the bar.

The chart is [`frappe-gantt`][gantt], Frappe's own package, so this is a
dependency rather than a port — one of the few places where the answer to "take
it or write it" is neither. It is MIT and it is on npm; the parts of the
library that would have been ours to write (the time scale, the week and month
modes, the header that follows the scroll) are the whole of what it does.

Read-only, for the calendar's reason: dragging a bar writes two fields on a
record, and a handle that moves and springs back is worse than one that does
not move. Clicking a bar opens the record.

[gantt]: https://github.com/frappe/gantt

### Tree — a register that has a shape

```json
"view_settings": {"tree": {"parent_field": "renews"}}
```

The field has to be a **Link at this screen's own doctype**. A Link somewhere
else is a relation and not a hierarchy: nesting a licence under its issuer is a
different picture with the same shape.

**Declared, never inferred**, and that is the one place this parts from the
desk. Frappe reads a nested set's own `parent_<doctype>` and has no answer at
all for a doctype that is not one. Guessing "the Link that points at this
doctype" is worse than asking, because a doctype can have several — our own
Compliance Document has `renews` *and* `renewed_by`, and only one of the two is
a hierarchy. Where a doctype is a nested set, `parent_<doctype>` is still the
obvious thing to name; the manifest just has to name it.

The nesting is built from **the page**, not from a second query per node, which
leaves one question: what happens to a record whose parent is not there. It is
drawn as a root, muted, and never dropped — the parent may have been filtered
out, or be on a page nobody has loaded yet, and a tree that hides a record for
either reason is one that disagrees with the count in its own footer. Load more
re-nests it. Two records naming each other are both left at the top, which is
the only drawing of a circle that terminates. `lib/tree.js` owns all of that,
and is where its tests are.

Clicking a record's *name* opens it; clicking the rest of the row expands it,
which is what the desk's tree does too. One limit worth stating: a node with no
children is drawn as a leaf whether or not the doctype would call it a group, so
an empty group and a leaf look alike.

---

## 6. The record

**Three surfaces, and only one of them is a modal.** A record is something you
read *against* the list — mark this done, glance at the next, come back — which
is why it was never a dialog.

| | |
|---|---|
| **pane** | The resizable column beside the list. The desktop default; its width is dragged and remembered. |
| **page** | The whole content area. Always on a phone; on a desktop where the screen declares a showcase, or where the reader pressed the expand control — which is remembered per screen, so "a project is a page and a task is a pane" is a thing a person can have. The list is hidden rather than unmounted, so closing comes back to the same rows and the same scroll position. |
| **drawer** | An overlay over a page, for a record opened *from* another one: a variation from its job, an invoice from the project it was raised against. In the URL as `peek` + `peekScreen`, so it is linkable and the back button and Escape both close it. It is the one record surface that takes Escape, because it is the one that is modal. |

`lib/surfaces.js` holds the vocabulary and the remembered preference.

**One header, and it says the record's name once.** A record used to draw its
own bar under the screen's — two bands, and on a showcase page the second one
held two icons and fifty pixels of white between the trail and the photograph.
So on a desktop *page* the record has no bar: its controls teleport onto the
trail's line, which is already naming the record, and New stands down there
because the list it would add a row to is not on screen. A pane keeps its own
bar — it is a column beside a list whose header is that trail — and the drawer
and the phone keep theirs because both cover the trail. `RecordControls` is the
row, drawn in whichever of the two places applies; `MERGE_TARGET` in
`lib/surfaces.js` is the id the two halves agree on.

The identity follows the same question: the trail says it on both desktop
surfaces, the hero says it wherever there is a showcase, so the header draws it
only on a phone and in the drawer. The drawer also offers the one control the
others have no use for: open this properly, on its own screen.

The tabs:

| | |
|---|---|
| **Details** | The doctype's own form. Tab, Section and Column Breaks read the way the desk reads them, collapsing below the breakpoint. **Heading** and **HTML** fields are drawn too — both carry no value, which is why they are layout fields and why the form dropped them for years, and both are the author of the doctype annotating their own form. An HTML block's markup goes through DOMPurify before it is drawn. Its tabs are a **pill track**, not a second underlined strip: the two sit an inch apart and both open with the word Details, and drawn alike they read as one strip split in half. They are not siblings — the record's strip moves between the record and everything filed against it, the form's moves inside one of those. |
| **Connections** | One tab per other screen in this space that points back at this record — a project's quotations, its purchase orders, its invoices, a licence's letters. See below. |
| **Activity** | One timeline: what was said, what changed, and when it started, newest first. Merged in the browser from two queries; every entry carries a glyph from a closed set, because a column of identical avatars makes a comment and a field change look alike. |
| **Files** | Frappe's own File rows, so an Attach field's file and a dropped file are one list. |
| **Meta** | The desk's sidebar: the face and name, then the four things you do to a record *about other people* — assign, attach, tag, share — then who made it and when, then its id. The only place assignment is offered; it was in the header too, which made it one control in two places. |

Behind the three dots, beside print, follow and like: **Duplicate**, **Copy
link** and **Reload**. Duplicate is Frappe's own — `copy_doc` on the server, so
`no_copy` fields are dropped and the amended-from chain is not carried, and the
values open in the ordinary create dialog rather than being inserted. A copy is
a draft somebody is about to change the date on, not a document that has been
raised, and cancelling it leaves nothing behind.

### Connections, derived rather than declared

Every screen in this space whose doctype carries a link back at this one becomes
a tab, and opening it is that screen filtered to this record — the same columns,
the same widths, the same title field, because it *is* that screen. There is a
New on it with the link already filled in, which is Frappe's "New linked
document" on the tab that is already about the link.

Two shapes count as pointing back. A **Link** field naming this doctype, which
is a screen saying "this is always about a project" — where a doctype has more
than one, the field named after the doctype wins, because a Sales Invoice
carries both `project` and `cost_center`. And a **Dynamic Link**, the pair of
fields Frappe uses for "about anything" — a letter about a licence, a task
against a project — where the tab filters on the doctype as well as the id, or a
licence's letters would turn up on a project that shares its name. Named links
are offered first: both are worth having and only one of them is a statement
about *this* doctype.

Bounded by the space, not by the schema. Frappe's own `get_linked_doctypes`
answers over the whole site and half of what it returns is a doctype this
workspace has no screen for and no permission on — and a connection that opens
nothing is worse than no connection. So only screens the space already has, and
at most six. A showcase that declares its own tabs keeps them, first and in its
own words; the derived ones follow, minus any it already named.

`spaceview/connections.py` decides; `RelatedRows` draws it, and drew the
declared half already.

### A link is a record, so it opens like one

A Link field holds another record, and for a long time the form let you change
which one and never let you look at it. Two buttons on the field's label row,
where the field has a value and the space has somewhere to take it:

| | |
|---|---|
| **Open beside this** | The record in the drawer, over the one you are on. `peek` and `peekScreen` in the URL — the same pair a showcase's rail uses, so the back button closes it. |
| **Open** | Its own screen, its own list behind it. The view type and any saved view are dropped: they belonged to the screen being left. |

Both are absent more often than they are present, and that is the interesting
part. A Link holds a *doctype*; this product has routes for *screens*; which
screen shows a doctype is a question only the space's own manifest answers, and
for most links the answer is none. Currency, UOM, Warehouse and Territory are
all on an invoice and none of them is a screen anybody browses — a button
offering to open one would be a door onto a wall. So the buttons appear when
the space shows that doctype somewhere, and the resolution happens against the
session's own manifest rather than over the wire, which is why a form with
nineteen links makes no extra requests to find out.

A filter's picker never offers them: somebody narrowing a list by customer is
not asking to leave for that customer, and a control inside a popover that
navigates out from under itself loses what was being typed.

### A record that is a place, not a form

Some records are not a column of labelled inputs. A project is a photograph of a
building, a contract value, a percentage done, thirteen variation orders hanging
off it and five hundred documents filed against it — and drawing that as a form
is technically a record page and practically a filing cabinet.

So a screen may declare a **showcase** in its `view_settings`, and then opening
one of its records looks like this: the photographs filed against it running the
full height of the section and crossfading every six seconds, the name over
them, a status badge, up to four numbers worth reading at a glance, a sideways
row of cards for whatever hangs off this record *sitting on the artwork* rather
than in a panel under it — one scrim over the whole section, solid black through
the bottom quarter so the cards have a ground and gone by the top so the
photograph is a photograph — and a tab strip that carries the other screens
in the same space that point back at it — beside the record's own Details,
Activity, Files and Meta. The record takes the whole content area rather than a
pane, because a hero in a 480-pixel column is a thumbnail; the list behind it is
hidden rather than unmounted, so closing comes back to the same rows and the
same scroll position.

```json
{"showcase": {
  "images": true,
  "eyebrow_field": "custom_location",
  "badge_field": "custom_stage",
  "facts": [{"field": "estimated_costing", "label": "Contract"}],
  "children": {"screen": "projects", "field": "custom_parent_project",
               "label": "Variations", "icon": "lucide-git-branch"},
  "tabs": [{"screen": "invoices", "field": "project", "label": "Invoices"}]
}}
```

**The name is set in the one face this product has that is not the interface
face.** Anton for Latin, Reem Kufi for Arabic, under a single `OneSpace Display`
family so the browser picks per glyph and a bilingual title is set in both
without anything asking what language it is in; `unicode-range` on each so a
page of Latin never fetches the Arabic file. Both are SIL OFL 1.1 and both are
self-hosted — a tenant's browser asking Google for a stylesheet on every page
load is a third-party request on somebody else's site, in whatever jurisdiction
they are in, to render a font. `font-display` is the Tailwind token; the
`@font-face` rules and the reasoning are in `src/index.css`, and
`tests/test_display_font.py` plus one browser check keep the file, the rule, the
licence and the actual download honest. Use it for a title somebody is meant to
look at rather than read past. A display face used twice is a voice; used
everywhere it is a costume.

**The rail can add one.** A plus in its corner opens the ordinary create dialog
for the child screen with the linking field already filled in — the parent as a
preset, an ordinary value in an ordinary control that the person can change
before saving, the same way a board's New seeds the column it was pressed in.
Offered only where *that* screen says this person may create one, which is its
own `can_create` and not the screen being read. Creating from here stays on the
parent and re-reads the rail: you were reading a job and you added a variation
to it, so the job is where you still want to be. It is also the only place that
knows which record a new one hangs off — the alternative is making it from its
own list and remembering to set the parent by hand, which is where every orphan
comes from.

**Nothing in it is about construction, and nothing in it is a query.** A tab
names another screen in the same space and the field on it that points back
here; the browser then asks that screen's own `rows` for that filter, which is
where the space, the permissions, the columns and the filter are all checked —
the same checks any other list goes through. `showcase.shape` drops what is
structurally not a showcase and checks every fieldname against the screen's own
columns, so a manifest with a typo renders a form rather than a broken page; it
is a validator, not the security boundary. A related tab drops the column it
filtered on, because on a project's Invoices tab that column is the project's
own name written down six times.

This is the answer to "manifests or bespoke UI": it is a *declaration*, not a
registered component, so the space that wants a Netflix page writes eleven lines
of JSON and a customer, a property or a case would declare the same shape and
get the same page. The escape hatch in §2 is still there for a screen that is
genuinely not a list of records; this is for the far more common thing, which is
a record that deserves better than a form.

**Making a record is a dialog**, the one place a modal is right: nothing behind
it to refer to, a short decision, cancelling leaves nothing. Headed with the
screen's own word for one of these, singularised — the doctype's name is a
Frappe word, and a screen called Tasks used to open **New ToDo**. A screen
whose plural the rule gets wrong says so with `singular`. It shows the whole
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

A Link *inside* one reaches its picker through the same check as a Link on the
parent — the field has to be one the screen offers — and for a long time it did
not: `_link_column` looked only at the parent doctype's fields, so `item_code`
on an invoice line was "not on this screen" and every picker in every grid in
the product answered 403. It looked like a disabled control. Two smaller things
came out of fixing it. A picker used to fetch its first page of options and its
create-spec on mount, which is fine for the two on a form and ruinous in a grid
— one invoice fired thirty-eight requests before anybody clicked anything — so
it now fetches on first touch. What is left is one request per filled Link field
to resolve the label the closed box shows; resolving child-row links server-side
in `_with_children`, the way `_with_links` already does for list rows, would
remove those too. And where two child tables on one doctype share a fieldname,
the first is used: the browser should say which grid is asking, and does not.

**The header is one button and one menu.** It was eight controls in a row —
screen actions, assign, like, the document's steps, print, follow, Save, close
— each defensible alone and together a toolbar you read rather than use. Now:
who else has it open, the step the record is waiting for, `⋯`, Save, close.
The menu holds the record's other verbs (print, follow, like — with its count
in the label) and, last and in red, the steps that unwind a submitted document.
Save and the step swap places, never both.

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
  submitted document is three dots and nothing else: unwinding a ledger entry
  should not sit where the eye has just learned to click.
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

### Mail

An address in OneSpace is a **delivery point, not a mailbox**. Cloudflare gives
us sending and inbound routing and deliberately not storage, so there is no IMAP
server behind `sales@acme.4dl.app` — mail addressed to it arrives at the site as
a `Communication`, which is a document, which means it is already listed,
permissioned, searchable, attachable and printable. The whole feature is
therefore small: `docs/EMAIL.md` is the argument and the stages.

The four things worth knowing here:

**The tenant's slug is a subdomain.** `sales@acme.4dl.app` and
`sales@rua.4dl.app` are different addresses, so the namespace is per workspace
and nothing central allocates anything. A workspace may also send as its own
domain, and does not until SPF and DKIM verify — sending as a domain that has
not authorised us is how a shared IP gets listed.

**An address held by one person and an address a team shares differ only in how
many names are against them.** Both are an `Email Account` plus `User Email`
rows, which is Frappe's own model and not a parallel one, so a grant is a row
and revoking it is deleting the row. Settings → Email is the one list; a person
may edit the signature on any address they hold, and connect a mailbox they
already have — Gmail, Outlook, anything with IMAP — without being an owner,
because that mailbox is theirs.

**Reading is a filtered `Communication` list.** The Mail page's three columns
are the shape every mail client has had for thirty years; a conversation is
`custom_thread` — walked from `in_reply_to` on insert, falling back to the
subject with `Re:` stripped — and it lives in the URL so the back button closes
it. Unread is per person rather than Frappe's per-document `seen` flag, because
two people on `sales@` each need their own idea of what they have read, and star
and draft are per person for the same reason.

**A mailbox somebody connects stays theirs, both ways.** Their folders come
across, including the ones they made, and a folder made here is an IMAP `CREATE`
that Outlook shows. Filing, archiving and deleting go back out over IMAP, so the
same conversation is in the same place in both clients. What is ours rather than
the server's: paging, body search, drafts, an Undo that is really
`Email Queue.send_after` rather than a countdown a closed tab defeats, and rules
that are four words — look at this field, for this text, file it there.

### Calendar

Beside Mail and Files on the rail, and the same argument for being there: a week
does not belong to one space. `/one/calendar` is a **merge**, not a store —
nothing on it is written here, every entry belongs to a record somewhere else,
says which, and opens it.

Two sources, both already permissioned, in `oneapp_core/diary.py` (named
`diary` because a module called `calendar` inside a package is one import from
shadowing the standard library's):

* **Every screen the reader can open that declares a calendar**, resolved
  through `_resolve` — the same path the screen's own calendar uses, so a
  record absent there is absent here for the same reason.
* **The reader's own `Event` rows** — owned by them, or naming them among the
  participants. An events *screen* is what the workspace has; this is what is
  theirs.

**One record, one entry.** A workspace with an events screen reaches Tuesday's
review twice, and a calendar that draws it twice is one nobody trusts about
Wednesday. De-duplicated on `(doctype, name)`, and the screen's copy wins
because it knows where the record lives.

The rail lists the sources with the colour their entries carry, and switching
one off is a filter in the browser rather than a second request. The colours
are frappe-ui's seven, taken in source order, so the dot and the entries are
one fact rather than a legend to learn.

**Yours opens here; everything else opens where it lives.** The de-duplication
hands a screen the win for *reading* a record — that is where the doctype's own
form and rules are — but ownership is carried separately, because a workspace
with an events screen would otherwise let somebody press New here, write an
event, and never edit it from the diary they wrote it in.

New, edit and delete are the one thing this surface stores, and they are core
`Event` rows — the framework's own doctype, the same one the diary already
reads. Four fields: a name, when, whether it is a whole day, and notes.
`ignore_permissions` behind this module's own gate, and the gate is *ownership*:
"you may put something in your own week" is not a thing an admin should have to
enable per workspace, and a row you do not own is a row `_mine` will not fetch.
Events are Private, not a choice on the form — sharing one is naming who is in
it, which is the next piece rather than a dropdown.

The grid stays read-only: it can drag, resize and create, and every one of
those writes a field that the record dialog already writes properly.

Not built yet: participants, reminders, recurrence. Frappe Suite's `Calendar Event` is
JMAP/JSCalendar-shaped — participants, alerts, recurrence rules, an exchange
layer for CalDAV — and that is what to adopt when invites and RSVP are wanted.
It is AGPL-3.0, the same as this repo.

### Files

**It is `File`, not a new model.** Frappe already has one file table and every
attachment in the workspace is in it; the Drive adds four columns and no second
store. A file attached to a record has `attached_to_doctype`, a file in a folder
has `folder`, and it can have both — so `/one/files` and a record's Files tab are
two `where` clauses over one table, drawn by one component. `docs/DRIVE.md` is
the argument and the stages.

The five things worth knowing here:

**The rail is five filters over one column each.** All files, Recent,
Favourites, Shared with me, Bin. Recent is `custom_opened`, stamped when
somebody opens a file; Favourites is `_liked_by`, which the framework keeps on
every doctype and this product already draws as a heart; Shared is "reachable
and not mine", where what makes it reachable is a `DocShare` `get_list` has
already applied. A sixth place would be a filter rather than a feature.

**The bin is a promise with a date on it.** Deleting used to remove the row and
the object together, so the only undo was a backup — which is not an undo, it is
a support ticket. Trashing sets a column; a scheduled sweep empties what has
been there thirty days and deletes the object then. Taking a file off a record
goes the same way. Which means a binned file still counts against the storage
quota, correctly and confusingly — so the storage screen says how much the bin
is holding and offers to empty it, because deleting a gigabyte and watching the
meter not move is indistinguishable from a bug unless something says otherwise.

**A file counts once, however many records it is on.** Attaching a drawing the
workspace already has writes a second `File` row over the same object; summing
`file_size` over rows billed it once per record it appeared on, so a workspace
storing four megabytes could be refused at forty. `quota.current_usage` groups
by the object — `r2_key`, or `file_url` where the file is on local disk — and
takes each one once. A sheet weighs what its stored workbook weighs, stamped
onto the `File` when it saves; before that every sheet showed as zero bytes in a
file list whose whole job is to say how big things are.

**Every read is `get_list`.** That one word is the whole access model. `get_all`
ignores permissions, and a file manager built on it would hand every reader
every file on the site — most of which are attachments on records they cannot
open.

**Attaching is one control everywhere, with three sources.** `FilePicker` opens
on **Library** — every file this person can see, flat, searchable — with **This
device** and **Camera** beside it. Upload writes into the Drive and then picks
the result, so there is one path and one place files end up. It replaced five
separate uploaders that could not see each other's work, which is how the same
drawing came to exist four times under four names. Picking a file that is
already attached somewhere writes a second row over the same object rather than
moving the first.

Three, not five: Frappe's desk offers Library, Link, Camera and Google Drive. A
Link is a `File` row pointing at somebody else's server — an attachment that
breaks when they tidy up, indistinguishable from one that does not until
somebody needs it — and Google Drive is a second cloud beside the one we run.

The library is first on purpose. The file somebody wants is usually one the
workspace already has, and a dialog that opens on an upload button teaches
everyone to upload it again. Sheet import is the same dialog, narrowed to the
three extensions it can read, so a spreadsheet attached to a quotation last
March imports without being downloaded and uploaded first.

The upload goes through `lib/attach.js`, which every attach surface shares, so a
large file attaches to a record by the same presigned route it takes into the
Drive — see `docs/DRIVE.md` §8. It used to post through Frappe here, and a large
attachment simply failed.

**A link outlives a session, and only that.** Sharing with a colleague is a
`DocShare`; sharing with a consultant who has no account here is a `File Link` —
a secret in the URL, an expiry, and a revoked flag. It refuses a folder, refuses
no expiry, and every refusal on the way in says the same sentence, because a
message that distinguished expired from wrong would tell a stranger whether the
secret was right.

### Spreadsheets

**A sheet is a File too**, with `custom_kind = 'Sheet'` — so it arrived already
able to sit in a folder, be shared, be thrown in the bin, be handed to a
stranger on an expiring link, and hang off a quotation. `docs/SHEETS.md` is the
argument and the stages. Four things carry the weight:

**The browser evaluates; the server stores what it computed.** `Sheet Cell`
keeps `raw` (`=C2*D2*E2*F2/1000000`) beside `value` (`6480`), and nothing on the
server ever reads `raw`. A print format, a report and the read-back all want the
number and none of them has a browser — which is why there is no formula engine
in Python here, and why there does not need to be.

**A named range is a contract.** Select a rectangle, give it a name, and a
record can fill a child table from it: the first row names the columns, a
heading may carry its unit in brackets (`Width [mm]`), and a heading matches a
field by fieldname or by label. Everything outside the named range is the
estimator's working — lookup tables, scratch columns, a note to themselves — and
none of it is anybody else's business. That is what makes a spreadsheet usable
as a spreadsheet rather than as a form with grid lines.

**A pull replaces, never appends.** The preview is the confirmation, and it runs
the same code the pull does, so what it shows is what lands. Pressing it twice
cannot double a quotation.

**A filled table says where it came from, and can be locked.** Under the rows:
"Filled from Padel Pro estimator · LineItems, five minutes ago". Locking is
RUA's lock — after it the document is the record and the sheet is history, and
the server refuses a pull rather than the control merely disappearing. The
record survives the sheet being deleted, because that is the moment it is worth
most.

**Nothing pushes.** Editing the sheet never touches the document; somebody
presses Fill again. What the note does instead is say *the sheet has changed
since* — so you find out, with the control that would act on it right there,
and nothing moves behind you. A spreadsheet that could reprice a quotation
after it was sent would make locking the thing you must remember rather than
the thing you choose.

**The control is on every editable child table**, not on the ones a manifest
named. Declaring the binding is the more disciplined design and the wrong one:
it would mean nobody can price a job in a grid and feed it into a doctype
nobody thought of in advance, which is the thing spreadsheets are for.

Not built yet, and deliberately: two people in one sheet at once, charts,
pivots, and cell protection.

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

## 9. Two registers OneSpace ships itself

Every doctype a screen shows belongs to Frappe, to ERPNext, or to the app that
declared it — with two exceptions, and both came out of reading a real
customer's system rather than out of a design meeting.

**Compliance Document** is a paper that expires: a trade licence, a residence
visa, a vehicle registration, a site insurance policy. It hangs off anything
through a Dynamic Link, because a visa belongs to an employee and a licence to
the company and an insurance policy to a project, and a register that knew about
only one of those would be four registers within a year. Its status — Expired,
Expiring, No expiry, Valid — is **derived** from the expiry date and a per-row
warning window, on save and once a day, never typed: a status somebody can set
is a status that eventually reads Valid over a date in 2019.

The daily sweep is the point of the whole thing. A document that crosses into
Expiring notifies whoever it is assigned to, whoever follows it and its owner —
Frappe's own assignment and following, so this adds no third idea of "people who
care about this record" — and then says nothing more until it actually expires,
which is different news. A register that warns every morning is a register
people filter into a folder, and then the one that mattered is in the folder
too.

**Correspondence** is a bilingual letter and form register: English and Arabic
side by side, neither the "real" one, with author and signee blocks in both,
templates, and `LTR-` / `FRM-` / `MEM-` numbering. Nothing in Frappe does this,
and a company writing to a municipality in Arabic and a consultant in English
does both from the same screen on the same day.

Both are ordinary records with no component anywhere: a space declares a screen
over them and the generic engine draws the rest. That is checked rather than
claimed — the dev seed declares a screen for each, so every browser run opens
them.

**And the whole product became bidi-correct on the way.** Every text control and
every text cell carries `dir="auto"`, so the browser lays a value out from its
own first strong character. An Arabic subject reads right-to-left in the box
above an English one that does not, with nothing declared anywhere — Frappe has
no direction property on a DocField and it would be the wrong place for one,
because direction belongs to the value. Never `rtl`: a field forced
right-to-left mangles the English that ends up in it just as thoroughly.

---

## 10. AI in a workspace

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

## 11. Workspace settings

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

## 12. The UI rules

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

## 13. What the generic screen does not do yet

Worth knowing before designing around it.

* **A workflow builder.** Workflows run; there is no screen for drawing one.
* **Computed child-table columns.** A quotation line is width × height × qty ×
  rate; the grid edits values and does not derive them.
* **Notification rules and email templates.** The feed and the digest exist; the
  rules that would produce "email the owner when this goes overdue" do not.
* **Data import and export.** No CSV either way.
* **Customize Form.** We write Property Setters for naming and default print
  formats; there is no UI for adding a field or relabelling one.
* **User Permission.** Enforced on every path, and there is nowhere to grant
  one.
* **Bulk edit.** Selection does delete and declared actions only.
* **The map view**, which a manifest may already declare — a type nothing can
  draw is dropped rather than refused, so the screen renders as a list and
  gains the map without a manifest edit. The calendar shipped and is below.
* **Free-text search across a whole doctype**, drag-to-resize a column, and
  filtering on a child table (Frappe needs a four-part filter there and a
  three-part one names a column that is not present).

Also, deliberately: **Assignment is not shown in the list.** The activity column
is a fixed 176px track already holding an age, a count and a heart. If
assignment should be readable in a list the honest answer is a column of its
own, filterable like any other.
