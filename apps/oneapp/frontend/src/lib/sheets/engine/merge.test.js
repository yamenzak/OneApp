// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/engine/merge.test.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/sheets/VENDORED.md before editing or moving it.

// Merge engine — per-sheet isolation and the migration from the
// legacy (sheet-blind) snapshot shape. The previous engine kept a
// single global masterMap / slaveMap, so a merge in Sheet1 visually
// bled into Sheet2 because the canvas painter asked `getMasterInfo("A1")`
// without a sheet name and got Sheet1's data back. Anyone reverting
// these tests is reintroducing that corruption.

import { describe, it, expect } from 'vitest'
import { createMergeEngine } from './merge.js'

describe('createMergeEngine — basic API per sheet', () => {
  it('merge+isMaster+resolveId are scoped to the named sheet', () => {
    const m = createMergeEngine()
    m.merge(0, 0, 1, 1, 'Sheet1')

    // Sheet1 sees the merge
    expect(m.isMaster('A1', 'Sheet1')).toBe(true)
    expect(m.isSlave('B2', 'Sheet1')).toBe(true)
    expect(m.resolveId('B2', 'Sheet1')).toBe('A1')

    // Sheet2 is independent
    expect(m.isMaster('A1', 'Sheet2')).toBe(false)
    expect(m.isSlave('B2', 'Sheet2')).toBe(false)
    expect(m.resolveId('B2', 'Sheet2')).toBe('B2')   // no slave → returns id as-is
  })

  it('unmerge in one sheet leaves the same range merged in another', () => {
    const m = createMergeEngine()
    m.merge(0, 0, 2, 2, 'Sheet1')
    m.merge(0, 0, 2, 2, 'Sheet2')

    m.unmerge(0, 0, 2, 2, 'Sheet1')

    expect(m.isMaster('A1', 'Sheet1')).toBe(false)
    expect(m.isMaster('A1', 'Sheet2')).toBe(true)   // untouched
  })

  it('a 1×1 merge call is a no-op', () => {
    const m = createMergeEngine()
    m.merge(3, 3, 3, 3, 'Sheet1')
    expect(m.isMaster('D4', 'Sheet1')).toBe(false)
  })

  it('overlapping merge clears the existing one first', () => {
    const m = createMergeEngine()
    m.merge(0, 0, 1, 1, 'Sheet1')   // A1:B2
    m.merge(1, 1, 2, 2, 'Sheet1')   // B2:C3 — overlaps; should drop A1:B2
    expect(m.isMaster('A1', 'Sheet1')).toBe(false)
    expect(m.isMaster('B2', 'Sheet1')).toBe(true)
  })
})

describe('snapshot / restore', () => {
  it('snapshot returns a per-sheet shape independent of the live store', () => {
    const m = createMergeEngine()
    m.merge(0, 0, 1, 1, 'Sheet1')
    const snap = m.snapshot()

    // Mutating the live engine doesn't bleed into the snapshot.
    m.merge(2, 2, 3, 3, 'Sheet1')
    expect(snap.Sheet1.masterMap.A1).toBeTruthy()
    expect(snap.Sheet1.masterMap.C3).toBeUndefined()
  })

  it('restore on a new engine round-trips merges per sheet', () => {
    const a = createMergeEngine()
    a.merge(0, 0, 1, 1, 'Sheet1')
    a.merge(2, 0, 3, 0, 'Sheet2')

    const b = createMergeEngine()
    b.restore(a.snapshot())

    expect(b.getMasterInfo('A1', 'Sheet1')).toMatchObject({ rowSpan: 2, colSpan: 2 })
    expect(b.getMasterInfo('A3', 'Sheet2')).toMatchObject({ rowSpan: 2, colSpan: 1 })
    expect(b.getMasterInfo('A1', 'Sheet2')).toBeNull()
  })

  it('restore migrates the legacy flat snapshot into the default sheet', () => {
    // Saved docs from before the per-sheet rewrite had this shape.
    // The migration keeps them functional without a one-off upgrade.
    const legacy = {
      masterMap: { A1: { rowSpan: 2, colSpan: 2, r: 0, c: 0 } },
      slaveMap:  { A2: 'A1', B1: 'A1', B2: 'A1' },
    }
    const m = createMergeEngine()
    m.restore(legacy)

    expect(m.isMaster('A1', 'Sheet1')).toBe(true)
    expect(m.isSlave('B2', 'Sheet1')).toBe(true)
    expect(m.isMaster('A1', 'Sheet2')).toBe(false)   // didn't bleed across
  })

  it('restore(null) and restore({}) both clear the engine', () => {
    const m = createMergeEngine()
    m.merge(0, 0, 1, 1, 'Sheet1')
    m.restore(null)
    expect(m.isMaster('A1', 'Sheet1')).toBe(false)

    m.merge(0, 0, 1, 1, 'Sheet1')
    m.restore({})
    expect(m.isMaster('A1', 'Sheet1')).toBe(false)
  })
})

describe('sheet-level operations', () => {
  it('renameSheet moves the slice under the new name', () => {
    const m = createMergeEngine()
    m.merge(0, 0, 1, 1, 'OldName')
    m.renameSheet('OldName', 'NewName')

    expect(m.isMaster('A1', 'OldName')).toBe(false)
    expect(m.isMaster('A1', 'NewName')).toBe(true)
  })

  it('duplicateSheet deep-copies merges so edits to the copy do not affect the source', () => {
    const m = createMergeEngine()
    m.merge(0, 0, 1, 1, 'Src')
    m.duplicateSheet('Src', 'Copy')

    expect(m.isMaster('A1', 'Copy')).toBe(true)
    m.unmerge(0, 0, 1, 1, 'Copy')
    expect(m.isMaster('A1', 'Copy')).toBe(false)
    expect(m.isMaster('A1', 'Src')).toBe(true)   // source intact
  })

  it('deleteSheet drops the slice entirely', () => {
    const m = createMergeEngine()
    m.merge(0, 0, 1, 1, 'Doomed')
    m.deleteSheet('Doomed')
    expect(m.isMaster('A1', 'Doomed')).toBe(false)
  })

  it('renameSheet refuses to clobber an existing sheet', () => {
    const m = createMergeEngine()
    m.merge(0, 0, 1, 1, 'A')
    m.merge(2, 2, 3, 3, 'B')
    m.renameSheet('A', 'B')   // collision → no-op
    expect(m.isMaster('A1', 'A')).toBe(true)
    expect(m.isMaster('C3', 'B')).toBe(true)
  })
})
