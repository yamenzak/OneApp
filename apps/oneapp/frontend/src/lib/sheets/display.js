/**
 * What a cell looks like: the text in it, and how it is painted.
 *
 * A cell holds a value and a format, and neither on its own says what to draw.
 * `1234.5` with `#,##0.00` is `1,234.50`; the same number with `dd-mmm-yyyy` is
 * a date in 1903. Excel's own number-format grammar is the one people know, so
 * it is the one used here — `SSF`, which ships inside `fast-formula-parser`
 * and is the same formatter SheetJS uses.
 *
 * The format itself is `Sheet Cell.format_json`, a small object rather than
 * Excel's full style model:
 *
 *     { numFmt, bold, italic, underline, align, colour, fill, wrap }
 *
 * Small on purpose. Every property here is one somebody can set from the
 * toolbar and one that survives a round trip to CSV or xlsx; a border model
 * and a font stack would be neither.
 */

import FormulaParser from 'fast-formula-parser'

const { SSF } = FormulaParser

/** What "no format" means, so callers never branch on undefined. */
export const PLAIN = Object.freeze({
  numFmt: '',
  bold: false,
  italic: false,
  underline: false,
  align: '',
  colour: '',
  fill: '',
  wrap: false,
})

/** The formats the toolbar offers, in the order it offers them. */
export const NUMBER_FORMATS = [
  { label: 'Automatic', code: '' },
  { label: 'Plain number', code: '0.##########' },
  { label: 'Two decimals', code: '#,##0.00' },
  { label: 'Thousands', code: '#,##0' },
  { label: 'Percent', code: '0.00%' },
  { label: 'Currency', code: '#,##0.00' },
  { label: 'Accounting', code: '#,##0.00;(#,##0.00)' },
  { label: 'Scientific', code: '0.00E+00' },
  { label: 'Date', code: 'dd-mmm-yyyy' },
  { label: 'Time', code: 'hh:mm' },
  { label: 'Date and time', code: 'dd-mmm-yyyy hh:mm' },
  { label: 'Text', code: '@' },
]

export function parseFormat(formatJson) {
  if (!formatJson) return PLAIN
  if (typeof formatJson === 'object') return { ...PLAIN, ...formatJson }
  try {
    return { ...PLAIN, ...JSON.parse(formatJson) }
  } catch {
    return PLAIN
  }
}

/**
 * The text a cell shows.
 *
 * An unformatted number is rendered by the browser rather than by a format
 * code, because `toLocaleString` knows the reader's separators and `0.##` does
 * not — and a workspace in Dubai and one in Berlin should not have to agree on
 * a decimal point to share a sheet.
 */
export function text(cell, locale) {
  if (!cell) return ''
  const { value, kind } = cell
  if (value === null || value === undefined || value === '') return ''
  if (kind === 'error') return String(value)

  const format = parseFormat(cell.format)
  const number = kind === 'number' ? Number(value) : null

  if (format.numFmt === '@') return String(value)

  if (number !== null && Number.isFinite(number)) {
    if (!format.numFmt) return number.toLocaleString(locale, { maximumFractionDigits: 10 })
    try {
      return SSF.format(format.numFmt, number)
    } catch {
      return String(value)
    }
  }

  if (kind === 'bool') return value ? 'TRUE' : 'FALSE'
  return String(value)
}

/**
 * Which side of the cell the text sits on.
 *
 * Numbers right, text left, errors and booleans centred — Excel's rule, which
 * is worth keeping because a column of numbers reads as a column only when the
 * digits line up. An explicit alignment from the toolbar wins.
 */
export function align(cell) {
  const format = parseFormat(cell?.format)
  if (format.align) return format.align
  if (!cell || cell.value === null || cell.value === '') return 'left'
  if (cell.kind === 'number') return 'right'
  if (cell.kind === 'bool' || cell.kind === 'error') return 'center'
  return 'left'
}

/** Inline styles for one cell, from its format. Classes cannot carry a colour. */
export function styleFor(cell) {
  const format = parseFormat(cell?.format)
  const style = { textAlign: align(cell) }
  if (format.bold) style.fontWeight = '600'
  if (format.italic) style.fontStyle = 'italic'
  if (format.underline) style.textDecoration = 'underline'
  if (format.colour) style.color = format.colour
  if (format.fill) style.backgroundColor = format.fill
  if (format.wrap) {
    style.whiteSpace = 'pre-wrap'
    style.overflowWrap = 'anywhere'
  }
  return style
}

/**
 * The format after a toolbar click, or nothing at all.
 *
 * Nothing rather than an object of falses: `format_json` is stored per cell and
 * a workbook of twenty thousand `{"bold":false,…}` is a table that is mostly
 * defaults. `writing._format` drops a falsy value, and this is what makes it
 * falsy.
 */
export function withChange(current, change) {
  const merged = { ...parseFormat(current), ...change }
  const kept = {}
  for (const [property, value] of Object.entries(merged)) {
    if (value && value !== PLAIN[property]) kept[property] = value
  }
  return Object.keys(kept).length ? kept : null
}
