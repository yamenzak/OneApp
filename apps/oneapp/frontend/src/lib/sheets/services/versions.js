/**
 * Version history — the server half is not ported, so this says so.
 *
 * Frappe Sheets keeps an operation log (`Sheet Op Log`), periodic snapshots
 * (`Sheet Snapshot`) and a sequence per workbook, and its version panel, cell
 * history popover and preview banner all read them. That is a real feature and
 * a separable one: none of it is needed to open, edit or save a sheet, and all
 * of it needs three doctypes and a retention job we have not written.
 *
 * `AVAILABLE` is what the editor branches on. Every call below answers the
 * empty shape rather than throwing, so a stale button or a keyboard shortcut
 * that slips past the flag does nothing instead of breaking the page.
 */

export const AVAILABLE = false

export async function list() { return [] }
export async function getState() { return null }
export async function restore() { return null }
export async function name() { return null }
export async function clearName() { return null }
export async function saveVersion() { return null }
export async function makeACopy() { return null }
export async function cellHistory() { return [] }
export async function cellDiff() { return null }
export async function latestVersion() { return null }

/**
 * Upstream this posts one entry to the op log. Nothing records ops here, and a
 * caller that awaited a sequence number gets none — which is the truth.
 */
export function recordOp() { return Promise.resolve(null) }
