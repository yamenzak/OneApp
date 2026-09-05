// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/engine/formats.test.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/sheets/VENDORED.md before editing or moving it.

import { describe, it, expect, beforeEach } from 'vitest'
import { createFormatsEngine } from './formats.js'

describe('formats engine — cell layer (unchanged behaviour)', () => {
  let f
  beforeEach(() => { f = createFormatsEngine() })

  it('set/get/clear a single cell', () => {
    f.set('A1', { bold: true })
    expect(f.get('A1')).toEqual({ bold: true })
    f.clear('A1')
    expect(f.get('A1')).toEqual({})
  })

  it('toggleRange turns on when any cell lacks the key', () => {
    f.set('A1', { bold: true })
    f.toggleRange(['A1', 'A2'], 'bold')   // A2 lacks bold → turn ON
    expect(f.get('A1').bold).toBe(true)
    expect(f.get('A2').bold).toBe(true)
  })

  it('get returns the raw cell object on the fast path (no col/row formats)', () => {
    f.set('A1', { italic: true })
    expect(f.getCellFormat('A1')).toEqual({ italic: true })
  })
})

describe('formats engine — column / row cascade', () => {
  let f
  beforeEach(() => { f = createFormatsEngine() })

  it('column format applies to every cell in the column', () => {
    f.setCol(5, { bold: true })            // column F
    expect(f.get('F1').bold).toBe(true)
    expect(f.get('F999').bold).toBe(true)
    expect(f.get('A1').bold).toBeUndefined()
  })

  it('cell overrides row overrides column (most specific wins)', () => {
    f.setCol(0, { bold: true, color: 'red' })  // column A
    f.setRow(2, { italic: true })              // row 3
    f.set('A1', { color: 'blue' })
    expect(f.get('A1')).toEqual({ bold: true, color: 'blue' })             // col + cell override
    expect(f.get('A2')).toEqual({ bold: true, color: 'red' })              // just the column
    expect(f.get('A3')).toEqual({ bold: true, color: 'red', italic: true }) // col + row merged
    expect(f.get('B3')).toEqual({ italic: true })                          // just the row
  })

  it('getCellFormat ignores the cascade so undo captures only the cell layer', () => {
    f.setCol(0, { bold: true })
    f.set('A1', { italic: true })
    expect(f.getCellFormat('A1')).toEqual({ italic: true })
  })

  it('toggleColumns flips the whole column with one entry', () => {
    f.toggleColumns([0, 1], 'bold')
    expect(f.getCol(0).bold).toBe(true)
    expect(f.getCol(1).bold).toBe(true)
    f.toggleColumns([0, 1], 'bold')        // all on → turn off
    expect(f.getCol(0).bold).toBe(false)
  })

  it('replaceCol replaces (not merges) — undo restores exact state', () => {
    f.setCol(0, { bold: true, italic: true })
    f.replaceCol(0, { bold: true })        // italic dropped
    expect(f.getCol(0)).toEqual({ bold: true })
    f.replaceCol(0, {})                     // empty → entry removed
    expect(f.getCol(0)).toEqual({})
  })

  it('clearColumns drops the column layer', () => {
    f.setCol(3, { bold: true })
    f.clearColumns([3])
    expect(f.get('D1').bold).toBeUndefined()
  })
})

describe('formats engine — snapshot / restore', () => {
  let f
  beforeEach(() => { f = createFormatsEngine() })

  it('round-trips the layered shape', () => {
    f.setCol(2, { bold: true })
    f.setRow(4, { italic: true })
    f.set('A1', { color: 'red' })
    const snap = f.snapshot()
    const g = createFormatsEngine()
    g.restore(snap)
    expect(g.get('C1').bold).toBe(true)
    expect(g.get('A5').italic).toBe(true)
    expect(g.get('A1').color).toBe('red')
  })

  it('restores LEGACY flat { sheet: { cellId: fmt } } snapshots', () => {
    const g = createFormatsEngine()
    g.restore({ Sheet1: { A1: { bold: true }, B2: { color: 'red' } } })
    expect(g.get('A1')).toEqual({ bold: true })
    expect(g.get('B2')).toEqual({ color: 'red' })
  })
})

describe('formats engine — structural shifts move col/row layers', () => {
  let f
  beforeEach(() => { f = createFormatsEngine() })

  it('insertCol shifts column format keys right', () => {
    f.setCol(2, { bold: true })            // column C
    f.insertCol(1)                          // insert before B → C becomes D
    expect(f.getCol(3).bold).toBe(true)
    expect(f.getCol(2).bold).toBeUndefined()
  })

  it('deleteRow shifts row format keys up and drops the deleted one', () => {
    f.setRow(5, { italic: true })
    f.deleteRow(3)
    expect(f.getRow(4).italic).toBe(true)
    expect(f.getRow(5).italic).toBeUndefined()
  })
})
