import { ref } from 'vue'

import { workspace } from '../lib/workspace'

/**
 * The records a screen lists, and everything about having fetched them.
 *
 * This owns its state rather than being handed it: the rows, what they were
 * fetched *with*, and the four flags a list needs to say whether it is loading,
 * failed, has more, or is counting. The host reads them and so does the
 * template; nothing outside needs to know how a page is asked for.
 *
 * `payload` and `onChange` are thunks — the host builds its request and decides
 * what an unsaved change means below this call.
 */
export function useRows({ spaceCode, spec, payload, onChange }) {
  const rows = ref([])
  const columns = ref([])
  const selection = ref([])
  const total = ref(null)
  const hasMore = ref(false)
  const rowsLoading = ref(false)
  const loadingMore = ref(false)
  const rowsError = ref('')
  const pageLength = ref(100)

  // What the rows actually came back *as*, which is not always what the
  // controls currently say. Pressing Done sets the local answer immediately,
  // and a list that redrew from it would regroup the rows it still has — in
  // the old order — into headings that repeat, for as long as the request
  // takes.
  const groupedBy = ref('')
  const fetchedBoard = ref(null)
  const fetchedCards = ref(null)

  const fetchPage = (start) =>
    workspace.screenRows(
      spaceCode,
      spec.value.screen,
      payload(),
      spec.value.layout || '',
      { start, limit: pageLength.value },
      spec.value.view_type,
    )

  // Asked after the rows and never awaited with them: the footer says how many
  // are loaded until this answers, and then how many there are.
  let counting = 0
  const countRows = async () => {
    const asked = ++counting
    total.value = null
    try {
      const answer = await workspace.screenRowCount(
        spaceCode,
        spec.value.screen,
        payload(),
        spec.value.layout || '',
      )
      // A count that arrives after the question changed is an answer to the
      // old question, and putting it in the footer is worse than leaving it
      // blank.
      if (asked === counting) total.value = answer?.total ?? null
    } catch {
      // The rows are already on screen. A count that could not be taken leaves
      // the footer saying how many are loaded, which is true and is enough —
      // it is not a reason to shout at somebody reading a list.
    }
  }

  const loadRows = async () => {
    if (!spec.value?.doctype) {
      rows.value = []
      columns.value = spec.value?.columns || []
      return
    }
    rowsLoading.value = true
    rowsError.value = ''
    try {
      const page = await fetchPage(0)
      rows.value = page?.rows || []
      selection.value = []
      // The columns the rows were actually fetched with, which is not always
      // the screen's: an unsaved change to the column list narrows the fetch,
      // and a header list that does not follow leaves a column standing over
      // empty cells.
      columns.value = page?.columns || spec.value.columns || []
      groupedBy.value = page?.group_by || ''
      fetchedBoard.value = page?.board || null
      fetchedCards.value = page?.cards || null
      hasMore.value = !!page?.has_more
      countRows()
    } catch (error) {
      // A read that fails is not an empty list, and this one is asked quietly
      // — so without this a server error renders as "nothing here yet", which
      // is the most confidently wrong thing a screen can say. It cost an
      // afternoon once: a count query Frappe refused, shown as an empty
      // backlog.
      rows.value = []
      total.value = null
      hasMore.value = false
      rowsError.value = error?.message || String(error)
    } finally {
      rowsLoading.value = false
    }
  }

  // Appends rather than replaces, and keeps the selection: someone who ticked
  // four rows and then asked for more has not changed their mind about the four.
  const loadMore = async () => {
    if (loadingMore.value || !hasMore.value) return
    loadingMore.value = true
    try {
      const page = await fetchPage(rows.value.length)
      const seen = new Set(rows.value.map((row) => row.name))
      rows.value = [...rows.value, ...(page?.rows || []).filter((row) => !seen.has(row.name))]
      hasMore.value = !!page?.has_more
    } finally {
      loadingMore.value = false
    }
  }

  // A page size is part of the screen, so changing it is a change to save like
  // any other — and it starts the list again rather than truncating what is
  // loaded.
  const setPageLength = (size) => {
    if (!size || size === pageLength.value) return
    pageLength.value = size
    onChange()
  }

  return {
    rows, columns, selection, total, hasMore, rowsLoading, loadingMore,
    rowsError, pageLength, groupedBy, fetchedBoard, fetchedCards,
    loadRows, countRows, loadMore, setPageLength,
  }
}
