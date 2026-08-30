# Building an app

An app is configuration before it is code.

It declares which doctypes it grants and which screens it puts in front of a
customer. OneSpace renders those screens from the *tenant site's own metadata* —
what each field is called, what a Select offers, whether this user may write it —
so most apps need no frontend code at all, and a new one is a registration plus
its doctypes with no OneSpace release.

The escape hatch is there for the rest.

---

## What an app is made of

| | Where | What it does |
|---|---|---|
| Registration | `OneApp App` in OneAdmin | Name, icon, availability, and the role that gates it |
| Manifest | `OneApp App Doctype` | Which doctypes the role may touch, and how much |
| Screens | `OneApp App View` | What the customer sees |
| AI features | `@ai_feature` in app code | See `docs/AI.md` |

Availability is the lever: **General** reaches every workspace, **Restricted**
only those granted it individually on their own page. An app with no screens is
an entitlement with no interface — a real thing to be, since it still grants its
roles and doctypes to whatever else is using them.

## A screen

```
view          invoices            slug in the URL; a bookmark points at it
label         Invoices            the app's navigation
icon          lucide-receipt
document_type Sales Invoice       what the list shows
fields        customer,status,grand_total
filters       {"status": "Open"}  always applied
order_by      modified desc
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

Screens are edited in OneAdmin under **Settings → App screens**. Their order
there is the order of the app's navigation, in the sidebar and in the phone's
bottom bar alike.

## Two rules make a screen safe to hand a customer

**A screen is an allowlist, twice over.** It can only be reached through an app
the workspace is entitled to, and can only name a doctype that app's manifest
already granted — checked against the DocPerms actually written, not against the
manifest as sent. A view pointing outside its app is refused rather than left to
come back as an empty list, which reads like there is no data.

**A write is bounded by the doctype the app granted, not by the manifest's field
list.** Reads and writes go through the view rather than a generic document API,
so a screen cannot reach a doctype outside its app's grant. Within that doctype
the bound is Frappe's own: `has_permission(write)` decides, `read_only` fields
are not editable, a field above this user's permlevel is never offered, and
Frappe's bookkeeping never is. The manifest's `fields` used to narrow this too;
it no longer does, because the record now shows the whole doctype and a control
that looks editable and is silently discarded is worse than one that is absent.

Both are exercised against a real site, and the logic behind them is pinned in
`tests/test_app_views.py`.

## When a list is not enough

Register a component under `appCode/view` in
`apps/oneapp/frontend/src/apps/index.js`:

```js
export const APP_COMPONENTS = {
  'crm/pipeline': () => import('./crm/Pipeline.vue'),
}
```

Set `component` on the view to `crm/pipeline` and everything else on it is
ignored: the component receives `appCode` and `view` as props, and the rest of
the screen is the app's business rather than ours. Lazy, so an app nobody opened
costs nothing to load. Keyed by app so two apps can each have an `overview`.

Use it for a dashboard, a wizard, a calendar — anything a list of records and one
of those records open cannot be. Reach for it second: the generic path already
handles most of what an app is, and every screen written by hand is a screen that
has to be maintained by hand.

## What a screen carries without being asked

None of this is written into a manifest. It comes off the doctype the screen
already names, so an app gets it by existing.

* **Every fieldtype has a control.** The map is generated from Frappe's own
  `data_fieldtypes` (`scripts/field_types.py`), so a fieldtype Frappe adds fails
  a test here rather than rendering as a text box that writes a string into a
  Currency column. Colour, signature, geolocation, barcode and icon have no
  frappe-ui counterpart: they are shown, never offered.
* **Link fields get a picker.** A Combobox backed by `appview.link_options`,
  bounded by the screen the same way its rows are, and honouring the field's own
  `link_filters`.
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
* **Saved views.** Filters, sort, columns and their order, and page length, per
  person per screen, in `OneApp Saved View`. A saved view narrows what the
  screen offers and can never widen it — see ADR-13. The same bounds apply to
  an unsaved change, which is why the controls can show their answer before
  anything is saved.

## What the generic screen does not do yet

Worth knowing before designing around it:

* **No child tables.** A doctype with rows inside it shows its top-level fields
  only.
* **One page of records.** A hundred, then a line saying there are more. Filters
  and sort narrow it; there is no infinite scroll and no free-text search across
  the whole set.
* **A child table cannot be filtered.** It is rows rather than a value, so
  Frappe needs a four-part filter naming the child doctype and a three-part one
  names a column that is not there. Shown, never filtered.
* **No delete from the UI**, though the endpoint exists.

None of these block a first app; all of them are worth knowing about before
designing one around a list of five thousand invoices.
