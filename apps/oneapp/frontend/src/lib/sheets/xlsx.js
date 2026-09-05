/**
 * A sheet as a real spreadsheet file, both ways.
 *
 * CSV is what a sheet's `file_url` produces — one tab, values, no formats — and
 * it is the right thing for a link somebody clicks. It is the wrong thing for
 * the estimator somebody has been keeping in Excel for six years: that person
 * wants their formulas, their number formats and their tabs, in and out.
 *
 * `exceljs` (MIT) does the file format. It is loaded with a dynamic `import`
 * and nowhere else, so the 900KB it costs is paid by the person who presses
 * Import or Download as Excel and by nobody who merely opens a grid. SheetJS
 * would have been the obvious choice and is not: the version on npm is 0.18.5,
 * which carries two advisories fixed only in releases published on the
 * project's own CDN.
 *
 * What survives a round trip, deliberately: cell values, formulas, number
 * formats, bold, italic, underline, alignment, text colour, fill, and the tab
 * each cell is on. What does not: merged cells, column widths, charts,
 * validation, conditional formats, images. Those are things this product does
 * not have, and inventing storage for them on the way through would be storing
 * what nothing reads.
 */

import { columnLetters, format, parse, MAX_CELLS } from './refs'
import { parseFormat } from './display'

/** Files the importer will take. Anything else is refused by name, up front. */
export const ACCEPTS = '.xlsx,.xlsm,.csv'

async function library() {
  const module = await import('exceljs')
  return module.default || module
}

// --------------------------------------------------------------------------- //
// Out
// --------------------------------------------------------------------------- //

/**
 * The whole workbook as an xlsx `Blob`.
 *
 * Formulas go out as formulas with their last computed value beside them,
 * which is what `Sheet Cell` already holds — so Excel shows the number
 * immediately and recalculates when it feels like it, rather than showing a
 * column of zeroes until somebody presses F9.
 */
export async function toBlob({ cells, tabs, title }) {
  const ExcelJS = await library()
  const workbook = new ExcelJS.Workbook()
  workbook.creator = 'OneSpace'
  workbook.created = new Date()

  const names = tabs?.length ? tabs.map((one) => one.tab_name) : ['Sheet1']
  const sheets = new Map(names.map((name) => [name, workbook.addWorksheet(name)]))

  for (const cell of cells) {
    const worksheet = sheets.get(cell.tab)
    if (!worksheet) continue
    let at
    try {
      at = parse(cell.ref)
    } catch {
      continue
    }
    const target = worksheet.getCell(at.row, at.column)
    target.value = outgoing(cell)
    style(target, parseFormat(cell.format))
  }

  const buffer = await workbook.xlsx.writeBuffer()
  return new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    endings: 'native',
  })
}

function outgoing(cell) {
  const raw = cell.raw ?? ''
  const value = cell.value

  if (typeof raw === 'string' && raw.startsWith('=') && raw.length > 1) {
    return { formula: raw.slice(1), result: computed(cell) }
  }
  if (value === null || value === undefined || value === '') return null
  if (cell.kind === 'number') return Number(value)
  if (cell.kind === 'bool') return value === true || value === 'true' || value === 'TRUE'
  return String(value)
}

/** A formula's stored result, in the shape exceljs wants beside the formula. */
function computed(cell) {
  if (cell.kind === 'error') return { error: String(cell.value) }
  if (cell.kind === 'number') return Number(cell.value)
  if (cell.kind === 'bool') return cell.value === true || cell.value === 'TRUE'
  return cell.value === null || cell.value === undefined ? '' : String(cell.value)
}

function style(target, shape) {
  if (shape.numFmt) target.numFmt = shape.numFmt
  if (shape.bold || shape.italic || shape.underline || shape.colour) {
    target.font = {
      bold: !!shape.bold,
      italic: !!shape.italic,
      underline: !!shape.underline,
      ...(shape.colour ? { color: { argb: argb(shape.colour) } } : {}),
    }
  }
  if (shape.align || shape.wrap) {
    target.alignment = {
      ...(shape.align ? { horizontal: shape.align } : {}),
      ...(shape.wrap ? { wrapText: true } : {}),
    }
  }
  if (shape.fill) {
    target.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: argb(shape.fill) } }
  }
}

/** `#f3f4f6` → `FFF3F4F6`. Excel's colours carry an alpha byte in front. */
function argb(colour) {
  const hex = String(colour).replace('#', '')
  const six = hex.length === 3 ? hex.split('').map((c) => c + c).join('') : hex
  return `FF${six.toUpperCase()}`.slice(0, 8)
}

// --------------------------------------------------------------------------- //
// In
// --------------------------------------------------------------------------- //

/**
 * A file's cells, as this product stores them.
 *
 * Returns `{ tabs, cells, skipped }`. `skipped` is how many cells were past the
 * cap and dropped — said out loud rather than silently truncating, because a
 * quotation missing its last four lines is worse than an import that refused.
 */
export async function fromFile(file) {
  const ExcelJS = await library()
  const workbook = new ExcelJS.Workbook()
  const buffer = await file.arrayBuffer()

  if (/\.csv$/i.test(file.name)) {
    // exceljs's CSV reader wants a stream; the text is already here, and a
    // CSV is one tab of strings — parsing it ourselves is shorter than
    // shimming a stream into a browser.
    return fromCsv(new TextDecoder().decode(buffer))
  }

  await workbook.xlsx.load(buffer)

  const tabs = []
  const cells = []
  let skipped = 0

  workbook.eachSheet((worksheet) => {
    tabs.push({ tab_name: worksheet.name, position: tabs.length })
    worksheet.eachRow({ includeEmpty: false }, (row, rowNumber) => {
      row.eachCell({ includeEmpty: false }, (cell, columnNumber) => {
        if (rowNumber > 100_000 || columnNumber > 702) {
          skipped += 1
          return
        }
        if (cells.length >= MAX_CELLS) {
          skipped += 1
          return
        }
        const made = incoming(cell)
        if (!made) return
        cells.push({
          tab: worksheet.name,
          ref: format(rowNumber, columnNumber),
          ...made,
          format_json: shapeOf(cell),
        })
      })
    })
  })

  return { tabs: tabs.length ? tabs : [{ tab_name: 'Sheet1', position: 0 }], cells, skipped }
}

function fromCsv(text) {
  const cells = []
  const lines = String(text).replace(/^﻿/, '').replace(/\r\n?/g, '\n').split('\n')
  lines.forEach((line, index) => {
    if (!line.trim()) return
    splitCsv(line).forEach((value, column) => {
      if (value === '' || cells.length >= MAX_CELLS) return
      const number = Number(value)
      cells.push({
        tab: 'Sheet1',
        ref: format(index + 1, column + 1),
        raw: value,
        value,
        kind: value.trim() && !Number.isNaN(number) ? 'number' : 'text',
        format_json: null,
      })
    })
  })
  return { tabs: [{ tab_name: 'Sheet1', position: 0 }], cells, skipped: 0 }
}

/** One CSV line, respecting quotes and doubled quotes inside them. */
function splitCsv(line) {
  const out = []
  let current = ''
  let quoted = false
  for (let i = 0; i < line.length; i++) {
    const character = line[i]
    if (quoted) {
      if (character === '"' && line[i + 1] === '"') {
        current += '"'
        i += 1
      } else if (character === '"') quoted = false
      else current += character
    } else if (character === '"') quoted = true
    else if (character === ',') {
      out.push(current)
      current = ''
    } else current += character
  }
  out.push(current)
  return out
}

/**
 * One exceljs cell as `{ raw, value, kind }`.
 *
 * `cell.formula` is read rather than `cell.value.formula`, because a shared
 * formula — Excel's own compression, where B4:B20 all point at B3 — has no
 * `formula` inside its value at all, and the getter is what translates the
 * master's `A3*2` into this row's `A4*2`.
 */
function incoming(cell) {
  const value = cell.value

  if (cell.formula) {
    const result = value?.result
    return { raw: `=${cell.formula}`, ...typed(result?.error ?? result) }
  }

  if (value === null || value === undefined || value === '') return null

  if (value instanceof Date) {
    const day = value.toISOString().slice(0, 10)
    return { raw: day, value: day, kind: 'date' }
  }
  if (value.richText) {
    const text = value.richText.map((part) => part.text).join('')
    return { raw: text, value: text, kind: 'text' }
  }
  if (value.text !== undefined) return { raw: value.text, value: value.text, kind: 'text' }
  if (value.error) return { raw: value.error, value: value.error, kind: 'error' }

  return { raw: String(value), ...typed(value) }
}

function typed(value) {
  if (value === null || value === undefined) return { value: null, kind: '' }
  if (typeof value === 'number') return { value: Number(value.toPrecision(15)), kind: 'number' }
  if (typeof value === 'boolean') return { value, kind: 'bool' }
  if (value instanceof Date) return { value: value.toISOString().slice(0, 10), kind: 'date' }
  const text = String(value)
  return { value: text, kind: text.startsWith('#') ? 'error' : 'text' }
}

/** The bits of an exceljs style this product has somewhere to put. */
function shapeOf(cell) {
  const shape = {}
  if (cell.numFmt && cell.numFmt !== 'General') shape.numFmt = cell.numFmt
  if (cell.font?.bold) shape.bold = true
  if (cell.font?.italic) shape.italic = true
  if (cell.font?.underline) shape.underline = true
  if (cell.font?.color?.argb) shape.colour = hex(cell.font.color.argb)
  if (cell.alignment?.horizontal && cell.alignment.horizontal !== 'general') {
    shape.align = cell.alignment.horizontal
  }
  if (cell.alignment?.wrapText) shape.wrap = true
  if (cell.fill?.fgColor?.argb && cell.fill.pattern === 'solid') {
    shape.fill = hex(cell.fill.fgColor.argb)
  }
  return Object.keys(shape).length ? JSON.stringify(shape) : null
}

/** `FFF3F4F6` → `#f3f4f6`. The alpha byte is dropped; nothing here reads it. */
function hex(value) {
  const text = String(value)
  return `#${(text.length === 8 ? text.slice(2) : text).toLowerCase()}`
}

/** The letter a column takes in a message about an import. */
export const letterFor = columnLetters
