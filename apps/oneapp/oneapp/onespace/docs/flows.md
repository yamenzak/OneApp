# Flows

## Resolving a screen — `spaceview/`

The layer map, and it is the import order: **a module may use the ones above it
and never the ones below**, which is what stops it becoming one 4,000-line
module again.

    meta        what a doctype's metadata says a screen may show
    viewtypes   the ways a screen can be looked at, and what each needs
    connections what else in this space is about one record
    actions     the actions a space declares for a screen
    filters     what a reader asked for, as a query the framework accepts
    saved       reading saved layouts, and picking which one applies
    views       per-view-type shaping: board columns, cards, widgets
    applied     folding a saved layout, then the live controls, onto a screen
    resolve     one screen resolved: which doctype, columns, views
    people      users as the UI needs them
    links       Link fields: searching a target, and creating into one
    records     reading and writing the records a screen is over
    export      those same rows, as a file somebody can open elsewhere
    guard       the one check every record-scoped endpoint makes first
    surround    a record's timeline, files, comments, likes
    mail        the correspondence about a record, and writing more
    assign      who a record is assigned to
    bulk        one change, applied to a selection
    sharing     tags and shares
    docstate    submit, cancel, amend, workflow
    printing    print formats, reached from a record
    layouts     writing a saved view
    run         running a declared action

Everything is re-exported from the package, because the whitelisted paths the
SPA calls are `oneapp.onespace.spaceview.rows` and always have been. **That
re-export is an address, not a seam**: inside the package, import from the layer
that owns a thing.

## Opening a space

1. **`sync.state()`** returns the cached manifest — spaces, screens, roles,
   custom fields, alerts, field levels.
2. **`resolve.visible`** narrows it to the spaces this reader may open: any of
   the four seats, or a space that declares no role at all.
3. **`resolve.navigable`** narrows one space's screens to the ones this reader
   can open. A screen naming no doctype has no grant to consult and stays; a
   screen whose doctype **no** seat grants also stays, because hiding it would
   turn a manifest mistake somebody can see into one nobody can.
4. **`_resolve(space, screen)`** resolves the screen against this site's own
   metadata: field labels, types, Select options, and what this person may do.

`_refuse_ungranted` makes two different refusals, because there are two reasons
and only one is a mistake: *not part of this space* and *part of it, and not of
your role in it*.

## A Single's page — `singles.py`

`page`, `save`, `run`. A space names a screen `"component": "single"` with a
`document_type` and a `fields` list, and this answers with the same
`columns`/`form` shape a record page is handed.

1. **`_screen`** looks the screen up in the manifest and refuses one that is
   not a `single` — a screen key arrives from the browser, so this is the gate.
2. **`_allowed`** asks the space's grant through `_refuse_ungranted`, then
   Frappe's own `read` or `write`.
3. **`columns_of`** is `_columns(meta, fields)`, so the writable fieldnames are
   the manifest's rather than the doctype's.
4. **`save`** writes a settings page. **`run`** calls the one method `VERBS`
   names for that doctype, after checking the document really is the class the
   path names, and never saves: a tool's document is used and dropped.

## Staying in sync — `sync.py`

The tenant's whole relationship with the control plane, on a schedule:

* `sync_permissions` writes DocPerms from the manifest, keeping the **wider** of
  two rows for one doctype. It used to keep the last, which made the answer
  depend on the order rows came out of a child table.
* `sync_field_levels` reconciles permlevels — the one fixture reconciled rather
  than seeded, because a permlevel is a security control.
* `_seed_alerts` writes the notification rules a space ships, **once each, keyed
  on the subject**, through the same door a workspace's own rules go through.
* `_reconcile_app_roles` adds and **removes** roles per user. Removal is the
  interesting half: somebody moved off Sales keeps selling until something takes
  the role away.
* `_space_role` composes `<prefix>-<Seat>` and returns nothing for a seat this
  site does not hold.

## The workspace's own settings — `workspace.py`, `tabs.py`, `me.py`

`workspace.py` is the parts of Frappe a customer owns; `tabs.py` is every tab in
the settings dialog and who each is for; `me.py` is what a person may change
about *themselves* as opposed to about the workspace, and its spec is the
allowlist.

## A space turned on and off — `spacelife.py`

What happens when an entitlement lands and when it is taken away.

## The clock

`expiry.py` walks documents that expire. `retention.py` is what a job book
keeps. `jobs.py` bounds background work by plan. `alerts.late_now`-style sweeps
belong to the spaces that declare them.
