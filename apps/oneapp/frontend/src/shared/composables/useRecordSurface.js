/**
 * The record a screen has open, and whether it is a pane or the page.
 *
 * Which record is in the URL, so it is a link somebody can send. What is
 * deliberately *not* in the URL is a record that does not exist yet.
 *
 * Null is "no record", and it is also what closing one means. There is no
 * second flag, because two of them is how a pane ends up open over nothing.
 */
import { computed, ref, watch } from 'vue'

import { workspace } from '@/shared/lib/workspace'
import { PAGE, declared, remember, remembered } from '@/modules/onespace/lib/screen/surfaces'

export function useRecordSurface({ spaceCode, spec, route, router, reloadList }) {
  const editing = ref(null)
  const shownRecord = computed(() => editing.value)

  // What this person has said about this screen, or null for "has not said".
  const surface = ref(null)

  // Read when the screen changes rather than watched: `localStorage` fires no
  // events for its own tab, and a screen is the only thing that changes which
  // answer applies.
  watch(
    () => [spaceCode, spec.value?.screen],
    ([space, screen]) => {
      surface.value = remembered(space, screen)
    },
    { immediate: true },
  )

  /**
   * Whether the open record takes the page rather than a pane beside the list:
   * the reader's answer where they have given one, the manifest's otherwise.
   * Nothing here asks the viewport — the phone's answer is `RecordPane`'s and
   * it wins either way.
   */
  const asPage = computed(
    () => !!shownRecord.value && (surface.value || declared(spec.value)) === PAGE,
  )

  // Remembered as well as applied: clicking it on every project is the thing
  // the control exists to stop.
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
   * On a page the answer is the drawer: you are reading the job, you glance at
   * one of its lines, and replacing the page with the line is correct
   * navigation and the wrong thing to do. Everywhere else it is the ordinary
   * screen-and-record URL.
   *
   * The saved view and the view type are dropped when navigating: they belong
   * to the screen being left.
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
    if (!route.query.record) return
    const query = { ...route.query }
    delete query.record
    router.replace({ query })
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

  // Saving from the pane refreshes the list under it and re-reads the record,
  // so what the pane shows is what the server has rather than what was typed.
  const recordSaved = async () => {
    await reloadList()
    const name = editing.value?.name
    if (!name) return
    editing.value = null
    await openRecord(name)
  }

  // Gone. The pane shuts and the list behind it has one row fewer — and it
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
    await router.replace({ query: { ...route.query, record: name } })
    await reloadList()
  }

  return {
    shownRecord, asPage, setSurface,
    open, openElsewhere, openRecord, closeRecord, recordRemoved,
    reloadRecord, recordSaved, recordRenamed,
  }
}
