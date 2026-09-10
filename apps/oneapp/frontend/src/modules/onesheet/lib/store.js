/**
 * Loading a workbook and saving one.
 *
 * The seam between Frappe's editor and our server. Upstream this is
 * `pages/SheetEditor/usePersistence.js` talking to `sheets.api`; here it talks
 * to `oneapp.onesheet`, where a sheet is a `File` in the Drive — so
 * there is no create, no trash and no share to do.
 *
 * Two things are genuinely ours rather than renamed.
 *
 * **A `values` slice.** The saved payload carries what was typed *and* what it
 * came to: the read-back into a child table, the CSV a share link serves and
 * any print format all want `6480` rather than `=A2*B2`, and none of them has a
 * browser to work it out.
 *
 * **`fetch`, not `resource.js`.** A save cannot go through `callMethod`: the
 * last one fires from `pagehide`, and only `keepalive: true` survives the
 * document going away.
 */

import { encodeForUpload, isDecompressionSupported, decodeFromDownload } from '@/modules/onesheet/lib/utils/compress.js'
import { packSheet, packSheetChunked, unpackSheet, boundsOf } from '@/modules/onesheet/lib/utils/sheet-codec.js'
import { linkSecret } from '@/shared/lib/live/link'

const GET = 'oneapp.onesheet.get_sheet'
const SAVE = 'oneapp.onesheet.save_sheet'

// The other door in, for a browser that arrived at `/one/link/<secret>` with
// no account. Two endpoints of their own rather than a flag on the two above,
// because a guest cannot be granted a permission in Frappe — the reasoning is
// in `onestorage/linked.py` and the whole point is that the guest's surface is
// separately reviewable.
const LINK_GET = 'oneapp.onestorage.open_file'
const LINK_SAVE = 'oneapp.onestorage.save_file'


/**
 * One request to Frappe. `keepalive` for the save that outlives the page.
 *
 * A read goes as a GET and a write as a POST, because that is what the
 * endpoints declare: a POST to `get_sheet` is a 403 rather than a 405, which
 * reads from inside the editor like a sheet somebody may not open.
 */
async function call(method, args = {}, { keepalive = false, get = false } = {}) {
  const url = get
    ? `/api/method/${method}?${new URLSearchParams(args)}`
    : `/api/method/${method}`
  const res = await fetch(url, {
    method: get ? 'GET' : 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Frappe-CSRF-Token': window.csrf_token ?? '',
    },
    ...(get ? {} : { body: JSON.stringify(args) }),
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
 * Everything the editor needs to draw a workbook, restored into the engines. A
 * slice that is absent is a feature the workbook never used, not an error.
 */
/**
 * One workbook, read and unpacked, with nothing loaded into anything.
 *
 * `loadWorkbook` restores into live engines and every `restore` is
 * destructive, so it cannot be used to *read* a second workbook while one is
 * open. Loading a template's tabs into the workbook you are in needs exactly
 * this: the other book's slices, in hand, to merge from.
 */
export async function fetchWorkbook(name) {
  const canGz = isDecompressionSupported()
  const secret = linkSecret()
  const doc = secret
    ? await call(LINK_GET, { secret, compressed: canGz ? 1 : 0 }, { get: true })
    : await call(GET, { name, compressed: canGz ? 1 : 0 }, { get: true })
  const plain = canGz ? await decodeFromDownload(doc.sheets_data) : doc.sheets_data

  try {
    return { doc, saved: JSON.parse(plain || '{}') || {} }
  } catch {
    return { doc, saved: {} }
  }
}


export async function loadWorkbook(name, engines) {
  const { doc, saved } = await fetchWorkbook(name)

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
 * could finish. Everything else yields every fifty thousand cells, because a
 * two-million-cell pack that does not is six seconds during which a keystroke
 * cannot be handled.
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
 * Every cell of every tab as the number or string it displays. Only formulas
 * cost anything, and the engine memoises results.
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
  const secret = linkSecret()
  // No title through a link. A stranger renaming somebody's file in their
  // Drive is not part of what "edit this" meant, and the endpoint does not
  // take one.
  if (secret) return call(LINK_SAVE, { secret, payload: body }, { keepalive })
  return call(SAVE, { name, title, sheets_data: body }, { keepalive })
}

/**
 * Which kind of failure a save hit — worth a retry, or worth telling somebody.
 * No status means `fetch` itself threw; a 5xx, 408 or 429 is the server saying
 * "later"; everything else will fail identically however many times it is sent.
 */
export function isTransient(err) {
  if (err?.status == null) return true
  if (err.status >= 500 && err.status <= 599) return true
  return err.status === 408 || err.status === 429
}
