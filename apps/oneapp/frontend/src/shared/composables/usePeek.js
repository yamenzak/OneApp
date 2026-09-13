import { computed, ref, watch } from 'vue'

import { workspace } from '@/shared/lib/workspace'
import { KIND, atOf, peekScreenOf, popAt, pushAt, writeAt } from '@/shared/lib/url/at'

/**
 * A record opened from inside another one.
 *
 * `?at=peek:<screen>/<name>` — one parameter, and it carries the screen
 * because the thing being peeked at is usually on a different one: a project's
 * invoices are the invoices screen, and a name with no screen is a name the
 * host would look up in the wrong place. §C4.
 *
 * `reloadList` is a thunk: the host defines its loader below this call.
 */
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
   * empty closes the drawer rather than leaving an empty one open.
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

  /** Deleted from the drawer. Shuts it and reloads the list underneath. */
  const peekRemoved = async () => {
    closePeek()
    await reloadList()
  }

  return {
    peeked, peekSpec, peekScreen, peekName,
    loadPeek, closePeek, peekSaved, expandPeek, peekRenamed, peekRemoved,
  }
}
