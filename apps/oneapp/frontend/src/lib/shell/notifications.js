import { reactive } from 'vue'

import { getSocket } from '@/lib/runtime/socket'
import { callMethod } from '@/lib/runtime/resource'
import { __ } from '@/lib/runtime/translate'
import { session } from '@/lib/shell/session'

/**
 * The notification feed.
 *
 * One store for the whole app rather than state inside the panel, because the
 * bell has to know the count while the panel is shut.
 *
 * The server pushes `notification` into this user's room whenever a row is
 * written for them, **with no payload** — Frappe's own design and worth
 * keeping: nothing sensitive rides the socket, and there is no second
 * serialisation to keep in step with the first.
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
 * Mark one read, or all of them. Marked here as well as on the server rather
 * than refetching: a panel that reorders itself under a click loses the thing
 * you were about to press.
 */
export async function markRead(name) {
  const answer = await callMethod(`${METHOD}.mark_read`, { name }, { silent: true })
  for (const row of notifications.rows) {
    if (!name || row.name === name) row.read = true
  }
  notifications.unread = answer?.unread ?? 0
}

/**
 * Follow the server's own notification event. Frappe publishes to the user's
 * room, which the socket joins on authentication, so there is nothing to
 * subscribe to and nothing to clean up.
 */
let following = false

export function followNotifications() {
  if (following || !session.isLoggedIn) return
  following = true
  getSocket().on('notification', () => {
    // The count always, the rows only when somebody is looking at them.
    if (notifications.loaded) loadNotifications()
    else countNotifications()
  })
  countNotifications()
}

/**
 * What this person has said about being notified. Frappe's own `Notification
 * Settings`, read and written through our own endpoints only so the browser
 * gets a shape it can render.
 */
export async function loadPreferences() {
  return callMethod(`${METHOD}.preferences`, {}, { silent: true, method: 'GET' })
}

export async function savePreferences(changes) {
  const answer = await callMethod(`${METHOD}.set_preferences`, changes, {
    successMessage: __('Saved'),
  })
  // The master switch decides whether a notification is written at all, so
  // turning it off makes the bell's count wrong until something else asks.
  countNotifications()
  return answer
}

/**
 * One channel, for one kind. The panel's own control.
 *
 * Its own call rather than a shape passed through `savePreferences`: the two
 * halves are stored in different places — email is the framework's allow-list,
 * the app is ours — and one endpoint pretending otherwise would be a lie the
 * next person has to unpick.
 */
export async function setChannel(kind, channel, on) {
  const answer = await callMethod(
    `${METHOD}.set_channel`,
    { kind, channel, on: on ? 1 : 0 },
    { successMessage: __('Saved') },
  )
  // Muting a kind hides what is already in the feed, so the bell is wrong
  // until something asks again.
  countNotifications()
  return answer
}
