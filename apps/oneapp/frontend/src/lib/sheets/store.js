/**
 * Loading a workbook and saving one.
 *
 * This is the seam between Frappe's editor and our server, and it is the only
 * file in `lib/sheets/` that is ours rather than vendored. Upstream this is
 * `pages/SheetEditor/usePersistence.js` talking to `sheets.api`; here it talks
 * to `oneapp.oneapp_core.sheets`, where a sheet is a `File` in the Drive and
 * not a `Sheet` doctype — so there is no create, no trash and no share to do:
 * the Drive did all three before a grid existed.
 *
 * Two things are genuinely ours rather than renamed.
 *
 * **A `values` slice.** The saved payload carries what was typed *and* what it
 * came to. Frappe's server never needs a number, so their payload has no such
 * slice; ours does — the read-back into a child table, the CSV a share link
 * serves and any print format all want `6480` rather than `=A2*B2`, and none of
 * them has a browser to work it out. `codec.py` reads it.
 *
 * **`fetch`, not `resource.js`.** Every other call in this app goes through
 * `callMethod`. A save cannot: the last one fires from `pagehide`, and only
 * `keepalive: true` survives the document going away. Losing the last thing
 * somebody typed because the request was cancelled at unload is the one bug an
 * editor may not have.
 */

import { encodeForUpload, isDecompressionSupported, decodeFromDownload } from './utils/compress.js'
import { packSheet, packSheetChunked, unpackSheet, boundsOf } from './utils/sheet-codec.js'

const GET = 'oneapp.oneapp_core.sheets.get_sheet'
const SAVE = 'oneapp.oneapp_core.sheets.save_sheet'

/** One request to Frappe. `keepalive` for the save that outlives the page. */
async function call(method, args = {}, { keepalive = false } = {}) {
  const res = await fetch(`/api/method/${method}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': window.csrf_token ?? '',
    },
    body: JSON.stringify(args),
    keepalive,
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok || json.exc) {
    const err = new Error(serverMessage(json) || 'Server error')
    err.excType = json.exc_type || ''
    err.status = res.status
    throw err
  }
  return json.message
}

/** Frappe puts the human sentence inside a JSON string inside a JSON array. */
function serverMessage(json) {
  if (!json?._server_messages) return json?.exc_type || ''
  try {
    const parsed = JSON.parse(json._server_messages)
    const first = Array.isArray(parsed) ? JSON.parse(parsed[0]) : parsed
    return first.message || ''
  } catch {
    return String(json._server_messages)
  }
}

/**
 * Everything the editor needs to draw a workbook, restored into the engines.
 *
 * `engines` is the bag the editor already holds — sheet, formats, merge and
 * the rest — so restoring is a walk over the slices that are present. A slice
 * that is absent is a feature the workbook never used, not an error: a sheet
 * saved before pivots existed simply has no pivots.
 */
export async function loadWorkbook(name, engines) {
  const canGz = isDecompressionSupported()
  const doc = await call(GET, { name, compressed: canGz ? 1 : 0 })
  const plain = canGz ? await decodeFromDownload(doc.sheets_data) : doc.sheets_data

  let saved = {}
  try {
    saved = JSON.parse(plain || '{}') || {}
  } catch {
    saved = {}
  }

  if (saved.formats) engines.formats?.restore(saved.formats)
  engines.sheet.restore(
    unpackSheet(saved.sheet) ?? { sheets: { Sheet1: {} }, current: 'Sheet1' },
    boundsOf(saved.sheet),
  )
  for (const [slice, engine] of Object.entries({
    merge: engines.merge,
    comments: engines.comments,
    validation: engines.validation,
    protection: engines.protection,
    condFormat: engines.condFormat,
    sortFilter: engines.sortFilter,
    slicers: engines.slicers,
    pivot: engines.pivot,
    charts: engines.charts,
    namedRanges: engines.namedRanges,
  })) {
    if (saved[slice] && engine?.restore) engine.restore(saved[slice])
  }
  if (saved.view && engines.applyViewState) engines.applyViewState(saved.view)

  return doc
}

/**
 * The payload a save sends: what was typed, what it came to, and the rest.
 *
 * `keepalive` packs synchronously — the page may be gone before an async pass
 * could finish. Everything else yields to the event loop every fifty thousand
 * cells, because a two-million-cell pack that does not is six seconds during
 * which a keystroke cannot be handled.
 */
export async function buildPayload(engines, { keepalive = false } = {}) {
  const current = engines.sheet.getCurrentSheet()
  const live = { sheets: engines.sheet.getAllRaw(), current }
  const pack = keepalive ? packSheet : packSheetChunked

  return JSON.stringify({
    sheet: await pack(live),
    values: await pack({ sheets: computed(engines.sheet), current }),
    formats: engines.formats?.snapshot?.() ?? null,
    merge: engines.merge?.snapshot?.() ?? null,
    comments: engines.comments?.snapshot?.() ?? null,
    validation: engines.validation?.snapshot?.() ?? null,
    protection: engines.protection?.snapshot?.() ?? null,
    condFormat: engines.condFormat?.snapshot?.() ?? null,
    sortFilter: engines.sortFilter?.snapshot?.() ?? null,
    slicers: engines.slicers?.snapshot?.() ?? null,
    pivot: engines.pivot?.snapshot?.() ?? null,
    charts: engines.charts?.snapshot?.() ?? null,
    namedRanges: engines.namedRanges?.snapshot?.() ?? null,
    view: engines.getViewState?.() ?? null,
  })
}

/**
 * Every cell of every tab as the number or string it displays.
 *
 * Only cells that hold something are walked, and only formulas cost anything:
 * a literal is returned as it was stored. The engine memoises results, so on a
 * save right after an edit this is mostly cache hits.
 */
function computed(sheet) {
  const out = {}
  const raw = sheet.getAllRaw()
  for (const tab of Object.keys(raw)) {
    const cells = raw[tab]
    const done = {}
    for (const id of Object.keys(cells)) {
      const value = cells[id]
      done[id] = typeof value === 'string' && value.startsWith('=')
        ? sheet.getDisplayValue(id, tab)
        : value
    }
    out[tab] = done
  }
  return out
}

/** Write the workbook back. Returns the save count, or throws. */
export async function saveWorkbook(name, title, payload, { keepalive = false } = {}) {
  const body = await encodeForUpload(payload)
  return call(SAVE, { name, title, sheets_data: body }, { keepalive })
}

/**
 * Which kind of failure a save hit — worth a retry, or worth telling somebody.
 *
 * No status means `fetch` itself threw: offline, DNS, the server killed
 * mid-flight. A 5xx, a 408 or a 429 is the server saying "later". Everything
 * else is a 4xx, which will fail identically however many times it is sent, so
 * re-sending it only delays an honest error by seven seconds.
 */
export function isTransient(err) {
  if (err?.status == null) return true
  if (err.status >= 500 && err.status <= 599) return true
  return err.status === 408 || err.status === 429
}
