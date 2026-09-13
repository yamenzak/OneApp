/**
 * Everything that *changes* the Drive's list.
 *
 * Not the reading of it. §B1 moved that to `lib/list/files.js` and
 * `components/DataList.vue`, which is where the skeleton, the empty state,
 * the paging and the failed read now live for every file surface in the
 * product. What is left here is the half that really is the Drive's: five
 * places, a selection that has to survive a reload, and eight mutations that
 * all end the same way — re-read the place you are looking at, because the
 * server decided what happened and the client's guess about it is how a list
 * goes out of step with the database.
 *
 * So this is handed the rows rather than fetching them, and handed the way to
 * ask for them again. `rows` is the frame's accumulated list, pages and all,
 * which is the set the selection is over.
 *
 * The selection is by name and not by row. A reload replaces every row object,
 * and a selection held as objects would silently empty itself on the reload
 * that follows every action performed on it.
 */
import { computed, ref, unref } from 'vue'

import { workspace } from '@/shared/lib/workspace'
import { notifyUndoable } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'
import { useSaving } from '@/shared/composables/useSaving'
import { recallJson, rememberJson } from '@/shared/lib/url/remember'

//: Where the chosen order is *remembered*. One key for both halves, because
//: "by size, biggest first" is one decision and storing it as two lets them
//: drift.
//:
//: A memory and not the answer. The order lives in the URL — see below — and
//: this is what a fresh visit falls back to. It used to be the whole story,
//: which meant a Drive link sent to a colleague arrived in whatever order
//: *their* browser last used while a screen link arrived exactly as sent.
//: `docs/UNIFICATION.md` §C4.
const ORDER_KEY = 'drive.order'

function read() {
  const held = recallJson(ORDER_KEY) || {}
  return { key: held.key || '', down: !!held.down }
}

const write = (key, down) => rememberJson(ORDER_KEY, { key, down })

export function useDrive({ rows, reread, folder, route, router }) {
  const files = computed(() => unref(rows) || [])
  const { saving: busy, error, attempt: attemptBusy } = useSaving()
  const path = ref([])
  const picked = ref(new Set())

  // What the reader put this place in. Empty means the place's own default —
  // Home leads with folders and then names, Recents with what was opened last
  // — and the server decides that, so an empty key here is not "no order" but
  // "whatever this place is for".
  //
  // **The URL first, then the browser's memory.** A link that names an order
  // arrives in it; a visit that names none gets what this person last chose.
  // That is C4's split — the URL carries what somebody would send to a
  // colleague, `localStorage` carries a per-browser convenience — and it is
  // the arrangement a screen has had since saved views were built.
  const asked = () => route?.query || {}
  const sort = ref(asked().sort ?? read().key)
  const descending = ref(
    asked().desc === undefined ? read().down : asked().desc === '1',
  )

  const selected = computed(() => files.value.filter((one) => picked.value.has(one.name)))
  const anySelected = computed(() => picked.value.size > 0)
  const allSelected = computed(
    () => files.value.length > 0 && files.value.every((one) => picked.value.has(one.name)),
  )

  /** Ask the frame to read again, and drop anything that is no longer there. */
  async function load() {
    await reread?.()
    // A row that is gone is not still selected. Without this, deleting four
    // files leaves a selection bar claiming four are chosen.
    const here = new Set(files.value.map((one) => one.name))
    picked.value = new Set([...picked.value].filter((name) => here.has(name)))
  }

  /** The path to the open folder, off the answer the frame got. */
  function walked(found) {
    path.value = found?.path || []
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
    remember(key, down)
    return load()
  }

  /**
   * The order, in the address bar.
   *
   * `replace` and not `push`: sorting a folder is not a place to come back
   * to, and a history full of orderings is a back button that does nothing
   * visible four times. The place's own default is an *absent* key rather
   * than an empty one, so a plain `/files` link stays plain.
   */
  function remember(key, down) {
    if (!router || !route) return
    const query = { ...route.query }
    if (key) query.sort = key
    else delete query.sort
    if (down) query.desc = '1'
    else delete query.desc
    router.replace({ query })
  }

  return {
    files, error, path, busy, walked,
    picked, selected, anySelected, allSelected,
    sort, descending, orderBy,
    load, toggle, toggleAll, clear, act,

    // The eight. Each is a call and a re-read, which is why they are one line.
    favourite: (file) =>
      act(() => workspace.driveFavourite(file.name, !file.liked)),
    rename: (file, title) => act(() => workspace.driveRename(file.name, title)),
    move: (what, into) => act(() => workspace.driveMove(names(what), into)),
    /**
     * The bin, and the way back out of it.
     *
     * The first `notifyUndoable` in the product, and the reason §D2 built it:
     * the bin is *the* reversible destructive verb, and until now the only
     * way back was to change place, find the file among everything anybody
     * had thrown away, and put it back. An undo for eight seconds is the
     * answer to the mistake people actually make, which is the click rather
     * than the decision.
     */
    trash: async (what) => {
      const gone = names(what)
      await act(() => workspace.driveTrash(gone))
      notifyUndoable(
        gone.length === 1 ? __('Moved to the bin') : __('{0} moved to the bin', [gone.length]),
        () => act(() => workspace.driveRestore(gone)),
      )
    },
    restore: (what) => act(() => workspace.driveRestore(names(what))),
    destroy: (what) => act(() => workspace.driveEmptyTrash(names(what))),
    emptyBin: () => act(() => workspace.driveEmptyTrash([])),
    newFolder: (title) => act(() => workspace.driveNewFolder(title, unref(folder) || '')),
  }
}
