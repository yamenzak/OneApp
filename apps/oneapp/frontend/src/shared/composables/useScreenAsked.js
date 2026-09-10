import { computed, ref } from 'vue'

import { DEFAULT_VIEW_TYPE } from '@/modules/onespace/lib/screen/viewTypes'

/**
 * What the reader has asked of a screen, and how it is sent.
 *
 * Two questions, and the reader already tells them apart: a filter, a sort and
 * "only my favourites" are about **which records**; columns, widths, pinning,
 * grouping and what a card carries are about **how they are drawn**. Switching
 * from a list to a board changes the second and not the first, which is why
 * `askedOfRows` is a smaller thing than `payload`.
 *
 * `pageLength`, `reloadRows` and `reload` are thunks: the host's rows and its
 * screen resolution are declared below this call.
 */
export function useScreenAsked({ spec, pageLength, reloadRows, reload }) {
  // Two filter surfaces asked together, which is what Frappe does: the boxes
  // above answer the common question and the panel answers the rest, and
  // neither clears the other.
  const quickFilters = ref([])
  const panelFilters = ref([])
  // The one box. Not a filter and not stored with a view: a saved view that
  // carried somebody's half-typed search would open narrowed for reasons
  // nothing on screen explains.
  const search = ref('')
  const order = ref('')
  const chosenColumns = ref([])
  const favourites = ref(false)
  const groupBy = ref('')
  // Keyed by view type, the shape the manifest and a saved view both store: a
  // board's card and a grid's card are separate answers.
  const viewSettings = ref({})
  const dirty = ref(false)

  const changed = async () => {
    dirty.value = true
    await reloadRows()
  }

  const payload = () => ({
    // Without the view type every save landed on the screen's *first* one, so
    // a view saved from the board was filed as a list view.
    view_type: spec.value?.view_type || DEFAULT_VIEW_TYPE,
    filters: [...quickFilters.value, ...panelFilters.value],
    search: search.value,
    order_by: order.value,
    columns: chosenColumns.value,
    favourites: favourites.value,
    group_by: groupBy.value,
    page_length: pageLength(),
    // Sent whole so that clearing a choice clears it: a truthiness check would
    // leave the last board field standing after a reset.
    view_settings: viewSettings.value,
  })

  /**
   * What a dashboard is narrowed by — only the parts that decide which records.
   *
   * A computed rather than a call, because the body watches it: a function
   * returning a fresh object every render is a watcher that never settles.
   */
  const dashboardAsked = computed(() => ({
    filters: [...quickFilters.value, ...panelFilters.value],
    search: search.value,
    order_by: order.value,
    favourites: favourites.value,
  }))

  const askedOfRows = () => ({
    quick: quickFilters.value.map((one) => [...one]),
    panel: panelFilters.value.map((one) => [...one]),
    search: search.value,
    order: order.value,
    favourites: favourites.value,
  })

  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b)

  /** Seed from a screen that has just resolved, dropping anything unsaved. */
  const seedFrom = (resolved) => {
    quickFilters.value = []
    search.value = ''
    viewSettings.value = {}
    panelFilters.value = (resolved?.saved?.filters || []).map((filter) => [...filter])
    order.value = resolved?.order_by || ''
    chosenColumns.value = (resolved?.columns || []).map((column) => ({
      fieldname: column.fieldname,
      width: column.width,
      pin: column.pin,
      // Empty where nobody has said, which means the fieldtype decides.
      align: column.align || '',
    }))
    favourites.value = !!resolved?.saved?.favourites
    groupBy.value = resolved?.saved?.group_by || ''
    dirty.value = false
  }

  /**
   * Apply what was being asked before the view type changed underneath.
   *
   * Marked unsaved where it differs from what this type resolved to, so the
   * switcher says "this view, with changes" rather than showing a filtered
   * board under a view's name that means something else.
   */
  const carry = (carried) => {
    const resolved = askedOfRows()
    quickFilters.value = carried.quick
    panelFilters.value = carried.panel
    search.value = carried.search || ''
    order.value = carried.order || order.value
    favourites.value = carried.favourites
    dirty.value = !same(carried, resolved)
  }

  const onQuickFilters = (filters) => {
    quickFilters.value = filters
    changed()
  }

  const onPanelFilters = (filters) => {
    panelFilters.value = filters
    changed()
  }

  /**
   * Narrow to one value of one field, from the tally.
   *
   * Into the panel's filters rather than the quick row: this is the same
   * `[field, =, value]` a person would have added by hand, and putting it where
   * they can see and remove it is what stops a list being narrowed by something
   * invisible. Replaces any filter already on that field — two equalities on
   * one column match nothing, which reads as the tally lying.
   */
  const narrowTo = ({ field, value }) => {
    if (!field) return
    panelFilters.value = [
      ...panelFilters.value.filter((one) => one[0] !== field),
      [field, '=', value ?? ''],
    ]
    changed()
  }

  const onColumns = (chosen) => {
    chosenColumns.value = chosen
    changed()
  }

  const clearAllFilters = () => {
    quickFilters.value = []
    panelFilters.value = []
    search.value = ''
    // The controls read their state from the spec, so re-resolving is what puts
    // the boxes back to empty rather than leaving them showing a cleared filter.
    reload()
  }

  const onGroupBy = (fieldname) => {
    groupBy.value = fieldname || ''
    changed()
  }

  const toggleFavourites = () => {
    favourites.value = !favourites.value
    changed()
  }

  const cardsChanged = (changes) => {
    const type = spec.value?.view_type || DEFAULT_VIEW_TYPE
    viewSettings.value = {
      ...viewSettings.value,
      [type]: { ...(viewSettings.value[type] || {}), ...changes },
    }
    changed()
  }

  return {
    quickFilters, panelFilters, search, order, chosenColumns, favourites, groupBy,
    viewSettings, dirty,
    payload, dashboardAsked, askedOfRows, seedFrom, carry, changed,
    onQuickFilters, onPanelFilters, narrowTo, onColumns, clearAllFilters,
    onGroupBy, toggleFavourites, cardsChanged,
  }
}
