import { onBeforeUnmount } from 'vue'

import { onDoctypeChange } from '../lib/socket'

// Long enough that a burst settles, short enough that a person reads it as
// "it just updated".
const SETTLE = 400

/**
 * Keep a list current with the site it is a list of.
 *
 * Frappe publishes `list_update` for every document that changes, so a list
 * left open on a second screen stops being a photograph of when it was opened.
 *
 * Coalesced, and deliberately: a bulk import or a background job can publish
 * hundreds of these in a second, and one refetch per event is a list that
 * spends its afternoon reloading.
 *
 * `paused` is asked on every event rather than at subscribe time — refetching
 * while something is unsaved would replace the rows under a filter somebody is
 * still choosing, and the Save button would then be offering to save a screen
 * they are no longer looking at.
 */
export function useListFollow({ paused, reload }) {
  let pending = null
  let watching = null
  let unfollow = null

  const follow = (doctype) => {
    if (watching === doctype) return
    if (unfollow) unfollow()
    unfollow = null
    watching = doctype
    if (!doctype) return
    unfollow = onDoctypeChange(doctype, () => {
      if (paused.value) return
      clearTimeout(pending)
      pending = setTimeout(() => reload(), SETTLE)
    })
  }

  onBeforeUnmount(() => {
    clearTimeout(pending)
    if (unfollow) unfollow()
  })

  return { follow }
}
