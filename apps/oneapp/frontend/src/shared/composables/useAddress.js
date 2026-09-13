/**
 * A panel with an address.
 *
 * The settings dialog has twenty-four panels and there was no way to link to
 * one, which makes every support answer "open settings, then find Backups".
 * The assistant, the filter panel and the column picker had the same problem
 * and the same cause: none of them is a route, so none of them was in the URL.
 *
 * They stay dialogs and panels — C2 is clear that a place you come back to is
 * a route and a thing you toggle is not, and settings is the second. What
 * changes is only that a thing you toggle can still be *said*. A dialog with
 * an address is a dialog somebody can be sent to, and it costs one watcher.
 *
 * Two directions, and the loop between them is why this is a composable rather
 * than four pairs of watchers:
 *
 *   the URL says something  ->  `write` puts the panel in that state
 *   the panel changes       ->  the URL says so, by `replace`
 *
 * `replace` and never `push`: opening settings is not a place to come back to
 * with the back button, and a history full of panel toggles is a back button
 * that does nothing visible four times. What it *is* is a link somebody can
 * send, which is the whole of what this is for.
 *
 * `docs/UNIFICATION.md` §C4.
 */
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

/**
 * @param key   the declared query parameter — `lib/url/params.js`
 * @param read  what the URL should say right now; `''` for "not open"
 * @param write what to do when the URL says something; `''` means close
 */
export function useAddress(key, { read, write }) {
  const route = useRoute()
  const router = useRouter()

  //: The URL's answer, as a string. Vue Router gives `undefined` for an
  //: absent key and an array for a repeated one; both mean nothing useful is
  //: being asked for.
  const asked = () => {
    const value = route.query[key]
    return typeof value === 'string' ? value : ''
  }

  // The URL first, on mount and on every navigation — including the back
  // button, which is what makes this a real address rather than a label.
  watch(asked, (value) => {
    if (value !== read()) write(value)
  }, { immediate: true })

  watch(read, (value) => {
    if (value === asked()) return
    const query = { ...route.query }
    if (value) query[key] = value
    else delete query[key]
    router.replace({ query })
  })
}
