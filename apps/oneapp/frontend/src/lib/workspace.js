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
  // Rows and writes go through the view too, rather than a generic document
  // API. That is what stops a screen being used to read a doctype the
  // entitlement did not include, or to write a field it does not show.
  appView: (appCode, view) =>
    callMethod(
      'oneapp.oneapp_core.appview.spec',
      { app_code: appCode, view },
      {
        silent: true,
        method: 'GET',
      },
    ),

  // `overrides` carries a filter or sort the person changed but has not saved:
  // the list answers the question the controls are asking, saved or not.
  appRows: (appCode, view, overrides) =>
    callMethod(
      'oneapp.oneapp_core.appview.rows',
      { app_code: appCode, view, overrides: overrides ? JSON.stringify(overrides) : null },
      { silent: true, method: 'GET' },
    ),

  saveAppRecord: (appCode, view, values, name) =>
    callMethod(
      'oneapp.oneapp_core.appview.save',
      { app_code: appCode, view, values, name },
      { successMessage: 'Saved' },
    ),

  // One call for a whole selection: forty rows is forty round trips otherwise,
  // and a failure halfway through leaves nobody able to say what happened.
  removeAppRecords: (appCode, view, names) =>
    callMethod(
      'oneapp.oneapp_core.appview.remove',
      { app_code: appCode, view, name: names },
      { silent: true },
    ),

  // A Link is a foreign key, and a text box over one asks a customer to know a
  // record's name. Bounded by the screen like every other read.
  linkOptions: (appCode, view, fieldname, query) =>
    callMethod(
      'oneapp.oneapp_core.appview.link_options',
      { app_code: appCode, view, fieldname, query },
      { silent: true, method: 'GET' },
    ),

  // Comments and the change log. Frappe keeps both on every doctype, so no app
  // has to ask for them.
  timeline: (appCode, view, name) =>
    callMethod(
      'oneapp.oneapp_core.appview.timeline',
      { app_code: appCode, view, name },
      { silent: true, method: 'GET' },
    ),

  comment: (appCode, view, name, content) =>
    callMethod(
      'oneapp.oneapp_core.appview.comment',
      { app_code: appCode, view, name, content },
      { successMessage: 'Added' },
    ),

  toggleLike: (appCode, view, name) =>
    callMethod(
      'oneapp.oneapp_core.appview.toggle_like',
      { app_code: appCode, view, name },
      { silent: true },
    ),

  // How this person likes this screen: filters, sort and columns, restored when
  // they come back. Narrows what the screen offers; never widens it.
  saveView: (appCode, view, payload) =>
    callMethod(
      'oneapp.oneapp_core.appview.save_view',
      { app_code: appCode, view, ...payload },
      { successMessage: 'View saved' },
    ),

  resetView: (appCode, view) =>
    callMethod(
      'oneapp.oneapp_core.appview.reset_view',
      { app_code: appCode, view },
      { successMessage: 'Back to the default view' },
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
