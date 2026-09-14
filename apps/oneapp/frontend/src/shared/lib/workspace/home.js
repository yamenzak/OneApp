/**
 * The workspace's front page.
 *
 * One call for three blocks — see `oneapp/onespace/home.py`. Silent, because
 * every block on it is optional: a workspace with no calendar sources and a
 * Drive nobody has opened answers with two empty lists, which the page says
 * in a sentence rather than in a toast.
 */

import { callMethod } from '@/shared/lib/runtime/resource'

export const home = {
  /** What needs you, what is next, and what you had open. */
  myHome: () =>
    callMethod('oneapp.onespace.home.mine', {}, { silent: true, method: 'GET' }),
}
