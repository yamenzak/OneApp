// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/utils/cells.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/sheets/VENDORED.md before editing or moving it.

export function colLabel(idx) {
  let s = ''; idx++
  while (idx > 0) { s = String.fromCharCode(64 + (idx % 26 || 26)) + s; idx = Math.floor((idx - 1) / 26) }
  return s
}

export function cellId(row, col) { return colLabel(col) + (row + 1) }

export function parseCellId(id) {
  const m = id.match(/^([A-Z]+)(\d+)$/)
  if (!m) return null
  return { row: parseInt(m[2]) - 1, col: m[1].split('').reduce((a, c) => a * 26 + c.charCodeAt(0) - 64, 0) - 1 }
}
