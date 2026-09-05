/**
 * The workbook in memory: what every cell holds, and what changes when one does.
 *
 * This is the half of a spreadsheet the server does not do. `Sheet Cell` keeps
 * `raw` beside `value` and never reads `raw`; the browser is what turns
 * `=C2*D2*E2*F2/1000000` into `6480`, and this module is that. See
 * `docs/SHEETS.md` §1 for why the evaluation lives here rather than there.
 *
 * Three things happen when somebody types into a cell:
 *
 *   1. the cell's own value is worked out,
 *   2. every cell that depends on it, directly or through a chain, is worked
 *      out again, in an order where nothing is computed before what it reads,
 *   3. the caller is handed the list of cells that actually changed, which is
 *      what gets sent to the server and what the grid repaints.
 *
 * Step 2 is the whole of the difficulty. A sheet is a graph, formulas point at
 * each other, and a naive "recompute everything" is fine at twenty cells and
 * visible at two thousand. `dependents()` walks the reverse graph and
 * `ordered()` topologically sorts what it finds; a cycle is not an error the
 * user should have to debug from a stack trace, so cells inside one are given
 * `#CIRCULAR!` and the walk carries on.
 *
 * `fast-formula-parser` (MIT) does the parsing and the four hundred functions.
 * It is wrapped rather than used directly for two reasons that both bit during
 * the build: an unknown function *throws* where every other failure returns an
 * error value, and its errors are objects rather than the strings a cell holds.
 */

import FormulaParser from 'fast-formula-parser'

// Destructured off the default rather than imported by name: the package is
// CommonJS and hangs these on the class as statics, which Node's named-export
// detection does not see. `import { DepParser }` throws at load.
const { DepParser, FormulaError } = FormulaParser

import { format, parse } from './refs'

/** A cell nobody has typed in. Distinct from a cell holding the empty string. */
const BLANK = null

/**
 * Excel's own answer for a formula that reads itself, which Excel words as a
 * warning and a zero. A visible error is the better answer in a product where
 * the sheet feeds an invoice: a zero that should have been a total is the one
 * failure nobody notices.
 */
export const CIRCULAR = '#CIRCULAR!'

export function key(tab, ref) {
  return `${tab}!${ref}`
}

function split(cellKey) {
  const at = cellKey.lastIndexOf('!')
  return { tab: cellKey.slice(0, at), ref: cellKey.slice(at + 1) }
}

function isFormula(raw) {
  return typeof raw === 'string' && raw.startsWith('=') && raw.length > 1
}

/**
 * What a raw string means when it is not a formula.
 *
 * Deliberately shorter than Excel's coercion: a number is a number, `TRUE` and
 * `FALSE` are booleans, and everything else is text. Dates are *not* guessed —
 * a sheet that reads `3/4` as the third of April for one person and the fourth
 * of March for another is worse than one that reads it as text, and the cell
 * format is where a date is declared.
 */
export function literal(raw) {
  if (raw === BLANK || raw === '') return { value: BLANK, kind: '' }

  const text = String(raw)
  const upper = text.trim().toUpperCase()
  if (upper === 'TRUE' || upper === 'FALSE') {
    return { value: upper === 'TRUE', kind: 'bool' }
  }

  // `Number('')` is 0 and `Number(' ')` is 0, which is how a cell holding a
  // space becomes a zero if this is written the obvious way.
  const trimmed = text.trim()
  if (trimmed && !Number.isNaN(Number(trimmed))) {
    return { value: Number(trimmed), kind: 'number' }
  }

  return { value: text, kind: 'text' }
}

/**
 * A workbook.
 *
 * `cells` is a flat `Map` keyed `Tab!A1` rather than a per-tab grid, for the
 * same reason `Sheet Cell` is a table: a sheet is mostly empty, and a grid of
 * arrays for a hundred rows nobody used is a hundred rows of `undefined`.
 */
export function makeWorkbook(initial = []) {
  const cells = new Map()
  /** cellKey -> Set(cellKey) — who reads me. Built as formulas are parsed. */
  const readers = new Map()
  /** [{ key, sheet, from, to }] — the same, for cells read through a range. */
  const rangeReaders = []
  /**
   * cellKey -> what that formula reads, so forgetting it is proportional to
   * its own dependencies rather than to the size of the workbook. Without this
   * every keystroke sweeps every reader set, which is invisible at twenty
   * cells and quadratic at twenty thousand.
   */
  const reads = new Map()

  const depParser = new DepParser()
  const parser = new FormulaParser({
    onCell: ({ sheet, row, col }) => valueAt(sheet, row, col),
    onRange: (ref) => {
      const rows = []
      for (let row = ref.from.row; row <= ref.to.row; row++) {
        const line = []
        for (let column = ref.from.col; column <= ref.to.col; column++) {
          line.push(valueAt(ref.sheet, row, column))
        }
        rows.push(line)
      }
      return rows
    },
  })

  function valueAt(tab, row, column) {
    const cell = cells.get(key(tab, format(row, column)))
    if (!cell) return BLANK
    return cell.value === undefined ? BLANK : cell.value
  }

  for (const row of initial) put(row.tab, row.ref, row.raw, row.value, row.kind, row.format_json)

  function put(tab, ref, raw, value, kind, formatJson, because = '') {
    const cell = {
      tab,
      ref,
      raw: raw ?? BLANK,
      value: value === undefined ? BLANK : value,
      kind: kind || '',
      format: formatJson || null,
      // Why a cell reads `#NAME?`, for the tooltip. Client-side only: the
      // server stores the error value, not the sentence explaining it.
      because,
    }
    cells.set(key(tab, ref), cell)
    return cell
  }

  function get(tab, ref) {
    return cells.get(key(tab, ref)) || null
  }

  // ----------------------------------------------------------------------- //
  // Dependencies
  // ----------------------------------------------------------------------- //

  /**
   * Record what one formula reads, so a change to any of it can find its way
   * back here.
   *
   * Precise cells go in a reverse index and are O(1) to look up. Ranges go in
   * a list that is scanned, because `=SUM(A:A)` names a million cells and
   * indexing them would cost a million entries to answer a question a
   * containment test answers in a comparison. The list is short: it holds one
   * entry per range in the workbook, not per cell.
   */
  function record(cellKey, raw, tab) {
    forget(cellKey)
    if (!isFormula(raw)) return

    const mine = { cells: [], ranges: [] }
    reads.set(cellKey, mine)

    const { row, column } = parse(split(cellKey).ref)
    let found
    try {
      found = depParser.parse(raw.slice(1), { sheet: tab, row, col: column })
    } catch {
      // A formula that will not parse reads nothing, and says so as a value
      // when it is evaluated. Nothing to record.
      return
    }

    for (const dep of found) {
      if (dep.from) {
        const watcher = { key: cellKey, sheet: dep.sheet, from: dep.from, to: dep.to }
        rangeReaders.push(watcher)
        mine.ranges.push(watcher)
      } else {
        const target = key(dep.sheet, format(dep.row, dep.col))
        if (!readers.has(target)) readers.set(target, new Set())
        readers.get(target).add(cellKey)
        mine.cells.push(target)
      }
    }
  }

  function forget(cellKey) {
    const mine = reads.get(cellKey)
    if (!mine) return
    for (const target of mine.cells) readers.get(target)?.delete(cellKey)
    for (const watcher of mine.ranges) {
      const at = rangeReaders.indexOf(watcher)
      if (at >= 0) rangeReaders.splice(at, 1)
    }
    reads.delete(cellKey)
  }

  /** Who reads this cell — directly, and through any range that covers it. */
  function directReaders(cellKey) {
    const out = new Set(readers.get(cellKey) || [])
    const { tab, ref } = split(cellKey)
    let at
    try {
      at = parse(ref)
    } catch {
      return out
    }
    for (const watcher of rangeReaders) {
      if (watcher.sheet !== tab) continue
      if (at.row < watcher.from.row || at.row > watcher.to.row) continue
      if (at.column < watcher.from.col || at.column > watcher.to.col) continue
      out.add(watcher.key)
    }
    return out
  }

  /**
   * Everything downstream of these cells, in an order safe to evaluate.
   *
   * A depth-first walk that emits a node only once everything reading it has
   * been emitted, reversed — which is a topological sort. `onPath` catches a
   * cycle: a node reached while it is still on the path back to the root reads
   * itself, and everything from there to the top of the path is on the loop.
   *
   * Written with an explicit stack rather than recursion, and that is not
   * style. A column of four thousand formulas each reading the one above is a
   * plausible sheet and recursed fine; twenty thousand — which our own cell cap
   * allows — overflowed the call stack and took the grid down with it.
   */
  function ordered(seeds) {
    const out = []
    const done = new Set()
    const onPath = new Set()
    const path = []
    const circular = new Set()
    const frames = []

    const enter = (cellKey) => {
      onPath.add(cellKey)
      path.push(cellKey)
    }
    const leave = () => onPath.delete(path.pop())

    for (const seed of seeds) {
      if (done.has(seed)) continue
      enter(seed)
      // The seed is walked but never emitted: it is what just changed. It goes
      // on the path all the same, because `=A1+1` typed into A1 is a cycle and
      // this is the only place it can be caught.
      frames.push({ key: seed, readers: [...directReaders(seed)], at: 0, emit: false })

      while (frames.length) {
        const frame = frames[frames.length - 1]
        if (frame.at < frame.readers.length) {
          const next = frame.readers[frame.at++]
          if (done.has(next)) continue
          if (onPath.has(next)) {
            for (const node of path.slice(path.indexOf(next))) circular.add(node)
            continue
          }
          enter(next)
          frames.push({ key: next, readers: [...directReaders(next)], at: 0, emit: true })
        } else {
          frames.pop()
          leave()
          done.add(frame.key)
          if (frame.emit) out.push(frame.key)
        }
      }
    }

    out.reverse()
    return { order: out, circular }
  }

  // ----------------------------------------------------------------------- //
  // Evaluation
  // ----------------------------------------------------------------------- //

  /**
   * One cell's value from its raw string.
   *
   * Every failure comes back as a cell value rather than an exception, because
   * a cell holding `#NAME?` is a spreadsheet behaving correctly and a thrown
   * error is a grid that stops repainting.
   */
  function evaluate(tab, ref, raw) {
    if (!isFormula(raw)) return literal(raw)

    const { row, column } = parse(ref)
    let result
    try {
      result = parser.parse(raw.slice(1), { sheet: tab, row, col: column }, true)
    } catch (error) {
      // `fast-formula-parser` throws for a function it does not implement,
      // where every other failure is a returned error value — and it words
      // that one `#ERROR!`. Excel says `#NAME?` for a name it does not know,
      // and a person comparing the two sheets is the audience, so the
      // translation happens here rather than being explained later.
      if (error instanceof FormulaError) {
        const unknown = /is not implemented/.test(error.message || '')
        return {
          value: unknown ? '#NAME?' : error.toString(),
          kind: 'error',
          because: error.message || '',
        }
      }
      return { value: '#ERROR!', kind: 'error', because: String(error?.message || error) }
    }

    if (result instanceof FormulaError) return { value: result.toString(), kind: 'error' }
    if (Array.isArray(result)) {
      // A formula that returns a rectangle spills in Excel and does not here:
      // spilling writes cells nobody typed in, and undoing that is a feature
      // of its own. The top-left is the answer, which is what Excel did for
      // twenty years before spilling.
      const first = Array.isArray(result[0]) ? result[0][0] : result[0]
      return classify(first)
    }
    return classify(result)
  }

  function classify(value) {
    if (value === null || value === undefined) return { value: BLANK, kind: '' }
    if (typeof value === 'number') {
      // A float that came out of arithmetic carries the binary representation
      // with it — 2.4 * 3 is 7.199999999999999 — and a cell showing that is a
      // cell nobody trusts. Fifteen significant digits is what Excel keeps.
      return { value: Number(value.toPrecision(15)), kind: 'number' }
    }
    if (typeof value === 'boolean') return { value, kind: 'bool' }
    if (value instanceof Date) return { value: value.toISOString().slice(0, 10), kind: 'date' }
    const text = String(value)
    return { value: text, kind: text.startsWith('#') ? 'error' : 'text' }
  }

  // ----------------------------------------------------------------------- //
  // The one thing callers do
  // ----------------------------------------------------------------------- //

  /**
   * Type into cells, and get back every cell that changed.
   *
   * `edits` is `[{ tab, ref, raw, format }]` — a batch, because a paste is a
   * batch and recomputing once for four hundred cells is the difference
   * between instant and a second.
   *
   * The returned rows are exactly the shape `sheets.write_cells` takes, which
   * is not a coincidence: the caller sends what it got.
   */
  function apply(edits) {
    const seeds = []
    const changed = new Map()

    for (const edit of edits) {
      const cellKey = key(edit.tab, edit.ref)
      const raw = edit.raw === '' ? BLANK : edit.raw
      const computed = evaluate(edit.tab, edit.ref, raw)
      const existing = cells.get(cellKey)
      const cellFormat = edit.format === undefined ? existing?.format ?? null : edit.format

      put(edit.tab, edit.ref, raw, computed.value, computed.kind, cellFormat, computed.because)
      record(cellKey, raw, edit.tab)
      seeds.push(cellKey)
      changed.set(cellKey, cells.get(cellKey))
    }

    const { order, circular } = ordered(seeds)

    for (const cellKey of circular) {
      const cell = cells.get(cellKey)
      if (!cell) continue
      cell.value = CIRCULAR
      cell.kind = 'error'
      cell.because = 'This formula depends on its own result.'
      changed.set(cellKey, cell)
    }

    for (const cellKey of order) {
      if (circular.has(cellKey)) continue
      const cell = cells.get(cellKey)
      if (!cell) continue
      const computed = evaluate(cell.tab, cell.ref, cell.raw)
      if (cell.value === computed.value && cell.kind === computed.kind) continue
      cell.value = computed.value
      cell.kind = computed.kind
      cell.because = computed.because || ''
      changed.set(cellKey, cell)
    }

    return [...changed.values()]
  }

  /**
   * Work out every formula in the workbook, in order.
   *
   * Called once after loading, because `Sheet Cell.value` is what some other
   * browser computed and may have been written against a cell that has since
   * changed by a path this one did not see. Cheap — it is the same walk, seeded
   * with every non-formula cell.
   */
  function recalculate() {
    const seeds = []
    for (const [cellKey, cell] of cells) {
      if (isFormula(cell.raw)) record(cellKey, cell.raw, cell.tab)
      else seeds.push(cellKey)
    }
    return apply(seeds.map((cellKey) => {
      const cell = cells.get(cellKey)
      return { tab: cell.tab, ref: cell.ref, raw: cell.raw }
    }))
  }

  /**
   * Rename a tab, carrying its cells with it.
   *
   * The graph is thrown away and rebuilt rather than rewritten, because every
   * formula that named the old tab has to be re-read anyway. What is *not*
   * done here is rewriting `=Sheet1!A1` inside a formula to name the new tab —
   * Excel does that and we do not yet, so a cross-tab formula breaks on a
   * rename. Worth fixing when a second tab is a normal thing to have.
   */
  function renameTab(from, to) {
    for (const [cellKey, cell] of [...cells]) {
      if (cell.tab !== from) continue
      cells.delete(cellKey)
      cell.tab = to
      cells.set(key(to, cell.ref), cell)
    }
    readers.clear()
    rangeReaders.length = 0
    reads.clear()
    recalculate()
  }

  function dropTab(tab) {
    for (const [cellKey, cell] of [...cells]) {
      if (cell.tab === tab) {
        cells.delete(cellKey)
        forget(cellKey)
      }
    }
  }

  return { cells, get, put, apply, evaluate, recalculate, renameTab, dropTab }
}
