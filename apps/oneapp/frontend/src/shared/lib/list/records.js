/**
 * Where a list of *records* comes from.
 *
 * The last of the four, and the one the plan put last on purpose: it is the
 * one that must not regress. The record engine already offers all fourteen
 * capabilities — it is the surface the audit's table was measured *against* —
 * so unlike the other three this is not filling a gap. It is closing the
 * vocabulary: the engine's fetch now answers the same four questions as a
 * file list and a mailbox, and declares what it can do in the same words.
 *
 * That buys two things. The engine stops being the one list in the product
 * whose capabilities are implicit, which is what §F1 was about. And a surface
 * that wants *records* without the engine's chrome — a related-records list, a
 * picker, a panel beside something else — can have the frame without taking
 * the view switcher, the filter panel, saved views and grouping with it.
 *
 * What this deliberately does not do is move the engine into `DataList`. The
 * board, the cards, the calendar, the columns a page was actually fetched with
 * and what the money columns add up to are all part of `load`'s *answer*, and
 * they reach the caller through `onAnswer` because they are the screen's to
 * draw. A frame that knew about any of them would be the engine again.
 *
 * `docs/UNIFICATION.md` §B1.
 */
import { unref } from 'vue'

import { CAN, offers } from '@/shared/lib/capability'
import { workspace } from '@/shared/lib/workspace'

/**
 * One screen's records.
 *
 * `payload` and `range` are thunks because the caller builds the request
 * below this: the filters, the order, the columns and the days a calendar has
 * on screen are the screen's state, and a source that held a copy of them
 * would be a copy that goes stale.
 */
export function recordSource({
  spaceCode, spec, payload, range = null, can = {}, empty = {}, onAnswer = null,
} = {}) {
  return {
    identify: (row) => row.name,
    empty,

    //: Everything, because the engine really does offer everything — this is
    //: the surface the audit measured the other seventeen against. A caller
    //: that is *not* the engine narrows it: a picker over records offers
    //: search and nothing else, and says so here rather than by drawing
    //: fewer controls and hoping.
    can: offers({
      [CAN.SORT]: true,
      [CAN.SEARCH]: true,
      [CAN.FILTER]: true,
      [CAN.COLUMNS]: true,
      [CAN.SAVED]: true,
      [CAN.COUNT]: true,
      [CAN.PAGE]: true,
      [CAN.VIRTUAL]: true,
      [CAN.GROUP]: true,
      [CAN.BULK]: true,
      [CAN.CREATE]: true,
      [CAN.DELETE]: true,
      [CAN.EXPORT]: true,
      ...can,
    }),

    async load({ start = 0, pageLength = 100 } = {}) {
      const screen = unref(spec) || {}
      // A screen with no doctype is a dashboard or a placeholder, not an empty
      // list. Asking would be asking the server about nothing.
      if (!screen.doctype) {
        onAnswer?.({})
        return { rows: [], hasMore: false }
      }

      const page = await workspace.screenRows(
        unref(spaceCode),
        screen.screen,
        payload(),
        screen.layout || '',
        // The days a calendar has on screen travel beside `start` and `limit`
        // rather than in the payload: a saved view that carried a month would
        // be one that shows nothing in the next.
        { start, limit: pageLength, ...(range?.() || {}) },
        screen.view_type,
      )
      onAnswer?.(page || {})
      return { rows: page?.rows || [], hasMore: !!page?.has_more }
    },
  }
}
