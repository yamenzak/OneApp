/**
 * What `RECORD()` in a cell reads from.
 *
 * The formula engine is synchronous and has to stay that way — a spreadsheet
 * recalculates thousands of cells on one keystroke, and a promise per cell is
 * a different product. So this is a cache the engine reads and something else
 * fills: `collect` walks the workbook for every record it names, one request
 * resolves them all, and the grid recomputes once at the end.
 *
 * Which settles the freshness question for a workbook, and settles it the
 * only way it can be settled. A cell's stored value is what the browser last
 * computed (`onesheet/codec.py` says why the server cannot compute it), so a
 * `RECORD()` value on disk is a snapshot however it got there. What is left
 * to decide is *when to ask again*, and the answer is: when the workbook is
 * opened, and when somebody presses Refresh — the same contract every
 * spreadsheet that talks to an external source has.
 *
 * A miss is `#N/A` rather than a blank or a zero. Before the fetch comes back
 * that is honestly what is known, and for a record this person may not read
 * it is the answer forever — nineteen numbers and one `#N/A` beats a workbook
 * that will not open.
 */

import { setRecordResolver } from '@/modules/onesheet/lib/engine/formula'
import { workspace } from '@/shared/lib/workspace'

//: What the server keys its answer by. A separator no doctype or record id
//: can contain, so `Quotation` + `Q-1` cannot collide with anything.
const SEP = '\x1f'

//: `RECORD(...)`, as it appears in a stored formula. Only the arguments are
//: read here — the engine does the evaluating; this needs to know which
//: records to fetch before it can.
const CALL = /\bRECORD\s*\(([^()]*)\)/gi

//: One workbook's answers: `"doctype\x1fname" → {fieldname: {value, text}}`.
//: Module-level because it is keyed by record: two workbooks open on the same
//: quotation want the same number, not two of them.
const held = new Map()

//: Which record the one-argument form means. Set when a workbook opens.
let own = { doctype: '', name: '' }

/** Point the engine at this cache. Called once, when the module loads. */
setRecordResolver((doctype, name, field) => {
  const where = doctype && name ? { doctype, name } : own
  if (!where.doctype || !where.name || !field) return undefined
  const said = held.get(`${where.doctype}${SEP}${where.name}`)?.[field]
  // The number, never the text: a cell that says `AED 144,235.00` cannot be
  // added up, and a formula around this one is the ordinary case.
  return said?.value
})

/** Which record the workbook itself is about. */
export function setOwnRecord(bound) {
  own = { doctype: bound?.doctype || '', name: bound?.name || '' }
}

/** Forget everything. What closing a workbook does. */
export function forgetRecordFields() {
  held.clear()
  own = { doctype: '', name: '' }
}

/**
 * Every record and field the formulas in these tabs name.
 *
 * `tabs` is `{tabName: {cellId: rawValue}}` — the shape the store holds. Read
 * off the raw text rather than off the parsed formulas, because the parse is
 * the engine's and this runs before it: the question is what to fetch, and
 * the engine cannot answer it without the fetch.
 */
export function collect(tabs) {
  const asks = new Map()
  // Whether anything asked for "the sheet's own record" while we did not know
  // what that is. One cheap probe fixes it; asking on every open would be a
  // request every ordinary sheet pays for and nothing reads.
  let wantsOwn = false

  for (const cells of Object.values(tabs || {})) {
    for (const raw of Object.values(cells || {})) {
      if (typeof raw !== 'string' || !raw.startsWith('=')) continue
      for (const found of raw.matchAll(CALL)) {
        const parts = split(found[1])
        // Read by position, not by how many happened to be literals: with
        // `RECORD("Quotation", A1, "qty")` two come back, and treating that
        // as the one-argument form would fetch a field called Quotation.
        const [doctype, name, field] =
          parts.length >= 3 ? parts : ['', '', parts.length === 1 ? parts[0] : '']
        if (!field) continue
        const about = doctype || own.doctype
        const which = name || own.name
        // A one-argument `RECORD()` in a workbook bound to nothing has no
        // record to be about — either because nothing is, or because nobody
        // has asked yet.
        if (!about || !which) {
          if (!doctype && !name) wantsOwn = true
          continue
        }
        const key = `${about}${SEP}${which}`
        if (!asks.has(key)) asks.set(key, new Set())
        asks.get(key).add(field)
      }
    }
  }

  const out = [...asks].map(([key, wanted]) => {
    const [doctype, name] = key.split(SEP)
    return { doctype, name, fields: [...wanted] }
  })
  return { asks: out, wantsOwn }
}

/**
 * One argument list, as the strings inside it.
 *
 * Only literal arguments are followed. `RECORD(A1)` is a cell reference and
 * this cannot know what it holds without evaluating, which is the engine's
 * job and happens after the fetch — so it is skipped, and that cell answers
 * `#N/A`. A worse alternative would be fetching whatever a cell happened to
 * contain, which is a request shaped by a spreadsheet.
 */
function split(inside) {
  return inside
    .split(',')
    .map((one) => one.trim())
    // Position is kept: a reference among the arguments becomes an empty
    // string rather than disappearing, so the three-argument form is still
    // recognisable as three arguments.
    .map((one) => (/^["'].*["']$/.test(one) ? one.slice(1, -1) : ''))
}

/**
 * Ask the server, and say whether anything moved.
 *
 * The caller recomputes when it did. Answering false for an unchanged read is
 * what stops a Refresh on a settled workbook repainting the grid.
 */
export async function resolveRecordFields(sheet, tabs) {
  let { asks, wantsOwn } = collect(tabs)

  // A `RECORD("grand_total")` and no binding in hand: ask what this workbook
  // is about, then work out what to fetch again. An empty ask list is what
  // makes that probe cheap — the server answers the binding and no records.
  if (wantsOwn && !own.doctype) {
    try {
      const first = await workspace.sheetRecordFields(sheet, [])
      setOwnRecord(first?.bound)
    } catch {
      return false
    }
    asks = collect(tabs).asks
  }

  if (!asks.length) return false

  let answer
  try {
    answer = await workspace.sheetRecordFields(sheet, asks)
  } catch {
    return false
  }

  let moved = false
  for (const [key, said] of Object.entries(answer?.records || {})) {
    const before = held.get(key)
    if (JSON.stringify(before) !== JSON.stringify(said)) moved = true
    held.set(key, said)
  }
  return moved
}
