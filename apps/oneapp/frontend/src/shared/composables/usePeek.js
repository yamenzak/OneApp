import { computed, reactive, watch } from 'vue'

import { workspace } from '@/shared/lib/workspace'
import {
  close as closeWindow, closeAll, frontOf, open as openWindow,
} from '@/modules/onespace/lib/desk/windows'
import { identityOf } from '@/modules/onespace/lib/screen/identity'
import { KIND, allAt, popAt, pushAt, writeAt } from '@/shared/lib/url/at'

/**
 * Records opened from inside another one.
 *
 * `?at=peek:<screen>/<name>` — one parameter, and it carries the screen
 * because the thing being peeked at is usually on a different one: a project's
 * invoices are the invoices screen, and a name with no screen is a name the
 * host would look up in the wrong place. §C4.
 *
 * It was a drawer sliding over the page; it is a window now — `docs/DESKTOP.md`
 * stage 4. The gesture is the same one the breadcrumb makes, which is the
 * point: "open the thing this points at" is one behaviour in the product
 * rather than two that look alike. What it costs is the scrim, and that turns
 * out to be a gain — a drawer over a page you are still reading *from* is an
 * overlay that dims the reason you opened it.
 *
 * **Several, since stage 5.** `at` was always a stack and only ever held one
 * peek; it holds as many as you open now, and each gets a window and a dock
 * tile with the record's own face on it. Glancing at a second thing is not a
 * reason to forget the first.
 *
 * They share one corner, so all but the front one are covered completely, and
 * only the front one is *drawn* — see `frontOf`. That is the whole of the
 * hibernation this was going to need: a preview is read-only, so there is no
 * state to suspend. What is kept is the fetched record and spec, which are
 * JSON and cost nothing beside a mounted form, and which make raising one
 * instant rather than a reload with a blank frame in the middle of it.
 *
 * `reloadList` is a thunk: the host defines its loader below this call.
 */

/** The family every record window's id starts with — `lib/desk/windows.js`. */
export const RECORD = 'record:'

/** One window per record, and per *screen*: the same name behind two screens
 *  is two different drawings of it. */
const idOf = (one) => `${RECORD}${one.screen}/${one.ref}`

export function usePeek({ spaceCode, spec, route, router, reloadList }) {
  /**
   * What is open, outermost first — `{ key, screen, name, record, spec }`.
   *
   * Reactive rather than computed: the URL says which records are open and
   * fetching says what they are, so this is the URL's list with the answers
   * filled in as they arrive. Entries already loaded are kept across a change
   * to the stack, which is what makes closing the front one show the one
   * underneath rather than a blank window and a request.
   */
  const stack = reactive([])

  /** The URL's own reading, which is the source of truth for *which*. */
  const wanted = computed(() => allAt(route.query, KIND.PEEK).map((one) => ({
    key: idOf(one),
    screen: one.screen || spec.value?.screen || '',
    name: one.ref,
  })))

  /**
   * The ones with a window to draw — everything fetched.
   *
   * An entry exists the moment the URL names it and is empty until its record
   * arrives, so this is what the host iterates: a `v-if` inside a `v-for` is
   * the same list filtered twice, and the guard that says so is right.
   */
  const ready = computed(() => stack.filter((one) => one.record && one.spec?.doctype))

  /** Which one is drawn: the frontmost window on the desk, which is not the
   *  last in the URL once somebody has raised one from its tile. */
  const front = computed(() => stack.find((one) => one.key === frontOf(RECORD)) || null)

  /**
   * The peeked record and the spec to draw it with — both, and in parallel:
   * reusing this screen's spec would render an invoice through the projects
   * screen's columns.
   *
   * A record that comes back empty closes its own window rather than leaving
   * an empty one open.
   */
  const load = async (one) => {
    if (!one.name || !one.screen || one.loading) return
    one.loading = true
    try {
      const [found, drawn] = await Promise.all([
        workspace.screenRecord(spaceCode, one.screen, one.name),
        workspace.screenSpec(spaceCode, one.screen),
      ])
      // It may have been closed while this was in flight.
      if (!stack.some((open) => open.key === one.key)) return
      if (!found?.name) {
        closePeek(one.key)
        return
      }
      one.record = found
      one.spec = drawn || null
      tile(one)
    } finally {
      one.loading = false
    }
  }

  /**
   * Its place on the desk, named and faced from the record rather than from
   * the screen: five tiles reading "Clients" is five presses to tell apart.
   *
   * Never `front`. Which window is in front is the URL's answer, settled in
   * the reconcile below — this is called again every time a record arrives or
   * is reloaded, and raising on each would hand the front to whichever fetch
   * came back last. It would unfold a window somebody had put away, too.
   */
  const tile = (one) => {
    const who = identityOf(one.record, one.spec)
    openWindow(one.key, {
      label: who.label || one.name,
      image: who.image,
      // Drawn as a record rather than as a window: a picture where there is
      // one, initials where there is not. `lib/desk/windows.js`.
      face: true,
    }, { front: false })
  }

  /**
   * Back, in both senses: the record underneath is still there and the
   * browser's own back button does the same thing.
   *
   * A pop of *one*, not a clear: the record underneath and any peek below this
   * one are still open and still in the URL.
   */
  const closePeek = (key) => {
    const one = stack.find((open) => open.key === key) || front.value
    if (!one) return
    router.push({ query: popAt(route.query, KIND.PEEK, one.name, one.screen) })
  }

  const peekSaved = async (key) => {
    const one = stack.find((open) => open.key === key)
    if (one) await load(one)
    // The page underneath may be showing what just changed — a variation's
    // stage in the rail, an invoice's total in a tab.
    await reloadList()
  }

  /**
   * A peeked record, opened properly: its own screen, its own list behind it.
   *
   * Pushed rather than replaced — the job you were reading is a place you may
   * want the back button to return to — and every other peek closes with it,
   * because they were glances *from* the page you are now leaving.
   */
  const expandPeek = (key) => {
    const one = stack.find((open) => open.key === key) || front.value
    if (!one) return
    router.push({
      query: { screen: one.screen, at: writeAt(KIND.RECORD, one.name) },
    })
  }

  const peekRenamed = (key, name) => {
    const one = stack.find((open) => open.key === key)
    if (!one || !name) return
    router.replace({
      query: pushAt(
        popAt(route.query, KIND.PEEK, one.name, one.screen),
        KIND.PEEK, name, one.screen,
      ),
    })
  }

  /** Deleted from a window. Shuts that one and reloads the list underneath. */
  const peekRemoved = async (key) => {
    closePeek(key)
    await reloadList()
  }

  /**
   * The stack, reconciled against the URL.
   *
   * What the URL has gained is fetched, what it has lost leaves the desk, and
   * the order follows the URL. Keeping the entries themselves is the point: a
   * record already loaded is not fetched again because somebody opened a
   * second one over it, which is what makes closing the front window show the
   * one underneath instead of a blank frame and a request.
   *
   * Watched on the *keys*, spelled as one string, rather than on the list.
   * `wanted` builds fresh objects every read, so a deep watch fired on every
   * change to the query — a saved view, a filter, a folder — and each firing
   * re-opened every window, which unfolds them and reorders the desk. Changing
   * the page's layout would have raised and unfolded three previews somebody
   * had put away.
   */
  const keys = computed(() => wanted.value.map((one) => one.key).join('|'))

  watch(keys, (now, before) => {
    const want = wanted.value
    const held = new Map(stack.map((one) => [one.key, one]))
    for (const one of stack) {
      if (!want.some((open) => open.key === one.key)) closeWindow(one.key)
    }
    const next = want.map((one) => (
      held.get(one.key) || reactive({ ...one, record: null, spec: null, loading: false })
    ))
    stack.splice(0, stack.length, ...next)

    // On the desk in the URL's order and before anything is fetched, so the
    // tiles read left to right the way the stack was built — its name is the
    // record's id until the record says otherwise, which is a second or so.
    for (const one of next) {
      openWindow(one.key, { label: one.record ? undefined : one.name, face: true }, { front: false })
      if (!one.record && !one.loading) load(one)
    }

    // And the one just opened in front. The last entry is it — or, where that
    // one was already open, this is the same record peeked a second time from
    // somewhere else, and the answer to that is still the window you have,
    // brought forward and unfolded.
    const last = next[next.length - 1]
    if (last && last.key !== String(before || '').split('|').pop()) openWindow(last.key)
  }, { immediate: true })

  // Nothing open: every record window off the desk. The windows are `v-if`'d
  // on their records, so this is only about tiles and the stack — but a tile
  // for a window that is not there is a tile that does nothing.
  watch(() => stack.length, (now) => {
    if (!now) closeAll(RECORD)
  })

  return {
    peeks: ready, front, closePeek, peekSaved, expandPeek, peekRenamed, peekRemoved,
    loadPeek: () => Promise.all(stack.map(load)),
  }
}
