/**
 * One open sheet: what is in it, what is selected, and what has yet to be saved.
 *
 * Split from the page for the same reason `useDrive` was — the page is a
 * layout and this is a state machine. Four things live here and nowhere else:
 *
 *   the workbook      `lib/sheets/engine`, which owns values and recalculation
 *   the selection     an anchor and a head, which together are a rectangle
 *   the write queue   what changed since the last save, and when to send it
 *   the tabs          which one is showing, and the geometry of each
 *
 * The write queue is the part worth understanding. A person typing produces an
 * edit every keystroke-and-Enter, and a request each would be a request each.
 * So edits accumulate by cell — the last value for a cell wins, because that is
 * what the cell holds — and go out on a timer. A save in flight does not block
 * further typing; the queue simply refills and goes again.
 */

import { computed, onBeforeUnmount, onMounted, reactive, ref, shallowRef } from 'vue'

import { workspace } from '../lib/workspace'
import { csrfToken } from '../lib/boot'
import { errorText } from '../lib/errors'
import { makeWorkbook, key } from '../lib/sheets/engine'
import { areaOf, cellsIn, columnLetters, format, parse } from '../lib/sheets/refs'
import { withChange } from '../lib/sheets/display'

/** How long typing has to stop before what was typed is sent. */
export const SETTLE = 700

/** What a fresh sheet shows: enough grid to look like one. */
export const MIN_ROWS = 60
export const MIN_COLUMNS = 26

/** Room past the last used cell, so there is always somewhere to type next. */
const SLACK_ROWS = 30
const SLACK_COLUMNS = 6

export function useSheet(name) {
  const loading = ref(true)
  const error = ref('')
  const title = ref('')
  const canWrite = ref(false)
  const isTemplate = ref(false)
  const attachedTo = ref({ doctype: '', docname: '' })
  const limit = ref(0)

  const tabs = ref([])
  const active = ref('Sheet1')
  const ranges = ref([])

  // Shallow: the workbook is a Map of thousands of cells and making every one
  // of them deeply reactive is the difference between a grid that repaints and
  // one that stutters. `version` is what the grid watches instead.
  const book = shallowRef(makeWorkbook())
  const version = ref(0)

  const anchor = reactive({ row: 1, column: 1 })
  const head = reactive({ row: 1, column: 1 })
  const editing = ref(false)
  const draft = ref('')

  const pending = new Map()
  const dirty = ref(0)
  const saving = ref(false)
  const saveError = ref('')
  let timer = null

  const area = computed(() => areaOf(anchor, head))
  const cursor = computed(() => format(anchor.row, anchor.column))
  const tabNames = computed(() => tabs.value.map((one) => one.tab_name))
  const geometry = computed(
    () => tabs.value.find((one) => one.tab_name === active.value) || {},
  )

  /** The cell at the cursor, or null. `version` is read so this re-runs. */
  const current = computed(() => {
    version.value
    return book.value.get(active.value, cursor.value)
  })

  /**
   * What the formula bar shows: the formula if there is one, else the value.
   *
   * `raw`, not `value` — the whole point of the bar is to show `=A2*B2` where
   * the cell shows `6480`.
   */
  const formula = computed(() => {
    const cell = current.value
    if (!cell) return ''
    return cell.raw === null || cell.raw === undefined ? '' : String(cell.raw)
  })

  /** How far the grid goes: past the last used cell, never less than a screen. */
  const extent = computed(() => {
    version.value
    let rows = 0
    let columns = 0
    for (const cell of book.value.cells.values()) {
      if (cell.tab !== active.value) continue
      if (cell.value === null && cell.raw === null) continue
      try {
        const at = parse(cell.ref)
        if (at.row > rows) rows = at.row
        if (at.column > columns) columns = at.column
      } catch {
        // A ref this browser cannot parse is one the server should not have
        // stored. Skipping it is better than refusing to draw the sheet.
      }
    }
    return {
      rows: Math.max(rows + SLACK_ROWS, MIN_ROWS),
      columns: Math.max(columns + SLACK_COLUMNS, MIN_COLUMNS),
    }
  })

  // ----------------------------------------------------------------------- //
  // Loading
  // ----------------------------------------------------------------------- //

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const found = await workspace.sheetOpen(name)
      title.value = found?.title || ''
      canWrite.value = !!found?.can_write
      isTemplate.value = !!found?.is_template
      attachedTo.value = found?.attached_to || { doctype: '', docname: '' }
      limit.value = found?.limit || 0
      tabs.value = found?.tabs || []
      ranges.value = found?.ranges || []
      active.value = tabs.value[0]?.tab_name || 'Sheet1'
      book.value = makeWorkbook(found?.cells || [])

      // Every formula's value came from whichever browser last touched it, and
      // that browser may have been working from a cell this one has since seen
      // change. Recomputing on open is cheap and is the only thing that makes
      // a shared sheet agree with itself; anything it corrects is written back.
      const corrected = book.value.recalculate()
      if (corrected.length && canWrite.value) queue(corrected)
      version.value += 1
    } catch (raised) {
      error.value = errorText(raised)
    } finally {
      loading.value = false
    }
  }

  // ----------------------------------------------------------------------- //
  // Writing
  // ----------------------------------------------------------------------- //

  /**
   * Type into cells.
   *
   * `edits` is `[{ tab, ref, raw, format }]`. The engine works out what that
   * changed — which is nearly always more cells than were typed in — and every
   * one of those goes to the server, because a formula's value is stored and
   * a stored value nobody updated is a wrong number in a print format.
   */
  function write(edits) {
    if (!canWrite.value) return []
    const changed = book.value.apply(edits)
    version.value += 1
    queue(changed)
    return changed
  }

  function queue(cells) {
    for (const cell of cells) {
      pending.set(key(cell.tab, cell.ref), {
        tab: cell.tab,
        ref: cell.ref,
        raw: cell.raw,
        value: cell.value,
        kind: cell.kind,
        format_json: cell.format,
      })
    }
    dirty.value = pending.size
    if (timer) clearTimeout(timer)
    timer = setTimeout(flush, SETTLE)
  }

  /** Send what is queued. Safe to call at any time, including twice. */
  async function flush() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
    if (!pending.size) return
    const batch = [...pending.values()]
    pending.clear()
    dirty.value = 0
    saving.value = true
    saveError.value = ''
    try {
      await workspace.sheetWrite(name, batch)
    } catch (raised) {
      saveError.value = errorText(raised)
      // Put it back. A failed save that drops the edit is the one bug in a
      // spreadsheet nobody forgives: the number on screen is not the number
      // stored and nothing says so.
      for (const cell of batch) {
        if (!pending.has(key(cell.tab, cell.ref))) pending.set(key(cell.tab, cell.ref), cell)
      }
      dirty.value = pending.size
    } finally {
      saving.value = false
    }
  }

  /**
   * Send what is queued to a page that is going away.
   *
   * A normal `flush` is a promise, and a promise does not survive the document
   * being torn down — closing the tab or typing a URL loses up to `SETTLE`
   * milliseconds of typing, which in a spreadsheet is the last thing somebody
   * typed and the thing they will look for first. `sendBeacon` is the one
   * request the browser promises to finish after the page is gone.
   *
   * Form-encoded with the CSRF token as a field, because a beacon cannot set a
   * header and Frappe reads `form_dict.csrf_token` as well as the header.
   */
  function beacon() {
    if (!pending.size || typeof navigator === 'undefined' || !navigator.sendBeacon) return false
    const body = new FormData()
    body.append('sheet', name)
    body.append('cells', JSON.stringify([...pending.values()]))
    if (csrfToken) body.append('csrf_token', csrfToken)
    const sent = navigator.sendBeacon(
      '/api/method/oneapp.oneapp_core.sheets.write_cells', body,
    )
    if (sent) {
      pending.clear()
      dirty.value = 0
    }
    return sent
  }

  // `pagehide` and not `beforeunload`: the latter is unreliable on a phone,
  // where a tab is usually never "unloaded" at all — it is hidden and then
  // discarded.
  function onLeaving() {
    if (pending.size) beacon()
  }

  onMounted(() => {
    window.addEventListener('pagehide', onLeaving)
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') onLeaving()
    })
  })

  onBeforeUnmount(() => {
    window.removeEventListener('pagehide', onLeaving)
  })

  /** Clear the selection — Delete, and what a cut leaves behind. */
  function clear() {
    write(cellsIn(area.value).map((ref) => ({ tab: active.value, ref, raw: '' })))
  }

  /** Apply a format change to every cell in the selection. */
  function paint(change) {
    write(
      cellsIn(area.value).map((ref) => {
        const cell = book.value.get(active.value, ref)
        return {
          tab: active.value,
          ref,
          raw: cell?.raw ?? '',
          format: withChange(cell?.format, change),
        }
      }),
    )
  }

  // ----------------------------------------------------------------------- //
  // Selection
  // ----------------------------------------------------------------------- //

  function select(row, column, { extend = false } = {}) {
    const limits = extent.value
    const at = {
      row: Math.min(Math.max(1, row), limits.rows),
      column: Math.min(Math.max(1, column), limits.columns),
    }
    head.row = at.row
    head.column = at.column
    if (!extend) {
      anchor.row = at.row
      anchor.column = at.column
    }
    editing.value = false
  }

  function move(rows, columns, { extend = false } = {}) {
    const from = extend ? head : anchor
    select(from.row + rows, from.column + columns, { extend })
  }

  /** Every ref in the selection, for a copy. */
  function selectionText() {
    const { top, left, bottom, right } = area.value
    const lines = []
    for (let row = top; row <= bottom; row++) {
      const line = []
      for (let column = left; column <= right; column++) {
        const cell = book.value.get(active.value, format(row, column))
        line.push(cell?.value === null || cell?.value === undefined ? '' : String(cell.value))
      }
      lines.push(line.join('\t'))
    }
    return lines.join('\n')
  }

  /**
   * Paste, from this grid or from Excel.
   *
   * Tab-separated, which is what every spreadsheet puts on the clipboard as
   * `text/plain`. Pasted values land at the cursor and spread down and right;
   * what they overwrite is overwritten, which is what paste means.
   */
  function paste(text) {
    const lines = String(text || '').replace(/\r\n?/g, '\n').replace(/\n$/, '').split('\n')
    const edits = []
    lines.forEach((line, down) => {
      line.split('\t').forEach((value, across) => {
        edits.push({
          tab: active.value,
          ref: format(anchor.row + down, anchor.column + across),
          raw: value,
        })
      })
    })
    write(edits)
    select(anchor.row, anchor.column)
    select(anchor.row + lines.length - 1, anchor.column + (lines[0]?.split('\t').length || 1) - 1,
           { extend: true })
  }

  // ----------------------------------------------------------------------- //
  // Tabs
  // ----------------------------------------------------------------------- //

  async function addTab() {
    const made = await workspace.sheetAddTab(name, '')
    tabs.value = [...tabs.value, { ...made, frozen_rows: 0, frozen_columns: 0 }]
    active.value = made.tab_name
    select(1, 1)
  }

  async function renameTab(from, to) {
    await workspace.sheetRenameTab(name, from, to)
    book.value.renameTab(from, to)
    tabs.value = tabs.value.map((one) =>
      one.tab_name === from ? { ...one, tab_name: to } : one)
    ranges.value = ranges.value.map((one) => (one.tab === from ? { ...one, tab: to } : one))
    if (active.value === from) active.value = to
    version.value += 1
  }

  async function removeTab(which) {
    await workspace.sheetRemoveTab(name, which)
    book.value.dropTab(which)
    tabs.value = tabs.value.filter((one) => one.tab_name !== which)
    ranges.value = ranges.value.filter((one) => one.tab !== which)
    if (active.value === which) active.value = tabs.value[0]?.tab_name || 'Sheet1'
    version.value += 1
  }

  function show(which) {
    active.value = which
    select(1, 1)
  }

  // ----------------------------------------------------------------------- //
  // Named ranges
  // ----------------------------------------------------------------------- //

  /** Mark this sheet as one to start from, or stop. */
  async function setTemplate(on) {
    const done = await workspace.sheetSetTemplate(name, on)
    isTemplate.value = !!done?.is_template
    return isTemplate.value
  }

  async function nameSelection(label) {
    const { top, left, bottom, right } = area.value
    const ref = `${format(top, left)}:${format(bottom, right)}`
    const made = await workspace.sheetSetRange(name, { label, tab: active.value, ref })
    const without = ranges.value.filter((one) => one.label !== made.label)
    ranges.value = [...without, made].sort((a, b) => a.label.localeCompare(b.label))
    return made
  }

  async function forgetRange(label) {
    await workspace.sheetRemoveRange(name, label)
    ranges.value = ranges.value.filter((one) => one.label !== label)
  }

  function goToRange(range) {
    active.value = range.tab
    const [from, to] = String(range.ref).split(':')
    const start = parse(from)
    const end = parse(to || from)
    select(start.row, start.column)
    select(end.row, end.column, { extend: true })
  }

  return {
    // identity
    name, title, canWrite, isTemplate, attachedTo, limit,
    // state
    loading, error, tabs, tabNames, active, geometry, ranges, book, version, extent,
    // selection
    anchor, head, area, cursor, current, formula, editing, draft,
    select, move, selectionText, paste, clear,
    // writing
    write, paint, flush, beacon, dirty, saving, saveError,
    // structure
    load, addTab, renameTab, removeTab, show,
    nameSelection, forgetRange, goToRange, setTemplate,
    // helpers the grid needs and should not re-derive
    columnLetters, format,
  }
}
