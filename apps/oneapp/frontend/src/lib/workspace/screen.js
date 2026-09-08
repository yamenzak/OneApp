/** One screen: its spec, its rows, one record, and the link fields on it. */

import { callMethod } from '@/lib/runtime/resource'
import { __ } from '@/lib/runtime/translate'

export const screen = {
  // One screen, resolved against this site's own metadata: what each field is
  // called and whether this user may write it are facts only the tenant has.
  //
  // Rows and writes go through the screen too, rather than a generic document
  // API. That is what stops a screen being used to read a doctype the
  // entitlement did not include, or to write a field it does not show.
  screenSpec: (spaceCode, screen, layout, viewType) =>
    callMethod(
      'oneapp.onespace.spaceview.spec',
      { space_code: spaceCode, screen, layout, view_type: viewType },
      {
        silent: true,
        method: 'GET',
      },
    ),

  // `overrides` carries a filter or sort the person changed but has not saved.
  screenRows: (spaceCode, screen, overrides, layout, page = {}, viewType) =>
    callMethod(
      'oneapp.onespace.spaceview.rows',
      {
        space_code: spaceCode,
        screen,
        layout,
        view_type: viewType,
        // `start` pages; `limit` is how big a page is, which the reader picks
        // in the footer and the server bounds again.
        start: page.start || 0,
        limit: page.limit || undefined,
        // The days a calendar has on screen, applied to the screen's own date
        // field — a range that cannot name a column.
        //
        // Spread rather than set to `undefined`: `since=undefined` reaches the
        // server as the four-letter string, which is a date to nobody.
        ...(page.since && page.until ? { since: page.since, until: page.until } : {}),
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

  // Its own request, deliberately after the rows: a count over a filter with no
  // index behind it is a full scan.
  screenRowCount: (spaceCode, screen, overrides, layout, viewType) =>
    callMethod(
      'oneapp.onespace.spaceview.count',
      {
        space_code: spaceCode,
        screen,
        layout,
        view_type: viewType,
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

  // One change to a whole selection. POST because it writes, and each record is
  // saved on its own so what could not be saved comes back named.
  screenBulkSet: (spaceCode, screen, names, field, value) =>
    callMethod('oneapp.onespace.spaceview.bulk_set', {
      space_code: spaceCode,
      screen,
      names: JSON.stringify(names || []),
      field,
      value,
    }),

  // People added to the assignment on every record in a selection. Added and
  // never replaced — see `bulk_assign`.
  screenBulkAssign: (spaceCode, screen, names, users) =>
    callMethod('oneapp.onespace.spaceview.bulk_assign', {
      space_code: spaceCode,
      screen,
      names: JSON.stringify(names || []),
      users: JSON.stringify(users || []),
    }),

  // A whole selection moved one step of its docstatus. Not `bulk_set`: a submit
  // is not a save, and `docflow` is what a workflow's transition goes through.
  screenBulkSubmit: (spaceCode, screen, names) =>
    callMethod('oneapp.onespace.spaceview.bulk_submit', {
      space_code: spaceCode,
      screen,
      names: JSON.stringify(names || []),
    }),

  screenBulkCancel: (spaceCode, screen, names) =>
    callMethod('oneapp.onespace.spaceview.bulk_cancel', {
      space_code: spaceCode,
      screen,
      names: JSON.stringify(names || []),
    }),

  // What the money columns add up to. Its own request, for the reason the count
  // is one.
  screenTotals: (spaceCode, screen, overrides, layout, viewType) =>
    callMethod(
      'oneapp.onespace.spaceview.totals',
      {
        space_code: spaceCode,
        screen,
        layout,
        view_type: viewType,
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

  // How many records there are for each value of one field — Frappe's list
  // sidebar, as a menu. Under the same filters the rows are.
  screenTally: (spaceCode, screen, field, overrides, layout) =>
    callMethod(
      'oneapp.onespace.spaceview.tally',
      {
        space_code: spaceCode,
        screen,
        field,
        layout,
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

  // The same rows, as a file. Its own endpoint rather than a page size of five
  // thousand: the CSV is built on the server where the quoting is testable, and
  // `names` narrows it to a selection.
  screenExport: (spaceCode, screen, overrides, layout, viewType, names) =>
    callMethod(
      'oneapp.onespace.spaceview.export_rows',
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
  // see; the record shows the doctype's whole field list, which is also what
  // lets a record be a link somebody can send.
  screenRecord: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.onespace.spaceview.record',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  // What a copy of one record would start with. Values rather than a record: a
  // duplicate is a draft somebody is about to change. `copy_doc` on the server
  // decides what carries over.
  duplicateRecord: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.onespace.spaceview.duplicate',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  saveRecord: (spaceCode, screen, values, name) =>
    callMethod(
      'oneapp.onespace.spaceview.save',
      { space_code: spaceCode, screen, values, name },
      { successMessage: __('Saved') },
    ),

  // One call for a whole selection: forty rows is forty round trips otherwise,
  // and a failure halfway through leaves nobody able to say what happened.
  removeRecords: (spaceCode, screen, names) =>
    callMethod(
      'oneapp.onespace.spaceview.remove',
      { space_code: spaceCode, screen, name: names },
      { silent: true },
    ),

  // A Link is a foreign key, and a text box over one asks a customer to know a
  // record's name. Bounded by the screen like every other read.
  //
  // `target` is only meaningful for a Dynamic Link, whose doctype is on the
  // record rather than on the field; the server validates it against the
  // space's grant and ignores it for a plain Link.
  linkOptions: (spaceCode, screen, fieldname, query, target) =>
    callMethod(
      'oneapp.onespace.spaceview.link_options',
      { space_code: spaceCode, screen, fieldname, query, target },
      { silent: true, method: 'GET' },
    ),

  // What choosing that record fills in elsewhere on the form. `fetch_from`
  // already applies on save wherever the write came from, so this changes no
  // outcome — only when you see it. `silent`: if the lookup fails the field
  // stays as it was and the save still fills it.
  fetched: (spaceCode, screen, fieldname, value) =>
    callMethod(
      'oneapp.onespace.spaceview.fetched',
      { space_code: spaceCode, screen, fieldname, value },
      { silent: true, method: 'GET' },
    ),

  // What creating one of those records would ask for: Frappe's own quick entry.
  // Answers `can_create: false` rather than raising when the target is outside
  // the space — a picker with no Create row is the right shape for that.
  linkNewSpec: (spaceCode, screen, fieldname, target) =>
    callMethod(
      'oneapp.onespace.spaceview.link_new_spec',
      { space_code: spaceCode, screen, fieldname, target },
      { silent: true, method: 'GET' },
    ),

  // Create one, and hand back the picker row so the field can adopt the record
  // without a second search.
  linkNew: (spaceCode, screen, fieldname, values, target) =>
    callMethod(
      'oneapp.onespace.spaceview.link_new',
      { space_code: spaceCode, screen, fieldname, values, target },
      { successMessage: __('Created') },
    ),

  // Every named layout in a space, keyed by screen: the sidebar lists what each
  // screen can be looked at as before anybody has opened one.

  // A few facts about the record a link points at, for a card on hover. Which
  // facts is the target doctype's own answer — its `in_preview` fields.
  linkPreview: (spaceCode, screen, fieldname, name, target) =>
    callMethod(
      'oneapp.onespace.spaceview.link_preview',
      { space_code: spaceCode, screen, fieldname, name, target },
      { silent: true, method: 'GET' },
    ),

  // Comments and the change log. Frappe keeps both on every doctype, so no app
  // has to ask for them.

  // The numbers behind a screen's dashboard. Its own call rather than part of
  // the spec, which is read on every navigation.
  dashboard: (spaceCode, screen, { layout = '', overrides = null } = {}) =>
    callMethod(
      'oneapp.onespace.spaceview.dashboard_data',
      {
        space_code: spaceCode,
        screen,
        layout: layout || undefined,
        overrides: overrides ? JSON.stringify(overrides) : undefined,
      },
      { silent: true, method: 'GET' },
    ),

  // --- mail ---------------------------------------------------------------
  // Addresses, who holds each, and what they sign with. The model is Frappe's
  // Email Account and User Email, so none of this is a parallel permission
  // system. See `onemail/addresses.py`.
}
