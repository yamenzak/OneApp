/**
 * Spreadsheets: the grid a `File` could not hold.
 *
 * A sheet's identity is a File row, so everything about *the file* — rename,
 * move, share, trash, the expiring link — goes through `drive.js` and none of
 * it is repeated here. What is here is the workbook: loading one, saving one,
 * templates, and the read-back that fills a document's child table from a
 * named rectangle. See `onesheet`.
 *
 * Two calls carry the grid, and that is the whole protocol. The editor is
 * Frappe's (`lib/sheets/VENDORED.md`) and holds the entire workbook in memory,
 * so there is nothing smaller to send: no cell endpoint, no tab endpoint, no
 * range endpoint. `lib/sheets/store.js` is what actually calls these two, over
 * plain `fetch` rather than through here, because a save has to survive the
 * page being closed and `useCall` cannot do `keepalive`.
 */

import { callMethod } from '@/shared/lib/runtime/resource'

export const sheets = {
  sheetMake: (params) =>
    callMethod('oneapp.onesheet.make', params, {
      success: 'Sheet created',
    }),

  // The contract, and nothing else about the sheet. A record's fill control
  // wants four labels, not the workbook.
  sheetRanges: (name) =>
    callMethod('oneapp.onesheet.named_ranges', { sheet: name }, {
      silent: true, method: 'GET',
    }),

  // Printing. The whole page comes back as one string and goes into a frame —
  // `lib/paper/print.js` says why, and `onesheet/printing.py` is what
  // turns a rectangle of values into it. POST because the options are a body.
  sheetPrintable: (name, options, setup) =>
    callMethod(
      'oneapp.onesheet.printable',
      { name, options: JSON.stringify(options || {}), setup: JSON.stringify(setup || {}) },
      { silent: true },
    ),

  sheetTemplates: () =>
    callMethod('oneapp.onesheet.listing', {}, { silent: true, method: 'GET' }),

  sheetSetTemplate: (name, on) =>
    callMethod('oneapp.onesheet.set_template', { sheet: name, on: on ? 1 : 0 }),

  // The read-back. `preview` says what would happen; `pull` does it. Two calls
  // rather than one with a flag, because the confirmation step is the whole
  // point — a pull replaces the child table, and replacing somebody's priced
  // line items with the wrong range is not an undo away.
  sheetPreview: (name, params) =>
    callMethod('oneapp.onesheet.preview', { sheet: name, ...params }, {
      silent: true, method: 'GET',
    }),

  // Where a document's rows came from. Its own call rather than a field on the
  // record, because `Sheet Feed` is ours and the document is somebody else's
  // doctype — this product does not add columns to Frappe's Quotation.
  sheetFeeds: (doctype, docname) =>
    callMethod('oneapp.onesheet.feeds', { doctype, docname }, {
      silent: true, method: 'GET',
    }),

  sheetLock: (doctype, docname, into) =>
    callMethod('oneapp.onesheet.lock', { doctype, docname, into }, {
      success: 'These rows are locked',
    }),

  sheetUnlock: (doctype, docname, into) =>
    callMethod('oneapp.onesheet.unlock', { doctype, docname, into }, {
      success: 'Following the sheet again',
    }),

  // The outward leg: these rows become a sheet, headings and named range and
  // all, so pulling them back needs nothing set up by hand. Pressing it again
  // opens the same sheet — one estimator per table, not one per press.
  sheetFromTable: (params) =>
    callMethod('oneapp.onesheet.start_from', params, { silent: true }),

  // Which record and table this sheet feeds, so the estimator can send the
  // rows back without walking to the record to press a button there.
  sheetBoundTo: (name) =>
    callMethod('oneapp.onesheet.bound_to', { sheet: name }, {
      silent: true, method: 'GET',
    }),

  // --- a record a workbook reads ------------------------------------------
  // The other direction from `sheetPull`: `bound_to` says which table this
  // sheet *feeds*, these say which record it *reads*. See `onesheet/records.py`.

  // Every record the workbook's formulas name, in one request. One call and
  // not one per cell — a schedule of forty `RECORD()` rows would otherwise be
  // forty round trips on every open.
  sheetRecordFields: (name, asks) =>
    callMethod('oneapp.onesheet.record_fields', {
      sheet: name, asks: JSON.stringify(asks || []),
    }, { silent: true }),

  sheetPull: (name, params) =>
    callMethod('oneapp.onesheet.pull', { sheet: name, ...params }, {
      success: 'Filled from the sheet',
    }),
}
