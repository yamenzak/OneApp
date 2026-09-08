/**
 * A template's tabs, added to the workbook you are already in.
 *
 * Written for one shape of work and it is worth naming, because it is the
 * reason this is not "open the template as a new file": a sheet bound to a
 * record's child table is *that record's* workbook. Somebody pricing a
 * quotation opens the line items in a sheet, loads their estimator beside it,
 * does the working, fills the bound tab from it and sends the rows back. The
 * working has to live in the same book as the bound tab — so a formula can
 * reach across to it, and so it is still there the next time that quotation is
 * repriced. A separate file would be a calculation nobody can find again.
 *
 * So: add tabs, never replace one. Nothing already in the workbook is written
 * over, and the tab you were on is the tab you come back to.
 *
 * What comes across is cells, formats and merges — which is exactly what the
 * XLSX import beside this brings in, for the same reason: they are the parts
 * that are per-tab and self-contained. Charts, pivots and named ranges are
 * workbook-scoped and name their sheet inside their own config; carrying them
 * means rewriting configs and reconciling names, and half-carrying them would
 * put a chart in the book pointing at a range that is not what it was drawn
 * from. They are left behind, and `left` says so.
 */

import { unpackSheet } from '@/lib/sheets/utils/sheet-codec.js'
import { fetchWorkbook } from '@/lib/sheets/store.js'

/** `Sheet1`, `Sheet1 (2)`, `Sheet1 (3)` — the import path's rule, reused. */
function unique(name, taken) {
  let out = name || 'Sheet'
  let n = 1
  while (taken.has(out.toLowerCase())) {
    n += 1
    out = `${name} (${n})`
  }
  taken.add(out.toLowerCase())
  return out
}

/**
 * Point a formula's sheet references at the tabs as they were actually named.
 *
 * A template whose second tab reads `=Rates!B2` is a template whose second tab
 * is wrong the moment `Rates` had to come in as `Rates (2)`. This rewrites the
 * references it can see: `Name!` and `'Name'!`, which is how every sheet
 * reference in this engine is written.
 *
 * Textual, and honestly so — a sheet name inside a string literal would be
 * rewritten too. The alternative is a formula parser, and the case it would
 * save is a template with a tab named the same as a word somebody quoted in a
 * cell. Renaming only happens on a collision, so most loads rewrite nothing.
 */
function repoint(formula, renames) {
  let out = formula
  for (const [was, now] of Object.entries(renames)) {
    if (was === now) continue
    const quoted = new RegExp(`'${was.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}'!`, 'g')
    const bare = new RegExp(`\\b${was.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}!`, 'g')
    out = out.replace(quoted, `'${now}'!`).replace(bare, `${now}!`)
  }
  return out
}

export function useTemplateInsert({
  getSheet, getFormats, getMerge, syncNames, switchSheet, repopulateGrid, isDirty,
}) {
  /**
   * Read a template and add every tab it has to the open workbook.
   *
   * Returns what happened, so the caller can say it: the names the tabs came
   * in under, and what was not carried.
   */
  async function insertTemplate(name) {
    const { saved } = await fetchWorkbook(name)
    const book = unpackSheet(saved.sheet)
    const tabs = Object.entries(book?.sheets || {})
    if (!tabs.length) return { added: [], left: [] }

    const sheet = getSheet()
    const formats = getFormats()
    const merge = getMerge()

    const taken = new Set(sheet.getSheetNames().map((one) => one.toLowerCase()))

    // Named first, all of them, before a single cell is written: a formula in
    // the first tab may reach into the third, and it can only be repointed
    // once every tab's final name is known.
    const renames = {}
    for (const [was] of tabs) renames[was] = unique(was, taken)

    for (const [was, cells] of tabs) {
      const now = renames[was]
      sheet.addSheet(now)

      const values = {}
      for (const [id, raw] of Object.entries(cells || {})) {
        values[id] = typeof raw === 'string' && raw.startsWith('=')
          ? repoint(raw, renames)
          : raw
      }
      // `replace: false`, which is the whole promise of this: a tab that is new
      // has nothing to replace, and the flag says so where somebody reading it
      // would otherwise have to check.
      sheet.batchSetCells(values, now, { replace: false })

      const cellFormats = saved.formats?.[was]
      if (cellFormats && formats) {
        for (const [id, format] of Object.entries(cellFormats.cells || {})) {
          formats.set(id, format, now)
        }
        for (const [col, format] of Object.entries(cellFormats.cols || {})) {
          formats.setCol(Number(col), format, now)
        }
        for (const [row, format] of Object.entries(cellFormats.rows || {})) {
          formats.setRow(Number(row), format, now)
        }
      }

      const merged = saved.merge?.[was]?.masterMap
      if (merged && merge) {
        for (const rect of Object.values(merged)) {
          if (!rect) continue
          merge.merge(rect.r0 ?? rect.startRow, rect.c0 ?? rect.startCol,
            rect.r1 ?? rect.endRow, rect.c1 ?? rect.endCol, now)
        }
      }
    }

    syncNames()
    switchSheet(renames[tabs[0][0]])
    repopulateGrid()
    isDirty.value = true

    // What the workbook now holds that it did not, and what the template had
    // that did not come. Said rather than silently dropped.
    const left = ['charts', 'pivot', 'namedRanges']
      .filter((slice) => {
        const held = saved[slice]
        return held && Object.keys(held.charts || held.pivots || held.entries || {}).length
      })

    return { added: Object.values(renames), left }
  }

  return { insertTemplate }
}
