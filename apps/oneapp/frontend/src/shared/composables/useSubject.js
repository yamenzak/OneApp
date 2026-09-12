/**
 * What the engine is looking at, as the header draws it.
 *
 * Split out of `shared/composables/useCrumbs.js` by §C1: the *trail* is one
 * thing every surface has and the *subject* is what this one has — a record's
 * face, its id, and the two badges beside it. A record is not a crumb, so it
 * is not built by the thing that builds crumbs.
 *
 * All of it derived: functions of the spec and the record, and nothing here
 * writes anything back.
 */
import { computed } from 'vue'

import { docBadge } from '@/modules/onespace/lib/screen/docstate'
import { VIEW_TYPES } from '@/modules/onespace/lib/screen/viewTypes'

export function useSubject({ spec, shownRecord, viewType }) {
  const viewLabel = computed(() => {
    const type = viewType.value || spec.value?.view_type
    return VIEW_TYPES[type]?.label || 'List'
  })

  /**
   * The record, when one is open.
   *
   * Worth being honest about what this is not yet: the record opens as a
   * modal dialog, and a modal takes the rest of the page out of the
   * accessibility tree, so while it is open this can be read by eye and not
   * by a screen reader. What it does buy today is the URL — a record is a
   * link somebody can send — and it is the subject a record *page* will want
   * when there is one.
   */
  const subject = computed(() => {
    const open = shownRecord.value
    if (!open) return null
    const title = spec.value?.title_field
    const label = (title && open[title]) || open.name
    return {
      value: open.name,
      label: String(label),
      // The id, and only where the name is not already it.
      id: label === open.name ? '' : open.name,
      image: spec.value?.image_field ? open[spec.value.image_field] : null,
    }
  })

  // Where the record stands. Which field that is comes from the manifest and
  // is checked against the doctype on the way out; what colour it is comes
  // from the doctype's own states, the same way the list cell reads it.
  const statusValue = computed(() => {
    const field = spec.value?.status_field
    return (field && shownRecord.value?.[field]) || ''
  })

  // And where the framework stands on it: a workflow's state, or Draft /
  // Submitted / Cancelled. De-duped against the field above, because a screen
  // whose `status_field` *is* the workflow's state field is already saying it.
  const docState = computed(() =>
    docBadge(shownRecord.value?._state, spec.value?.status_field || ''),
  )

  return { viewLabel, subject, statusValue, docState }
}
