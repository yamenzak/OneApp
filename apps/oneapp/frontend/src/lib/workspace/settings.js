/** The parts of Frappe a workspace owns: its own settings, its books, its naming. */

import { callMethod } from '../resource'

export const settings = {
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

  // --- alerts ---------------------------------------------------------------
  //
  // "Tell the accounts role when an invoice is three days past due." Frappe's
  // own `Notification`, gated to this workspace's doctypes and narrowed to the
  // sentence somebody would say out loud — see `oneapp_core/alerts.py`.
  alerts: () =>
    callMethod('oneapp.oneapp_core.workspace.alerts', {}, { silent: true, method: 'GET' }),

  saveAlert: (values) =>
    callMethod(
      'oneapp.oneapp_core.workspace.save_alert',
      { values: JSON.stringify(values) },
      { successMessage: 'Alert saved' },
    ),

  setAlertEnabled: (name, enabled) =>
    callMethod(
      'oneapp.oneapp_core.workspace.set_alert_enabled',
      { name, enabled: enabled ? 1 : 0 },
      { silent: true },
    ),

  removeAlert: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.remove_alert',
      { name },
      { successMessage: 'Alert removed' },
    ),

  // Message templates: written here, used in the composer. The listing is the
  // same endpoint the composer reads — one list, not an admin copy of it.
  saveMailTemplate: (values) =>
    callMethod(
      'oneapp.oneapp_core.workspace.save_mail_template',
      { values: JSON.stringify(values) },
      { successMessage: 'Template saved' },
    ),

  removeMailTemplate: (name) =>
    callMethod(
      'oneapp.oneapp_core.workspace.remove_mail_template',
      { name },
      { successMessage: 'Template removed' },
    ),

  naming: () =>
    callMethod('oneapp.oneapp_core.workspace.naming', {}, { silent: true, method: 'GET' }),

  setNaming: (doctype, series) =>
    callMethod(
      'oneapp.oneapp_core.workspace.set_naming',
      { doctype, series: JSON.stringify(series) },
      { successMessage: 'Series saved' },
    ),

  setNamingCounter: (doctype, prefix, value) =>
    callMethod(
      'oneapp.oneapp_core.workspace.set_naming_counter',
      { doctype, prefix, value },
      { successMessage: 'Counter moved' },
    ),

  namingPreview: (doctype, prefix) =>
    callMethod(
      'oneapp.oneapp_core.workspace.naming_preview',
      { doctype, prefix },
      { silent: true, method: 'GET' },
    ),

  // --- bringing their data with them ------------------------------------
  //
  // See `oneapp_core/importer.py`. The panel is one read and two buttons; the
  // rest of this is watching a job somebody else is running.
}
