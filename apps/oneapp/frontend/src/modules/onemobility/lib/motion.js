/**
 * Moving a vehicle between the moments a feed reports one.
 *
 * A feed reports every fifteen to thirty seconds. A marker that jumps every
 * twenty seconds reads as broken, so between reports the vehicle is moved
 * along **its own line's shape** rather than in a straight line — a bus follows
 * the road, and a straight line between two reports around a corner puts it
 * through a building.
 *
 * Three steps, and each is plain geometry:
 *
 *   project   the reported position onto the shape, because raw GPS lands in
 *             gardens and on roofs and the vehicle is on its route
 *   advance   interpolate *along* the shape between the last two reports
 *   ease      approach the truth over about a second when a new report lands,
 *             rather than teleporting — a marker that jumps looks wrong even
 *             when it has just become more correct
 *
 * Pure and unit-tested. `motion.test.js` holds it to a corner, a doubled point,
 * a shape of one vertex and a vehicle that has not moved.
 */

/** Squared planar distance. Fine at city scale, and three operations. */
function near(ax, ay, bx, by) {
  const dx = ax - bx
  const dy = ay - by
  return dx * dx + dy * dy
}

/**
 * Cumulative distance to each vertex, so a position along the line is a
 * lookup rather than a walk. Computed once per shape and cached by the caller.
 */
export function measure(points) {
  const along = [0]
  for (let at = 1; at < points.length; at += 1) {
    along.push(along[at - 1] + Math.hypot(
      points[at][0] - points[at - 1][0],
      points[at][1] - points[at - 1][1],
    ))
  }
  return along
}

/**
 * The nearest point on the shape to a reported position, as a distance along
 * it. This is the map-matching step, and it is what stops a vehicle sitting in
 * the river when the GPS is having a moment.
 */
export function project(points, along, lon, lat) {
  if (!points || points.length < 2) return 0

  let best = 0
  let bestGap = Infinity
  for (let at = 0; at < points.length - 1; at += 1) {
    const [x0, y0] = points[at]
    const [x1, y1] = points[at + 1]
    const dx = x1 - x0
    const dy = y1 - y0
    const span = dx * dx + dy * dy
    // A doubled vertex is common in real feeds and would divide by zero.
    const t = span ? Math.max(0, Math.min(1, ((lon - x0) * dx + (lat - y0) * dy) / span)) : 0
    const gap = near(lon, lat, x0 + dx * t, y0 + dy * t)
    if (gap < bestGap) {
      bestGap = gap
      best = along[at] + Math.sqrt(span) * t
    }
  }
  return best
}

/** The point a given distance along the shape. The inverse of `project`. */
export function at(points, along, distance) {
  if (!points || !points.length) return null
  if (points.length === 1) return points[0]

  const total = along[along.length - 1]
  const want = Math.max(0, Math.min(total, distance))
  for (let index = 1; index < along.length; index += 1) {
    if (want > along[index]) continue
    const span = along[index] - along[index - 1]
    const t = span ? (want - along[index - 1]) / span : 0
    const [x0, y0] = points[index - 1]
    const [x1, y1] = points[index]
    return [x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]
  }
  return points[points.length - 1]
}

/**
 * Where a vehicle is now, given its last two reports and the clock.
 *
 * `k` is how far past the newer report we are, as a fraction of the gap
 * between the two. Below 1 it is interpolation; above 1 it is extrapolation —
 * the vehicle is assumed to keep going at the speed it was — and it is capped,
 * because a vehicle that stopped reporting has not necessarily kept driving
 * and drawing it a kilometre further on is a lie the map tells confidently.
 */
export const MAX_EXTRAPOLATION = 1.5

export function between(shape, previous, latest, k) {
  if (!latest) return null
  if (!shape || shape.points.length < 2 || !previous) {
    return [latest.lon, latest.lat]
  }

  const from = project(shape.points, shape.along, previous.lon, previous.lat)
  const to = project(shape.points, shape.along, latest.lon, latest.lat)
  const capped = Math.max(0, Math.min(MAX_EXTRAPOLATION, k))
  return at(shape.points, shape.along, from + (to - from) * capped)
}

/**
 * Ease rather than snap. A cubic ease-out: fast at first, settling — which is
 * how a correction reads as a correction rather than as a glitch.
 */
export function ease(t) {
  const clamped = Math.max(0, Math.min(1, t))
  return 1 - (1 - clamped) ** 3
}

/** Two positions, blended. Used to walk the drawn marker onto the true one. */
export function blend(from, to, t) {
  if (!from) return to
  if (!to) return from
  const k = ease(t)
  return [from[0] + (to[0] - from[0]) * k, from[1] + (to[1] - from[1]) * k]
}

/**
 * A shape, prepared once. Held by the screen per line rather than recomputed
 * every frame: `measure` is O(n) and a frame is sixty times a second.
 */
export function prepare(geometry) {
  const points = geometry?.coordinates
  if (!Array.isArray(points) || points.length < 2) return null
  return { points, along: measure(points) }
}
