/**
 * What can be drawn over the network, declared once.
 *
 * The map, the panel that switches between them and the key that explains the
 * chosen one all read this table. Three places that have to agree about what a
 * layer is called, what it is measured in and what colour means what — and
 * three places is exactly enough for them to stop agreeing, which is how a map
 * comes to have a legend describing the layer before last.
 *
 * Two shapes of overlay, because the data has two shapes:
 *
 *   surface  a measure averaged into a grid of places, off `observation` —
 *            drawn as tiles under the routes, because it is the ground the
 *            network runs over
 *   points   a measure per stop, off `stopHour` — drawn as circles over the
 *            routes, because it happens *at* something
 */

import { __ } from '@/shared/lib/runtime/translate'
import { delayInk, divergingRamp, occupancyInk, OCCUPANCY } from './palette'

export const OVERLAYS = [
  {
    key: 'none',
    icon: 'lucide-map',
    label: () => __('Just the network'),
    kind: 'none',
  },
  {
    key: 'delay',
    icon: 'lucide-timer',
    label: () => __('Where it runs late'),
    hint: () => __('Average minutes behind the timetable, per place'),
    kind: 'surface',
    // Diverging, because lateness has a real zero: early is a different failure
    // from late and the middle of this ramp is the timetable itself.
    ramp: () => {
      const spread = divergingRamp()
      return [spread[0], spread[2], spread[4], spread[6], spread[8]]
    },
    unit: () => __('min'),
  },
  {
    key: 'occupancy',
    icon: 'lucide-users',
    label: () => __('Where it fills up'),
    hint: () => __('Average percent of capacity, per place'),
    kind: 'surface',
    // The *same five colours the vehicles wear*. A reader who has learnt that
    // orange means standing on a marker should not have to learn a second
    // scale to read the ground underneath it.
    ramp: () => OCCUPANCY.filter((one) => one.floor >= 0).map((one) => occupancyInk(one.floor)),
    unit: () => __('%'),
  },
  {
    key: 'busy',
    icon: 'lucide-circle-dot',
    label: () => __('Where the service goes'),
    hint: () => __('Vehicle visits, worked out from positions'),
    kind: 'points',
    field: 'visits',
    // One hue, sized by the count. A quantity at a place is a magnitude, and a
    // magnitude wants area rather than hue — the colour here is identity, not
    // a second scale.
    ink: () => occupancyInk(20),
    unit: () => __('visits'),
  },
  {
    key: 'bunching',
    icon: 'lucide-git-commit-vertical',
    label: () => __('Where the wait bunches'),
    hint: () => __('Extra minutes over the timetable, on the worst wait in six'),
    kind: 'points',
    field: 'bunching',
    ink: () => delayInk(300),
    unit: () => __('min'),
  },
]

export function overlayFor(key) {
  return OVERLAYS.find((one) => one.key === key) || OVERLAYS[0]
}

/**
 * A MapLibre `interpolate` expression across a ramp, from `low` to `high`.
 *
 * Built here rather than at the call site so both surfaces step the same way,
 * and so the key can walk the same stops to draw its own swatches.
 */
export function rampStops(ramp, low, high) {
  const span = high - low || 1
  return ramp.flatMap((ink, at) => [low + (span * at) / (ramp.length - 1), ink])
}
