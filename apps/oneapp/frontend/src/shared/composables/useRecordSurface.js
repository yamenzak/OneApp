/**
 * The record a screen has open.
 *
 * Which record is in the URL, so it is a link somebody can send. What is
 * deliberately *not* in the URL is a record that does not exist yet.
 *
 * Null is "no record", and it is also what closing one means. There is no
 * second flag, because two of them is how a surface ends up open over nothing.
 *
 * It used to answer a second question — pane or page — with a manifest default,
 * a remembered preference per screen, and a control to change it. All of that
 * is gone: a record is a page. `lib/screen/surfaces.js` has the argument, and
 * `docs/DESKTOP.md` has the whole of it.
 */
import { computed, ref } from 'vue'

import { workspace } from '@/shared/lib/workspace'
import { KIND, atOf, pushAt, withAt } from '@/shared/lib/url/at'

export function useRecordSurface({ spaceCode, spec, route, router, reloadList }) {
  const editing = ref(null)
  const shownRecord = computed(() => editing.value)

  const open = (row) => {
    router.push({ query: withAt(route.query, KIND.RECORD, row.name) })
  }

  /**
   * A record opened from inside another one — a variation from the job it hangs
   * off, an invoice from the project it was raised against.
   *
   * Always a window over the page, because replacing the page with it is
   * correct navigation and the wrong thing to do: you were reading the job, you
   * glanced at one of its lines, and the job is gone. It was a drawer; it is a
   * window now, which is the same gesture the breadcrumb makes and one fewer
   * overlay to learn.
   *
   * It used to have a second branch — navigate to the other screen outright —
   * for the case where this record was a pane rather than a page. There is no
   * such case.
   */
  const openElsewhere = ({ screen, name }) => {
    if (!name) return
    router.push({
      query: pushAt(route.query, KIND.PEEK, name, screen || route.query.screen),
    })
  }

  // Opening it is a fetch rather than a read of the row: the list carries the
  // columns somebody chose to see, and seeding the form from the row left every
  // unlisted field blank on a record that has a value for it.
  const openRecord = async (name) => {
    if (!name) {
      editing.value = null
      return
    }
    if (editing.value && editing.value.name === name) return
    const found = await workspace.screenRecord(spaceCode, spec.value?.screen || '', name)
    if (!found?.name) {
      // A link to something that is gone, or that this screen does not list.
      // Drop it from the URL rather than leaving a pane that never opens.
      closeRecord()
      return
    }
    editing.value = found
  }

  const closeRecord = () => {
    editing.value = null
    if (!atOf(route.query, KIND.RECORD)) return
    router.replace({ query: withAt(route.query, null) })
  }

  // Somebody else saved it while this was open, and the reader asked for their
  // version.
  const reloadRecord = async () => {
    const name = editing.value?.name
    if (!name) return
    editing.value = null
    await openRecord(name)
    await reloadList()
  }

  // Saving refreshes the list behind the record and re-reads the record, so
  // what is on screen is what the server has rather than what was typed.
  const recordSaved = async () => {
    await reloadList()
    const name = editing.value?.name
    if (!name) return
    editing.value = null
    await openRecord(name)
  }

  // Gone. The record closes and the list behind it has one row fewer — and it
  // has to be told, because nothing else on this screen knows.
  const recordRemoved = async () => {
    closeRecord()
    await reloadList()
  }

  // The record's id changed, so the URL points at something that no longer
  // exists. Replaced rather than pushed: leaving it in the history is leaving a
  // 404 in it.
  const recordRenamed = async (name) => {
    if (!name) return
    await router.replace({ query: withAt(route.query, KIND.RECORD, name) })
    await reloadList()
  }

  return {
    shownRecord,
    open, openElsewhere, openRecord, closeRecord, recordRemoved,
    reloadRecord, recordSaved, recordRenamed,
  }
}
