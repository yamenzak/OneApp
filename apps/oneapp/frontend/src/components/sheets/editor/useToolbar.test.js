// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/pages/SheetEditor/useToolbar.test.js, which is AGPL-3.0,
// and modified for OneSpace — see lib/sheets/VENDORED.md.

// useToolbar records format changes as op DIFFs, not full-workbook snapshots.
// This is the fix for multi-second toolbar latency on large sheets: a bold
// toggle used to history.push() a deepClone of every cell. Now it pushes a
// { beforeFormats, afterFormats } diff of just the selection.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useToolbar } from './useToolbar.js'
import { createFormatsEngine } from '@/lib/sheets/engine/formats.js'

function setup(selection = ['A1', 'B1']) {
  const formats = createFormatsEngine()
  const history = { push: vi.fn(), pushOp: vi.fn() }
  const grid    = { render: vi.fn(), getActiveCell: () => selection[0] }
  const t = useToolbar({
    sheet:        { getCurrentSheet: () => 'Sheet1' },
    formats,
    getGrid:      () => grid,
    history,
    selectionIds: () => selection,
    syncFlags:    vi.fn(),
    markDirty:    vi.fn(),
  })
  return { ...t, formats, history, grid }
}

describe('useToolbar format history', () => {
  let h
  beforeEach(() => { h = setup() })

  it('toggleFmt pushes an op diff, never a full snapshot', () => {
    h.toggleFmt('bold')
    expect(h.history.push).not.toHaveBeenCalled()
    expect(h.history.pushOp).toHaveBeenCalledTimes(1)
    const op = h.history.pushOp.mock.calls[0][0]
    expect(op.opType).toBe('format')
    expect(op.subSheet).toBe('Sheet1')
    // before: both cells unformatted (empty format, which _applyFormatMap
    // treats as "clear" on undo); after: both bold.
    expect(op.beforeFormats).toEqual({ A1: {}, B1: {} })
    expect(op.afterFormats.A1.bold).toBe(true)
    expect(op.afterFormats.B1.bold).toBe(true)
  })

  it('captures the pre-mutation value even though set() replaces in place', () => {
    h.formats.set('A1', { bold: true }, 'Sheet1')
    h.setColor('color', '#f00')
    const op = h.history.pushOp.mock.calls[0][0]
    // before must still show only bold (the color hadn't been applied yet)
    expect(op.beforeFormats.A1).toEqual({ bold: true })
    expect(op.afterFormats.A1).toEqual({ bold: true, color: '#f00' })
  })

  it('setAlign / clearFormatting also go through the op path', () => {
    h.setAlign('center')
    h.clearFormatting()
    expect(h.history.push).not.toHaveBeenCalled()
    expect(h.history.pushOp).toHaveBeenCalledTimes(2)
    expect(h.history.pushOp.mock.calls.every(c => c[0].opType === 'format')).toBe(true)
  })
})
