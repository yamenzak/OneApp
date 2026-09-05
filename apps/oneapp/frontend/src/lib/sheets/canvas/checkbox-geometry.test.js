// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/canvas/checkbox-geometry.test.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/sheets/VENDORED.md before editing or moving it.

import { describe, it, expect } from 'vitest'
import { checkboxRect, CHECKBOX } from './checkbox-geometry.js'

describe('checkboxRect', () => {
  it('centres the box in the cell', () => {
    const { x, y, size } = checkboxRect(100, 40)
    expect(x).toBe((100 - size) / 2)
    expect(y).toBe((40 - size) / 2)
  })

  it('caps the size at maxSize on a tall cell', () => {
    expect(checkboxRect(100, 100).size).toBe(CHECKBOX.maxSize)
  })

  it('shrinks to fit a short row', () => {
    expect(checkboxRect(100, 12).size).toBe(12 - CHECKBOX.margin)
  })
})
