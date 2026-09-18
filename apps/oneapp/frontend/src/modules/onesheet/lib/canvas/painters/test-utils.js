// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/suite (95c38bfdd975), frontend/src/apps/sheets/canvas/painters/test-utils.js,
// which is AGPL-3.0. One is AGPL-3.0 too and this file stays that way
// — see lib/VENDORED.md before editing or moving it.

import { vi } from 'vitest'

export function createMockCtx() {
  return {
    save:        vi.fn(),
    restore:     vi.fn(),
    beginPath:   vi.fn(),
    rect:        vi.fn(),
    clip:        vi.fn(),
    fillRect:    vi.fn(),
    strokeRect:  vi.fn(),
    arc:         vi.fn(),
    // Ours, and the one line in this file that is: `cell-painter` draws a
    // checkbox as a rounded rect and reaches for `arcTo`, which upstream's
    // own double does not answer to. A stand-in for a canvas context that
    // is missing a method the painter calls is a gap in the double rather
    // than a difference of opinion, so it is filled here.
    arcTo:       vi.fn(),
    moveTo:      vi.fn(),
    lineTo:      vi.fn(),
    stroke:      vi.fn(),
    fill:        vi.fn(),
    closePath:   vi.fn(),
    fillText:    vi.fn(),
    measureText: vi.fn(() => ({ width: 40 })),
    setLineDash: vi.fn(),
    scale:       vi.fn(),
    fillStyle:   '',
    strokeStyle: '',
    lineWidth:   1,
    font:        '',
    textBaseline:'',
    textAlign:   '',
    lineDashOffset: 0,
  }
}

export function createMockGeo({ colWidths = {}, rowHeights = {}, filterHidden = new Set() } = {}) {
  const cw  = vi.fn((c) => colWidths[c]  ?? 100)
  const rh  = vi.fn((r) => rowHeights[r] ?? 24)
  const colX = vi.fn((c) => 50 + c * 100)
  const rowY = vi.fn((r) => 24 + r * 24)
  const isFilterHidden = vi.fn((r) => filterHidden.has(r))
  return {
    cw, rh, colX, rowY, isFilterHidden,
    firstVisCol: vi.fn(() => 0),
    firstVisRow: vi.fn(() => 0),
    lastVisCol:  vi.fn(() => 5),
    lastVisRow:  vi.fn(() => 10),
    frozenW:     vi.fn(() => 0),
    frozenH:     vi.fn(() => 0),
  }
}
