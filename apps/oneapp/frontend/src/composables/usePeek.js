import { computed, ref, watch } from 'vue'

import { workspace } from '../lib/workspace'

/**
 * A record opened from inside another one.
 *
 * Two query parameters rather than one, because the thing being peeked at is
 * usually on a different screen — a project's invoices are the invoices screen
 * — and a name with no screen is a name the host would look up in the wrong
 * place.
 *
 * `reloadList` is a thunk rather than the function itself: the host defines its
 * loader below this call, so passing it directly would pass `undefined`.
 */
export function usePeek({ spaceCode, spec, route, router, reloadList }) {
  const peeked = ref(null)
  const peekSpec = ref(null)

  const peekScreen = computed(() => String(route.query.peekScreen || spec.value?.screen || ''))
  const peekName = computed(() => String(route.query.peek || ''))

  // Back, in both senses: the record underneath is still there and the
  // browser's own back button does the same thing, because the drawer is in
  // the URL.
  const closePeek = () => {
    const query = { ...route.query }
    delete query.peek
    delete query.peekScreen
    router.push({ query })
  }

  /**
   * The peeked record and the spec to draw it with.
   *
   * Both, and in parallel: the spec answers what a record of *that* screen
   * looks like — its fields, its states, its own showcase — and reusing this
   * screen's would render an invoice through the projects screen's columns.
   *
   * Cleared first, so switching from one peeked record to another does not show
   * the last one's fields under the new one's name for as long as the request
   * takes. A record that comes back empty — moved, deleted, or never visible to
   * this reader — closes the drawer rather than leaving an empty one open.
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
    if (peekName.value !== String(route.query.peek || '')) return
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
    // stage in the rail, an invoice's total in a tab — so it is re-read too.
    await reloadList()
  }

  // The peeked record, opened properly: its own screen, its own list behind it,
  // and the drawer gone. Pushed rather than replaced — the job you were reading
  // is a place you may well want the back button to return to.
  const expandPeek = () => {
    if (!peekName.value) return
    router.push({ query: { screen: peekScreen.value, record: peekName.value } })
  }

  const peekRenamed = (name) => {
    if (!name) return
    router.replace({ query: { ...route.query, peek: name } })
  }

  watch([peekName, peekScreen], loadPeek, { immediate: true })

  return {
    peeked, peekSpec, peekScreen, peekName,
    loadPeek, closePeek, peekSaved, expandPeek, peekRenamed,
  }
}
