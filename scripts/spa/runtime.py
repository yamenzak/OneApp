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

export default {
  siteName,
  socketioPort,
  csrfToken,
  sessionUser,
  systemTimezone,
  isDev,
  devServer,
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
  if (!error) return { title: 'Something went wrong', message: '', detail: null }

  // A string is its own message. Callers hand one over whenever the detail is
  // theirs rather than the server's — a bulk change naming the four records
  // that refused it, say — and without this every one of those rendered as
  // "Something went wrong / No further detail was returned", which is the
  // most confidently useless pair of sentences in the product. It had been
  // doing that on a refused bulk delete since that was written.
  if (typeof error === 'string') {
    return {
      title: 'Something went wrong',
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

  // FrappeResponseError already carries the parsed fields.
  const title =
    first.title ||
    error.title ||
    (error.name === 'FrappeResponseError' ? 'Request failed' : null) ||
    'Something went wrong'

  const message =
    fromServer ||
    stripTags(error.message) ||
    lastTracebackLine(error.exception) ||
    'No further detail was returned.'

  return {
    title: stripTags(title),
    message,
    // Extra server messages beyond the first, shown as additional lines.
    extra: messages.slice(1).map((m) => stripTags(m.message)).filter(Boolean),
    indicator: first.indicator || error.indicator || 'red',
    detail: error.exception || error.stack || null,
    raw: error,
  }
}

export function errorText(error) {
  const { title, message } = normalizeError(error)
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

const STORAGE_KEY = 'oneapp:sound'

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

export function soundEnabled() {
  try {
    return localStorage.getItem(STORAGE_KEY) !== 'off'
  } catch {
    // Private mode and blocked storage both throw; default to on.
    return true
  }
}

export function setSoundEnabled(enabled) {
  try {
    localStorage.setItem(STORAGE_KEY, enabled ? 'on' : 'off')
  } catch {
    /* nothing we can do, and nothing worth failing for */
  }
}

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
 * Notifications.
 *
 * Every mutation reports its outcome and every failure is rendered from a
 * normalised Frappe error, so users never see a raw traceback or a silent
 * no-op. Both play a short tone.
 *
 * Pages should not call `toast` directly — these wrappers are what guarantee
 * the sound and the error parsing happen.
 */

import { toast } from 'frappe-ui'

import { normalizeError } from './errors'
import { playSound } from './sound'

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

export { toast }
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

import { siteName, socketioPort, devServer } from './boot'

let socket = null
const subscribers = new Map()
const documents = new Map()
const viewers = new Map()
const rooms = new Set()

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

export function getSocket() {
  if (socket) return socket

  socket = io(socketUrl(), {
    withCredentials: true,
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

import { notifyError, notifySuccess } from './notify'
import { onDoctypeChange } from './socket'

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
    successMessage = 'Saved',
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
