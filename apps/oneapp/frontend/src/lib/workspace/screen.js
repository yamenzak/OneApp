/** One screen: its spec, its rows, one record, and the link fields on it. */

import { callMethod } from '../resource'

export const screen = {
  // One screen, resolved against this site's own metadata: what each field is
  // called and whether this user may write it are facts only the tenant has.
  //
  // Rows and writes go through the screen too, rather than a generic document
  // API. That is what stops a screen being used to read a doctype the
  // entitlement did not include, or to write a field it does not show.
  screenSpec: (spaceCode, screen, layout, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.spec',
      { space_code: spaceCode, screen, layout, view_type: viewType },
      {
        silent: true,
        method: 'GET',
      },
    ),

  // `overrides` carries a filter or sort the person changed but has not saved:
  // the list answers the question the controls are asking, saved or not.

  // `overrides` carries a filter or sort the person changed but has not saved:
  // the list answers the question the controls are asking, saved or not.
  screenRows: (spaceCode, screen, overrides, layout, page = {}, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.rows',
      {
        space_code: spaceCode,
        screen,
        layout,
        view_type: viewType,
        // `start` pages; `limit` is how big a page is, which the reader picks
        // in the footer and the server bounds again.
        start: page.start || 0,
        limit: page.limit || undefined,
        // The days a calendar has on screen. The server applies them to the
        // screen's own date field, so these two are the whole of it — a range
        // that cannot name a column.
        //
        // Spread rather than set to `undefined`: the key is serialised either
        // way, and `since=undefined` reaches the server as the four-letter
        // string, which is a date to nobody.
        ...(page.since && page.until ? { since: page.since, until: page.until } : {}),
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

  // Its own request, and deliberately after the rows: a count over a filter
  // with no index behind it is a full scan, and nothing should hold a list up
  // for one.

  // Its own request, and deliberately after the rows: a count over a filter
  // with no index behind it is a full scan, and nothing should hold a list up
  // for one.
  screenRowCount: (spaceCode, screen, overrides, layout, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.count',
      {
        space_code: spaceCode,
        screen,
        layout,
        view_type: viewType,
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

  // What the money columns add up to. Its own request for the reason the count
  // is one: an aggregate over the whole filter, which nothing should wait for.
  screenTotals: (spaceCode, screen, overrides, layout, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.totals',
      {
        space_code: spaceCode,
        screen,
        layout,
        view_type: viewType,
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

  // The same rows, as a file. Its own endpoint rather than a page size of five
  // thousand: an export is the whole answer, it is built as a CSV on the server
  // where the quoting is testable, and `names` narrows it to a selection so
  // "export this list" and "export the four I ticked" are one path.
  screenExport: (spaceCode, screen, overrides, layout, viewType, names) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.export_rows',
      {
        space_code: spaceCode,
        screen,
        layout,
        view_type: viewType,
        overrides: overrides ? JSON.stringify(overrides) : null,
        names: names?.length ? JSON.stringify(names) : null,
      },
      { method: 'GET' },
    ),

  // One record, by id. The list row carries only the columns somebody chose to
  // see; the record shows the doctype's whole field list, so it is fetched
  // rather than read out of the row — which is also what lets a record be a
  // link somebody can send.

  // One record, by id. The list row carries only the columns somebody chose to
  // see; the record shows the doctype's whole field list, so it is fetched
  // rather than read out of the row — which is also what lets a record be a
  // link somebody can send.
  screenRecord: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.record',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  saveRecord: (spaceCode, screen, values, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.save',
      { space_code: spaceCode, screen, values, name },
      { successMessage: 'Saved' },
    ),

  // One call for a whole selection: forty rows is forty round trips otherwise,
  // and a failure halfway through leaves nobody able to say what happened.

  // One call for a whole selection: forty rows is forty round trips otherwise,
  // and a failure halfway through leaves nobody able to say what happened.
  removeRecords: (spaceCode, screen, names) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.remove',
      { space_code: spaceCode, screen, name: names },
      { silent: true },
    ),

  // A Link is a foreign key, and a text box over one asks a customer to know a
  // record's name. Bounded by the screen like every other read.
  //
  // `target` is only meaningful for a Dynamic Link, whose doctype is on the
  // record rather than on the field. The server validates it against the
  // space's grant and this user's permissions before fetching anything, and
  // ignores it for a plain Link.

  // A Link is a foreign key, and a text box over one asks a customer to know a
  // record's name. Bounded by the screen like every other read.
  //
  // `target` is only meaningful for a Dynamic Link, whose doctype is on the
  // record rather than on the field. The server validates it against the
  // space's grant and this user's permissions before fetching anything, and
  // ignores it for a plain Link.
  linkOptions: (spaceCode, screen, fieldname, query, target) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.link_options',
      { space_code: spaceCode, screen, fieldname, query, target },
      { silent: true, method: 'GET' },
    ),

  // What choosing that record fills in elsewhere on the form.
  //
  // Frappe's `fetch_from` already applies on save, wherever the write came
  // from, so this changes no outcome — only when you see it. Without it the
  // Company box sits empty, somebody types into it, and the save quietly
  // replaces what they typed with the value it was always going to use.
  //
  // `silent`, because a form that fills itself in is a convenience: if the
  // lookup fails the field stays as it was and the save still fills it, which
  // is the behaviour that existed before this call did.

  // What choosing that record fills in elsewhere on the form.
  //
  // Frappe's `fetch_from` already applies on save, wherever the write came
  // from, so this changes no outcome — only when you see it. Without it the
  // Company box sits empty, somebody types into it, and the save quietly
  // replaces what they typed with the value it was always going to use.
  //
  // `silent`, because a form that fills itself in is a convenience: if the
  // lookup fails the field stays as it was and the save still fills it, which
  // is the behaviour that existed before this call did.
  fetched: (spaceCode, screen, fieldname, value) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.fetched',
      { space_code: spaceCode, screen, fieldname, value },
      { silent: true, method: 'GET' },
    ),

  // What creating one of those records would ask for: Frappe's own quick entry,
  // which is the fields a doctype marks `allow_in_quick_entry` plus anything
  // mandatory. Answers `can_create: false` rather than raising when the target
  // is outside the space or this user may not create it — a picker with no
  // Create row is the right shape for that.

  // What creating one of those records would ask for: Frappe's own quick entry,
  // which is the fields a doctype marks `allow_in_quick_entry` plus anything
  // mandatory. Answers `can_create: false` rather than raising when the target
  // is outside the space or this user may not create it — a picker with no
  // Create row is the right shape for that.
  linkNewSpec: (spaceCode, screen, fieldname, target) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.link_new_spec',
      { space_code: spaceCode, screen, fieldname, target },
      { silent: true, method: 'GET' },
    ),

  // Create one, and hand back the picker row for it so the field can adopt the
  // record without a second search.

  // Create one, and hand back the picker row for it so the field can adopt the
  // record without a second search.
  linkNew: (spaceCode, screen, fieldname, values, target) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.link_new',
      { space_code: spaceCode, screen, fieldname, values, target },
      { successMessage: 'Created' },
    ),

  // Every named layout in a space, keyed by screen. The sidebar's question:
  // it lists what each screen can be looked at as before anybody has opened
  // one, and asking a spec per screen to draw a menu is a request per item.

  // A few facts about the record a link points at, for a card on hover. Which
  // facts is the target doctype's own answer — its `in_preview` fields — so no
  // manifest chooses them and every screen pointing at that doctype agrees.
  linkPreview: (spaceCode, screen, fieldname, name, target) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.link_preview',
      { space_code: spaceCode, screen, fieldname, name, target },
      { silent: true, method: 'GET' },
    ),

  // Comments and the change log. Frappe keeps both on every doctype, so no app
  // has to ask for them.

  // The numbers behind a screen's dashboard. Its own call rather than part of
  // the spec: a spec is read on every navigation and this is one aggregate
  // query per widget.
  dashboard: (spaceCode, screen, { layout = '', overrides = null } = {}) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.dashboard_data',
      {
        space_code: spaceCode,
        screen,
        layout: layout || undefined,
        overrides: overrides ? JSON.stringify(overrides) : undefined,
      },
      { silent: true, method: 'GET' },
    ),

  // --- mail ---------------------------------------------------------------
  // Addresses, who holds each, and what they sign with. See
  // `oneapp_core/email/addresses.py` — the model is Frappe's Email Account and
  // User Email, so none of this is a parallel permission system.
}
