/**
 * Where a list's rows come from.
 *
 * The engine is not an engine: it is one screen, decomposed. Every list
 * composable has exactly one consumer and every signature says why —
 * `useRows({ spaceCode, spec, … })`, `useSorting({ order, spec, … })`. They
 * were pulled out of a 2,000-line `ScreenHost`, which was worth doing and is
 * not the same thing as building an engine. Nothing whose rows come from
 * anywhere but the framework's own list call, against a declared screen, can
 * use any of it — so seventeen other surfaces built their own, and the
 * audit's table of fourteen capabilities against those seventeen is almost
 * entirely blank.
 *
 * A source is the seam. It answers four questions and declares what it can
 * do; `components/DataList.vue` renders exactly that much and nothing else.
 *
 *     load({ start, pageLength, orderBy, filters, search })
 *                             -> { rows, total, hasMore }
 *     identify(row)           -> a stable key
 *     can                     -> `lib/capability.js`, §F1
 *     empty                   -> what nothing means here
 *     busy()                  -> are the rows still on their way?
 *
 * There are four implementations and they are all here.
 *
 *     source.js    an array already in hand — notifications, versions,
 *                  Attention, the marketplace's two lists, people, roles,
 *                  the launcher. Seven of the seventeen, and the cheapest
 *                  proof the shape was right.
 *     files.js     the one file query, which the Drive, a record's Files tab
 *                  and the attach picker are three readings of.
 *     threads.js   a mailbox, which pages by a cursor and whose rows can
 *                  straddle a page.
 *     records.js   the record engine, which was last on purpose: it is the
 *                  one that must not regress, and the browser suite is its
 *                  check.
 *
 * The order was the argument. Each one had to make the contract earn a shape
 * rather than the contract predicting it — `busy` came from a panel that
 * fetches, `fold` and `append` from a mailbox, the caller-owned search box
 * from a page that keeps it in its header. None of those were guessed.
 *
 * `docs/UNIFICATION.md` §B1.
 */
import { unref } from 'vue'

import { CAN, offers } from '@/shared/lib/capability'

/**
 * Rows that are already here.
 *
 * Everything happens in memory because everything is in memory: the caller
 * fetched a list, or built one, and what it wants from this is the frame
 * around it rather than a query. That is why `search` is a predicate the
 * caller writes — only the caller knows which of a row's fields a person
 * would be searching *for*, and a source that guessed by stringifying the row
 * would match on an id nobody can see.
 */
export function staticSource({
  rows,
  key = (row) => row.name ?? row.key ?? row.id,
  search = null,
  compare = null,
  empty = {},
  can = {},
  loading = false,
} = {}) {
  const all = () => [...(unref(rows) || [])]

  return {
    identify: key,
    empty,

    //: Rows already in hand still arrive from somewhere, and the moment
    //: between the fetch starting and the array being assigned is a real one:
    //: without this the frame reads an empty array as "there is nothing here"
    //: and draws the empty state where the skeleton belongs.
    busy: () => !!unref(loading),

    //: What this source honours. `search` and `sort` only where the caller
    //: said how — a control offered over a predicate nobody wrote is a
    //: control that does nothing.
    can: offers({
      ...(search ? { [CAN.SEARCH]: true } : {}),
      ...(compare ? { [CAN.SORT]: true } : {}),
      ...can,
    }),

    load({ start = 0, pageLength = 0, search: query = '', orderBy = '' } = {}) {
      let found = all()

      const asked = String(query || '').trim()
      if (asked && search) found = found.filter((row) => search(row, asked))
      if (orderBy && compare) found = [...found].sort((a, b) => compare(a, b, orderBy))

      const total = found.length
      const page = pageLength ? found.slice(start, start + pageLength) : found
      return { rows: page, total, hasMore: start + page.length < total }
    },
  }
}
