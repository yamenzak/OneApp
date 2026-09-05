// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/pages/SheetEditor/useEditOps.test.js, which is AGPL-3.0,
// and modified for OneSpace — see lib/sheets/VENDORED.md.

// useEditOps — diff-and-record helper for cell-edit paths. The
// 1-in-A1, 2-in-A2, drag-to-A7-and-undo bug shipped from this contract
// breaking, so the round-trip is worth pinning explicitly.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useEditOps } from './useEditOps.js'

// Minimal stand-ins for the engines / helpers useEditOps consumes.
function _fakeSheet(initial = {}, currentSheet = 'Sheet1') {
  const cells = { ...initial }
  return {
    getCell:         (id, _sn) => cells[id] ?? '',
    setCell:         (id, v, _sn) => { cells[id] = v },
    getCurrentSheet: () => currentSheet,
    _cells:          cells,
  }
}

function _fakeHistory()                  { return { pushOp: vi.fn() } }
function _queueOpFn()                    { return vi.fn() }
function _broadcastBatchChangeFn()       { return vi.fn() }
function _syncFlagsFn()                  { return vi.fn() }
function _isDirtyRef()                   { return { value: false } }

function _setup(overrides = {}) {
  const sheet                = overrides.sheet                || _fakeSheet()
  const history              = overrides.history              || _fakeHistory()
  const queueOp              = overrides.queueOp              || _queueOpFn()
  const broadcastBatchChange = overrides.broadcastBatchChange || _broadcastBatchChangeFn()
  const syncFlags            = overrides.syncFlags            || _syncFlagsFn()
  const isDirty              = overrides.isDirty              || _isDirtyRef()
  const { pushEditOp } = useEditOps({
    sheet, history, queueOp, broadcastBatchChange, syncFlags, isDirty,
  })
  return { pushEditOp, sheet, history, queueOp, broadcastBatchChange, syncFlags, isDirty }
}

describe('useEditOps.pushEditOp', () => {
  beforeEach(() => vi.clearAllMocks())

  it('returns null when there is no diff (caller wrote the same value)', () => {
    const sheet = _fakeSheet({ A1: 'x' })
    const ctx = _setup({ sheet })
    // beforeMap says A1 used to be 'x'; setCell already wrote 'x'.
    const op = ctx.pushEditOp('Sheet1', { A1: 'x' })
    expect(op).toBeNull()
    expect(ctx.queueOp).not.toHaveBeenCalled()
    expect(ctx.history.pushOp).not.toHaveBeenCalled()
    expect(ctx.broadcastBatchChange).not.toHaveBeenCalled()
  })

  it('returns null when beforeMap is null / undefined', () => {
    const ctx = _setup()
    expect(ctx.pushEditOp('Sheet1', null)).toBeNull()
    expect(ctx.pushEditOp('Sheet1', undefined)).toBeNull()
    expect(ctx.queueOp).not.toHaveBeenCalled()
  })

  it('emits a single edit op carrying only the cells that actually changed', () => {
    const sheet = _fakeSheet({ A1: '7', A2: '', A3: 'unchanged' })
    // Caller pattern: capture beforeMap → mutate → pushEditOp.
    // A1 stays at 7 (no diff) and A2 goes from '' → 'new'. A3 isn't
    // in beforeMap so it shouldn't appear even though its value is set.
    sheet.setCell('A2', 'new', 'Sheet1')
    const ctx = _setup({ sheet })
    const op = ctx.pushEditOp('Sheet1', { A1: '7', A2: '' })
    expect(op).not.toBeNull()
    expect(op.opType).toBe('edit')
    expect(op.cellRefs).toEqual(['A2'])
    expect(op.before).toEqual({ A2: '' })
    expect(op.after).toEqual({ A2: 'new' })
  })

  it('captures before/after only for cells whose value differs', () => {
    const sheet = _fakeSheet({ A1: 'old1', A2: 'old2' })
    sheet.setCell('A1', 'new1', 'Sheet1')   // changed
    // A2 stays old2 in storage — beforeMap also says old2 → no diff
    const ctx = _setup({ sheet })
    const op = ctx.pushEditOp('Sheet1', { A1: 'old1', A2: 'old2' })
    expect(op.cellRefs).toEqual(['A1'])
    expect(op.before).toEqual({ A1: 'old1' })
    expect(op.after).toEqual({ A1: 'new1' })
  })

  it('routes the op through queueOp, history.pushOp, broadcastBatchChange', () => {
    const sheet = _fakeSheet({ A1: '' })
    sheet.setCell('A1', 'x', 'Sheet1')
    const ctx = _setup({ sheet })
    ctx.pushEditOp('Sheet1', { A1: '' }, 'Edit cell')

    expect(ctx.queueOp).toHaveBeenCalledTimes(1)
    expect(ctx.history.pushOp).toHaveBeenCalledTimes(1)
    expect(ctx.broadcastBatchChange).toHaveBeenCalledTimes(1)
    // Server queue + history both see the same op
    expect(ctx.queueOp.mock.calls[0][0]).toEqual(ctx.history.pushOp.mock.calls[0][0])
    // Broadcast receives sheet name + [{id, value}, ...]
    const [bsn, bchanges] = ctx.broadcastBatchChange.mock.calls[0]
    expect(bsn).toBe('Sheet1')
    expect(bchanges).toEqual([{ id: 'A1', value: 'x' }])
  })

  it('flips the dirty flag and calls syncFlags on a real change', () => {
    const sheet = _fakeSheet({ A1: '' })
    sheet.setCell('A1', 'x', 'Sheet1')
    const ctx = _setup({ sheet })
    ctx.pushEditOp('Sheet1', { A1: '' })
    expect(ctx.isDirty.value).toBe(true)
    expect(ctx.syncFlags).toHaveBeenCalled()
  })

  it('leaves dirty unset and syncFlags un-called when nothing changed', () => {
    const ctx = _setup()   // sheet is empty, beforeMap A1='' matches getCell('A1')
    ctx.pushEditOp('Sheet1', { A1: '' })
    expect(ctx.isDirty.value).toBe(false)
    expect(ctx.syncFlags).not.toHaveBeenCalled()
  })

  it('falls back to sheet.getCurrentSheet() when sheetName arg is empty', () => {
    const sheet = _fakeSheet({ A1: '' }, 'Sheet42')
    sheet.setCell('A1', 'v', 'Sheet42')
    const ctx = _setup({ sheet })
    const op = ctx.pushEditOp('', { A1: '' })
    expect(op.subSheet).toBe('Sheet42')
  })

  it('the op carries the user-supplied summary', () => {
    const sheet = _fakeSheet({ A1: '' })
    sheet.setCell('A1', 'v', 'Sheet1')
    const ctx = _setup({ sheet })
    const op = ctx.pushEditOp('Sheet1', { A1: '' }, 'Fill down')
    expect(op.summary).toBe('Fill down')
  })

  it('tolerates missing optional collaborators (queueOp, broadcast)', () => {
    // The composable signature marks queueOp / broadcastBatchChange /
    // syncFlags as optional so a future caller can wire only what
    // they need (e.g. a non-collab unit test harness).
    const sheet = _fakeSheet({ A1: '' })
    sheet.setCell('A1', 'v', 'Sheet1')
    const history = _fakeHistory()
    const { pushEditOp } = useEditOps({
      sheet, history,
      queueOp: undefined, broadcastBatchChange: undefined, syncFlags: undefined,
      isDirty: undefined,
    })
    expect(() => pushEditOp('Sheet1', { A1: '' })).not.toThrow()
    expect(history.pushOp).toHaveBeenCalled()
  })
})
