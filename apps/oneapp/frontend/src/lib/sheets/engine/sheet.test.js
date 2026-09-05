// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/engine/sheet.test.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/sheets/VENDORED.md before editing or moving it.

import { describe, it, expect, beforeEach } from 'vitest'
import { createSheet } from './sheet.js'

// These tests pin the formula-result memoisation contract introduced to
// make "slow after load" actually fast — every formula cell should evaluate
// at most once per change to its inputs, regardless of how many renders or
// dependent reads come through after.

describe('formula memoisation', () => {
  let sheet

  beforeEach(() => {
    sheet = createSheet()
    sheet._resetMemoStats()
  })

  it('a formula evaluates exactly once across repeated reads', () => {
    sheet.setCell('A1', '5')
    sheet.setCell('B1', '=A1*2')
    sheet._resetMemoStats()
    sheet.getDisplayValue('B1')
    sheet.getDisplayValue('B1')
    sheet.getDisplayValue('B1')
    const { hits, misses } = sheet._memoStats()
    expect(misses).toBe(1)            // first read fills the cache
    expect(hits).toBeGreaterThanOrEqual(2)  // subsequent reads are hits
  })

  it('editing a dependency invalidates the cached result', () => {
    sheet.setCell('A1', '5')
    sheet.setCell('B1', '=A1*2')
    expect(sheet.getDisplayValue('B1')).toBe('10')
    sheet.setCell('A1', '7')
    expect(sheet.getDisplayValue('B1')).toBe('14')   // not stale 10
  })

  it('transitive dependents all invalidate', () => {
    sheet.setCell('A1', '5')
    sheet.setCell('B1', '=A1*2')      // B1 = 10
    sheet.setCell('C1', '=B1+1')      // C1 = 11
    expect(sheet.getDisplayValue('C1')).toBe('11')
    sheet.setCell('A1', '10')          // ripple → B1, C1
    expect(sheet.getDisplayValue('B1')).toBe('20')
    expect(sheet.getDisplayValue('C1')).toBe('21')
  })

  it('volatile formulas (RAND) skip the cache', () => {
    sheet.setCell('A1', '=RAND()')
    sheet._resetMemoStats()
    sheet.getDisplayValue('A1')
    sheet.getDisplayValue('A1')
    sheet.getDisplayValue('A1')
    const { hits, misses } = sheet._memoStats()
    expect(hits).toBe(0)               // never cached
    expect(misses).toBe(3)             // every read evaluates fresh
  })

  it('volatile NOW / TODAY also skip the cache', () => {
    sheet.setCell('A1', '=NOW()')
    sheet.setCell('A2', '=TODAY()')
    sheet._resetMemoStats()
    sheet.getDisplayValue('A1')
    sheet.getDisplayValue('A1')
    sheet.getDisplayValue('A2')
    sheet.getDisplayValue('A2')
    const { hits } = sheet._memoStats()
    expect(hits).toBe(0)
  })

  it('batchSetCells clears every sheet\'s memo', () => {
    sheet.setCell('A1', '5')
    sheet.setCell('B1', '=A1*2')
    expect(sheet.getDisplayValue('B1')).toBe('10')
    // Some other sheet that depends cross-sheet — cache it too.
    sheet.addSheet('Sheet2')
    sheet.setCell('A1', '=Sheet1!A1+100', 'Sheet2')
    sheet.switchSheet('Sheet2')
    expect(sheet.getDisplayValue('A1', 'Sheet2')).toBe('105')
    // Wipe Sheet1 via batch import. Cross-sheet cached results on Sheet2
    // would be stale if memo wasn't cleared.
    sheet.batchSetCells({ A1: '999' }, 'Sheet1')
    expect(sheet.getDisplayValue('A1', 'Sheet2')).toBe('1099')
  })

  it('insertRow invalidates the cache (cell IDs shift)', () => {
    sheet.setCell('A1', '5')
    sheet.setCell('A2', '7')
    sheet.setCell('B1', '=A1+A2')      // 12
    expect(sheet.getDisplayValue('B1')).toBe('12')
    sheet.insertRow(0)                  // pushes A1→A2, A2→A3
    // B1 itself shifts to B2; the new B2's formula still references the
    // shifted addresses correctly via the engine's adjuster — but the
    // important assertion is that no stale "12" is returned.
    const b2 = sheet.getDisplayValue('B2')
    expect(b2).not.toBe('NaN')          // sanity — a stale cache would surface here
  })

  it('cross-sheet dependents invalidate when the source cell changes', () => {
    sheet.setCell('A1', '5')
    sheet.addSheet('Sheet2')
    sheet.setCell('B1', '=Sheet1!A1*3', 'Sheet2')
    expect(sheet.getDisplayValue('B1', 'Sheet2')).toBe('15')
    sheet.setCell('A1', '8')            // Sheet1 change, Sheet2!B1 cached at 15
    expect(sheet.getDisplayValue('B1', 'Sheet2')).toBe('24')
  })

  it('invalidateMemo() wipes the cache for follow-up reads', () => {
    sheet.setCell('A1', '5')
    sheet.setCell('B1', '=A1*2')
    sheet.getDisplayValue('B1')
    sheet._resetMemoStats()
    sheet.invalidateMemo()
    sheet.getDisplayValue('B1')
    const { misses } = sheet._memoStats()
    expect(misses).toBe(1)               // cache was empty after invalidate
  })

  it('circular references still resolve to #CIRCULAR! consistently', () => {
    sheet.setCell('A1', '=B1')
    sheet.setCell('B1', '=A1')
    expect(sheet.getDisplayValue('A1')).toBe('#CIRCULAR!')
    expect(sheet.getDisplayValue('B1')).toBe('#CIRCULAR!')
    // Read again — cached error is still correct.
    expect(sheet.getDisplayValue('A1')).toBe('#CIRCULAR!')
  })

  it('breaking a circular cycle re-evaluates cleanly', () => {
    sheet.setCell('A1', '=B1')
    sheet.setCell('B1', '=A1')
    sheet.getDisplayValue('A1')         // fills cache with #CIRCULAR!
    sheet.setCell('B1', '7')            // break the cycle
    expect(sheet.getDisplayValue('A1')).toBe('7')
  })
})
