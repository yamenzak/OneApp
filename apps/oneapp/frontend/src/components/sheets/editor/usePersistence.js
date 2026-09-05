/**
 * Loading and saving, in the shape the editor above expects.
 *
 * Upstream this file talks to `sheets.api.get_sheet` / `save_sheet` on a `Sheet`
 * doctype. Here it talks to `oneapp.oneapp_core.sheets`, where a sheet is a
 * `File` in the Drive — so the same five refs and five functions come back, and
 * `index.vue` is untouched, but three things behind them differ.
 *
 * **Creating.** There is no create here. A sheet is made in the Drive, by
 * `sheets.make`, which is where a folder and an attachment to a record are
 * decided; the editor is only ever opened on one that exists. `autoCreate` is
 * kept because the editor calls it for `id === 'new'`, and it does the same
 * thing the Drive's New button does.
 *
 * **Sharing.** `isPublic` / `isPublicWrite` stay `false` and nothing flips them.
 * A sheet is shared the way every other file is — `DocShare`, or an expiring
 * link — from the file list, not from inside the grid. Two share models for one
 * object is the bug, not the missing dialog.
 *
 * **Ops.** The `ops` argument is accepted and dropped. It feeds Frappe's
 * version history, whose server half is not ported; see
 * `lib/sheets/services/versions.js`.
 */

import { ref } from 'vue'

import { sheets as api } from '@/lib/workspace/sheets'

import { buildPayload, isTransient, loadWorkbook, saveWorkbook } from '@/lib/sheets/store.js'

export function usePersistence(engines) {
  const isSaving = ref(false)
  const saveError = ref('')
  // "Couldn't open this sheet" as a shape the editor can render: `denied`
  // wants "ask the owner to share it", `missing` wants "the link is wrong",
  // and they are different recoveries.
  const loadError = ref(null)
  // True until the first load says otherwise, so a sheet being created is
  // editable before its load resolves.
  const canWrite = ref(true)
  const isPublic = ref(false)
  const isPublicWrite = ref(false)
  const sheetOwner = ref('')

  async function loadSheet(name) {
    loadError.value = null
    try {
      const doc = await loadWorkbook(name, engines)
      engines.currentTitle.value = doc.title
      canWrite.value = doc.can_write !== false
      sheetOwner.value = doc.owner || ''
    } catch (err) {
      const type = err?.excType || ''
      loadError.value = {
        kind: type === 'PermissionError' ? 'denied'
          : type === 'DoesNotExistError' ? 'missing'
            : 'other',
        message: err?.message || 'Could not open this sheet',
      }
    }
  }

  async function autoCreate(title) {
    const made = await api.sheetMake({ title: title || 'Untitled sheet' })
    return made?.name || null
  }

  // Populated at the start of every attempt, cleared on success, so a retry
  // button and the watchdog can re-run the last failed save without the person
  // having to type something else to re-arm the timer.
  let lastAttempt = null

  async function retrySave() {
    if (!lastAttempt) return null
    return saveExisting(lastAttempt.name, lastAttempt.title, lastAttempt.opts)
  }

  async function saveExisting(name, title, { keepalive = false } = {}) {
    lastAttempt = { name, title, opts: { keepalive } }
    isSaving.value = true

    let payload
    try {
      // Built once, before the first attempt. Rebuilding per retry would let a
      // keystroke that arrived between attempts into a payload the caller
      // thinks it already snapshotted.
      payload = await buildPayload(engines, { keepalive })
    } catch (err) {
      isSaving.value = false
      saveError.value = err?.message || "Couldn't prepare this sheet to save."
      return null
    }

    // A keepalive save fires from `onBeforeUnmount`; the page may be gone
    // before a backoff finishes, so it gets one attempt.
    const backoff = keepalive ? [0] : [0, 1000, 2500]
    let last = null
    try {
      for (const wait of backoff) {
        if (wait) await new Promise((done) => setTimeout(done, wait))
        try {
          const result = await saveWorkbook(name, title, payload, { keepalive })
          saveError.value = ''
          lastAttempt = null
          return result?.name || name
        } catch (err) {
          last = err
          if (!isTransient(err)) break
        }
      }
      // No auto-clear. Quietly hiding "your work is not saved" is the worst
      // thing an editor can do, so the message stays until a save succeeds.
      saveError.value = last?.message
        ? `Couldn't save: ${last.message}`
        : "Couldn't save — check your connection, then retry."
      return null
    } finally {
      isSaving.value = false
    }
  }

  return {
    isSaving, saveError, canWrite, isPublic, isPublicWrite, sheetOwner, loadError,
    loadSheet, autoCreate, saveExisting, retrySave,
  }
}
