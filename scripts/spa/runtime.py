"""Data fetching, realtime, errors and notifications.

Identical in both SPAs by construction: written once here, generated into both,
and enforced by ESLint so no page can quietly bypass them. A page that fetches
nothing at all would still want most of it, because the toast an error becomes
is part of the request layer.
"""

from .spec import BANNER


BOOT_JS = BANNER + """
/**
 * Boot data injected by frappe-ui's vite plugin.
 *
 * The plugin's jinjaBootData sub-plugin writes the www page's `boot` context
 * onto `window`, so whatever the page controller puts there is available before
 * the app mounts. Everything here degrades to a sane default, because the dev
 * server serves index.html without Jinja and would otherwise crash on boot.
 */

// The plugin emits `window["<key>"] = <value>` for each key in the page's boot
// context — so `boot.site_name` lands as `window.site_name`, not under a `boot`
// object. Reading window.boot would silently yield undefined and leave the
// socket pointed at the wrong host.
const read = (key, fallback) => (window[key] !== undefined ? window[key] : fallback)

export const siteName = read('site_name', window.location.hostname)
export const socketioPort = read('socketio_port', 9000)
export const csrfToken = read('csrf_token', null)
export const sessionUser = read('user', 'Guest')
// Frappe stores datetimes in the system timezone, not the reader's. `dayjsLocal`
// converts between the two, but only once it has been told which system zone to
// convert from — see main.js. Empty is the safe default: dayjsLocal then behaves
// exactly like dayjs rather than shifting by a guess.
export const systemTimezone = read('system_timezone', '')
// Two different questions, and they used to be one. `import.meta.env.DEV` says
// Vite is serving the app; `dev_server` says the site has nothing in front of
// it routing `/socket.io/` to the socketio port. A built SPA served by a bench
// is the case where the first is false and the second is true — and the socket
// went same-origin and 404ed on every local run, which is why realtime was
// "not covered locally" for as long as it was.
export const isDev = import.meta.env.DEV
export const devServer = !!read('dev_server', 0) || import.meta.env.DEV
// What this workspace looks like: `{ accent, favicon, splash }`, built by
// `onespace/branding.py`. All three are wanted before the first paint — the
// accent so no button is drawn in the default colour and then repainted, the
// favicon so the tab does not visibly change — which is why they ride the boot
// payload rather than the session resource.
export const brand = read('brand', {})
// Which language to draw in, and therefore which way. The reader's own, or the
// workspace's — `www/one.py` decides; this only has to know the answer before
// the first paint, because changing it later moves the whole layout.
export const lang = read('lang', 'en')
// Who the assistant is: `{ name, avatar, tone, personality }`, built by
// `onespace/ai/settings.py`. Here for the same reason the favicon is — the
// chat rail and the panel header name it before anything is fetched, and a
// header that says "Assistant" for a moment and then says something else is a
// visible flicker. `lib/shell/assistant.js` makes it reactive from here.
export const assistant = read('assistant', {})
// Where map tiles come from: `{ style, tiles, attribution }`, built by
// `onespace/basemap.py` out of site config. A deployment fact, not a
// workspace's choice — which tile store a bench points at is decided by
// whoever runs the bench — and every map surface in the product reads the same
// answer, so a self-hosted or air-gapped install changes it in one place.
export const basemap = read('basemap', {})
// How this workspace writes a date, a time and a number: `{ date_format,
// time_format, number_format, float_precision, currency_precision, currency }`,
// built by `api.number_formats`. Here rather than on the session resource
// because a list draws numbers in its first frame, and a column that reads
// `1,234.50` and then `1.234,50` a round trip later is worse than one that was
// always right. Read through `lib/runtime/format.js` and nowhere else.
export const formats = read('formats', {})
// How big a file may be, here: `{ file }` in bytes, built by
// `onestorage/limits.py`, and zero where there is no fixed per-file ceiling
// — which is every site with a bucket, because those bytes never pass through
// the framework. Before first paint because the sentence belongs under the
// attach control rather than after it. Read through `lib/files/limits.js`.
export const limits = read('limits', {})

export default {
  siteName,
  socketioPort,
  csrfToken,
  sessionUser,
  systemTimezone,
  isDev,
  devServer,
  brand,
  lang,
  assistant,
  basemap,
  formats,
  limits,
}
"""


REMEMBER_JS = BANNER + """
/**
 * The per-browser conveniences, and the one door they go through.
 *
 * `localStorage` was written from seven places with seven key shapes, and the
 * question that decides whether something belongs in it was never asked out
 * loud. It is this: **would I want to send this to a colleague?** If yes it
 * belongs in the URL or in a saved view, because it is part of what I am
 * looking at. If no it belongs here, because it is a habit of mine and my
 * browser is where my habits live.
 *
 * Drive's order failed that test and moved to the URL — a link sent to a
 * colleague used to arrive in whatever order *their* browser last used, while
 * a screen link arrived exactly as sent. What is left here passes it: a rail
 * I collapsed, a pane I dragged narrower, the last thing I picked in a field.
 *
 * Every key is declared below, so the guard can check that what is stored is
 * the kind of thing this is for. Reads and writes both go through here, which
 * is also where the `try` lives: storage can be off, full, or blocked, and on
 * every one of those the right answer is to forget rather than to throw.
 *
 * `docs/UNIFICATION.md` §C4, rail 19.
 */

/**
 * What may be remembered, and why each is a habit rather than a place.
 *
 * A key is a prefix: `remember('drive.grid')` and
 * `remember('field.last', space, screen, fieldname)` both name the same
 * declared thing, and the parts after it say whose.
 */
export const KEYS = Object.freeze({
  'rail.shut': 'Whether I keep the space rail collapsed.',
  'drive.grid': 'Whether I look at files as thumbnails or as a list.',
  'drive.order': "The order I last put a Drive place in. A fallback: the URL wins, and a link that names one arrives in it.",
  'record.surface': 'Whether I open records in a pane or full width, per screen.',
  'child.columns': 'Which columns I keep on a child table.',
  'field.last': 'The last thing I picked in a field that asks to remember.',
  'pane.width': 'How wide I dragged a pane.',
  'sound': 'Whether I want the notification sound.',
})

const PREFIX = 'onespace'

/** The full key: the declared name, then whatever narrows it. */
function slot(key, ...parts) {
  if (!Object.hasOwn(KEYS, key)) {
    throw new Error(
      `Nothing may be remembered under "${key}". Declare it in lib/url/remember.js, `
      + 'and say there why it is a habit rather than a place.',
    )
  }
  return [PREFIX, key, ...parts.filter((one) => one !== undefined && one !== null)].join(':')
}

/**
 * What was remembered, or `null`.
 *
 * Never throws, and `null` is the only way it says no: a private window,
 * cleared site data and a full quota all mean "nothing was remembered", which
 * is true and is the only useful answer. The caller supplies its own default
 * with `??`, because the default is a fact about that surface rather than
 * about storage.
 */
export function recall(key, ...parts) {
  try {
    return window.localStorage.getItem(slot(key, ...parts))
  } catch {
    return null
  }
}

/** Remember it. Forgetting is the whole cost of failing, so nothing is said. */
export function remember(key, value, ...parts) {
  try {
    window.localStorage.setItem(slot(key, ...parts), String(value))
  } catch {
    // Storage off, or full. The next visit starts from the default.
  }
}

/** Stop remembering it. */
export function forget(key, ...parts) {
  try {
    window.localStorage.removeItem(slot(key, ...parts))
  } catch {
    // Already gone, as far as anybody can tell.
  }
}

/** The same three, for something that is not a string. */
export function recallJson(key, ...parts) {
  const held = recall(key, ...parts)
  if (held === null) return null
  try {
    return JSON.parse(held)
  } catch {
    return null
  }
}

export const rememberJson = (key, value, ...parts) =>
  remember(key, JSON.stringify(value), ...parts)
"""


SIZE_JS = BANNER + """
/**
 * How many bytes, said the way a person says it.
 *
 * There were two of these — `onestorage/lib/files.js` for a file row and
 * `UsageBar` for a quota — and they disagreed: one wrote "0 B" for nothing and
 * the other wrote nothing at all, one stopped at GB and the other went to TB,
 * and one rounded through `lib/runtime/format` while the other used
 * `toFixed`. A quota bar reading `1.2 GB` above a file list reading `1,2 GB`
 * is the whole of §A1's argument in one screen.
 *
 * `docs/UNIFICATION.md` §D3.
 */
import { number as count } from '@/lib/runtime/format'

const UNITS = ['B', 'KB', 'MB', 'GB', 'TB']

/**
 * `1.2 MB`, in the reader's own locale — the server sends bytes because it
 * does not know what locale that is.
 *
 * `blank` is what nothing looks like: a file list wants an empty cell and a
 * quota bar wants "0 B", and that is the only thing the two ever disagreed
 * about that was a real difference.
 */
export function sizeText(bytes, { blank = '' } = {}) {
  const size = Number(bytes) || 0
  if (!size) return blank
  const step = Math.min(Math.floor(Math.log(size) / Math.log(1024)), UNITS.length - 1)
  return `${count(size / 1024 ** step, step ? 1 : 0)} ${UNITS[step]}`
}
"""


ERRORS_JS = BANNER + """
/**
 * Frappe error normalisation.
 *
 * Frappe reports failures in several shapes: a FrappeResponseError from
 * frappe-ui's fetch layer, a JSON body with `_server_messages` (itself a
 * JSON-encoded array of JSON-encoded objects), an `exception` traceback string,
 * or a bare Error. Rendering any of those raw gives users a stack trace or
 * "[object Object]".
 *
 * This flattens all of them to { title, message, detail }, where `message` is
 * safe to show and `detail` is for the console.
 */

import { __ } from '@/lib/runtime/translate'

/** Strip the HTML Frappe puts in server messages. */
function stripTags(value) {
  if (typeof value !== 'string') return value
  const el = document.createElement('div')
  el.innerHTML = value
  return (el.textContent || '').trim()
}

/** `_server_messages` is a JSON string containing JSON strings. */
function parseServerMessages(raw) {
  if (!raw) return []
  try {
    const outer = typeof raw === 'string' ? JSON.parse(raw) : raw
    return (Array.isArray(outer) ? outer : [outer])
      .map((entry) => {
        try {
          return typeof entry === 'string' ? JSON.parse(entry) : entry
        } catch {
          return { message: entry }
        }
      })
      .filter(Boolean)
  } catch {
    return []
  }
}

/** Last frame of a traceback is the only useful line for a user-facing hint. */
function lastTracebackLine(exception) {
  if (typeof exception !== 'string') return ''
  const lines = exception.trim().split('\\n').filter(Boolean)
  return lines.length ? lines[lines.length - 1].trim() : ''
}

export function normalizeError(error) {
  if (!error) return { title: __('Something went wrong'), message: '', detail: null }

  // A string is its own message. Callers hand one over whenever the detail is
  // theirs rather than the server's — a bulk change naming the four records
  // that refused it, say — and without this every one of those rendered as
  // "Something went wrong / No further detail was returned", which is the
  // most confidently useless pair of sentences in the product. It had been
  // doing that on a refused bulk delete since that was written.
  if (typeof error === 'string') {
    return {
      title: __('Something went wrong'),
      titled: false,
      detailed: true,
      message: error,
      extra: [],
      indicator: 'red',
      detail: null,
      raw: error,
    }
  }

  const messages = parseServerMessages(
    error.messages || error._server_messages || error.response?._server_messages,
  )

  const first = messages[0] || {}
  const fromServer = stripTags(first.message)

  // Whether anybody actually wrote a title. `Request failed` and `Something
  // went wrong` below are both inventions of this file, and a `frappe.throw`
  // carries no title at all — which is the common case. Pairing its sentence
  // with an invented heading gives "Something went wrong: Say who the alert
  // goes to.", a first line that says less than the second and reads like two
  // separate errors.
  const titled = !!(first.title || error.title)

  // FrappeResponseError already carries the parsed fields.
  const title =
    first.title ||
    error.title ||
    (error.name === 'FrappeResponseError' ? __('Request failed') : null) ||
    __('Something went wrong')

  const detail =
    fromServer || stripTags(error.message) || lastTracebackLine(error.exception)

  const message = detail || __('No further detail was returned.')

  return {
    title: stripTags(title),
    titled,
    // Whether the message is something that was actually reported, rather than
    // the standing-in sentence below it. Without this, dropping an invented
    // title left "No further detail was returned." on its own — which is the
    // most confidently useless sentence in the product.
    detailed: !!detail,
    message,
    // Extra server messages beyond the first, shown as additional lines.
    extra: messages.slice(1).map((m) => stripTags(m.message)).filter(Boolean),
    indicator: first.indicator || error.indicator || 'red',
    detail: error.exception || error.stack || null,
    raw: error,
  }
}

export function errorText(error) {
  const { title, titled, detailed, message } = normalizeError(error)
  // A title nobody wrote is not worth a line, so long as there is something
  // real under it. The server's own sentence is then the whole message.
  if (detailed && !titled) return message
  return message && message !== title ? `${title}: ${message}` : title
}
"""


SOUND_JS = BANNER + """
/**
 * Notification sounds.
 *
 * Synthesised with WebAudio rather than shipped as audio files: two short tones
 * need no network request, no asset pipeline, and no licensing.
 *
 * Browsers refuse to start an AudioContext before a user gesture, so the
 * context is created lazily on first play and every failure is swallowed — a
 * silent notification is fine, a thrown error inside a toast is not.
 */

import { recall, remember } from '@/lib/url/remember'

const SOUND = 'sound'

let context = null

function audioContext() {
  if (context) return context
  const Ctor = window.AudioContext || window.webkitAudioContext
  if (!Ctor) return null
  try {
    context = new Ctor()
  } catch {
    context = null
  }
  return context
}

// On unless somebody turned it off — which is also what an unreadable store
// comes back as, and rightly: a preference nobody can read is one nobody set.
export const soundEnabled = () => recall(SOUND) !== 'off'

export const setSoundEnabled = (enabled) => remember(SOUND, enabled ? 'on' : 'off')

/** Two notes: rising for success, falling for failure. */
const TONES = {
  success: [660, 880],
  error: [440, 330],
}

function playTone(frequencies) {
  const ctx = audioContext()
  if (!ctx) return

  // Autoplay policy may leave it suspended until a gesture.
  if (ctx.state === 'suspended') ctx.resume().catch(() => {})

  const now = ctx.currentTime
  frequencies.forEach((frequency, index) => {
    const start = now + index * 0.09
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = 'sine'
    osc.frequency.value = frequency

    // Short envelope; a click is what you get without the ramps.
    gain.gain.setValueAtTime(0, start)
    gain.gain.linearRampToValueAtTime(0.05, start + 0.01)
    gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.16)

    osc.connect(gain).connect(ctx.destination)
    osc.start(start)
    osc.stop(start + 0.18)
  })
}

export function playSound(kind) {
  if (!soundEnabled()) return
  try {
    playTone(TONES[kind] || TONES.success)
  } catch {
    /* audio is a nicety; never let it break a notification */
  }
}
"""


NOTIFY_JS = BANNER + """
/**
 * Notifications, and the one door they all go through.
 *
 * Every mutation reports its outcome and every failure is rendered from a
 * normalised Frappe error, so nobody sees a raw traceback or a silent no-op.
 *
 * `toast` is deliberately **not** re-exported. It used to be, and seven files
 * took it — so those outcomes had no sound and their errors were whatever the
 * caller happened to pass rather than a parsed Frappe one.
 * `test_notify_is_the_only_door` is what stops the eighth.
 *
 * Which channel carries which news is a question about **how long the news is
 * true for**, and the table is short:
 *
 *   it worked and you can see it happen   nothing
 *   it worked and you cannot see it       `notifySuccess`, three seconds
 *   it worked and can be taken back       `notifyUndoable`, eight
 *   it failed, about a field              `<ErrorMessage>` under the field
 *   it failed, about the action           `notifyError`, eight
 *   it is broken until you fix it         an `<Alert>` in place
 *
 * The first row is the one that is easy to get wrong in both directions: a
 * toast for something visibly done is noise, and silence for something that
 * happened off screen is a person clicking twice.
 */

import { toast } from 'frappe-ui'

import { normalizeError } from '@/lib/runtime/errors'
import { playSound } from '@/lib/runtime/sound'
import { __ } from '@/lib/runtime/translate'

export function notifySuccess(message, options = {}) {
  playSound('success')
  return toast.success(message, options)
}

export function notifyError(error, options = {}) {
  const { title, message, extra, detail } = normalizeError(error)

  // The traceback goes to the console, never the toast.
  if (detail) console.error(title, detail)

  playSound('error')
  return toast.error(title, {
    description: [message, ...(extra || [])].filter(Boolean).join('\\n'),
    duration: 8000,
    ...options,
  })
}

export function notifyInfo(message, options = {}) {
  return toast.info(message, options)
}

/**
 * A warning: it did not fail, and it did not do what you meant either.
 *
 * No sound. A tone for every outcome trains people to stop hearing any of
 * them, and this is the class of news that is usually about the reader's own
 * next move — "select the words first" — rather than about something the
 * product did.
 */
export function notifyWarning(message, options = {}) {
  return toast.warning(message, options)
}

/**
 * It worked, and it can be taken back.
 *
 * The reason this exists is not the toast, it is the fifteen confirmation
 * dialogs. A dialog before a destructive verb is the heavy instrument, and it
 * was reached for everywhere because the light one did not exist: there was
 * no undo anywhere in the product, and the word appeared only in prose
 * explaining that something *could not* be undone.
 *
 * Eight seconds, the same as an error's, because both are news somebody may
 * have to act on. `undo` runs at most once however many times the button is
 * pressed, and a failure inside it is reported the way any other failure is —
 * an undo that silently does nothing is worse than no undo at all.
 */
export function notifyUndoable(message, undo, options = {}) {
  playSound('success')
  let spent = false
  return toast.success(message, {
    duration: 8000,
    action: {
      label: __('Undo'),
      onClick: async () => {
        if (spent) return
        spent = true
        try {
          await undo()
        } catch (raised) {
          notifyError(raised)
        }
      },
    },
    ...options,
  })
}
"""


SOCKET_JS = BANNER + """
/**
 * Frappe realtime.
 *
 * Frappe's socket.io server namespaces connections by site and pushes a
 * `list_update` event whenever a document changes. Subscribing to the doctypes
 * a page renders keeps it fresh without polling.
 *
 * One socket per app, shared by every subscriber. Subscriptions are reference
 * counted so a component unmounting does not cut off another that still needs
 * the same doctype.
 */

import { io } from 'socket.io-client'
import { onScopeDispose, getCurrentScope } from 'vue'

import { siteName, socketioPort, devServer } from '@/lib/runtime/boot'

let socket = null
const subscribers = new Map()
const documents = new Map()
const viewers = new Map()
const rooms = new Set()
const events = new Map()

const key = (doctype, name) => `${doctype}/${name}`

function socketUrl() {
  // Whether the socket is same-origin is a question about what is in front of
  // the site, not about how the SPA was built. In production nginx routes
  // `/socket.io/` to the socketio port; on a bench nothing does, so the socket
  // is addressed on the port itself. Frappe's own desk client makes the same
  // call from `window.dev_server`, and this reads the same flag.
  if (devServer) {
    return `${window.location.protocol}//${window.location.hostname}:${socketioPort}/${siteName}`
  }
  return `${window.location.origin}/${siteName}`
}

/**
 * The secret out of `/one/link/<secret>`, or nothing.
 *
 * Four lines rather than an import of `shared/lib/live/link.js`, which says
 * the same thing: this file is generated into *both* bundles and the control
 * plane has no `shared/lib/live` to import from. A shared module that only
 * one of the two can reach is not shared.
 */
function linkSecret() {
  const found = /\/one\/link\/([^/?#]+)/.exec(window.location.pathname)
  return found ? decodeURIComponent(found[1]) : ''
}

export function getSocket() {
  if (socket) return socket

  socket = io(socketUrl(), {
    withCredentials: true,
    // The link a page at `/one/link/<secret>` was opened with, if that is
    // where this browser is. A guest has no session and no cookie worth
    // anything, so the secret is the only credential — and a browser cannot
    // set headers on a websocket, which leaves the handshake query. It is
    // already in the address bar of the page making the connection, so this
    // puts it nowhere it was not.
    query: linkSecret() ? { oneapp_link: linkSecret() } : undefined,
    reconnection: true,
    reconnectionAttempts: Infinity,
    // Back off rather than hammering a bench that is restarting.
    reconnectionDelay: 1000,
    reconnectionDelayMax: 10000,
  })

  socket.on('connect', () => {
    // Re-subscribe after a reconnect; the server forgets on disconnect. Rooms
    // as well as doctypes — a reader whose wifi blinked is still looking at
    // the same record, and the list of who is in it is wrong until they say
    // so again.
    for (const doctype of subscribers.keys()) {
      socket.emit('doctype_subscribe', doctype)
    }
    for (const room of rooms) {
      const [doctype, name] = room.split('/')
      socket.emit('doc_subscribe', doctype, name)
      if (viewers.has(room)) socket.emit('doc_open', doctype, name)
    }
  })

  socket.on('list_update', (data) => {
    const handlers = subscribers.get(data?.doctype)
    if (handlers) handlers.forEach((fn) => fn(data.name, data))
  })

  // One document rather than a doctype. Frappe publishes `doc_update` into the
  // room a `doc_subscribe` joins, and `doc_viewers` into the one `doc_open`
  // joins — the second is how the desk shows who else has the form open.
  socket.on('doc_update', (data) => {
    const handlers = documents.get(key(data?.doctype, data?.name))
    if (handlers) handlers.forEach((fn) => fn(data))
  })

  socket.on('doc_viewers', (data) => {
    const handlers = viewers.get(key(data?.doctype, data?.docname))
    if (handlers) handlers.forEach((fn) => fn(data?.users || []))
  })

  return socket
}

/**
 * One `socket.on` per event name, however many handlers are waiting on it.
 *
 * Nothing re-registers this after a reconnect, unlike the three subscriptions
 * above, and that is not an omission: `publish_realtime(user=...)` puts the
 * message in the room every socket joins on connect, so there is no
 * subscription for the server to forget. socket.io keeps the `on` across a
 * reconnect by itself.
 */
function listen(event) {
  socket.on(event, (data) => {
    const handlers = events.get(event)
    if (handlers) handlers.forEach((fn) => fn(data))
  })
}

/**
 * Call `handler` for every `event` the server sends this person.
 *
 * For what the server pushes rather than what a document does: an AI run
 * arriving a phrase at a time, a long job saying where it got to. Frappe's
 * `publish_realtime(event, message, user=...)` writes to redis, the socketio
 * process emits it into this person's own room, and this is the other end.
 *
 * Nothing is subscribed to — the room is the one every socket joins on
 * connect — so this cannot be used to listen to somebody else's traffic, and
 * an event nobody sends simply never fires.
 */
export function onEvent(event, handler) {
  const sock = getSocket()

  if (!events.has(event)) {
    events.set(event, new Set())
    if (sock) listen(event)
  }
  events.get(event).add(handler)

  const stop = () => {
    const handlers = events.get(event)
    if (handlers) handlers.delete(handler)
  }

  if (getCurrentScope()) onScopeDispose(stop)
  return stop
}

/**
 * Call `handler` whenever any document of `doctype` changes.
 * Returns an unsubscribe function, and cleans up automatically inside a
 * component scope.
 */
export function onDoctypeChange(doctype, handler) {
  const sock = getSocket()

  if (!subscribers.has(doctype)) {
    subscribers.set(doctype, new Set())
    sock.emit('doctype_subscribe', doctype)
  }
  subscribers.get(doctype).add(handler)

  const stop = () => {
    const handlers = subscribers.get(doctype)
    if (!handlers) return
    handlers.delete(handler)
    if (handlers.size === 0) {
      subscribers.delete(doctype)
      sock.emit('doctype_unsubscribe', doctype)
    }
  }

  if (getCurrentScope()) onScopeDispose(stop)
  return stop
}

/**
 * Call `handler` when this one document changes on the server — somebody else
 * saving it, a background job touching it, a workflow moving it on.
 *
 * The server checks the reader may see the document before it lets them into
 * the room, so this is not a way to watch something you cannot open.
 */
export function onDocChange(doctype, name, handler) {
  return joinDoc(doctype, name, documents, handler, 'doc_subscribe', 'doc_unsubscribe')
}

/**
 * Call `handler` with everyone who currently has this document open, including
 * this reader. Frappe calls it the open-doc room, and it is what the desk's
 * row of faces at the top of a form is built on.
 */
export function onDocViewers(doctype, name, handler) {
  return joinDoc(doctype, name, viewers, handler, 'doc_open', 'doc_close')
}

function joinDoc(doctype, name, registry, handler, join, leave) {
  if (!doctype || !name) return () => {}
  const sock = getSocket()
  const room = key(doctype, name)

  // Both rooms need the subscribe: `doc_open` is what publishes the list of
  // viewers, and `doc_subscribe` is what carries the document's own events.
  if (!rooms.has(room)) {
    rooms.add(room)
    sock.emit('doc_subscribe', doctype, name)
  }
  if (!registry.has(room)) {
    registry.set(room, new Set())
    if (join !== 'doc_subscribe') sock.emit(join, doctype, name)
  }
  registry.get(room).add(handler)

  const stop = () => {
    const handlers = registry.get(room)
    if (!handlers) return
    handlers.delete(handler)
    if (handlers.size) return
    registry.delete(room)
    if (leave !== 'doc_unsubscribe') sock.emit(leave, doctype, name)
    // The room itself goes only when nothing is left watching it.
    if (!documents.has(room) && !viewers.has(room)) {
      rooms.delete(room)
      sock.emit('doc_unsubscribe', doctype, name)
    }
  }

  if (getCurrentScope()) onScopeDispose(stop)
  return stop
}

export function closeSocket() {
  if (!socket) return
  socket.close()
  socket = null
  subscribers.clear()
  documents.clear()
  viewers.clear()
  rooms.clear()
  events.clear()
}
"""


RESOURCE_JS = BANNER + """
/**
 * The single way this app talks to Frappe.
 *
 * Wraps frappe-ui's useCall so that every request in both SPAs gets the same
 * treatment:
 *
 *   - responses unwrapped, so pages read `data` rather than `data.message`
 *   - failures rendered through the Frappe error normaliser and toasted
 *   - mutations announce their result
 *   - lists refresh over the socket instead of polling
 *
 * ESLint forbids importing useCall or call directly, so this cannot be bypassed
 * without a visible disable comment.
 */

import { watch } from 'vue'
import {
  useCall,
  useList,
  useDoc,
  useDoctype,
  call as rawCall,
  frappeRequest,
} from 'frappe-ui'

import { notifyError, notifySuccess } from '@/lib/runtime/notify'
import { onDoctypeChange } from '@/lib/runtime/socket'
import { __ } from '@/lib/runtime/translate'

/**
 * Unwrap Frappe's envelope.
 *
 * Depending on the endpoint a response arrives as the value, as `{message: …}`,
 * or occasionally as `{message: {message: …}}` when a whitelisted method
 * returns something already enveloped. Pages should never have to care.
 */
export function normalize(data) {
  let value = data
  let depth = 0

  while (
    value &&
    typeof value === 'object' &&
    !Array.isArray(value) &&
    'message' in value &&
    Object.keys(value).length === 1 &&
    depth < 3
  ) {
    value = value.message
    depth += 1
  }

  return value
}

/**
 * A read. Toasts on failure; silent on success.
 *
 * `watch` names doctypes whose changes should trigger a refetch over the
 * socket.
 */
/**
 * Where useCall's reads have to point, and why it is v2.
 *
 * Two separate traps, and both end in a page that renders nothing:
 *
 * 1. useCall concatenates `url` onto the base without adding a prefix, so a
 *    bare dotted method resolves *relative to the current page*. Under our SPA
 *    route rules Frappe answers that with the app's own HTML at 200, so the
 *    fetch fails parsing JSON rather than 404ing.
 *
 * 2. useCall reads its payload as `data.value?.data` — the API **v2** envelope.
 *    `/api/method/…` is v1 and answers `{message: …}`, so the lookup finds
 *    nothing and the resource settles with `data === null` after a perfectly
 *    successful request. Every `useResource` read was silently empty: the
 *    customer portal sat on its spinner and the user menu showed "Account"
 *    instead of a name.
 *
 * `/api/v2/method/…` returns `{data: …}`, which is what useCall is built to
 * read. `normalize()` below stays as the belt to this braces — a whitelisted
 * method that returns something already enveloped still unwraps correctly.
 */
function methodUrl(method) {
  if (method.startsWith('/') || method.startsWith('http')) return method
  return `/api/v2/method/${method}`
}

/**
 * A request the caller replaced, rather than one that failed.
 *
 * The browser rejects a cancelled fetch with an AbortError, and frappe-ui
 * cancels the previous request whenever a resource's params change. Named
 * rather than matched at each call site: the message wording is the browser's
 * and differs between them, so the name is the reliable half.
 */
function isAbort(error) {
  return error?.name === 'AbortError' || /aborted/i.test(error?.message || '')
}

export function useResource(url, options = {}) {
  const { watch: watchDoctypes = [], silent = false, transform, onError, ...rest } = options

  const resource = useCall({
    url: methodUrl(url),
    transform: (data) => {
      const value = normalize(data)
      return transform ? transform(value) : value
    },
    onError: (error) => {
      // An abort is the resource cancelling its own in-flight request because
      // its params changed — a screen that fetched before its workspace was
      // chosen, and then fetched again once it was. Nothing failed and there is
      // nothing to do, so reporting it puts "Something went wrong" over a page
      // that is loading correctly.
      if (isAbort(error)) return
      if (!silent) notifyError(error)
      onError?.(error)
    },
    ...rest,
  })

  for (const doctype of watchDoctypes) {
    onDoctypeChange(doctype, () => resource.reload())
  }

  return resource
}

/**
 * A write. Always announces its outcome — a save that appears to do nothing is
 * indistinguishable from a broken one.
 */
export function useAction(url, options = {}) {
  const {
    successMessage = __('Saved'),
    silent = false,
    transform,
    onSuccess,
    onError,
    ...rest
  } = options

  return useCall({
    url,
    method: 'POST',
    immediate: false,
    transform: (data) => {
      const value = normalize(data)
      return transform ? transform(value) : value
    },
    onSuccess: (data) => {
      if (!silent && successMessage) notifySuccess(successMessage)
      onSuccess?.(data)
    },
    onError: (error) => {
      if (isAbort(error)) return
      if (!silent) notifyError(error)
      onError?.(error)
    },
    ...rest,
  })
}

/**
 * Documents and lists, through frappe-ui's own document layer.
 *
 * `useList` / `useDoc` / `useDoctype` are the recommended layer for new code —
 * they share one document store, so a row updated through a list and the same
 * document opened on a detail page stay in step, and they carry pagination and
 * write helpers. Rolling our own on top of `frappe.client.get_list` gave up all
 * of that and shadowed the library's name while doing it.
 *
 * These wrappers exist for the same reason `useResource` does: to apply one
 * error policy, and to refetch over the socket rather than by polling.
 */
export function useDocList(doctype, options = {}) {
  const { watch: watchDoctypes = [doctype], silent = false, onError, ...rest } = options

  const list = useList({
    doctype,
    onError: (error) => {
      if (!silent) notifyError(error)
      onError?.(error)
    },
    ...rest,
  })

  for (const watched of watchDoctypes) {
    onDoctypeChange(watched, () => list.reload())
  }

  return list
}

/**
 * One document. `name` may be a getter, so a detail page can follow its route
 * parameter without a watcher of its own.
 *
 * useDoc reports failures through its `error` ref rather than an `onError`
 * option, so the toast is wired to that.
 */
export function useDocument(doctype, name, options = {}) {
  const { watch: watchDoctypes = [doctype], silent = false, ...rest } = options

  const resource = useDoc({ doctype, name, ...rest })

  if (!silent) {
    watch(
      () => resource.error,
      (error) => error && notifyError(error),
    )
  }

  for (const watched of watchDoctypes) {
    onDoctypeChange(watched, () => resource.reload())
  }

  return resource
}

/**
 * The write side of a doctype — insert, setValue, delete, runDocMethod.
 *
 * Every submit runs independently, so saving two records at once does not
 * cancel either. `frappe.client.set_value` through `callMethod` was one shared
 * request that did.
 */
export function useDocWrites(doctype, options = {}) {
  const { successMessage, silent = false } = options
  const writes = useDoctype(doctype)

  const announce = (fn) => async (...args) => {
    try {
      const result = await fn(...args)
      if (successMessage && !silent) notifySuccess(successMessage)
      return result
    } catch (error) {
      if (!silent) notifyError(error)
      throw error
    }
  }

  return {
    raw: writes,
    insert: announce((values) => writes.insert.submit(values)),
    setValue: announce((values) => writes.setValue.submit(values)),
    delete: announce((name) => writes.delete.submit({ name })),
  }
}

/**
 * One-off call for imperative code. Normalised and toasted like everything else.
 *
 * `method: 'GET'` for reads. frappe-ui's `call()` is POST-only, and a method
 * whitelisted `methods=["GET"]` rejects a POST as a PermissionError — which
 * reads like an auth problem and is not one. That is what made every read on
 * the signup page fail, so the page reported signups closed on a site where
 * they were open. `tests/test_api_calls.py` checks the verb against the
 * whitelist now.
 */
export async function callMethod(method, params = {}, options = {}) {
  const { successMessage, silent = false, method: verb = 'POST' } = options
  try {
    const response =
      verb === 'POST'
        ? await rawCall(method, params)
        : await frappeRequest({ url: method, method: verb, params })
    const data = normalize(response)
    if (successMessage && !silent) notifySuccess(successMessage)
    return data
  } catch (error) {
    if (!silent) notifyError(error)
    throw error
  }
}
"""


BRAND_JS = BANNER + """
/**
 * What customers call us.
 *
 * The repositories and Frappe apps are oneapp and oneapp_control; those names
 * are internal and stay put. Nothing user-visible should spell either of them,
 * so every surface reads these instead.
 */
export const TENANT_APP = 'OneSpace'
"""


TRANSLATE_JS = BANNER + '''
/**
 * One sentence, in the reader's language.
 *
 * Frappe's own mechanism, deliberately, because half the sentences in this
 * product are sentences Frappe and ERPNext have already translated into forty
 * languages: the msgid *is* the English string, so `__("Delete")` resolves
 * against their catalogue with no work from us and no key to invent. What is
 * ours goes in `apps/<app>/<app>/locale/<lang>.po` beside theirs, and
 * `bench generate-pot-file` finds it — the extractor already reads `.vue` and
 * `.js` looking for this exact function name and signature.
 *
 * So the signature is not a choice: `__(text, values, context)`, `{0}` and
 * `{name}` placeholders, `msgid:context` for the two sentences that are the
 * same words meaning different things. Matching `frappe.public/js/translate.js`
 * is what makes the extractor and the catalogues work.
 *
 * English costs nothing. The msgid is the English, so an English reader
 * downloads no catalogue and every call returns its own argument.
 */

/** The catalogue for the reader's language. Empty for English, and for a
 *  language nobody has translated yet — both of which fall through to the
 *  msgid, which is the English sentence. */
let messages = {}

/** `{0}` and `{name}`, the two shapes Frappe's own `$.format` accepts. */
function fill(text, values) {
  if (!values) return text
  return text.replace(/\\{([\\w]+)\\}/g, (whole, key) => {
    const value = Array.isArray(values) ? values[Number(key)] : values[key]
    return value === undefined || value === null ? whole : String(value)
  })
}

/**
 * The sentence, translated where there is a translation.
 *
 * `context` is for the handful of words that are one word in English and two
 * everywhere else — "Open" the verb against "Open" the state. It is the second
 * half of the msgid, exactly as Frappe stores it.
 */
export function __(text, values = null, context = null) {
  if (!text || typeof text !== 'string') return text
  const translated =
    (context && messages[`${text}:${context}`]) || messages[text] || text
  return fill(translated, values)
}

/**
 * Fetch the catalogue, once, before anything is drawn.
 *
 * Before rather than after because a page that renders in English and then
 * repaints in Arabic has also changed direction, and that is not a flicker —
 * it is the whole layout moving. The endpoint is cached for a year by the
 * server it comes from, so this is one request on a cold visit and none after.
 *
 * Never throws: a workspace whose catalogue would not load is a workspace in
 * English, which is worse than the alternative and better than a blank page.
 */
export async function loadTranslations(lang) {
  if (!lang || lang === 'en') return {}
  try {
    const response = await fetch(
      `/api/method/frappe.translate.get_boot_translations?lang=${encodeURIComponent(lang)}`,
      { headers: { Accept: 'application/json' } },
    )
    if (!response.ok) return {}
    messages = (await response.json())?.message || {}
  } catch {
    messages = {}
  }
  return messages
}

/** What is loaded, for a test that wants to prove a sentence resolves. */
export function catalogue() {
  return messages
}

/**
 * Which way the page runs.
 *
 * The list rather than a lookup of every language: these are the ones written
 * right to left, and a language absent from it is left to right — which is the
 * right way for the guess to fail.
 */
const RIGHT_TO_LEFT = ['ar', 'arc', 'dv', 'fa', 'ha', 'he', 'ks', 'ku', 'ps', 'ur', 'yi']

export function direction(lang) {
  return RIGHT_TO_LEFT.includes(String(lang || '').split('-')[0]) ? 'rtl' : 'ltr'
}
'''

DATES_JS = BANNER + """
/**
 * Dates in the reader's language.
 *
 * A page can be translated down to the last button and still say the age of
 * every row in English, because "8 days ago" is not a msgid: it is built by
 * dayjs's `relativeTime` plugin out of a locale of its own. This loads that
 * locale, once, before the app mounts.
 *
 * Its own module rather than a corner of `translate.js`, which is deliberately
 * free of imports — it is read by a test that runs it under node, where `@/ui`
 * means nothing.
 */

import { dayjs } from '@/ui'

""" + '''/**
 * The languages dayjs has to be told about, and how.
 *
 * "8 days ago" is not translated by the catalogue: it is built by dayjs's
 * `relativeTime` plugin out of a locale that has to be loaded, and without one
 * every row of every list says its age in English on an otherwise Arabic
 * screen. Named one by one rather than built from the language — the import
 * path has to be a literal or the bundler cannot see which locales to ship, and
 * it would either bundle all one hundred and thirty or none.
 */
const DATE_LOCALES = {
  ar: () => import('dayjs/esm/locale/ar'),
  de: () => import('dayjs/esm/locale/de'),
}

/**
 * Teach dayjs the reader's language. English needs nothing — it is the default
 * — and a language we have no locale for keeps English dates rather than
 * failing, which is the same bargain `loadTranslations` makes.
 */
export async function loadDates(lang) {
  const base = String(lang || '').split('-')[0]
  if (!base || base === 'en' || !DATE_LOCALES[base]) return
  try {
    await DATE_LOCALES[base]()
    dayjs.locale(base)
  } catch {
    /* English dates on an Arabic page is a blemish; a blank page is not. */
  }
}
'''

FORMAT_JS = BANNER + """
/**
 * How a date, a time, a number and an amount of money read.
 *
 * One module, and nothing in the product formats any of the four outside it.
 * That is not tidiness: there were three clocks before this — `dayjsLocal`
 * (right, and guarded), `toLocaleDateString` (the reader's browser rather than
 * the workspace, and in `.js` where the guard did not look), and the server
 * sending `"d MMM, HH:mm"` already rendered, which the browser cannot convert
 * even if it wants to. And five date format strings for two ideas, with two
 * month spellings chosen per call site.
 *
 * The numbers were worse because the damage is invisible: they went through
 * `toLocaleString(undefined, …)`, which follows *the reader's browser
 * language*. A German workspace that sets `#.###,##` saw `1,234.50` or
 * `1.234,50` depending on nothing anybody configured, so two colleagues read
 * the same invoice differently and neither could tell.
 *
 * Every answer here comes from the workspace's own settings, which a person
 * can change on the Regional screen and which wrote through to System
 * Settings and were then read by nothing. They ride the boot payload because a
 * list draws its first numbers before any resource resolves.
 */

import { dayjs, dayjsLocal } from '@/ui'

import { formats as booted } from '@/lib/runtime/boot'

/**
 * Frappe's date spelling, in dayjs's.
 *
 * The System Settings Select offers six — `yyyy-mm-dd`, `dd-mm-yyyy`,
 * `dd/mm/yyyy`, `dd.mm.yyyy`, `mm/dd/yyyy`, `mm-dd-yyyy` — and the three
 * tokens below cover all of them. Translated here rather than stored in
 * dayjs's spelling because the stored string is what the settings screen
 * shows, and a workspace whose setting stopped matching its own dropdown is a
 * setting nobody can reason about.
 */
const DATE_TOKEN = /yyyy|yy|mm|dd/g
const AS_DAYJS = { yyyy: 'YYYY', yy: 'YY', mm: 'MM', dd: 'DD' }

/**
 * The number formats Frappe ships, and what each one's separators are.
 *
 * Derived from frappe/frappe's `number_format.js`, which keeps the same table
 * for the same reason: the string is a *label* for a shape rather than a
 * pattern to be parsed, and `#,###` and `#,###.##` differ in whether the
 * comma is a group separator or a decimal point in a way no general parser
 * gets right without being told.
 */
const SHAPES = {
  '#,###.##': { group: ',', decimal: '.', places: 2 },
  '#.###,##': { group: '.', decimal: ',', places: 2 },
  '# ###.##': { group: ' ', decimal: '.', places: 2 },
  '# ###,##': { group: ' ', decimal: ',', places: 2 },
  "#'###.##": { group: "'", decimal: '.', places: 2 },
  '#, ###.##': { group: ', ', decimal: '.', places: 2 },
  '#,##,###.##': { group: ',', decimal: '.', places: 2, indian: true },
  '#,###.###': { group: ',', decimal: '.', places: 3 },
  '#.###': { group: '.', decimal: '', places: 0 },
  '#,###': { group: ',', decimal: '', places: 0 },
}
const PLAIN = SHAPES['#,###.##']

/** What the workspace said, with a default for every key. */
export function settings() {
  const own = booted || {}
  return {
    date: String(own.date_format || 'yyyy-mm-dd'),
    time: String(own.time_format || 'HH:mm:ss'),
    shape: SHAPES[own.number_format] || PLAIN,
    float: Number(own.float_precision ?? 3),
    money: Number(own.currency_precision ?? PLAIN.places),
    currency: String(own.currency || ''),
  }
}

/** The workspace's day pattern, in dayjs's spelling. */
function datePattern() {
  return settings().date.replace(DATE_TOKEN, (token) => AS_DAYJS[token])
}

/**
 * A value as a dayjs in the reader's own zone, or null.
 *
 * A **string** is a Frappe datetime: a wall clock in the *site's* timezone, so
 * reading it as if it were the reader's own puts an invoice dated the 1st on
 * the 31st for anybody far enough west. `dayjsLocal` is what converts it.
 *
 * A **Date or a number** is an absolute instant — a browser's own
 * `Date.now()`, a comment posted in this tab a moment ago — and has no
 * timezone to convert *from*. Running it through `dayjsLocal` would shift it
 * by the site's offset and say a reply posted now arrived four hours ago.
 */
function read(value) {
  if (value === null || value === undefined || value === '') return null
  const when = typeof value === 'string' ? dayjsLocal(value) : dayjs(value)
  return when.isValid() ? when : null
}

/** A day, in the workspace's format. */
export function date(value) {
  return read(value)?.format(datePattern()) || ''
}

/** A time of day, in the workspace's format. */
export function time(value) {
  return read(value)?.format(settings().time) || ''
}

/** A day and a time of day. */
export function moment(value) {
  const when = read(value)
  return when ? when.format(`${datePattern()} ${settings().time}`) : ''
}

/**
 * How long ago, and the one rule that settles where it is right.
 *
 * Under a week it is relative — "3 days ago" is how a person thinks about
 * something that happened this week. Over a week it is a date, because
 * "8 months ago" is less useful than "12 Jan 2026" and every surface was
 * deciding that for itself.
 *
 * The absolute value belongs in a tooltip beside it; `moment()` is what to put
 * there.
 *
 * `bare` drops the "ago" — "3 days" rather than "3 days ago" — which is what a
 * list's meta column wants, where the header already says the word and the
 * space is three characters wide.
 */
export const RELATIVE_DAYS = 7

export function ago(value, bare = false) {
  const when = read(value)
  if (!when) return ''
  if (dayjs().diff(when, 'day') >= RELATIVE_DAYS) return when.format(datePattern())
  return when.fromNow(bare)
}

/**
 * Group the thousands and fix the decimals, the way this workspace writes
 * them. `places` defaults to the workspace's float precision.
 */
export function number(value, places) {
  if (value === null || value === undefined || value === '') return ''
  const amount = Number(value)
  if (!Number.isFinite(amount)) return String(value)

  const { shape, float } = settings()
  const digits = places === undefined ? float : Number(places)
  const fixed = Math.abs(amount).toFixed(Math.max(digits, 0))
  const [whole, part] = fixed.split('.')

  const grouped = shape.indian ? lakhs(whole) : thousands(whole, shape.group)
  const sign = amount < 0 ? '-' : ''
  return part ? `${sign}${grouped}${shape.decimal || '.'}${part}` : `${sign}${grouped}`
}

/** Three at a time, from the right. */
function thousands(digits, group) {
  return digits.replace(/\B(?=(\d{3})+(?!\d))/g, group)
}

/**
 * Two at a time above the first three, which is how the Indian system writes
 * a lakh: 12,34,567 rather than 1,234,567. Frappe ships `#,##,###.##` as a
 * format option, so a workspace can choose it and the general rule is wrong
 * for them.
 */
function lakhs(digits) {
  if (digits.length <= 3) return digits
  const last = digits.slice(-3)
  const rest = digits.slice(0, -3)
  return `${rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',')},${last}`
}

/**
 * An amount of money: the number at the currency's own precision, with its
 * symbol.
 *
 * Its own function because the symbol and the decimal count were deliberately
 * separated — which was right, and left every caller to re-join them, so a
 * currency's own precision was nobody's job. JPY has none and KWD has three;
 * `Intl` knows both, and asking it for the *shape* while formatting the digits
 * ourselves is what keeps the separators the workspace's rather than the
 * browser's.
 */
export function money(value, currency) {
  if (value === null || value === undefined || value === '') return ''
  const code = String(currency || settings().currency || '').toUpperCase()
  const digits = code ? placesFor(code) : settings().money
  const written = number(value, digits)
  const symbol = code ? symbolFor(code) : ''
  return symbol ? `${symbol} ${written}` : written
}

/** How many decimals this currency is written to. */
function placesFor(code) {
  try {
    return new Intl.NumberFormat('en', { style: 'currency', currency: code })
      .resolvedOptions().maximumFractionDigits
  } catch {
    // A code Intl does not know — a workspace's own unit, a crypto ticker.
    // The workspace's money precision is the honest answer.
    return settings().money
  }
}

/** The currency's symbol, or its code where it has none. */
function symbolFor(code) {
  try {
    const parts = new Intl.NumberFormat('en', { style: 'currency', currency: code })
      .formatToParts(0)
    return parts.find((one) => one.type === 'currency')?.value || code
  } catch {
    return code
  }
}

export default { settings, date, time, moment, ago, number, money, RELATIVE_DAYS }
"""
