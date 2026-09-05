/**
 * Files on their way in.
 *
 * The Drive had no upload control at all — the empty state said "Upload a file
 * or make a folder to start" beside a toolbar that offered only the folder.
 * The only ways in were a record's attach field and the picker's upload tab,
 * both of which put a file somewhere *else*.
 *
 * So: a queue rather than a dialog. Three things follow from that choice and
 * each is the reason a dialog was wrong.
 *
 * **It outlives the page.** Held at module scope, not in a component, so
 * walking into a folder — or out of the Drive entirely — does not cancel four
 * uploads. The tray reads this; nothing owns it.
 *
 * **It is serial.** Two at a time is not twice as fast on one connection and
 * is twice as likely to trip the quota check halfway, leaving a file uploaded
 * and a file refused with no way to tell which was which. One at a time, in
 * the order they were dropped.
 *
 * **A failure is kept, not toasted.** A toast for the third of nine files is
 * gone before the ninth finishes. A row that stays red with a Retry beside it
 * is the only version of this that a person can act on.
 *
 * The upload itself is frappe-ui's `upload`, which posts to Frappe's own
 * endpoint — so `storage/file.py` still moves the bytes to R2 and
 * `storage/quota.py` still refuses the one that would go over. Nothing about
 * where a file ends up is decided here.
 */
import { computed, reactive, readonly } from 'vue'
import { upload } from '@/ui'

import { errorText } from '../lib/errors'

/** Where a file is in its life. `queued → sending → done | failed`. */
const QUEUED = 'queued'
const SENDING = 'sending'
const DONE = 'done'
const FAILED = 'failed'

const items = reactive([])
let running = false
let nextId = 1

// Set by whoever last mounted the tray, so a finished upload can refresh the
// list it landed in. A callback rather than an import: the composable must not
// know what a Drive is.
let onFinished = null

export function useUploads() {
  return {
    items: readonly(items),
    active: computed(() => items.filter((one) => one.state === QUEUED || one.state === SENDING)),
    failed: computed(() => items.filter((one) => one.state === FAILED)),
    done: computed(() => items.filter((one) => one.state === DONE)),
    /** 0–100 across everything still in flight, for the collapsed tray. */
    progress: computed(() => {
      const live = items.filter((one) => one.state !== DONE)
      if (!live.length) return 100
      return Math.round(live.reduce((sum, one) => sum + one.progress, 0) / live.length)
    }),
    add,
    retry,
    remove,
    clearDone,
    onFinished: (fn) => { onFinished = fn },
  }
}

/**
 * Queue files for a folder. Folders dropped from the desktop are ignored:
 * `DataTransfer` reports a directory as a zero-byte `File` with no type, and
 * uploading that produces an empty file named after the folder.
 */
export function add(files, folder = 'Home') {
  for (const file of files) {
    if (!file || (!file.size && !file.type)) continue
    items.push({
      id: nextId++,
      file,
      name: file.name,
      size: file.size,
      folder,
      state: QUEUED,
      progress: 0,
      error: '',
    })
  }
  drain()
}

export function retry(id) {
  const one = items.find((each) => each.id === id)
  if (!one) return
  one.state = QUEUED
  one.error = ''
  one.progress = 0
  drain()
}

export function remove(id) {
  const at = items.findIndex((one) => one.id === id)
  // A queued one can go; one already on the wire cannot be un-sent, and
  // pretending otherwise would leave a file in the Drive that the tray says
  // was cancelled.
  if (at >= 0 && items[at].state !== SENDING) items.splice(at, 1)
}

export function clearDone() {
  for (let at = items.length - 1; at >= 0; at -= 1) {
    if (items[at].state === DONE) items.splice(at, 1)
  }
}

async function drain() {
  if (running) return
  running = true
  try {
    for (;;) {
      const next = items.find((one) => one.state === QUEUED)
      if (!next) break
      await send(next)
    }
  } finally {
    running = false
  }
}

async function send(one) {
  one.state = SENDING
  one.progress = 0
  try {
    await upload(one.file, {
      folder: one.folder,
      // Private, always. A workspace's files are not world-readable, and
      // `r2.download` is the only way to the bytes — see `storage/r2.py`.
      private: true,
      onProgress: ({ percent }) => { one.progress = percent },
    })
    one.state = DONE
    one.progress = 100
    onFinished?.(one)
  } catch (raised) {
    one.state = FAILED
    one.error = errorText(raised)
  }
}

export const STATES = { QUEUED, SENDING, DONE, FAILED }
