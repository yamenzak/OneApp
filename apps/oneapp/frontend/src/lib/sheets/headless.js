/**
 * A workbook built without a grid on screen.
 *
 * The Drive can import a spreadsheet without opening one: pick a file, get a
 * sheet. That used to be a parser of ours writing cells through a cell
 * endpoint, and there is no cell endpoint any more — a save is the whole
 * workbook (see `store.js`). So the import builds a whole workbook instead.
 *
 * It can, because none of Frappe's engines touch the DOM. `createSheet` and
 * friends are plain objects over plain maps; the canvas is a separate layer
 * that happens to be the only thing that needs a screen. So the same engines
 * the editor drives can be stood up here, fed, and asked for a payload — which
 * means an imported file lands through exactly the code path a typed one does,
 * rather than through a second parser that can disagree with it.
 */

import { createFormatsEngine } from './engine/formats.js'
import { createMergeEngine } from './engine/merge.js'
import { createSheet } from './engine/sheet.js'
import { fromXlsxCell, mergesFromXlsx } from './engine/xlsx-io.js'
import { parseCellId } from './utils/cells.js'
import { buildPayload } from './store.js'
import { readWorkbook } from './xlsx-file.js'

/** What the Drive's import dialog will accept. */
export const ACCEPTS = '.xlsx,.xlsm,.csv'

/**
 * One file → the payload a save would send, plus what is in it.
 *
 * A CSV is one tab named after the file; a workbook keeps its own tab names.
 * Returns `{ payload, tabs, cells }` — the counts are for the dialog to say
 * what it did, not for anything to branch on.
 */
export async function workbookFromFile(file) {
  const sheet = createSheet()
  const formats = createFormatsEngine()
  const merge = createMergeEngine()

  const name = String(file?.name || '')
  const isCsv = /\.csv$/i.test(name)

  const tabs = isCsv
    ? ingestCsv(sheet, await file.text(), name.replace(/\.[^.]+$/, '') || 'Sheet1')
    : ingestWorkbook(sheet, formats, merge, await readWorkbook(await file.arrayBuffer()))

  let cells = 0
  const raw = sheet.getAllRaw()
  for (const tab of Object.keys(raw)) cells += Object.keys(raw[tab]).length

  const payload = await buildPayload({
    sheet, formats, merge,
    getViewState: () => null,
  })

  return { payload, tabs, cells }
}

/** Every worksheet becomes a tab, cells, number formats and merges included. */
function ingestWorkbook(sheet, formats, merge, wb) {
  const names = []
  let first = true

  for (const wsName of wb.SheetNames) {
    const ws = wb.Sheets[wsName]
    if (!ws) continue

    // A fresh workbook already has one tab called Sheet1. The first worksheet
    // becomes that one rather than a second beside it, so an import never
    // leaves a stray empty tab nobody asked for.
    const tab = unique(wsName || 'Sheet1', names)
    if (first) sheet.renameSheet('Sheet1', tab)
    else sheet.addSheet(tab)
    first = false
    names.push(tab)

    const cells = {}
    const numberFormats = []
    for (const [id, cell] of Object.entries(ws)) {
      if (id[0] === '!') continue
      if (!parseCellId(id)) continue
      const { value, fmt } = fromXlsxCell(cell)
      if (value !== '' && value != null) cells[id] = value
      if (fmt) numberFormats.push([id, fmt])
    }

    sheet.batchSetCells(cells, tab, { replace: false })
    for (const [id, fmt] of numberFormats) formats.set(id, { numberFormat: fmt }, tab)
    for (const box of mergesFromXlsx(ws['!merges'] || [])) {
      merge.merge(box.r0, box.c0, box.r1, box.c1, tab)
    }
  }

  return names.length ? names : ['Sheet1']
}

/** One tab, from comma-separated text. */
function ingestCsv(sheet, text, title) {
  const tab = title.slice(0, 31) || 'Sheet1'
  sheet.renameSheet('Sheet1', tab)

  const cells = {}
  const rows = splitCsv(text)
  for (let r = 0; r < rows.length; r++) {
    const row = rows[r]
    for (let c = 0; c < row.length; c++) {
      const value = row[c]
      if (value !== '' && value != null) cells[cellRef(r, c)] = String(value)
    }
  }
  sheet.batchSetCells(cells, tab)
  return [tab]
}

/**
 * A CSV, split the way a CSV is actually written.
 *
 * Quoted fields hold commas and newlines of their own, and a doubled quote
 * inside one is a literal quote. Splitting on `,` handles none of that and
 * silently shifts every column after the first address with a comma in it.
 */
function splitCsv(text) {
  const source = String(text || '').replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const rows = []
  let at = 0

  while (at < source.length) {
    const row = []
    for (;;) {
      if (source[at] === '"') {
        at += 1
        let cell = ''
        while (at < source.length) {
          if (source[at] === '"' && source[at + 1] === '"') { cell += '"'; at += 2 } else if (source[at] === '"') { at += 1; break } else { cell += source[at]; at += 1 }
        }
        row.push(cell)
      } else {
        const from = at
        while (at < source.length && source[at] !== ',' && source[at] !== '\n') at += 1
        row.push(source.slice(from, at))
      }
      if (at >= source.length || source[at] === '\n') { at += 1; break }
      at += 1
    }
    rows.push(row)
  }
  return rows
}

function cellRef(row, col) {
  let label = ''
  let n = col + 1
  while (n > 0) {
    const rest = (n - 1) % 26
    label = String.fromCharCode(65 + rest) + label
    n = Math.floor((n - 1) / 26)
  }
  return label + (row + 1)
}

function unique(name, taken) {
  const base = String(name || 'Sheet').trim() || 'Sheet'
  let out = base
  let n = 1
  while (taken.some((t) => t.toLowerCase() === out.toLowerCase())) out = `${base} (${++n})`
  return out
}
