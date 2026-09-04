/**
 * The record a screen has open, and whether it is a pane or the page.
 *
 * Which record is in the URL, so it is a link somebody can send and a place a
 * reload comes back to. What is deliberately *not* in the URL is a record that
 * does not exist yet: there is nothing to link to, and a stale "new" in a
 * bookmark would open an empty form nobody asked for.
 *
 * Null is "no record", and it is also what closing one means. There is no
 * second flag, because two of them is how a pane ends up open over nothing.
 */
import { computed, ref, watch } from 'vue'

import { workspace } from '../lib/workspace'
import { PAGE, declared, remember, remembered } from '../lib/surfaces'

export function useRecordSurface({ spaceCode, spec, route, router, reloadList }) {
  const editing = ref(null)
  const shownRecord = computed(() => editing.value)

  // What this person has said about this screen, or null for "has not said".
  const surface = ref(null)

  // Read when the screen changes rather than watched: `localStorage` fires no
  // events for its own tab, so there is nothing to subscribe to, and a screen
  // is the only thing that changes which answer applies.
  watch(
    () => [spaceCode, spec.value?.screen],
    ([space, screen]) => {
      surface.value = remembered(space, screen)
    },
    { immediate: true },
  )

  /**
   * Whether the open record takes the page rather than a pane beside the list.
   *
   * The reader's answer where they have given one, the manifest's otherwise: a
   * screen that says a record is a place gets the width a place needs, and
   * every other screen keeps the pane it has always had — until somebody says
   * otherwise, per screen, and then it is remembered. Nothing here asks the
   * viewport; the phone's own answer is `RecordPane`'s and it wins either way.
   */
  const asPage = computed(
    () => !!shownRecord.value && (surface.value || declared(spec.value)) === PAGE,
  )

  // Remembered as well as applied. The point of the control is that it is a
  // preference — clicking it on every project is the thing it exists to stop.
  const setSurface = (chose) => {
    surface.value = chose
    remember(spaceCode, spec.value?.screen, chose)
  }

  const open = (row) => {
    router.push({ query: { ...route.query, record: row.name } })
  }

  /**
   * A record opened from inside another one.
   *
   * The showcase's variations and its related tabs both come out here, and
   * where it goes depends on what is underneath. On a page — a job filling the
   * window, with its variations up the side and its invoices behind a tab —
   * the answer is the drawer: you are reading the job, you glance at one of its
   * lines, and the job is the reason you are looking. Replacing the page with
   * the line is correct navigation and the wrong thing to do.
   *
   * Everywhere else it is the ordinary screen-and-record URL. Either way it is
   * in the URL, so it is a place with a link and the back button undoes it.
   *
   * The saved view and the view type are deliberately dropped when navigating:
   * they belong to the screen being left, and carrying `layout=my-overdue` onto
   * a different screen is asking it for a view that is not its.
   */
  const openElsewhere = ({ screen, name }) => {
    if (!name) return
    const where = screen || route.query.screen
    if (asPage.value) {
      router.push({ query: { ...route.query, peek: name, peekScreen: where } })
      return
    }
    router.push({ query: { screen: where, record: name } })
  }

  // Opening it is a fetch rather than a read of the row: the list carries the
  // columns somebody chose to see, and the record shows the doctype's whole
  // field list. Seeding the form from the row left every unlisted field blank
  // on a record that has a value for it.
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
    if (!route.query.record) return
    const query = { ...route.query }
    delete query.record
    router.replace({ query })
  }

  // Somebody else saved it while this was open, and the reader asked for their
  // version. The same re-read a save does, without the save.
  const reloadRecord = async () => {
    const name = editing.value?.name
    if (!name) return
    editing.value = null
    await openRecord(name)
    await reloadList()
  }

  // Saving from the pane refreshes the list under it — a title or a status that
  // changed is a row that now reads differently — and re-reads the record, so
  // what the pane shows is what the server has rather than what was typed.
  const recordSaved = async () => {
    await reloadList()
    const name = editing.value?.name
    if (!name) return
    editing.value = null
    await openRecord(name)
  }

  // The record's id changed, so the URL is now pointing at something that no
  // longer exists. Replaced rather than pushed: the old id is not a place to go
  // back to, and leaving it in the history is leaving a 404 in it.
  const recordRenamed = async (name) => {
    if (!name) return
    await router.replace({ query: { ...route.query, record: name } })
    await reloadList()
  }

  return {
    shownRecord, asPage, setSurface,
    open, openElsewhere, openRecord, closeRecord,
    reloadRecord, recordSaved, recordRenamed,
  }
}
