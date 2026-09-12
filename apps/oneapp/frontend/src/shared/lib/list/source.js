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
 *
 * Four implementations are planned and this file holds the first.
 * `StaticSource` is an array already in hand — notifications, versions,
 * Attention, the marketplace, people, roles, the launcher — which is seven of
 * the seventeen and the cheapest proof the shape is right. `FileSource`,
 * `ThreadSource` and `DoctypeSource` follow, and `DoctypeSource` is last on
 * purpose: it is the one that must not regress, and the browser suite is its
 * check.
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
} = {}) {
  const all = () => [...(unref(rows) || [])]

  return {
    identify: key,
    empty,

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
