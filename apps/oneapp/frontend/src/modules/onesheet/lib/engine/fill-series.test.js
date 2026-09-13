// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/engine/fill-series.test.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/VENDORED.md before editing or moving it.

import { describe, it, expect } from 'vitest'
import { computeFillDown, computeFillRight } from '@/modules/onesheet/lib/engine/fill-series.js'

// `detectStep` went private upstream. Its seven cases are what `computeFillDown`
// does with a numeric source, so they are asked of it: the step is whatever the
// first filled value is minus the last source one, and "no step" shows as the
// sequence being copied rather than continued.
describe('the step it continues by', () => {
	// A column of values, filled down: `computeFillDown` takes a grid of raw
	// values and gives back the rows that follow it.
	const filled = (source, count = 1) =>
		computeFillDown(source.map((one) => [one]), count).map((row) => row[0])

	it('continues a positive step', () => {
		expect(filled([1, 3, 5], 2)).toEqual([7, 9])
	})

	it('continues a negative step', () => {
		expect(filled([10, 7, 4], 2)).toEqual([1, -2])
	})

	it('repeats a constant sequence', () => {
		expect(filled([5, 5, 5], 2)).toEqual([5, 5])
	})

	it('continues a fractional step', () => {
		expect(filled([1, 1.5, 2], 2)).toEqual([2.5, 3])
	})

	it('copies rather than extrapolates a non-arithmetic sequence', () => {
		// 1, 2, 4 has no single step, so the block repeats from the start.
		expect(filled([1, 2, 4], 3)).toEqual([1, 2, 4])
	})

	it('takes a step from exactly two values', () => {
		expect(filled([2, 6], 2)).toEqual([10, 14])
	})

	it('copies a single value, having no step to find', () => {
		expect(filled([7], 2)).toEqual([7, 7])
	})
})

describe('computeFillDown', () => {
  it('fills down from a horizontal source — the user\'s primary use case', () => {
    // C1=3, D1=4 → drag down → C2=5 D2=6, C3=7 D3=8
    expect(computeFillDown([[3, 4]], 2)).toEqual([[5, 6], [7, 8]])
  })

  it('fills down from a single-cell numeric source by repeating', () => {
    // No cross-value step detectable → repeat
    expect(computeFillDown([[7]], 3)).toEqual([[7], [7], [7]])
  })

  it('repeats a non-arithmetic row when no step found', () => {
    expect(computeFillDown([[1, 3, 6]], 2)).toEqual([[1, 3, 6], [1, 3, 6]])
  })

  it('repeats non-numeric rows', () => {
    expect(computeFillDown([['a', 'b']], 2)).toEqual([['a', 'b'], ['a', 'b']])
  })

  it('fills down from a vertical source using per-column step', () => {
    // A1=1 A2=3, B1=3 B2=5 → col A step=2, col B step=2
    expect(computeFillDown([[1, 3], [3, 5]], 2)).toEqual([[5, 7], [7, 9]])
  })

  it('cycles columns whose per-column values are non-arithmetic', () => {
    // col A [1,2,4] diffs [1,2] – not constant → cycle; col B [2,3,5] same
    expect(computeFillDown([[1, 2], [2, 3], [4, 5]], 2)).toEqual([[1, 2], [2, 3]])
  })

  it('fills upward (dir = -1) from a horizontal source', () => {
    // C3=3, D3=4, fill UP 1 row → C2=1, D2=2
    expect(computeFillDown([[3, 4]], 1, -1)).toEqual([[1, 2]])
  })

  it('fills upward from a vertical source', () => {
    // A2=3, A3=5 (step=2), fill UP 1 row → A1=1
    expect(computeFillDown([[3], [5]], 1, -1)).toEqual([[1]])
  })
})

describe('computeFillRight', () => {
  it('fills right from a horizontal source using per-row step', () => {
    // A1=3, B1=4 → C1=5, D1=6
    expect(computeFillRight([[3, 4]], 2)).toEqual([[5, 6]])
  })

  it('fills right from a vertical single-column source using cross-row step', () => {
    // A1=3, A2=4 → B1=5 B2=6
    expect(computeFillRight([[3], [4]], 2)).toEqual([[5, 7], [6, 8]])
  })

  it('repeats non-numeric single-column source', () => {
    expect(computeFillRight([['x'], ['y']], 2)).toEqual([['x', 'x'], ['y', 'y']])
  })

  it('cycles a non-arithmetic multi-column source', () => {
    // [1,3,6] non-arithmetic → repeat cols
    expect(computeFillRight([[1, 3, 6]], 3)).toEqual([[1, 3, 6]])
  })

  it('fills leftward (dir = -1) from a horizontal source', () => {
    // Source C1=3, D1=4 (step=1). One step back from C1=3 is B1=2.
    expect(computeFillRight([[3, 4]], 1, -1)).toEqual([[2]])
  })
})

// ── Integration: smart patterns wired into computeFillDown ──────────────────
// These exercise the date + named-sequence detectors through the same entry
// point that SheetEditor's onFill calls.

describe('computeFillDown integration', () => {
  it('extends a daily date column', () => {
    // Each cell is its own row, so this goes through _fillVerticalFromCols.
    expect(computeFillDown([['01-04-2025'], ['02-04-2025']], 2))
      .toEqual([['03-04-2025'], ['04-04-2025']])
  })

  it('extends a monthly date column', () => {
    expect(computeFillDown([['Jan-2025'], ['Feb-2025']], 2))
      // Detector returns null for this format (only matches DMY/MDY/YMD),
      // so we expect cycling — verifies the fallback path.
      .toEqual([['Jan-2025'], ['Feb-2025']])
  })

  it('extends month-name column', () => {
    expect(computeFillDown([['Jan'], ['Feb']], 2))
      .toEqual([['Mar'], ['Apr']])
  })

  it('extends day-name column with wrap-around', () => {
    expect(computeFillDown([['Fri'], ['Sat']], 2))
      .toEqual([['Sun'], ['Mon']])
  })

  it('extends month names preserving lowercase', () => {
    expect(computeFillDown([['jan'], ['feb']], 1))
      .toEqual([['mar']])
  })

  it('fills backward through a named sequence', () => {
    expect(computeFillDown([['Wed'], ['Thu']], 2, -1))
      .toEqual([['Tue'], ['Mon']])
  })

  it('mode:copy forces cycling even when a series is detectable', () => {
    // 1, 2 would normally extend to 3, 4 — copy mode cycles the source.
    expect(computeFillDown([[1], [2]], 3, 1, { mode: 'copy' }))
      .toEqual([[1], [2], [1]])
  })

  it('mode:series leaves the auto-detected pattern intact', () => {
    expect(computeFillDown([[1], [2]], 2, 1, { mode: 'series' }))
      .toEqual([[3], [4]])
  })
})
