// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/engine/format-scope.test.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/sheets/VENDORED.md before editing or moving it.

import { describe, it, expect } from 'vitest'
import { formatScope } from './format-scope.js'

describe('formatScope', () => {
  const R = 1000, C = 26

  it('treats a full-height selection as column-level', () => {
    expect(formatScope({ r0: 0, c0: 5, r1: 999, c1: 5 }, R, C)).toEqual({ kind: 'cols', cols: [5] })
  })

  it('spans multiple columns', () => {
    expect(formatScope({ r0: 0, c0: 2, r1: 999, c1: 4 }, R, C)).toEqual({ kind: 'cols', cols: [2, 3, 4] })
  })

  it('treats a full-width selection as row-level', () => {
    expect(formatScope({ r0: 7, c0: 0, r1: 9, c1: 25 }, R, C)).toEqual({ kind: 'rows', rows: [7, 8, 9] })
  })

  it('prefers columns for a whole-sheet selection (they cover every cell)', () => {
    expect(formatScope({ r0: 0, c0: 0, r1: 999, c1: 25 }, R, C).kind).toBe('cols')
  })

  it('stays per-cell for a partial rectangle', () => {
    expect(formatScope({ r0: 1, c0: 1, r1: 4, c1: 3 }, R, C)).toEqual({ kind: 'cells' })
  })

  it('tolerates r1/c1 reported past the grid bound', () => {
    expect(formatScope({ r0: 0, c0: 1, r1: 1001, c1: 1 }, R, C).kind).toBe('cols')
  })
})
