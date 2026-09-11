/**
 * Applying a plan to the grid.
 *
 * `onesheet/intelligence.py` says why the answer is a plan and not cells: the
 * engine that evaluates `=SUM(D2:D20)` is in this browser, so a server that
 * wrote the formula would be writing a workbook whose stored values disagree
 * with it. The server validates every step against the workbook that exists —
 * a tab that is not there, a reference that does not parse, a rectangle bigger
 * than the store allows — and this applies what survived.
 *
 * It applies through the same calls the toolbar and the formula bar use, and
 * that is the whole reason this file is small: `setCell` and `applyToRange`
 * already record an op, so one press of Undo takes the entire plan back and a
 * colleague in the same workbook watches it arrive. Nothing here writes to the
 * store directly.
 *
 * The functions are handed in rather than imported. The editor owns the engine
 * instances, and a module that reached for them would be a second place that
 * knows how a workbook is wired — which is how the 4,000-line editor happened
 * the first time.
 */

/** A1 of the anchor, plus an offset. `refs.py` is the server's half of this. */
function at(ref, downBy, rightBy) {
  const [, letters, digits] = /^([A-Za-z]{1,3})([0-9]{1,7})$/.exec(ref) || []
  if (!letters) return null

  let column = 0
  for (const one of letters.toUpperCase()) column = column * 26 + (one.charCodeAt(0) - 64)
  column += rightBy

  let said = ''
  let n = column
  while (n > 0) {
    const rest = (n - 1) % 26
    said = String.fromCharCode(65 + rest) + said
    n = Math.floor((n - 1) / 26)
  }
  return `${said}${Number(digits) + downBy}`
}

/** Every cell id in `A1:C3`, row-major. */
export function cellsIn(range) {
  const corner = (ref) => {
    const [, letters, digits] = /^([A-Za-z]{1,3})([0-9]{1,7})$/.exec(ref || '') || []
    if (!letters) return null
    let column = 0
    for (const one of letters.toUpperCase()) column = column * 26 + (one.charCodeAt(0) - 64)
    return { row: Number(digits), column }
  }

  const [from, to] = String(range || '').split(':')
  const a = corner(from)
  // Validated even where there is one corner: the server checks every
  // reference it hands over, and a caller that skipped that must not turn
  // "nonsense" into a cell id the format layer then writes against.
  if (!a) return []
  const b = to ? corner(to) : a
  if (!b) return []

  const ids = []
  for (let row = Math.min(a.row, b.row); row <= Math.max(a.row, b.row); row += 1) {
    for (let col = Math.min(a.column, b.column); col <= Math.max(a.column, b.column); col += 1) {
      ids.push(at('A1', row - 1, col - 1))
    }
  }
  return ids
}

/**
 * Apply one validated plan.
 *
 * @param {Array} steps  what `onesheet.ask` returned, already checked
 * @param {object} api
 *   - `setCell(id, value, tab)` — the engine's own write
 *   - `pushEdit(tab, beforeMap, summary)` — `useEditOps.pushEditOp`
 *   - `applyFormat(ids, patch, tab)` — the format layer's range patch
 *   - `addTab(name)` — make a sheet, returning its name
 *   - `addNamedRange(label, tab, ref)` — optional; skipped where absent
 *   - `readCell(id, tab)` — what is there now, for the undo diff
 * @returns {{written: number, tabs: string[], touched: string[]}}
 *   what landed, so the caller can say so and put the glow on it
 */
export function applyPlan(steps, api) {
  const done = { written: 0, tabs: [], touched: [] }
  if (!Array.isArray(steps) || !steps.length) return done

  for (const step of steps) {
    if (step.op === 'tab') {
      const made = api.addTab?.(step.name)
      if (made) done.tabs.push(made)
      continue
    }

    if (step.op === 'set') {
      // Captured before the writes, because that is what `pushEditOp`
      // diffs against — see `useEditOps.js`.
      const before = {}
      const ids = []
      step.values.forEach((row, down) => {
        row.forEach((value, right) => {
          const id = at(step.ref, down, right)
          if (!id) return
          before[id] = api.readCell?.(id, step.tab)
          ids.push([id, value])
        })
      })
      for (const [id, value] of ids) api.setCell(id, value, step.tab)
      api.pushEdit?.(step.tab, before, 'AI')
      done.written += ids.length
      done.touched.push(...ids.map(([id]) => `${step.tab}!${id}`))
      continue
    }

    if (step.op === 'format') {
      const ids = cellsIn(step.ref)
      if (ids.length) api.applyFormat?.(ids, step.style, step.tab)
      continue
    }

    if (step.op === 'name') {
      api.addNamedRange?.(step.label, step.tab, step.ref)
    }
  }
  return done
}
