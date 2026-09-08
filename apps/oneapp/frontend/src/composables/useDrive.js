/**
 * The Drive's list, and everything that changes it.
 *
 * Split out of the page because the page is a layout and this is a state
 * machine: five places, a selection that has to survive a reload, and eight
 * mutations that all end the same way — re-read the place you are looking at,
 * because the server decided what happened and the client's guess about it is
 * how a list goes out of step with the database.
 *
 * The selection is by name and not by row. A reload replaces every row object,
 * and a selection held as objects would silently empty itself on the reload
 * that follows every action performed on it.
 */
import { computed, ref } from 'vue'

import { workspace } from '../lib/workspace'
import { useSaving } from './useSaving'

export const PAGE = 50

//: Where the chosen order is kept. One key for both halves, because "by size,
//: biggest first" is one decision and storing it as two lets them drift.
const ORDER_KEY = 'onespace:drive:order'

function read() {
  try {
    const held = JSON.parse(localStorage.getItem(ORDER_KEY) || '{}')
    return { key: held.key || '', down: !!held.down }
  } catch {
    return { key: '', down: false }
  }
}

function write(key, down) {
  try {
    localStorage.setItem(ORDER_KEY, JSON.stringify({ key, down }))
  } catch {
    // A browser with storage switched off orders this session and forgets.
  }
}

export function useDrive({ place, folder }) {
  const files = ref([])
  const more = ref(false)
  const { saving: loading, error, attempt: attemptLoad } = useSaving()
  const { saving: busy, attempt: attemptBusy } = useSaving(error)
  const search = ref('')
  const path = ref([])
  const picked = ref(new Set())

  // What the reader put this place in. Empty means the place's own default —
  // Home leads with folders and then names, Recents with what was opened last
  // — and the server decides that, so an empty key here is not "no order" but
  // "whatever this place is for".
  //
  // Remembered in the browser like the grid toggle, and for the same reason: a
  // person who wants the biggest file first wants it in every folder, not once.
  const sort = ref(read().key)
  const descending = ref(read().down)

  const selected = computed(() => files.value.filter((one) => picked.value.has(one.name)))
  const anySelected = computed(() => picked.value.size > 0)
  const allSelected = computed(
    () => files.value.length > 0 && files.value.every((one) => picked.value.has(one.name)),
  )

  async function load({ append = false } = {}) {
    await attemptLoad(async () => {
      const found = await workspace.driveList({
        place: place.value,
        folder: folder.value,
        search: search.value,
        start: append ? files.value.length : 0,
        limit: PAGE,
        sort: sort.value,
        descending: descending.value ? 1 : 0,
      })
      files.value = append ? [...files.value, ...(found?.files || [])] : found?.files || []
      more.value = !!found?.more
      path.value = found?.path || []
      // A row that is gone is not still selected. Without this, deleting four
      // files leaves a selection bar claiming four are chosen.
      const here = new Set(files.value.map((one) => one.name))
      picked.value = new Set([...picked.value].filter((name) => here.has(name)))
    })
  }

  function toggle(file) {
    const next = new Set(picked.value)
    if (next.has(file.name)) next.delete(file.name)
    else next.add(file.name)
    picked.value = next
  }

  function toggleAll() {
    picked.value = allSelected.value
      ? new Set()
      : new Set(files.value.map((one) => one.name))
  }

  function clear() {
    picked.value = new Set()
  }

  /**
   * Every mutation, wrapped the same way: one at a time, errors surfaced where
   * the list is rather than in a toast that has gone by the time anybody looks,
   * and a re-read at the end.
   */
  async function act(work) {
    await attemptBusy(async () => {
      await work()
      await load()
    })
  }

  const names = (of) => (Array.isArray(of) ? of : [of]).map((one) => one.name || one)

  /**
   * Put the place in an order, and read it back from the top.
   *
   * From the top because `start` is an offset into the old order: appending
   * page two of "by name" onto page one of "by date" is a list that is in
   * neither order and has rows twice.
   *
   * Pressing the key that is already in force turns it round, which is what a
   * sort control does everywhere; pressing it a third time is still descending
   * rather than back to nothing, because "no order" is not a state anybody is
   * trying to reach.
   */
  function orderBy(key) {
    const down = key === sort.value ? !descending.value : false
    sort.value = key
    descending.value = down
    write(key, down)
    return load()
  }

  return {
    files, more, loading, error, search, path, busy,
    picked, selected, anySelected, allSelected,
    sort, descending, orderBy,
    load, toggle, toggleAll, clear, act,

    // The eight. Each is a call and a re-read, which is why they are one line.
    favourite: (file) =>
      act(() => workspace.driveFavourite(file.name, !file.liked)),
    rename: (file, title) => act(() => workspace.driveRename(file.name, title)),
    move: (what, into) => act(() => workspace.driveMove(names(what), into)),
    trash: (what) => act(() => workspace.driveTrash(names(what))),
    restore: (what) => act(() => workspace.driveRestore(names(what))),
    destroy: (what) => act(() => workspace.driveEmptyTrash(names(what))),
    emptyBin: () => act(() => workspace.driveEmptyTrash([])),
    newFolder: (title) => act(() => workspace.driveNewFolder(title, folder.value)),
  }
}
