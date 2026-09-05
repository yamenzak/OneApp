/**
 * Spreadsheets: the grid a `File` could not hold.
 *
 * A sheet's identity is a File row, so everything about *the file* — rename,
 * move, share, trash, the expiring link — goes through `drive.js` and none of
 * it is repeated here. What is here is the workbook: loading one, saving one,
 * templates, and the read-back that fills a document's child table from a
 * named rectangle. See `oneapp_core/sheets`.
 *
 * Two calls carry the grid, and that is the whole protocol. The editor is
 * Frappe's (`lib/sheets/VENDORED.md`) and holds the entire workbook in memory,
 * so there is nothing smaller to send: no cell endpoint, no tab endpoint, no
 * range endpoint. `lib/sheets/store.js` is what actually calls these two, over
 * plain `fetch` rather than through here, because a save has to survive the
 * page being closed and `useCall` cannot do `keepalive`.
 */

import { callMethod } from '../resource'

export const sheets = {
  sheetMake: (params) =>
    callMethod('oneapp.oneapp_core.sheets.make', params, {
      success: 'Sheet created',
    }),

  sheetTemplates: () =>
    callMethod('oneapp.oneapp_core.sheets.listing', {}, { silent: true, method: 'GET' }),

  sheetSetTemplate: (name, on) =>
    callMethod('oneapp.oneapp_core.sheets.set_template', { sheet: name, on: on ? 1 : 0 }),

  // The read-back. `preview` says what would happen; `pull` does it. Two calls
  // rather than one with a flag, because the confirmation step is the whole
  // point — a pull replaces the child table, and replacing somebody's priced
  // line items with the wrong range is not an undo away.
  sheetPreview: (name, params) =>
    callMethod('oneapp.oneapp_core.sheets.preview', { sheet: name, ...params }, {
      silent: true, method: 'GET',
    }),

  // Where a document's rows came from. Its own call rather than a field on the
  // record, because `Sheet Feed` is ours and the document is somebody else's
  // doctype — this product does not add columns to Frappe's Quotation.
  sheetFeeds: (doctype, docname) =>
    callMethod('oneapp.oneapp_core.sheets.feeds', { doctype, docname }, {
      silent: true, method: 'GET',
    }),

  sheetLock: (doctype, docname, into) =>
    callMethod('oneapp.oneapp_core.sheets.lock', { doctype, docname, into }, {
      success: 'These rows are locked',
    }),

  sheetUnlock: (doctype, docname, into) =>
    callMethod('oneapp.oneapp_core.sheets.unlock', { doctype, docname, into }, {
      success: 'Following the sheet again',
    }),

  sheetPull: (name, params) =>
    callMethod('oneapp.oneapp_core.sheets.pull', { sheet: name, ...params }, {
      success: 'Filled from the sheet',
    }),
}
