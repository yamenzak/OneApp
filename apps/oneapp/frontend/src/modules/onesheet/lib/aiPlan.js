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

/**
 * A style with Vue taken off it.
 *
 * The format layer's undo `structuredClone`s what it captured, and a Proxy
 * cannot be cloned — so the moment a style grew a *nested* object (a border is
 * `{style, color}`) the whole save path threw and the plan landed in the grid
 * and nowhere else. Every flat style before it survived by accident: a string
 * read off a Proxy is a string.
 *
 * Through JSON rather than `toRaw`, because what is being undone is the
 * reactivity of a plan the server sent as JSON — there is nothing in here that
 * JSON cannot carry, and `toRaw` would unwrap only the outer object.
 */
function plain(style) {
  try {
    return JSON.parse(JSON.stringify(style || {}))
  } catch {
    return {}
  }
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
 *   - `setWidth(from, to, px, tab)` — columns, one-based; `px` 0 means fit
 *   - `freeze(rows, cols, tab)` — panes, counted from the top-left
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
      if (ids.length) api.applyFormat?.(ids, plain(step.style), step.tab)
      continue
    }

    if (step.op === 'width') {
      // One-based, the way A1 counts. `px` of 0 is "fit it to what is in it",
      // which is the one a plan almost always wants: the model has no idea
      // how wide the window is and a guessed pixel width is a guess.
      api.setWidth?.(step.from, step.to, step.px || 0, step.tab)
      continue
    }

    if (step.op === 'freeze') {
      api.freeze?.(step.rows || 0, step.cols || 0, step.tab)
      continue
    }

    if (step.op === 'name') {
      api.addNamedRange?.(step.label, step.tab, step.ref)
    }
  }
  return done
}
