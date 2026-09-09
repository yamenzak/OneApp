/**
 * The vehicle marker, drawn rather than fetched.
 *
 * MapLibre can only put an image on a symbol layer, and the style this screen
 * builds has no `glyphs` URL — so there is no text layer available, and a
 * marker has to *be* a picture. Rather than ship a sprite sheet and a build
 * step to keep it in step with the theme, they are drawn on a canvas at load:
 * one per mode per occupancy band, in that band's own colour, at the device's
 * pixel ratio.
 *
 * Drawing them also means they can take a colour at runtime, which a PNG
 * cannot. The fill is the occupancy band and the outline is the map's own
 * surface, so the same marker is legible on a light basemap and a dark one and
 * over a route line of its own colour — none of which survives contact with a
 * fixed-colour image.
 *
 * **Top view, and that is forced rather than chosen.** The symbol layer rotates
 * each marker to the vehicle's bearing with `icon-rotation-alignment: 'map'`,
 * because a marker that does not say which way the thing is facing is half a
 * marker. A side elevation turned ninety degrees is a bus lying on its side. So
 * every shape here is drawn as if from above, pointing north, symmetric about
 * the vertical, and the layer turns it.
 *
 * Each part is doing a job: a soft drop shadow so a vehicle sits *above* the
 * route rather than on it, a surface-coloured casing so it stays legible
 * crossing a line of its own colour, the body carrying the occupancy, and a
 * windscreen band at the front so the nose reads as a nose at sixteen pixels.
 */

import { __ } from '@/shared/lib/runtime/translate'

/** Points across, before the pixel ratio. Big enough for a bus to read as one. */
const SIZE = 40

/**
 * The silhouettes, in a unit box: x and y from -0.5 to 0.5, nose towards -y.
 *
 * A shape per mode rather than one shape with a badge on it, because the thing
 * a person is picking out of forty moving markers is the outline. A tram and a
 * bus differ in the only two ways that survive being small — how long they are
 * and how square the front is — and those are exactly what these encode.
 *
 * `joint` draws the articulation line across an articulated vehicle; `bow`
 * says the front is a point rather than a face, which changes where the
 * windscreen goes.
 */
const BODIES = {
  // Short, wide, square-cornered, flat-fronted. A city bus from above is very
  // nearly a rounded rectangle and pretending otherwise helps nobody.
  bus: { width: 0.50, length: 0.66, round: 0.09, taper: 0.10, joints: [] },
  // Longer and narrower, and articulated once — which is the thing that tells
  // a tram from a bus when both are sixteen pixels tall.
  tram: { width: 0.40, length: 0.86, round: 0.07, taper: 0.07, joints: [0.5] },
  // Longer again, jointed twice, and the front is rounded off rather than cut.
  metro: { width: 0.40, length: 0.94, round: 0.19, taper: 0.20, joints: [0.36, 0.68] },
  // The longest, and the only one with a nose that comes to a point.
  rail: { width: 0.36, length: 1.00, round: 0.07, taper: 0.34, nose: 0.30, joints: [0.62] },
  // A hull: pointed bow, blunt stern, wide in the middle.
  ferry: { width: 0.50, length: 0.82, round: 0.06, taper: 0.46, nose: 0, joints: [] },
  // A cabin hanging from a wire. Nearly square from above, and the cross-arm
  // above it is what says it is not a small bus.
  cable: { width: 0.44, length: 0.46, round: 0.10, taper: 0.06, arm: true, joints: [] },
  // Anything a feed calls something we have no drawing for. A plain capsule:
  // unmistakably a vehicle, and unmistakably not a claim about which kind.
  other: { width: 0.42, length: 0.60, round: 0.20, taper: 0.12, joints: [] },
}

/** Which drawing a mode gets. Unknown modes fall to the capsule, never to nothing. */
export function bodyFor(mode) {
  const key = String(mode || '').trim().toLowerCase()
  return BODIES[key] ? key : 'other'
}

/** Every drawing there is, so the caller can register one image per mode. */
export const MODES = Object.keys(BODIES)

/**
 * The outline, as points in the unit box.
 *
 * Built rather than hand-listed per mode so that the six shapes cannot drift
 * apart in the details that are meant to be shared — every one of them is the
 * same rounded body with a different length, width and front.
 */
function outline(body) {
  const halfWidth = body.width / 2
  const halfLength = body.length / 2
  const front = -halfLength
  const back = halfLength
  const taper = body.length * body.taper
  // How wide the front edge is, as a share of the body. `0` is a point — a
  // bow or a streamlined nose — and anything larger is a face.
  const tip = body.nose === undefined ? 0.72 : body.nose

  if (tip <= 0) {
    return [
      [-halfWidth, back],
      [-halfWidth, front + taper],
      [0, front],
      [halfWidth, front + taper],
      [halfWidth, back],
    ]
  }
  return [
    [-halfWidth, back],
    [-halfWidth, front + taper],
    [-halfWidth * tip, front],
    [halfWidth * tip, front],
    [halfWidth, front + taper],
    [halfWidth, back],
  ]
}

/**
 * A closed path through `points` with the corners rounded off.
 *
 * Arc-to rather than quadratics: it takes the radius directly and clamps itself
 * to whatever the two edges can afford, so a short vehicle with a generous
 * radius comes out as a capsule instead of turning inside out.
 */
function trace(context, points, radius, scale, middle) {
  const at = (one) => [middle + one[0] * scale, middle + one[1] * scale]
  const shaped = points.map(at)

  // Clamped to half the shortest edge. `arcTo` given a radius two edges cannot
  // accommodate does not clamp itself — it draws an arc outside the corner,
  // and a short body with a generous radius comes out as a spiked blob. That
  // is what the cable car and the fallback capsule looked like before this.
  let shortest = Infinity
  for (let index = 0; index < shaped.length; index += 1) {
    const one = shaped[index]
    const next = shaped[(index + 1) % shaped.length]
    shortest = Math.min(shortest, Math.hypot(next[0] - one[0], next[1] - one[1]))
  }
  const round = Math.min(radius * scale, shortest / 2)

  context.beginPath()
  const [firstX, firstY] = shaped[0]
  const [lastX, lastY] = shaped[shaped.length - 1]
  context.moveTo((firstX + lastX) / 2, (firstY + lastY) / 2)
  for (let index = 0; index < shaped.length; index += 1) {
    const corner = shaped[index]
    const next = shaped[(index + 1) % shaped.length]
    context.arcTo(corner[0], corner[1], next[0], next[1], round)
  }
  context.closePath()
}

/**
 * One marker, as an `addImage` payload.
 *
 * @param {string} mode  Bus, Tram, Metro, Rail, Ferry, Cable — anything else
 *   draws the capsule.
 * @param {string} fill  the body colour, already resolved to something a canvas
 *   can paint — the tokens are `oklch()` and a canvas will take those, but the
 *   caller has usually normalised them for MapLibre already.
 * @param {string} ring  the surface colour to outline it with
 * @param {number} ratio device pixels per CSS pixel
 */
export function vehicleMarker(mode, fill, ring, ratio = 2, hairline = true) {
  const size = Math.round(SIZE * ratio)
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const context = canvas.getContext('2d')

  const body = BODIES[bodyFor(mode)]
  const middle = size / 2
  // The unit box maps to rather less than the bitmap, so the shadow and the
  // casing both have room to fall inside it. A marker whose shadow is clipped
  // by its own edge reads as a square, which is worse than no shadow.
  const scale = size * 0.80
  const points = outline(body)

  // The casing: the same silhouette, stroked fat and filled, so the outline is
  // one shape with the body rather than a line drawn near it.
  context.save()
  context.shadowColor = 'rgba(15, 23, 42, 0.38)'
  context.shadowBlur = size * 0.09
  context.shadowOffsetY = size * 0.025
  if (body.arm) {
    // The hanger, under everything: a bar across the direction of travel, which
    // is the one thing that says this hangs from a wire.
    context.beginPath()
    context.lineWidth = size * 0.055
    context.strokeStyle = ring
    context.lineCap = 'round'
    context.moveTo(middle - scale * 0.30, middle - scale * 0.30)
    context.lineTo(middle + scale * 0.30, middle - scale * 0.30)
    context.stroke()
  }
  trace(context, points, body.round, scale, middle)
  context.fillStyle = ring
  context.lineJoin = 'round'
  context.lineWidth = size * 0.10
  context.strokeStyle = ring
  context.stroke()
  context.fill()
  context.restore()

  // The body.
  trace(context, points, body.round, scale, middle)
  context.fillStyle = fill
  context.fill()

  // Everything below is drawn inside the body, so it is clipped to it and a
  // detail can be laid out without checking whether it fits.
  context.save()
  trace(context, points, body.round, scale, middle)
  context.clip()

  // The windscreen. Dark rather than the casing colour: the casing is the map's
  // surface, which on a light basemap is white, and white glass on a pale green
  // body is nothing at all. A dark translucent band reads on every one of the
  // five occupancy colours, which is the only requirement it has.
  const halfLength = (body.length / 2) * scale
  const front = middle - halfLength
  const glassTop = front + scale * (body.nose === 0 ? body.taper * body.length * 0.75 : 0.045)
  context.fillStyle = 'rgba(15, 23, 42, 0.30)'
  context.fillRect(middle - scale, glassTop, scale * 2, scale * 0.085)

  // The joints. Where a vehicle bends, drawn as a gap in the roof rather than
  // a line on it: a dark hairline with a light one under it reads as a seam,
  // and one line on its own reads as a scratch in the drawing.
  for (const joint of body.joints) {
    const where = front + halfLength * 2 * joint
    context.fillStyle = 'rgba(15, 23, 42, 0.26)'
    context.fillRect(middle - scale, where, scale * 2, Math.max(1, size * 0.016))
    context.fillStyle = 'rgba(255, 255, 255, 0.30)'
    context.fillRect(middle - scale, where + Math.max(1, size * 0.016), scale * 2,
                     Math.max(1, size * 0.012))
  }

  // A highlight down one side, and it is deliberately slight. A gradient strong
  // enough to see as shading is strong enough to move the body off its
  // occupancy colour, and the colour is the thing this marker is for.
  const light = context.createLinearGradient(
    middle - (body.width / 2) * scale, 0, middle + (body.width / 2) * scale, 0,
  )
  light.addColorStop(0, 'rgba(255, 255, 255, 0.22)')
  light.addColorStop(0.5, 'rgba(255, 255, 255, 0)')
  light.addColorStop(1, 'rgba(0, 0, 0, 0.12)')
  context.fillStyle = light
  context.fillRect(middle - scale, middle - scale, scale * 2, scale * 2)
  context.restore()

  // A hairline around the body, inside the casing. Without it a pale vehicle on
  // a white casing on a light basemap is three shades of nearly-white and the
  // shape stops having an edge.
  if (hairline) {
    trace(context, points, body.round, scale, middle)
    context.lineWidth = Math.max(1, size * 0.022)
    context.strokeStyle = 'rgba(15, 23, 42, 0.22)'
    context.stroke()
  }

  // `{width, height, data}` and nothing else: the pixel ratio is style-image
  // metadata and goes in `addImage`'s third argument, not in here.
  return { width: size, height: size, data: context.getImageData(0, 0, size, size).data }
}

/**
 * The bearing from one position to another, in compass degrees.
 *
 * Equirectangular rather than the great-circle formula: between two pings
 * thirty seconds apart the difference is far below what a rotated icon can
 * show, and this is three operations rather than a dozen on every vehicle on
 * every frame.
 */
export function bearingBetween(from, to) {
  if (!from || !to) return 0
  const [lon1, lat1] = from
  const [lon2, lat2] = to
  const x = (lon2 - lon1) * Math.cos(((lat1 + lat2) / 2) * (Math.PI / 180))
  const y = lat2 - lat1
  if (!x && !y) return 0
  return (Math.atan2(x, y) * 180) / Math.PI
}

/**
 * A bearing that does not spin the long way round.
 *
 * Two headings either side of north are 359° and 1°, and easing between those
 * numbers turns the marker through the entire compass. Taking the shorter of
 * the two arcs is what keeps a vehicle rounding a corner looking like it
 * rounded a corner.
 */
export function easeBearing(from, to, k = 0.25) {
  if (!Number.isFinite(from)) return to
  let difference = ((to - from + 540) % 360) - 180
  return from + difference * k
}

/**
 * What each silhouette is called, in the order a legend should read them.
 *
 * Named after what the drawing *is*, not after the mode it usually belongs to —
 * a workspace can draw its Rail as a tram, and a key that then said "Train"
 * beside a tram outline would be explaining the wrong thing.
 */
export const SHAPE_NAMES = {
  bus: () => __('Bus'),
  tram: () => __('Tram'),
  metro: () => __('Metro'),
  rail: () => __('Train'),
  ferry: () => __('Ferry'),
  cable: () => __('Cable car'),
  other: () => __('Something else'),
}

/**
 * One silhouette as a `data:` URL, for a legend row or a picker button.
 *
 * The same `vehicleMarker` the map registers rather than a second drawing, so
 * a key cannot come to disagree with the thing it explains — which is what
 * happens the first time a shape changes and only one of the two is updated.
 */
export function swatchUrl(shape, fill, ring, ratio = 2) {
  const image = vehicleMarker(shape, fill, ring, ratio)
  const pad = document.createElement('canvas')
  pad.width = image.width
  pad.height = image.height
  pad.getContext('2d').putImageData(new ImageData(image.data, image.width, image.height), 0, 0)
  return pad.toDataURL()
}
