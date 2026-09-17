/**
 * What the service shows, and the four things it does.
 *
 * `docs/WORK.md` §12. OneTask owns no table: every row here is an ERPNext
 * `Task`, the same one OneProject's board draws, and every verb is something
 * a person could have done by going there. This module is the one round trip
 * — `onetask/service.py` answers both lists and the clock together, because a
 * 380px window that reflows three times as three requests land is worse than
 * one that waits for all of it.
 *
 * Module state rather than a store per mount: the window and the route draw
 * the same service, and two copies of it with two ideas of what is running is
 * the bug this shape rules out.
 */
import { reactive } from 'vue'
import { callMethod } from '@/shared/lib/runtime/resource'

const AT = 'oneapp.onetask.service.'
const CLOCK = 'oneapp.onetask.timing.'

/** The two lists, the clock, and whether the first read has happened. */
export const service = reactive({
  mine: [],
  inbox: [],
  running: {},
  ready: false,
  busy: false,
})

/** Which list is showing. Not server state: it is where the reader is looking. */
export const LISTS = ['mine', 'inbox']

export async function load() {
  service.busy = true
  try {
    const found = await callMethod(`${AT}now`, {}, { method: 'GET' })
    service.mine = found?.mine || []
    service.inbox = found?.inbox || []
    service.running = found?.running || {}
  } finally {
    service.busy = false
    service.ready = true
  }
}

/** A line of text becomes a task nobody has placed. */
export async function capture(subject) {
  const said = String(subject || '').trim()
  if (!said) return null
  const made = await callMethod(`${AT}capture`, { subject: said })
  await load()
  return made
}

/** Off the list, or back on it. */
export async function tick(name, done = true) {
  await callMethod(`${AT}tick`, { name, done: done ? 1 : 0 })
  await load()
}

/**
 * Start timing one, or stop whatever is running.
 *
 * Both through `onetask/timing.py`, which is the same clock the space's own
 * Start timing verb presses — one store, and a window that disagreed with the
 * screen behind it would be the whole argument of §12 undone in the corner.
 */
export async function clock(name) {
  if (name) await callMethod(`${CLOCK}start`, { task: name })
  else await callMethod(`${CLOCK}stop`, {})
  await load()
}
