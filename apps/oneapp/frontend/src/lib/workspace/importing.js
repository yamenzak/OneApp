/** Bringing another Frappe site's records across. */

import { callMethod } from '../resource'

export const importing = {
  // --- bringing their data with them ------------------------------------
  //
  // See `oneapp_core/importer.py`. The panel is one read and two buttons; the
  // rest of this is watching a job somebody else is running.
  importConsole: () =>
    callMethod('oneapp.oneapp_core.importer.console', {}, { silent: true, method: 'GET' }),

  saveImportSource: (name, baseUrl, apiKey, apiSecret) =>
    callMethod(
      'oneapp.oneapp_core.importer.save_source',
      { name, base_url: baseUrl, api_key: apiKey, api_secret: apiSecret },
      { successMessage: 'Saved' },
    ),

  installImportPlan: (plan, source) =>
    callMethod(
      'oneapp.oneapp_core.importer.install_plan',
      { plan, source },
      { successMessage: 'Set up' },
    ),

  verifyImportSource: (source) =>
    callMethod('oneapp.oneapp_core.importer.verify', { source }, { silent: true }),

  checkImportPlan: (plan) =>
    callMethod('oneapp.oneapp_core.importer.check', { plan }, { silent: true }),

  startImport: (plan, dryRun) =>
    callMethod('oneapp.oneapp_core.importer.start', { plan, dry_run: dryRun ? 1 : 0 }),

  importProgress: (run) =>
    callMethod('oneapp.oneapp_core.importer.progress', { run },
               { silent: true, method: 'GET' }),

  importIssues: (run) =>
    callMethod('oneapp.oneapp_core.importer.issues', { run }, { silent: true, method: 'GET' }),

  // --- printing ---------------------------------------------------------
  //
  // Frappe renders the format and Frappe makes the PDF; these are the screen's
  // own gate over both. See `oneapp_core/printing.py`.
}
