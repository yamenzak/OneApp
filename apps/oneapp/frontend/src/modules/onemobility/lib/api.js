/**
 * What OneMobility asks the server, in one place.
 *
 * The same shape `lib/workspace/` uses for every other module: a thin named
 * function per endpoint, so a screen says `network.shape()` and no component
 * anywhere holds a dotted path.
 */

import { callMethod } from '@/shared/lib/runtime/resource'

export const network = {
  /** Every line's geometry and every stop's position. Once per session. */
  shape: () => callMethod('oneapp.onemobility.shape', {}, { method: 'GET' }),

  /** Which days there is anything to play back, and the server's clock. */
  days: () => callMethod('oneapp.onemobility.days', {}, { method: 'GET' }),

  /** Every vehicle's position at a moment. Empty `when` means now. */
  at: (params) => callMethod('oneapp.onemobility.at', params, { method: 'GET', silent: true }),

  /** One vehicle's whole day, for the scrubber. */
  track: (params) => callMethod('oneapp.onemobility.track', params, { method: 'GET' }),

  /** How late a line runs, by hour and weekday. */
  punctuality: (params) =>
    callMethod('oneapp.onemobility.punctuality', params, { method: 'GET' }),

  /** Vehicles on one line that have caught each other. */
  bunching: (params) =>
    callMethod('oneapp.onemobility.bunching', params, { method: 'GET', silent: true }),
}
