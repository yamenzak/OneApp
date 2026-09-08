/** The parts of Frappe a workspace owns: its own settings, its books, its naming. */

import { callMethod } from '@/shared/lib/runtime/resource'
import { __ } from '@/shared/lib/runtime/translate'

export const settings = {
  // --- Yours, not the workspace's -----------------------------------------
  //
  // `onespace/me.py`. Every one of these names no user: the server writes
  // `frappe.session.user` and nothing else, so there is no shape of request
  // that edits a colleague.
  profile: () =>
    callMethod('oneapp.onespace.me.profile', {}, { silent: true, method: 'GET' }),

  saveProfile: (values) =>
    callMethod('oneapp.onespace.me.save_profile', { values }, {
      success: __('Profile saved'),
    }),

  security: () =>
    callMethod('oneapp.onespace.me.security', {}, { silent: true, method: 'GET' }),

  // Not silent and not toasted: the panel shows the refusal in the form, which
  // is where the correction has to be made.
  changePassword: (oldPassword, newPassword) =>
    callMethod('oneapp.onespace.me.change_password', {
      old_password: oldPassword, new_password: newPassword,
    }, { success: __('Password changed') }),

  endOtherSessions: () =>
    callMethod('oneapp.onespace.me.end_other_sessions', {}, {
      success: __('Signed out everywhere else'),
    }),


  settings: () =>
    callMethod('oneapp.onespace.workspace.get', {}, { silent: true, method: 'GET' }),

  save: (group, values) =>
    callMethod(
      'oneapp.onespace.workspace.save',
      { group, values },
      {
        successMessage: __('Saved'),
      },
    ),

  // The AI tab is not a field list like the rest: it is the feature registry
  // rendered, so the server sends rows rather than a spec. What it never sends
  // is our own instructions for a feature — only what the workspace added.
  ai: () => callMethod('oneapp.onespace.ai.settings.get', {}, { silent: true, method: 'GET' }),

  saveAi: (values) =>
    callMethod(
      'oneapp.onespace.ai.settings.update',
      { values },
      {
        successMessage: __('Saved'),
      },
    ),

  // One screen, resolved against this site's own metadata: what each field is
  // called and whether this user may write it are facts only the tenant has.
  //
  // Rows and writes go through the screen too, rather than a generic document
  // API. That is what stops a screen being used to read a doctype the
  // entitlement did not include, or to write a field it does not show.

  books: () => callMethod('oneapp.onespace.books.status', {}, { silent: true, method: 'GET' }),

  charts: (country) =>
    callMethod(
      'oneapp.onespace.books.charts',
      { country },
      {
        silent: true,
        method: 'GET',
      },
    ),

  resetBooks: () =>
    callMethod(
      'oneapp.onespace.books.reset',
      {},
      {
        successMessage: __('Books cleared'),
      },
    ),

  setUpBooks: (payload) =>
    callMethod('oneapp.onespace.books.create', payload, {
      successMessage: __('Books are ready'),
    }),

  // --- alerts ---------------------------------------------------------------
  //
  // "Tell the accounts role when an invoice is three days past due." Frappe's
  // own `Notification`, gated to this workspace's doctypes and narrowed to the
  // sentence somebody would say out loud — see `onespace/alerts.py`.
  alerts: () =>
    callMethod('oneapp.onespace.workspace.alerts', {}, { silent: true, method: 'GET' }),

  saveAlert: (values) =>
    callMethod(
      'oneapp.onespace.workspace.save_alert',
      { values: JSON.stringify(values) },
      { successMessage: __('Alert saved') },
    ),

  setAlertEnabled: (name, enabled) =>
    callMethod(
      'oneapp.onespace.workspace.set_alert_enabled',
      { name, enabled: enabled ? 1 : 0 },
      { silent: true },
    ),

  removeAlert: (name) =>
    callMethod(
      'oneapp.onespace.workspace.remove_alert',
      { name },
      { successMessage: __('Alert removed') },
    ),

  // Message templates: written here, used in the composer. The listing is the
  // same endpoint the composer reads — one list, not an admin copy of it.
  saveMailTemplate: (values) =>
    callMethod(
      'oneapp.onespace.workspace.save_mail_template',
      { values: JSON.stringify(values) },
      { successMessage: __('Template saved') },
    ),

  removeMailTemplate: (name) =>
    callMethod(
      'oneapp.onespace.workspace.remove_mail_template',
      { name },
      { successMessage: __('Template removed') },
    ),

  naming: () =>
    callMethod('oneapp.onespace.workspace.naming', {}, { silent: true, method: 'GET' }),

  setNaming: (doctype, series) =>
    callMethod(
      'oneapp.onespace.workspace.set_naming',
      { doctype, series: JSON.stringify(series) },
      { successMessage: __('Series saved') },
    ),

  setNamingCounter: (doctype, prefix, value) =>
    callMethod(
      'oneapp.onespace.workspace.set_naming_counter',
      { doctype, prefix, value },
      { successMessage: __('Counter moved') },
    ),

  namingPreview: (doctype, prefix) =>
    callMethod(
      'oneapp.onespace.workspace.naming_preview',
      { doctype, prefix },
      { silent: true, method: 'GET' },
    ),

  // --- bringing their data with them ------------------------------------
  //
  // See `onespace/importer.py`. The panel is one read and two buttons; the
  // rest of this is watching a job somebody else is running.
}
