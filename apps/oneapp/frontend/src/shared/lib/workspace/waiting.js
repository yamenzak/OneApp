/** What is waiting on you, across every space — `oneapp/onespace/waiting.py`. */

import { callMethod } from '@/shared/lib/runtime/resource'

export const waiting = {
  /** Every document waiting on this reader, placed and with its verbs. */
  waitingOnMe: () =>
    callMethod('oneapp.onespace.waiting.mine', {}, { silent: true, method: 'GET' }),

  /**
   * Just the number, for the badge.
   *
   * Its own call because the badge is wanted on every page and the list on
   * one: the server loads a document per row to work out its verbs, and a
   * count that did that would be the rail paying for a screen nobody opened.
   */
  waitingCount: () =>
    callMethod('oneapp.onespace.waiting.how_many', {}, { silent: true, method: 'GET' }),
}
