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

  /** What the network does over a day and over a week, off the aggregate tier. */
  rhythm: (params) => callMethod('oneapp.onemobility.rhythm', params, { method: 'GET' }),

  /** Every vehicle, ranked by how it actually ran. Off `vehicleDay`. */
  fleet: (params) => callMethod('oneapp.onemobility.fleet', params, { method: 'GET' }),

  /** What each stop does: how often, how long, how evenly. Off `stopHour`. */
  stops: (params) => callMethod('oneapp.onemobility.stops', params, { method: 'GET' }),

  /**
   * One measure averaged into a grid of places — where the network runs late,
   * where it fills up. See `onemobility/geo.py` for why it is binned and
   * averaged rather than drawn as a kernel density.
   */
  surface: (params) => callMethod('oneapp.onemobility.surface', params, { method: 'GET' }),

  /** Every stop with its position and what happens there. */
  demand: (params) => callMethod('oneapp.onemobility.demand', params, { method: 'GET' }),

  /**
   * Every facet and the values it can take. Once per session — the vocabulary
   * is a closed table on the server and the options are doctype rows read as
   * the person asking, so this is not something a screen can assemble itself.
   */
  offered: () => callMethod('oneapp.onemobility.offered', {}, { method: 'GET' }),

  /** Every mode, and which silhouette the map draws for it. Once per session. */
  markerStyles: () => callMethod('oneapp.onemobility.marker_styles', {}, { method: 'GET' }),

  /** Draw a mode as a different shape, for the whole workspace. */
  setMarkerStyle: (params) => callMethod('oneapp.onemobility.set_marker_style', params),

  /** Vehicles on one line that have caught each other. */
  bunching: (params) =>
    callMethod('oneapp.onemobility.bunching', params, { method: 'GET', silent: true }),

  /**
   * The four forward reads. Same aggregate tier as the charts above, asked
   * about a day that may not have happened — see `onemobility/forecast.py` for
   * why that is one lookup rather than a second subsystem.
   */

  /** A day, hour by hour, each hour with the spread it rests on. */
  outlook: (params) => callMethod('oneapp.onemobility.outlook', params, { method: 'GET' }),

  /** Every line's chance of running late at one hour, worst first. */
  risk: (params) => callMethod('oneapp.onemobility.risk', params, { method: 'GET' }),

  /** What today is doing that its own history does not. */
  unusual: (params) => callMethod('oneapp.onemobility.unusual', params, { method: 'GET' }),

  /** When a vehicle reaches one stop, as a range. */
  expect: (params) => callMethod('oneapp.onemobility.expect', params, { method: 'GET' }),

  /** How often the forecast's own range held. Off the record it wrote first. */
  accuracy: (params) => callMethod('oneapp.onemobility.accuracy', params, { method: 'GET' }),
}
