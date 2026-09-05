/**
 * Reading and writing a real .xlsx, in the cell shape the mapper already speaks.
 *
 * `engine/xlsx-io.js` — Frappe's, vendored — is a pure mapper between the
 * engine's state and a SheetJS cell: `{ t, v, f?, z? }`, where `t` is the type
 * (`n` number, `s` string, `b` boolean, `d` date), `v` the value, `f` a formula
 * without its leading `=`, and `z` an Excel number-format code. That mapping is
 * the hard part and it is theirs. What is *not* theirs is the file: upstream
 * hands those cells to SheetJS, and we use ExcelJS instead.
 *
 * The reason is narrow and worth stating so nobody "fixes" it back. SheetJS's
 * newest release on npm is 0.18.5 and carries two advisories — prototype
 * pollution and a ReDoS — fixed only in versions published on the project's own
 * CDN, which is not a registry a lockfile can pin against. ExcelJS is MIT, on
 * npm, maintained, and does the same job.
 *
 * So this file is an adapter and nothing more: in and out, a worksheet is the
 * same `{ 'A1': {t,v,f,z}, '!ref', '!merges' }` object SheetJS would have
 * produced, and every line that builds or consumes one is untouched upstream
 * code. Behind a dynamic `import`, so its 900KB is paid by the person who
 * presses Download or Import and by nobody else.
 */

import { cellId, colLabel, parseCellId } from './utils/cells.js'

/** Save `[{ name, ws }]` as an .xlsx the browser downloads. */
export async function writeWorkbook(sheets, filename) {
  const ExcelJS = (await import('exceljs')).default ?? (await import('exceljs'))
  const wb = new ExcelJS.Workbook()

  for (const { name, ws } of sheets) {
    const out = wb.addWorksheet(name)
    for (const [id, cell] of Object.entries(ws)) {
      if (id[0] === '!') continue
      const at = out.getCell(id)
      at.value = toExcel(cell)
      if (cell.z) at.numFmt = cell.z
    }
    for (const m of ws['!merges'] || []) {
      // SheetJS ranges are zero-based `{s:{r,c}, e:{r,c}}`; ExcelJS merges by
      // one-based row/column, top-left then bottom-right.
      out.mergeCells(m.s.r + 1, m.s.c + 1, m.e.r + 1, m.e.c + 1)
    }
  }

  const buffer = await wb.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
  const url = URL.createObjectURL(blob)
  const link = Object.assign(document.createElement('a'), { href: url, download: filename })
  link.click()
  URL.revokeObjectURL(url)
}

/** Read an .xlsx into `{ SheetNames, Sheets }`, SheetJS-shaped. */
export async function readWorkbook(buffer) {
  const ExcelJS = (await import('exceljs')).default ?? (await import('exceljs'))
  const wb = new ExcelJS.Workbook()
  await wb.xlsx.load(buffer)

  const SheetNames = []
  const Sheets = {}

  wb.eachSheet((sheet) => {
    const ws = {}
    let maxRow = 0
    let maxCol = 0

    sheet.eachRow({ includeEmpty: false }, (row, rowNumber) => {
      row.eachCell({ includeEmpty: false }, (cell, colNumber) => {
        const made = fromExcel(cell)
        if (!made) return
        ws[cellId(rowNumber - 1, colNumber - 1)] = made
        if (rowNumber > maxRow) maxRow = rowNumber
        if (colNumber > maxCol) maxCol = colNumber
      })
    })

    ws['!ref'] = `A1:${colLabel(Math.max(maxCol, 1) - 1)}${Math.max(maxRow, 1)}`
    const merges = mergesOf(sheet)
    if (merges.length) ws['!merges'] = merges

    SheetNames.push(sheet.name)
    Sheets[sheet.name] = ws
  })

  return { SheetNames, Sheets }
}

/** `{t,v,f,z}` → what ExcelJS wants in `cell.value`. */
function toExcel(cell) {
  if (cell.f) {
    // A formula cell carries what it came to as well, so a reader that does
    // not evaluate — Numbers, Google Sheets on first open, a preview pane —
    // still shows the number rather than an empty cell.
    return { formula: cell.f, result: cell.v ?? null }
  }
  return cell.v ?? null
}

/**
 * An ExcelJS cell → `{t,v,f,z}`.
 *
 * Rich text collapses to its text, and a hyperlink cell to its label: both are
 * what the grid would display, and neither the engine nor the mapper has
 * anywhere to put the rest.
 */
function fromExcel(cell) {
  const fmt = cell.numFmt || ''
  let value = cell.value
  let formula = ''

  if (value && typeof value === 'object') {
    if (value.formula || value.sharedFormula) {
      // `cell.formula` is the getter that translates a shared formula for this
      // row — `B4:B20` all point at `B3` and carry none of their own.
      formula = cell.formula || value.formula || ''
      value = value.result ?? null
    } else if (Array.isArray(value.richText)) {
      value = value.richText.map((part) => part.text).join('')
    } else if ('text' in value) {
      value = value.text
    } else if ('error' in value) {
      value = value.error
    }
  }

  if (value === null || value === undefined || value === '') {
    return formula ? { t: 's', v: '', f: formula, ...(fmt ? { z: fmt } : {}) } : null
  }

  const t = value instanceof Date ? 'd'
    : typeof value === 'number' ? 'n'
      : typeof value === 'boolean' ? 'b'
        : 's'

  return {
    t,
    v: value,
    ...(formula ? { f: formula } : {}),
    ...(fmt ? { z: fmt } : {}),
  }
}

/** ExcelJS's merge model, as SheetJS ranges. */
function mergesOf(sheet) {
  const out = []
  // ExcelJS exposes merges as an internal map of "A1:B2" ranges; the public
  // `model.merges` is the same list and is what survives a `load`.
  for (const range of sheet.model?.merges || []) {
    const [from, to] = String(range).split(':')
    const a = parseCellId(from)
    const b = parseCellId(to || from)
    if (!a || !b) continue
    out.push({ s: { r: a.row, c: a.col }, e: { r: b.row, c: b.col } })
  }
  return out
}
