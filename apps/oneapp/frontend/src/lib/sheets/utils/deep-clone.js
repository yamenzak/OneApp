// Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
// Vendored from frappe/sheets (3f9e37b5776f), frontend/src/utils/deep-clone.js, which is AGPL-3.0.
// OneSpace is AGPL-3.0 too and this file stays that way — see
// lib/sheets/VENDORED.md before editing or moving it.

// Deep clone — single shared helper so every engine's snapshot() uses
// the same fast path.
//
// Native structuredClone is ~5-10× faster than JSON.parse(JSON.stringify(x))
// for plain objects and avoids the giant intermediate JSON string that was
// driving Minor GC pressure during snapshot-heavy operations (paste,
// fill, format toggles). Available in all modern browsers and Node 17+;
// falls back to JSON for very old runtimes.
//
// Caveats vs JSON: structuredClone throws on functions, symbols, DOM
// nodes, and class instances with private fields. Every engine snapshot
// in this codebase serialises plain {string|number|boolean|null|array|
// object} trees, so the constraint is fine. If you ever try to snapshot
// a Vue ref or a class instance through here, structuredClone will tell
// you immediately instead of silently dropping it.

const _hasStructured = typeof structuredClone === 'function'

export function deepClone(x) {
  return _hasStructured ? structuredClone(x) : JSON.parse(JSON.stringify(x))
}
