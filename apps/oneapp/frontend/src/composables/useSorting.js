import { computed } from 'vue'

/**
 * The order the list is in, and what clicking a header does to it.
 *
 * The order belongs to the screen rather than to the body: it is saved with the
 * view, it goes into every request, and a board sorts its cards by the same
 * answer a list sorts its rows by. The body only says which column was clicked.
 */
export function useSorting({ order, spec, onChange }) {
  const sorted = computed(() => (order.value || spec.value?.order_by || '').split(' '))
  const sortField = computed(() => sorted.value[0])
  const ascending = computed(() => sorted.value[1] === 'asc')

  // Clicking the column already sorted flips it; clicking another starts on
  // descending, which is what "show me the newest" means for most columns.
  const sortBy = (fieldname) => {
    const flip = fieldname === sortField.value && !ascending.value
    order.value = `${fieldname} ${flip ? 'asc' : 'desc'}`
    onChange()
  }

  return { sortField, ascending, sortBy }
}
