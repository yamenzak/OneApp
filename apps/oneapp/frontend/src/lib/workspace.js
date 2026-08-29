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
    callMethod('oneapp.oneapp_core.workspace.save', { group, values }, {
      successMessage: 'Saved',
    }),

  books: () =>
    callMethod('oneapp.oneapp_core.books.status', {}, { silent: true, method: 'GET' }),

  charts: (country) =>
    callMethod('oneapp.oneapp_core.books.charts', { country }, {
      silent: true, method: 'GET',
    }),

  setUpBooks: (payload) =>
    callMethod('oneapp.oneapp_core.books.create', payload, {
      successMessage: 'Books are ready',
    }),
}
