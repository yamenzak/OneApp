/**
 * The vehicle marker, drawn rather than fetched.
 *
 * MapLibre can only put an image on a symbol layer, and the style this screen
 * builds has no `glyphs` URL — so there is no text layer available, and a
 * marker has to *be* a picture. Rather than ship five PNGs and a build step to
 * keep them in step with the theme, they are drawn on a canvas at load: one per
 * occupancy band, in that band's own colour, at the device's pixel ratio.
 *
 * The shape is the one every live-transit map converges on, and each part of it
 * is doing a job: a soft drop shadow so a vehicle sits *above* the route rather
 * than on it, a surface-coloured ring so it stays legible crossing a line of
 * its own colour, a filled disc carrying the occupancy, and a nose so the
 * marker says which way the thing is facing. Drawn pointing north and rotated
 * to the bearing by the layer, which is why the nose is symmetrical about the
 * vertical.
 */

/** Points across, before the pixel ratio. Big enough for the nose to read. */
const SIZE = 34

/**
 * One marker, as an `addImage` payload.
 *
 * @param {string} fill the disc colour, already resolved to something a canvas
 *   can paint — the tokens are `oklch()` and a canvas will take those, but the
 *   caller has usually normalised them for MapLibre already.
 * @param {string} ring the surface colour to outline it with
 * @param {number} ratio device pixels per CSS pixel
 */
export function vehicleMarker(fill, ring, ratio = 2) {
  const size = Math.round(SIZE * ratio)
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const context = canvas.getContext('2d')

  const middle = size / 2
  // Room for the shadow to fall inside the bitmap. A marker whose shadow is
  // clipped by its own edge reads as a square, which is worse than no shadow.
  const radius = size * 0.28
  const nose = size * 0.46

  context.save()
  context.shadowColor = 'rgba(15, 23, 42, 0.35)'
  context.shadowBlur = size * 0.10
  context.shadowOffsetY = size * 0.03

  // The nose first and underneath, so the disc's ring closes over its base and
  // the two read as one shape rather than a circle with a triangle stuck on.
  context.beginPath()
  context.moveTo(middle, middle - nose)
  context.lineTo(middle + radius * 0.78, middle - radius * 0.10)
  context.lineTo(middle - radius * 0.78, middle - radius * 0.10)
  context.closePath()
  context.fillStyle = ring
  context.fill()

  context.beginPath()
  context.arc(middle, middle, radius, 0, Math.PI * 2)
  context.fillStyle = ring
  context.fill()
  context.restore()

  // The coloured body, inset far enough that the ring survives at every zoom.
  const inset = size * 0.055
  context.beginPath()
  context.moveTo(middle, middle - nose + inset * 1.9)
  context.lineTo(middle + (radius - inset) * 0.74, middle - radius * 0.10)
  context.lineTo(middle - (radius - inset) * 0.74, middle - radius * 0.10)
  context.closePath()
  context.fillStyle = fill
  context.fill()

  context.beginPath()
  context.arc(middle, middle, radius - inset, 0, Math.PI * 2)
  context.fillStyle = fill
  context.fill()

  // A highlight along the top of the disc. One line, and it is the difference
  // between a flat dot and something that looks lit.
  context.beginPath()
  context.arc(middle, middle, radius - inset, Math.PI * 1.15, Math.PI * 1.85)
  context.lineWidth = Math.max(1, size * 0.03)
  context.strokeStyle = 'rgba(255, 255, 255, 0.45)'
  context.stroke()

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
