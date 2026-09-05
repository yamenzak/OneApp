/**
 * Spreadsheets: the grid a `File` could not hold.
 *
 * A sheet's identity is a File row, so everything about *the file* — rename,
 * move, share, trash, the expiring link — goes through `drive.js` and none of
 * it is repeated here. What is here is the grid: opening one, writing cells,
 * tabs, named ranges, and the read-back that fills a document's child table
 * from a named rectangle. See `oneapp_core/sheets`.
 */

import { callMethod } from '../resource'

export const sheets = {
  // Everything in one request: tabs, cells and ranges. A sheet is not usable
  // until all three have arrived, so three requests would be three chances to
  // paint a half-built grid.
  sheetOpen: (name) =>
    callMethod('oneapp.oneapp_core.sheets.open_sheet', { sheet: name }, {
      silent: true, method: 'GET',
    }),

  sheetMake: (params) =>
    callMethod('oneapp.oneapp_core.sheets.make', params, {
      success: 'Sheet created',
    }),

  // A batch, because a paste is a batch. `cells` is the list the engine handed
  // back — what changed, not what was typed.
  sheetWrite: (name, cells) =>
    callMethod(
      'oneapp.oneapp_core.sheets.write_cells',
      { sheet: name, cells: JSON.stringify(cells) },
      { silent: true },
    ),

  sheetAddTab: (name, tabName) =>
    callMethod('oneapp.oneapp_core.sheets.add_tab', { sheet: name, tab_name: tabName }),

  sheetRenameTab: (name, tab, tabName) =>
    callMethod('oneapp.oneapp_core.sheets.rename_tab', {
      sheet: name, tab, tab_name: tabName,
    }),

  sheetRemoveTab: (name, tab) =>
    callMethod('oneapp.oneapp_core.sheets.remove_tab', { sheet: name, tab }),

  sheetTabGeometry: (name, tab, geometry) =>
    callMethod(
      'oneapp.oneapp_core.sheets.set_tab_geometry',
      { sheet: name, tab, ...geometry },
      { silent: true },
    ),

  sheetSetRange: (name, { label, tab, ref }) =>
    callMethod('oneapp.oneapp_core.sheets.set_range', { sheet: name, label, tab, ref }, {
      success: 'Range named',
    }),

  sheetRemoveRange: (name, label) =>
    callMethod('oneapp.oneapp_core.sheets.remove_range', { sheet: name, label }),

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
