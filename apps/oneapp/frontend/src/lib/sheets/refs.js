/**
 * A1 notation, on this side of the wire.
 *
 * The same rules as `oneapp_core/sheets/refs.py` and deliberately a second
 * implementation rather than a shared one: the browser needs to name a cell
 * on every keystroke and cannot ask the server what `AA10` means. The two are
 * kept in step by `tests/test_sheets.py`, which reads the limits out of both.
 *
 * Pure. No Vue, no resource, no workbook — a function here answers a question
 * about a string.
 */

/** `ZZ`. Past that a spreadsheet is a database somebody has not written yet. */
export const MAX_COLUMN = 702

export const MAX_ROW = 100_000

/** Rows times columns, over the whole workbook. `docs/SHEETS.md` §7. */
export const MAX_CELLS = 20_000

const CELL = /^([A-Z]{1,3})([0-9]{1,7})$/

export class BadRef extends Error {}

/** `A` → 1, `AA` → 27. */
export function columnNumber(letters) {
  let n = 0
  for (const character of letters.toUpperCase()) {
    n = n * 26 + (character.charCodeAt(0) - 64)
  }
  return n
}

/** 1 → `A`, 27 → `AA`. */
export function columnLetters(number) {
  let n = number
  let out = ''
  while (n > 0) {
    const remainder = (n - 1) % 26
    out = String.fromCharCode(65 + remainder) + out
    n = Math.floor((n - 1) / 26)
  }
  return out
}

/** `'B3'` → `{ row: 3, column: 2 }`, or throws. */
export function parse(ref) {
  const match = CELL.exec(String(ref || '').trim().toUpperCase())
  if (!match) throw new BadRef(`${ref} is not a cell.`)

  const column = columnNumber(match[1])
  const row = Number(match[2])
  if (!row || row > MAX_ROW) throw new BadRef(`Row ${match[2]} is out of range.`)
  if (column > MAX_COLUMN) throw new BadRef(`Column ${match[1]} is out of range.`)
  return { row, column }
}

/** `(3, 2)` → `'B3'`. */
export function format(row, column) {
  return `${columnLetters(column)}${row}`
}

/**
 * `'C10:A1'` → `{ top: 1, left: 1, bottom: 10, right: 3 }`.
 *
 * Corners sorted, because a person dragging up and to the left has selected
 * the same rectangle as one dragging down and to the right.
 */
export function parseRange(ref) {
  const [first, second] = String(ref || '').split(':')
  const a = parse(first)
  const b = second ? parse(second) : a
  return {
    top: Math.min(a.row, b.row),
    left: Math.min(a.column, b.column),
    bottom: Math.max(a.row, b.row),
    right: Math.max(a.column, b.column),
  }
}

export function formatRange({ top, left, bottom, right }) {
  return `${format(top, left)}:${format(bottom, right)}`
}

/** Every `A1` in a rectangle, row by row. */
export function cellsIn(area) {
  const out = []
  for (let row = area.top; row <= area.bottom; row++) {
    for (let column = area.left; column <= area.right; column++) {
      out.push(format(row, column))
    }
  }
  return out
}

export function within(area, row, column) {
  return row >= area.top && row <= area.bottom && column >= area.left && column <= area.right
}

/** The rectangle two cells make — what a drag selection is. */
export function areaOf(a, b) {
  return {
    top: Math.min(a.row, b.row),
    left: Math.min(a.column, b.column),
    bottom: Math.max(a.row, b.row),
    right: Math.max(a.column, b.column),
  }
}
