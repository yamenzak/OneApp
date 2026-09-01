/**
 * Workspace settings: the parts of Frappe a customer owns.
 *
 * The field list is not written here. The server owns the spec — which setting
 * exists, what type it is, and which of Frappe's singles it writes — because
 * that same object is the allowlist the write path checks against. A copy in
 * the SPA would be a second list to keep in step, and the one that drifts is
 * always the one that decides what is rendered.
 */

import { callMethod } from './resource'

export const workspace = {
  settings: () =>
    callMethod('oneapp.oneapp_core.workspace.get', {}, { silent: true, method: 'GET' }),

  save: (group, values) =>
    callMethod(
      'oneapp.oneapp_core.workspace.save',
      { group, values },
      {
        successMessage: 'Saved',
      },
    ),

  // The AI tab is not a field list like the rest: it is the feature registry
  // rendered, so the server sends rows rather than a spec. What it never sends
  // is our own instructions for a feature — only what the workspace added.
  ai: () => callMethod('oneapp.oneapp_core.ai.settings.get', {}, { silent: true, method: 'GET' }),

  saveAi: (values) =>
    callMethod(
      'oneapp.oneapp_core.ai.settings.update',
      { values },
      {
        successMessage: 'Saved',
      },
    ),

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
        overrides: overrides ? JSON.stringify(overrides) : null,
      },
      { silent: true, method: 'GET' },
    ),

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
  linkNewSpec: (spaceCode, screen, fieldname, target) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.link_new_spec',
      { space_code: spaceCode, screen, fieldname, target },
      { silent: true, method: 'GET' },
    ),

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
  spaceLayouts: (spaceCode) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.space_layouts',
      { space_code: spaceCode },
      { silent: true, method: 'GET' },
    ),

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
  timeline: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.timeline',
      { space_code: spaceCode, screen, name },
      { silent: true, method: 'GET' },
    ),

  comment: (spaceCode, screen, name, content) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.comment',
      { space_code: spaceCode, screen, name, content },
      { successMessage: 'Added' },
    ),

  // Who a record is assigned to, and who it could be.
  //
  // Frappe's own model: `_assign` is a list of user ids on the document and a
  // ToDo sits beside each one, so assigning is how a record reaches somebody's
  // own list rather than only somebody's avatar. Both halves are the server's
  // — this sends a set of people and reads back what the document ended up
  // holding.
  assignees: (spaceCode, screen, query) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.assignees',
      { space_code: spaceCode, screen, query },
      { silent: true, method: 'GET' },
    ),

  assign: (spaceCode, screen, name, users) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.assign',
      { space_code: spaceCode, screen, name, users },
      { silent: true },
    ),

  toggleLike: (spaceCode, screen, name) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.toggle_like',
      { space_code: spaceCode, screen, name },
      { silent: true },
    ),

  // Follow this record, or stop. Not silent: unlike a like, nothing on the
  // screen changes to prove it worked — the whole result is a notification
  // that has not happened yet — so the toast is the confirmation.
  toggleFollow: (spaceCode, screen, name) =>
    callMethod('oneapp.oneapp_core.spaceview.toggle_follow', {
      space_code: spaceCode,
      screen,
      name,
    }),

  // What is filed against a record. Frappe's own File rows, so a file uploaded
  // through an Attach field and a file dropped on the record are one list.
  // `fieldname` narrows the list to one Attachment Gallery's share of them,
  // by the `link_filters` on that docfield. The filter is read off the field
  // server-side rather than sent from here, so this only names which field is
  // asking.
  attachments: (spaceCode, screen, name, fieldname) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.attachments',
      { space_code: spaceCode, screen, name, fieldname },
      { silent: true, method: 'GET' },
    ),

  removeAttachment: (spaceCode, screen, name, file) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.remove_attachment',
      { space_code: spaceCode, screen, name, file },
      { successMessage: 'File removed' },
    ),

  // A layout: the filters, the sort and the columns saved together under a
  // name, the way Frappe's own List Filter doctype models it. `layout` updates
  // one, `label` makes a new one, neither writes this person's unnamed default
  // — the Save button on the toolbar.
  //
  // Narrows what the screen offers; never widens it, shared or not.
  saveLayout: (spaceCode, screen, payload) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.save_layout',
      { space_code: spaceCode, screen, ...payload },
      { successMessage: 'View saved' },
    ),

  deleteLayout: (spaceCode, screen, layout) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.delete_layout',
      { space_code: spaceCode, screen, layout },
      { successMessage: 'View deleted' },
    ),

  // Not a delete. A shared view belongs to the workspace and somebody else may
  // be living in it — this says only that one reader would rather not see it.
  hideLayout: (spaceCode, screen, layout) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.hide_layout',
      { space_code: spaceCode, screen, layout },
      { successMessage: 'Hidden from your menu' },
    ),

  showLayouts: (spaceCode, screen) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.show_layouts',
      { space_code: spaceCode, screen },
      { successMessage: 'Hidden views are back' },
    ),

  defaultLayout: (spaceCode, screen, layout) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.default_layout',
      { space_code: spaceCode, screen, layout },
      { successMessage: 'This opens the screen now' },
    ),

  // The view type goes with it: a screen has one unnamed default per way of
  // looking at it, and "undo my tinkering" on the board is not a decision about
  // the list.
  resetLayout: (spaceCode, screen, viewType) =>
    callMethod(
      'oneapp.oneapp_core.spaceview.reset_layout',
      { space_code: spaceCode, screen, view_type: viewType || undefined },
      { successMessage: 'Back to the default screen' },
    ),

  books: () => callMethod('oneapp.oneapp_core.books.status', {}, { silent: true, method: 'GET' }),

  charts: (country) =>
    callMethod(
      'oneapp.oneapp_core.books.charts',
      { country },
      {
        silent: true,
        method: 'GET',
      },
    ),

  resetBooks: () =>
    callMethod(
      'oneapp.oneapp_core.books.reset',
      {},
      {
        successMessage: 'Cleared — set your books up again below',
      },
    ),

  setUpBooks: (payload) =>
    callMethod('oneapp.oneapp_core.books.create', payload, {
      successMessage: 'Books are ready',
    }),
}
