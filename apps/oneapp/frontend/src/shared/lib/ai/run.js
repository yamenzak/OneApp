/**
 * Watching one AI answer arrive.
 *
 * The server hands back a run id and then publishes over the socket every
 * browser is already on — `onespace/ai/streaming.py` says why it is a
 * background job and not a held-open request. This is the other half: one
 * composable, used identically by a mail summary, a paragraph being written
 * into a document and a column of cells filling in.
 *
 * Two things it does that a plain listener would not.
 *
 * **It catches up.** Realtime is best-effort and a laptop that slept has
 * missed frames it can never get back. So the final message carries the whole
 * text and replaces whatever was accumulated, and `catchUp()` fetches the same
 * thing for the case where even the final message was missed. Without either,
 * a dropped frame is a sentence with a hole in it that nothing ever fixes.
 *
 * **It is one socket handler for every run.** The event name is fixed and the
 * run id is in the message, so twenty cells filling at once are twenty
 * entries in a map rather than twenty `socket.on` registrations — which is the
 * difference between the sheet working and the sheet leaking listeners.
 */
import { computed, onScopeDispose, ref, shallowRef } from 'vue'

import { errorText } from '@/shared/lib/runtime/errors'
import { onEvent } from '@/shared/lib/runtime/socket'
import { workspace } from '@/shared/lib/workspace'

/** The one event the server publishes runs on. Matches `streaming.CHANNEL`. */
export const CHANNEL = 'oneapp_ai'

/** run id -> the ref set watching it. Module level: the socket is. */
const watching = new Map()
let listening = false

function attach() {
  if (listening) return
  listening = true
  // No scope: this outlives every component, the same way the socket does.
  onEvent(CHANNEL, (message) => {
    const seats = watching.get(message?.run)
    if (seats) seats.forEach((fn) => fn(message))
  })
}

function watch(run, handler) {
  attach()
  if (!watching.has(run)) watching.set(run, new Set())
  watching.get(run).add(handler)
  return () => {
    const seats = watching.get(run)
    if (!seats) return
    seats.delete(handler)
    if (!seats.size) watching.delete(run)
  }
}

/**
 * One run, as reactive state.
 *
 * `start` takes a function that posts to whichever endpoint owns this feature
 * and resolves to `{ok, run}` — this composable deliberately does not know how
 * a run is begun, because every module begins its own through its own narrow
 * endpoint rather than through a general "run a feature" call.
 */
export function useAiRun() {
  const text = ref('')
  const running = ref(false)
  const error = ref('')
  const credits = ref(0)
  /** Whatever the feature returned beyond text — actions, a link, a choice. */
  const extra = shallowRef(null)

  const id = ref('')
  let release = null
  let settle = null

  const streaming = computed(() => running.value)

  function reset() {
    release?.()
    release = null
    text.value = ''
    error.value = ''
    credits.value = 0
    extra.value = null
    id.value = ''
  }

  function land(message) {
    if (message.delta) {
      text.value += message.delta
      return
    }
    if (!message.done) return

    // The whole text, not what was accumulated: see the module comment.
    text.value = message.text || text.value
    credits.value = message.credits || 0
    error.value = message.state === 'done' || message.state === 'cancelled'
      ? ''
      : (message.message || '')
    const { run, done, state, delta, message: said, text: whole, credits: spent, ...rest } = message
    extra.value = Object.keys(rest).length ? rest : null

    running.value = false
    release?.()
    release = null
    settle?.(text.value)
    settle = null
  }

  /**
   * Begin a run. Resolves when it finishes, and updates `text` on the way.
   *
   * Resolving as well as streaming, because both callers exist: a summary
   * panel only wants `text` to be reactive, and a document that has to put
   * the finished paragraph somewhere wants to await it.
   */
  async function start(begin) {
    reset()
    running.value = true

    let answer
    try {
      answer = await begin()
    } catch (e) {
      running.value = false
      error.value = errorText(e)
      throw e
    }

    if (!answer?.ok || !answer?.run) {
      running.value = false
      error.value = answer?.message || ''
      return ''
    }

    id.value = answer.run
    release = watch(answer.run, land)

    // Between the POST returning and the handler attaching, a very short run
    // can have finished and published to nobody. One fetch closes that window;
    // a run still going answers `running` and costs one request.
    const caught = await workspace.aiResult(answer.run).catch(() => null)
    if (caught && caught.state !== 'running') {
      land({ ...caught, done: true })
      return text.value
    }
    if (caught?.text && !text.value) text.value = caught.text

    return new Promise((resolve) => { settle = resolve })
  }

  /** Stop it where it is. What arrived stays; the promise resolves with it. */
  async function stop() {
    if (!id.value || !running.value) return
    await workspace.aiStop(id.value).catch(() => null)
  }

  onScopeDispose(() => { release?.(); release = null })

  return { text, running, streaming, error, credits, extra, run: id, start, stop, reset }
}
