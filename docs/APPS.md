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

Only `fields` is worth writing down about the columns. Labels, types, Select
options and required-ness come from the tenant site, so a relabelled field is
relabelled on every workspace without a sync. A field the manifest names and a
site does not have is skipped rather than fatal — one manifest serves sites on
different versions. Naming none at all falls back to the doctype's own list
fields.

Screens are edited in OneAdmin under **Settings → App screens**. Their order
there is the order of the app's navigation, in the sidebar and in the phone's
bottom bar alike.

## Two rules make a screen safe to hand a customer

**A screen is an allowlist, twice over.** It can only be reached through an app
the workspace is entitled to, and can only name a doctype that app's manifest
already granted — checked against the DocPerms actually written, not against the
manifest as sent. A view pointing outside its app is refused rather than left to
come back as an empty list, which reads like there is no data.

**A write is bounded by what the screen shows.** Reads and writes go through the
view rather than a generic document API, so a screen cannot be used to set a
field it does not display. Frappe's own permissions still decide whether any of
it is allowed; this only bounds what is asked for.

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

## What the generic screen does not do yet

Worth knowing before designing around it:

* **Link fields render as plain text.** Editable, but with no picker behind
  them — a customer has to know the record's name. `Combobox` is in the
  vocabulary; wiring it to a search endpoint is the next thing this needs.
* **No child tables.** A doctype with rows inside it shows its top-level fields
  only.
* **One page of records.** A hundred, then a line saying there are more. No
  search, no filter, no infinite scroll.
* **No delete from the UI**, though the endpoint exists.

None of these block a first app; all of them are worth knowing about before
designing one around a list of five thousand invoices.
