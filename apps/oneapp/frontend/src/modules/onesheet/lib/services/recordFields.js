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

//: `RECORD(...)` and `RECORDROW(...)`, as they appear in a stored formula.
//: Only the arguments are read here — the engine does the evaluating; this
//: needs to know which records to fetch before it can. Two patterns rather
//: than one with an optional suffix, because what the arguments *mean*
//: differs and a single sweep would have to tell them apart afterwards.
const CALL = /\bRECORD\s*\(([^()]*)\)/gi
const ROW_CALL = /\bRECORDROW\s*\(([^()]*)\)/gi

//: One workbook's answers: `"doctype\x1fname" → {fieldname: {value, text}}`.
//: Module-level because it is keyed by record: two workbooks open on the same
//: quotation want the same number, not two of them.
const held = new Map()

//: And its schedules: `"doctype\x1fname\x1ftable" → {columns, rows, values}`.
//: A second map rather than a nested one, because a table is fetched by a
//: different ask and a cell reads it by a different function.
const blocks = new Map()

//: The workbook's sources, by key — `{key: {doctype, name}}`, and `''` for
//: the first, which is what a bare `RECORD("grand_total")` means. Filled from
//: the server's answer; empty until the workbook has been read once.
let keyed = new Map()

/**
 * Point the engine at this cache. Called once, when the module loads.
 *
 * `row` says which of the two functions is asking. `undefined` back is
 * `#N/A` — honestly what is known before the fetch, and forever for a record
 * this person may not read. A *row* past the end of a schedule answers
 * `null`, which the engine turns into a blank: a line that was deleted
 * leaves a gap, not an error.
 */
setRecordResolver((args, row = false) => {
  if (row) return rowCell(args)
  const where = which(args)
  if (!where?.doctype || !where.name || !where.field) return undefined
  const said = held.get(`${where.doctype}${SEP}${where.name}`)?.[where.field]
  // The number, never the text: a cell that says `AED 144,235.00` cannot be
  // added up, and a formula around this one is the ordinary case.
  return said?.value
})

/** `RECORDROW(source, table, index, column)` — one cell of a schedule. */
function rowCell(args) {
  const [key, table, index, column] = Array.isArray(args) ? args : []
  const where = keyed.get(key || '')
  if (!where?.doctype || !where.name || !table || !column) return undefined

  const found = blocks.get(`${where.doctype}${SEP}${where.name}${SEP}${table}`)
  if (!found) return undefined

  const at = Number(index)
  if (!Number.isFinite(at) || at < 1) return undefined
  const line = (found.values || [])[at - 1]
  // Past the last line. A blank, not `#N/A`: the schedule is shorter than the
  // block somebody wrote, which is a fact about the record rather than a
  // failure to read it.
  if (!line) return null

  const on = (found.columns || []).findIndex((one) => one.fieldname === column)
  // A column the block names and this reader may not see. `#N/A`, the same
  // answer a field behind a permlevel gets.
  if (on < 0) return undefined
  return line[on] ?? null
}

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

/**
 * What every source says now, keyed the way the rail reads it.
 *
 * `{"key.field": text}` — the *text*, not the value, because this is a
 * preview beside a field's name and `AED 144,235.00` is what a person
 * recognises. The cells get `value`; see the resolver above.
 */
/**
 * Put schedules in the cache without going through a recompute.
 *
 * What Load calls when it asks for a table nothing in the workbook names
 * yet: the answer has to be in the cache before the block it writes can
 * resolve, and the block is what would otherwise have triggered the fetch.
 */
export function setTables(answered) {
  for (const [key, table] of Object.entries(answered || {})) blocks.set(key, table)
}

/**
 * One schedule, as the rail's Load pressed it: `{columns, values}`.
 *
 * Read straight out of the cache the cells resolve through, so the block a
 * person is about to write and the block they will read back cannot
 * disagree about which columns those are.
 */
export function block(key, table) {
  const where = keyed.get(key || '')
  if (!where?.doctype || !where.name) return null
  return blocks.get(`${where.doctype}${SEP}${where.name}${SEP}${table}`) || null
}

export function said() {
  const out = {}
  for (const [key, where] of keyed) {
    if (!key || !where.doctype || !where.name) continue
    const answers = held.get(`${where.doctype}${SEP}${where.name}`) || {}
    for (const [field, one] of Object.entries(answers)) {
      out[`${key}.${field}`] = one?.text ?? ''
    }
  }
  return out
}

/** Forget everything. What closing a workbook does. */
export function forgetRecordFields() {
  held.clear()
  blocks.clear()
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

      // The schedules first. A block is a hundred cells naming one table, so
      // what matters here is that they fold into one ask — the columns
      // union, the row index ignored, because the answer is the whole table.
      for (const found of raw.matchAll(ROW_CALL)) {
        const [key, table, , column] = split(found[1])
        if (!table || !column) continue
        if (!keyed.size) { wantsSources = true; continue }
        const where = keyed.get(key || '')
        if (!where?.doctype || !where.name) continue
        add(asks, `#${where.doctype}${SEP}${where.name}${SEP}${table}`, column)
      }

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
    if (key.startsWith('#')) {
      const [doctype, name, table] = key.slice(1).split(SEP)
      return { doctype, name, table, fields: [...wanted] }
    }
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
  for (const [key, table] of Object.entries(answer?.tables || {})) {
    const before = blocks.get(key)
    if (JSON.stringify(before) !== JSON.stringify(table)) moved = true
    blocks.set(key, table)
  }
  return moved
}
