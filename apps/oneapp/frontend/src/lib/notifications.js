import { reactive } from 'vue'

import { getSocket } from './socket'
import { callMethod } from './resource'
import { session } from './session'

/**
 * The notification feed.
 *
 * One store for the whole app rather than state inside the panel, because the
 * bell has to know the count while the panel is shut — and because on a phone
 * the same feed is opened from somewhere else entirely.
 *
 * The server pushes `notification` into this user's room whenever a row is
 * written for them, **with no payload**. That is Frappe's own design and worth
 * keeping: nothing sensitive rides the socket, and there is no second
 * serialisation of a notification to keep in step with the first. The poke says
 * "ask again", so we do.
 */

const METHOD = 'oneapp.oneapp_core.notifications'

export const notifications = reactive({
  rows: [],
  unread: 0,
  loading: false,
  /** Whether the feed has ever been fetched, so an empty panel can say which. */
  loaded: false,
})

export async function loadNotifications() {
  if (!session.isLoggedIn) return
  notifications.loading = true
  try {
    const answer = await callMethod(`${METHOD}.feed`, {}, { silent: true, method: 'GET' })
    notifications.rows = answer?.rows || []
    notifications.unread = answer?.unread || 0
    notifications.loaded = true
  } finally {
    notifications.loading = false
  }
}

/** Just the number, for the bell. One query rather than a page of rows. */
export async function countNotifications() {
  if (!session.isLoggedIn) return
  const answer = await callMethod(`${METHOD}.unread`, {}, { silent: true, method: 'GET' })
  notifications.unread = Number(answer) || 0
}

/**
 * Mark one read, or all of them.
 *
 * The row is marked here as well as on the server rather than refetching: the
 * reader is looking at it, and a panel that reorders itself under a click is a
 * panel that loses the thing you were about to press.
 */
export async function markRead(name) {
  const answer = await callMethod(`${METHOD}.mark_read`, { name }, { silent: true })
  for (const row of notifications.rows) {
    if (!name || row.name === name) row.read = true
  }
  notifications.unread = answer?.unread ?? 0
}

/**
 * Follow the server's own notification event.
 *
 * Called once, from the shell. Frappe publishes to the user's room, which the
 * socket joins on authentication, so there is nothing to subscribe to and
 * nothing to clean up — unlike a doctype or a document room.
 */
let following = false

export function followNotifications() {
  if (following || !session.isLoggedIn) return
  following = true
  getSocket().on('notification', () => {
    // The count always, the rows only when somebody is looking at them: a
    // panel nobody has opened does not need a page of rows fetched at it every
    // time a colleague is assigned something.
    if (notifications.loaded) loadNotifications()
    else countNotifications()
  })
  countNotifications()
}
