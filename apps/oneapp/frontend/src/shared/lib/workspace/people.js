/**
 * One person, beyond what their record holds.
 *
 * Where somebody is *now* and how they have been are not fields on an Employee:
 * they are four HRMS doctypes reasoned over, which is `oneapp/onehr/presence.py`
 * and `history.py`. A record page asks for them here rather than assembling them
 * from four lists, because the ranking between those four — leave outranks a
 * badge-in, a holiday outranks both — is a product decision and belongs in one
 * place on the server.
 *
 * Silent, both of them. A workspace without HRMS answers "not known" and draws
 * nothing, and a toast saying so on every person you open would be a toast about
 * an app the reader never asked for.
 */

import { callMethod } from '@/shared/lib/runtime/resource'

export const people = {
  /** In, out, on leave, on holiday, absent — and whether an arrival was late. */
  presence: (employee) =>
    callMethod('oneapp.onehr.presence.of', { employee }, { silent: true, method: 'GET' }),

  /** Their last eight weeks of days, and the leave they have left by type. */
  personHistory: (employee) =>
    callMethod('oneapp.onehr.history.of', { employee }, { silent: true, method: 'GET' }),
}
