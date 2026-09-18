/** One box over every space — `oneapp/onespace/finding.py`. */

import { callMethod } from '@/shared/lib/runtime/resource'

export const finding = {
  /**
   * Records this person can find, from anywhere, for what they typed.
   *
   * `space` is where they were standing when they opened the box. It narrows
   * nothing — the whole point of the box is that it does not — and only breaks
   * the tie when one record is reachable from two spaces.
   *
   * Silent, because a search that fails while somebody is typing must not put
   * a red toast over the list they are reading. The dialog says so in the list
   * itself, where they are looking.
   */
  find: (query, space = '') =>
    callMethod(
      'oneapp.onespace.finding.look',
      { query, space },
      { silent: true, method: 'GET' },
    ),
}
