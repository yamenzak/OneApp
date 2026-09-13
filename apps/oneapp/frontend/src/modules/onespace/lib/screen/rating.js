/**
 * A Rating field, in the two units it exists in.
 *
 * Frappe stores a Rating as a **fraction of one** — four stars out of five is
 * `0.8` in the database — and frappe-ui's `Rating` counts **whole stars**,
 * `0..max`. The two were being handed to each other unconverted, which is
 * wrong in both directions and worse in one: reading, a four-star candidate
 * drew a single star, because 0.8 rounds to 1. Writing, clicking the fourth
 * star sent `4`, and Frappe stored a rating of four hundred per cent — a
 * number nothing clamps and every average is then wrong about.
 *
 * Its own module rather than a pair of functions in `cells.js` so it can be
 * tested: `cells.js` reaches the session for number formats, which reaches
 * frappe-ui's resource plugin, which does not load outside a browser.
 */

/** How many stars a Rating is drawn with. frappe-ui's own default. */
export const STARS = 5

/** A stored fraction, as whole stars. */
export function starsOf(value) {
  const said = Number(value) || 0
  return Math.round(Math.min(Math.max(said, 0), 1) * STARS)
}

/** Whole stars, as the fraction to store. */
export function ratingOf(stars) {
  const said = Number(stars) || 0
  return Math.min(Math.max(said, 0), STARS) / STARS
}
