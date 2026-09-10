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
 * A workbook reads a *set* of records rather than one, keyed, the same way a
 * document does — `shared/binding.py`. So there are three forms, and the
 * middle one is the reason this file knows what a key is:
 *
 *     RECORD("grand_total")                       the first record
 *     RECORD("customer", "credit_limit")          one of them, by key
 *     RECORD("Quotation", "SAL-QTN-0005", "qty")  one named outright
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

//: The workbook's sources, by key — `{key: {doctype, name}}`, and `''` for
//: the first, which is what a bare `RECORD("grand_total")` means. Filled from
//: the server's answer; empty until the workbook has been read once.
let keyed = new Map()

/** Point the engine at this cache. Called once, when the module loads. */
setRecordResolver((args) => {
  const where = which(args)
  if (!where?.doctype || !where.name || !where.field) return undefined
  const said = held.get(`${where.doctype}${SEP}${where.name}`)?.[where.field]
  // The number, never the text: a cell that says `AED 144,235.00` cannot be
  // added up, and a formula around this one is the ordinary case.
  return said?.value
})

/**
 * Which record and field one call means.
 *
 * The one place the three forms are told apart, and it is told apart by
 * *count* rather than by which arguments look like doctypes: with
 * `RECORD("Quotation", A1, "qty")` the middle one is a reference and arrives
 * empty, and guessing from the shape of what is left would fetch a field
 * called Quotation.
 */
function which(args) {
  const given = Array.isArray(args) ? args : []
  if (given.length >= 3) {
    return { doctype: given[0], name: given[1], field: given[2] }
  }
  const [key, field] = given.length === 2 ? given : ['', given[0] || '']
  return { ...(keyed.get(key) || {}), field }
}

/** What the workbook reads — `binding.file_sources`'s answer. */
export function setSources(sources) {
  keyed = new Map()
  const rows = sources || []
  rows.forEach((row, at) => {
    const where = { doctype: row.reference_doctype, name: row.reference_name || '' }
    keyed.set(row.key, where)
    // A bare token means the first source, whatever its key happens to be.
    if (at === 0) keyed.set('', where)
  })
}

/** Forget everything. What closing a workbook does. */
export function forgetRecordFields() {
  held.clear()
  keyed = new Map()
}

/**
 * Every record and field the formulas in these tabs name.
 *
 * `tabs` is `{tabName: {cellId: rawValue}}` — the shape the store holds. Read
 * off the raw text rather than off the parsed formulas, because the parse is
 * the engine's and this runs before it: the question is what to fetch, and
 * the engine cannot answer it without the fetch.
 *
 * A call naming a key comes back as `{source, fields}` rather than resolved
 * here, because the keys may not be known yet — the first open of a workbook
 * asks before it has been told what it reads. The server resolves either.
 */
export function collect(tabs) {
  const asks = new Map()
  // Whether anything named a source we have no record for. One cheap probe
  // fixes it; asking on every open would be a request every ordinary sheet
  // pays for and nothing reads.
  let wantsSources = false

  for (const cells of Object.values(tabs || {})) {
    for (const raw of Object.values(cells || {})) {
      if (typeof raw !== 'string' || !raw.startsWith('=')) continue
      for (const found of raw.matchAll(CALL)) {
        const parts = split(found[1])
        const asked = which(parts)
        if (!asked.field) continue

        if (parts.length >= 3) {
          if (!asked.doctype || !asked.name) continue
          add(asks, `${asked.doctype}${SEP}${asked.name}`, asked.field)
          continue
        }

        // A key. Resolved now if the sources are in hand, sent as a key if
        // they are not — and the second case is also how we learn to stop
        // asking, because the answer carries them.
        const key = parts.length === 2 ? parts[0] : ''
        if (!keyed.size) wantsSources = true
        if (asked.doctype && asked.name) {
          add(asks, `${asked.doctype}${SEP}${asked.name}`, asked.field)
        } else if (!keyed.size) {
          add(asks, `@${key}`, asked.field)
        }
      }
    }
  }

  const out = [...asks].map(([key, wanted]) => {
    if (key.startsWith('@')) return { source: key.slice(1), fields: [...wanted] }
    const [doctype, name] = key.split(SEP)
    return { doctype, name, fields: [...wanted] }
  })
  return { asks: out, wantsSources }
}

function add(asks, key, field) {
  if (!asks.has(key)) asks.set(key, new Set())
  asks.get(key).add(field)
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
  let { asks, wantsSources } = collect(tabs)

  // A keyed call and no sources in hand: ask what this workbook reads, then
  // work out what to fetch again. An empty ask list is what makes that probe
  // cheap — the server answers the sources and no records.
  if (wantsSources && !keyed.size) {
    try {
      const first = await workspace.sheetRecordFields(sheet, [])
      setSources(first?.sources)
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

  if (answer?.sources) setSources(answer.sources)

  let moved = false
  for (const [key, said] of Object.entries(answer?.records || {})) {
    const before = held.get(key)
    if (JSON.stringify(before) !== JSON.stringify(said)) moved = true
    held.set(key, said)
  }
  return moved
}
