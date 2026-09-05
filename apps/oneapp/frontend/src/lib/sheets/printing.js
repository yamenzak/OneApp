/**
 * A tab as a page somebody can hold.
 *
 * The grid on screen cannot be printed as it stands: it windows its rows, so
 * what the printer would be handed is the forty rows that happen to be in the
 * DOM. So printing builds its own document — a plain table of the used range —
 * and hands it to an iframe, which is the same shape `PrintDialog` already
 * uses for a record's print format.
 *
 * Values and not formulas, and the cell's own format applied: what is printed
 * is what is on screen, which is the only thing a printed spreadsheet can
 * honestly claim to be.
 */

import { columnLetters, parse } from './refs'
import { align, styleFor, text } from './display'

/** How wide a printed sheet may get before it is turned on its side. */
const PORTRAIT_COLUMNS = 6

/**
 * The whole document, as a string for an iframe's `srcdoc`.
 *
 * Self-contained on purpose: the page's own stylesheet is Tailwind's, and a
 * print document that depended on it would be a print document that changed
 * whenever a utility class did.
 */
export function toHtml({ cells, tab, title, locale }) {
  const grid = new Map()
  let rows = 0
  let columns = 0

  for (const cell of cells) {
    if (cell.tab !== tab) continue
    if (cell.value === null && cell.raw === null) continue
    let at
    try {
      at = parse(cell.ref)
    } catch {
      continue
    }
    grid.set(`${at.row}:${at.column}`, cell)
    rows = Math.max(rows, at.row)
    columns = Math.max(columns, at.column)
  }

  const heading = escape(title || 'Sheet')
  const body = rows
    ? table(grid, rows, columns, locale)
    : '<p class="empty">There is nothing on this tab to print.</p>'

  return `<!doctype html><html><head><meta charset="utf-8"><title>${heading}</title>
<style>
  @page { size: ${columns > PORTRAIT_COLUMNS ? 'landscape' : 'portrait'}; margin: 14mm; }
  body { font: 11px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         color: #171717; margin: 0; }
  h1 { font-size: 15px; font-weight: 600; margin: 0 0 2mm; }
  .tab { font-size: 10px; color: #737373; margin: 0 0 4mm; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 0.5px solid #d4d4d4; padding: 3px 6px; vertical-align: top;
           word-break: break-word; }
  th { background: #f5f5f5; font-weight: 600; text-align: center; width: 1%;
       white-space: nowrap; color: #737373; }
  tbody th { text-align: right; }
  tr { page-break-inside: avoid; }
  thead { display: table-header-group; }
  .empty { color: #737373; }
</style></head><body>
<h1>${heading}</h1>
<p class="tab">${escape(tab)}</p>
${body}
</body></html>`
}

function table(grid, rows, columns, locale) {
  const head = ['<thead><tr><th></th>']
  for (let column = 1; column <= columns; column++) {
    head.push(`<th>${columnLetters(column)}</th>`)
  }
  head.push('</tr></thead>')

  const lines = ['<tbody>']
  for (let row = 1; row <= rows; row++) {
    lines.push(`<tr><th>${row}</th>`)
    for (let column = 1; column <= columns; column++) {
      const cell = grid.get(`${row}:${column}`)
      lines.push(`<td style="${inline(cell)}">${escape(text(cell, locale))}</td>`)
    }
    lines.push('</tr>')
  }
  lines.push('</tbody>')

  return `<table>${head.join('')}${lines.join('')}</table>`
}

/** The cell's own format, as the handful of properties paper can carry. */
function inline(cell) {
  if (!cell) return 'text-align:left'
  const style = styleFor(cell)
  const parts = [`text-align:${style.textAlign || align(cell)}`]
  if (style.fontWeight) parts.push(`font-weight:${style.fontWeight}`)
  if (style.fontStyle) parts.push(`font-style:${style.fontStyle}`)
  if (style.textDecoration) parts.push(`text-decoration:${style.textDecoration}`)
  if (style.color) parts.push(`color:${style.color}`)
  if (style.backgroundColor) parts.push(`background:${style.backgroundColor}`)
  if (style.whiteSpace) parts.push('white-space:pre-wrap')
  return parts.join(';')
}

const ESCAPES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

/**
 * Everything a cell holds is somebody's typing, and it goes into a document
 * this builds by concatenation. A cell holding `<script>` must print as those
 * characters rather than run as one.
 */
function escape(value) {
  return String(value ?? '').replace(/[&<>"']/g, (character) => ESCAPES[character])
}
