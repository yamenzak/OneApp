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
import { errorText } from '../lib/errors'

export const PAGE = 50

export function useDrive({ place, folder }) {
  const files = ref([])
  const more = ref(false)
  const loading = ref(false)
  const error = ref('')
  const search = ref('')
  const path = ref([])
  const picked = ref(new Set())
  const busy = ref(false)

  const selected = computed(() => files.value.filter((one) => picked.value.has(one.name)))
  const anySelected = computed(() => picked.value.size > 0)
  const allSelected = computed(
    () => files.value.length > 0 && files.value.every((one) => picked.value.has(one.name)),
  )

  async function load({ append = false } = {}) {
    loading.value = true
    error.value = ''
    try {
      const found = await workspace.driveList({
        place: place.value,
        folder: folder.value,
        search: search.value,
        start: append ? files.value.length : 0,
        limit: PAGE,
      })
      files.value = append ? [...files.value, ...(found?.files || [])] : found?.files || []
      more.value = !!found?.more
      path.value = found?.path || []
      // A row that is gone is not still selected. Without this, deleting four
      // files leaves a selection bar claiming four are chosen.
      const here = new Set(files.value.map((one) => one.name))
      picked.value = new Set([...picked.value].filter((name) => here.has(name)))
    } catch (raised) {
      error.value = errorText(raised)
    } finally {
      loading.value = false
    }
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
    busy.value = true
    error.value = ''
    try {
      await work()
      await load()
    } catch (raised) {
      error.value = errorText(raised)
    } finally {
      busy.value = false
    }
  }

  const names = (of) => (Array.isArray(of) ? of : [of]).map((one) => one.name || one)

  return {
    files, more, loading, error, search, path, busy,
    picked, selected, anySelected, allSelected,
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
