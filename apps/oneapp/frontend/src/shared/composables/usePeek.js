import { computed, ref, watch } from 'vue'

import { workspace } from '@/shared/lib/workspace'
import { close as closeWindow, open as openWindow } from '@/modules/onespace/lib/desk/windows'
import { KIND, atOf, peekScreenOf, popAt, pushAt, writeAt } from '@/shared/lib/url/at'

/**
 * A record opened from inside another one.
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
 * `reloadList` is a thunk: the host defines its loader below this call.
 */

/** Its place on the desk — `lib/desk/windows.js`. */
export const RECORD = 'record'
export function usePeek({ spaceCode, spec, route, router, reloadList }) {
  const peeked = ref(null)
  const peekSpec = ref(null)

  const peekScreen = computed(() => peekScreenOf(route.query) || spec.value?.screen || '')
  const peekName = computed(() => atOf(route.query, KIND.PEEK))

  // Back, in both senses: the record underneath is still there and the
  // browser's own back button does the same thing.
  // A pop, not a clear: the record underneath is still open and is still in
  // the URL, which is what makes the browser's own back button do this too.
  const closePeek = () => router.push({ query: popAt(route.query, KIND.PEEK) })

  /**
   * The peeked record and the spec to draw it with — both, and in parallel:
   * reusing this screen's spec would render an invoice through the projects
   * screen's columns.
   *
   * Cleared first, so switching from one peeked record to another does not show
   * the last one's fields under the new one's name. A record that comes back
   * empty closes the window rather than leaving an empty one open.
   */
  const loadPeek = async () => {
    if (!peekName.value || !peekScreen.value) {
      peeked.value = null
      peekSpec.value = null
      return
    }
    peeked.value = null
    peekSpec.value = null
    const [found, drawn] = await Promise.all([
      workspace.screenRecord(spaceCode, peekScreen.value, peekName.value),
      workspace.screenSpec(spaceCode, peekScreen.value),
    ])
    if (peekName.value !== atOf(route.query, KIND.PEEK)) return
    if (!found?.name) {
      closePeek()
      return
    }
    peeked.value = found
    peekSpec.value = drawn || null
    // On the desk, so the dock has a tile for it and the stack knows where it
    // sits. Named from the record rather than the screen: two windows called
    // "Invoices" is two tiles you have to press to tell apart.
    openWindow(RECORD, {
      label: found.title || found.name,
      icon: 'lucide-file-text',
    })
  }

  const peekSaved = async () => {
    await loadPeek()
    // The page underneath may be showing what just changed — a variation's
    // stage in the rail, an invoice's total in a tab.
    await reloadList()
  }

  // The peeked record, opened properly: its own screen, its own list behind it.
  // Pushed rather than replaced — the job you were reading is a place you may
  // want the back button to return to.
  const expandPeek = () => {
    if (!peekName.value) return
    router.push({
      query: { screen: peekScreen.value, at: writeAt(KIND.RECORD, peekName.value) },
    })
  }

  const peekRenamed = (name) => {
    if (!name) return
    router.replace({ query: pushAt(route.query, KIND.PEEK, name, peekScreen.value) })
  }

  watch([peekName, peekScreen], loadPeek, { immediate: true })

  // Off the desk when the address stops naming one. The window is `v-if`'d on
  // the record, so this is only about the dock's tile and the stack — but a
  // tile for a window that is not there is a tile that does nothing.
  watch(peekName, (now) => {
    if (!now) closeWindow(RECORD)
  })

  /** Deleted from the window. Shuts it and reloads the list underneath. */
  const peekRemoved = async () => {
    closePeek()
    await reloadList()
  }

  return {
    peeked, peekSpec, peekScreen, peekName,
    loadPeek, closePeek, peekSaved, expandPeek, peekRenamed, peekRemoved,
  }
}
