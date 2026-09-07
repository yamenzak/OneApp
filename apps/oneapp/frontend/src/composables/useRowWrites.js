import { notifyError } from '@/lib/runtime/notify'
import { workspace } from '@/lib/workspace'

/**
 * The three writes a body makes without opening the record.
 *
 * They live with the list rather than in the body because only the shell can
 * re-read it: a card that appears where it was dropped and nowhere in the data
 * is the bug this shape exists to stop.
 */
export function useRowWrites({ spaceCode, spec, favourites, reloadRows }) {
  /**
   * One field, written from a body.
   *
   * A board's whole reason to exist: dragging a card between columns is a save
   * of the field the columns are. Optimistic on the row so the card stays where
   * it was dropped while the request is in flight, then the list is re-read —
   * the save may have changed more than was sent (a workflow, a `fetch_from`, a
   * `modified` that reorders the page), and a board showing our guess instead
   * of the server's answer is a board that lies quietly.
   */
  const writeField = async ({ row, field, value }) => {
    if (!row || !field) return
    const was = row[field]
    row[field] = value
    try {
      await workspace.saveRecord(spaceCode, spec.value.screen, { [field]: value }, row.name)
    } catch (e) {
      row[field] = was
      notifyError(e)
      return
    }
    await reloadRows()
  }

  /**
   * A record made from inside a body, without the dialog.
   *
   * The board's column foot: a name, Enter, and a card. The promise is the
   * body's — it keeps what was typed until this resolves, and puts it back
   * where it was if the save is refused.
   */
  const quickCreate = async ({ values, done, fail }) => {
    try {
      await workspace.saveRecord(spaceCode, spec.value.screen, values, null)
      await reloadRows()
      done?.()
    } catch (e) {
      notifyError(e)
      fail?.(e)
    }
  }

  const like = async (row) => {
    const result = await workspace.toggleLike(spaceCode, spec.value.screen, row.name)
    // Patched in place rather than reloaded: a like is not a reason to lose the
    // reader's scroll position.
    row._meta = {
      ...row._meta,
      liked: !!result?.liked,
      likes: (result?.likes || []).length,
    }
    // Unless the like is what the list is filtered by, in which case a row that
    // is no longer a favourite has no business still being in it.
    if (favourites.value) await reloadRows()
  }

  return { writeField, quickCreate, like }
}
