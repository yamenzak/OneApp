import { computed } from 'vue'

import { docBadge } from '../lib/docstate'
import { VIEW_TYPES } from '../lib/viewTypes'

/**
 * Where the reader is, as the header draws it.
 *
 * All of it derived: the trail, the record's own crumb, and the two badges
 * beside it are functions of the spec and the record, and nothing here writes
 * anything back.
 */
export function useCrumbs({ spaceCode, spec, space, shownRecord, viewType }) {
  const viewLabel = computed(() => {
    const type = viewType.value || spec.value?.view_type
    return VIEW_TYPES[type]?.label || 'List'
  })

  // The space's first screen, which is what the house goes to. A space home is
  // a page of its own one day; until it is, the first thing in the navigation
  // is the nearest true thing.
  const homeRoute = computed(() => {
    const first = spec.value?.screens?.[0]
    return {
      name: 'Screen',
      params: { spaceCode },
      ...(first ? { query: { screen: first.screen } } : {}),
    }
  })

  const crumbs = computed(() => {
    if (!space.value) return []
    const trail = [
      { label: '', home: true, space: space.value.space_label, route: homeRoute.value },
    ]
    if (spec.value?.screen_label) {
      trail.push({
        label: spec.value.screen_label,
        route: {
          name: 'Screen',
          params: { spaceCode },
          query: { screen: spec.value.screen },
        },
      })
    }
    return trail
  })

  // The record, when one is open. It is where you are, so it takes the last
  // place from the view.
  //
  // Worth being honest about what this is not yet: the record opens as a modal
  // dialog, and a modal takes the rest of the page out of the accessibility
  // tree, so while it is open this can be read by eye and not by a screen
  // reader. What it does buy today is the URL — a record is a link somebody can
  // send — and it is the trail a record *page* will want when there is one.
  const recordCrumb = computed(() => {
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

  // Where the record stands. Which field that is comes from the manifest and is
  // checked against the doctype on the way out; what colour it is comes from
  // the doctype's own states, the same way the list cell reads it.
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

  return { viewLabel, homeRoute, crumbs, recordCrumb, statusValue, docState }
}
