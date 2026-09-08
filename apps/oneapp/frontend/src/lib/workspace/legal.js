/**
 * The agreements a workspace runs under.
 *
 * Assembled on the server from what every module declares — see
 * `oneapp/onelegal` — so there is nothing here but the four calls: what the
 * documents are, one document's text, what this person still has to agree to,
 * and agreeing.
 *
 * `outstanding` is asked once when the shell boots rather than on every request.
 * A person who has not agreed is stopped by a dialog they cannot dismiss, and
 * by the server on the two paths where carrying on would mean carrying on under
 * an agreement nobody made: creating a workspace, and enabling a space.
 */

import { callMethod } from '@/lib/runtime/resource'
import { __ } from '@/lib/runtime/translate'

export const legal = {
  legalCatalogue: () =>
    callMethod('oneapp.onelegal.catalogue', {}, { silent: true, method: 'GET' }),

  legalDocument: (key, version = '') =>
    callMethod('oneapp.onelegal.document', { key, version }, {
      silent: true, method: 'GET',
    }),

  legalHistory: (key = '') =>
    callMethod('oneapp.onelegal.history', { key }, { silent: true, method: 'GET' }),

  legalOutstanding: () =>
    callMethod('oneapp.onelegal.outstanding', {}, { silent: true, method: 'GET' }),

  legalAccept: (documents) =>
    callMethod('oneapp.onelegal.accept', { documents: JSON.stringify(documents) }, {
      successMessage: __('Recorded'),
    }),
}
