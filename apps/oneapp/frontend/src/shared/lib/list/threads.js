/**
 * Where a list of *conversations* comes from.
 *
 * The third of the four sources, and the one that shows why the contract has
 * the shapes it has. A mailbox is not a table: it pages by a cursor the server
 * hands back rather than by an offset into a fixed list, and a conversation
 * can have some of its messages on one page and the rest on the next. Both of
 * those are the source's business and neither leaks into the frame — `append`
 * says "the next one" and `fold` says how two pages add up.
 *
 * `docs/UNIFICATION.md` §B1.
 */
import { ref, unref } from 'vue'

import { CAN, offers } from '@/shared/lib/capability'
import { workspace } from '@/shared/lib/workspace'

/** What one page of a mailbox is, as the server counts it. */
export const PAGE = 50

/**
 * A mailbox folder.
 *
 * `cursor` is held here rather than passed in, because it is a fact about
 * this reading and nothing outside it has any use for the number. It is
 * exposed as a ref for exactly one caller: mail arriving over the socket
 * refreshes the list only while somebody is still on the first page, and
 * quietly does not while they are four pages down reading something.
 */
export function threadSource({ folder, empty = {}, can = {} } = {}) {
  const cursor = ref(0)

  return {
    identify: (thread) => thread.key,
    empty,
    cursor,

    //: Search and paging. No sort: a mailbox is in one order and it is the
    //: order mail arrived in; no count, because the server answers "is there
    //: more" rather than "how many", which is the only question a mailbox can
    //: answer cheaply.
    can: offers({
      [CAN.SEARCH]: true,
      [CAN.PAGE]: true,
      ...can,
    }),

    async load({ append = false, search = '' } = {}) {
      const found = await workspace.mailThreads(
        unref(folder), append ? cursor.value : 0, search,
      )
      cursor.value = found?.next || 0
      return { rows: found?.threads || [], hasMore: !!found?.more }
    },

    /**
     * Two pages of a mailbox, added up.
     *
     * A conversation that straddles the boundary arrives twice with half its
     * messages in each, so the counts are summed rather than the second copy
     * dropped — a thread of nine would otherwise say four in the list and open
     * on nine.
     */
    fold(have, arriving) {
      const by = new Map(have.map((one) => [one.key, one]))
      for (const one of arriving) {
        const already = by.get(one.key)
        if (!already) {
          by.set(one.key, one)
          continue
        }
        already.count += one.count
        already.unread += one.unread
      }
      return [...by.values()]
    },
  }
}
