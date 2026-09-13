/**
 * A record that lasts more than a day, as the days it covers.
 *
 * frappe-ui's Calendar places an event by its *start* and nothing else:
 * `Calendar.vue` sets `date = fromDate`, and both the month grid and the week
 * strip group by that — `toDate` reaches the event modal and no layout code at
 * all. So a leave application from Monday to Friday drew one chip on Monday and
 * left the rest of the week empty, which on a leave screen is not a cosmetic
 * loss: the month was wrong about who was in.
 *
 * The fix a grid like this can actually render is a chip a day. Clipped to the
 * window on screen, because a contract running to next December is three
 * hundred chips and the month showing twenty of them is the only month that
 * needs any.
 *
 * The sibling of `recurrence.js` and the same contract: `YYYY-MM-DD` strings in
 * and out, which a calendar compares without a timezone, and nothing is ever
 * written — one record with two dates stays one record.
 */

/**
 * A ceiling on how many days one record contributes to one window. Only ever
 * reached by a span nobody meant — a date typed as 2206 rather than 2026 — and
 * it is what stops that one row from being sixty thousand chips.
 */
export const MOST = 400

const asDate = (value) => {
  const said = String(value || '').trim().slice(0, 10)
  if (!/^\d{4}-\d{2}-\d{2}$/.test(said)) return null
  // Local midnight rather than `new Date(said)`, which parses a bare date as
  // UTC and lands on the previous day west of Greenwich.
  const [year, month, day] = said.split('-').map(Number)
  const made = new Date(year, month - 1, day)
  return Number.isNaN(made.getTime()) ? null : made
}

const asText = (date) => {
  const pad = (one) => String(one).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/**
 * How many days apart two dates are. Zero for a record with no end, for one
 * that ends on the day it starts, and for one whose end is *before* its start —
 * which is a record somebody typed wrong and not a reason to draw nothing.
 */
export function daysBetween(from, to) {
  const one = asDate(from)
  const other = asDate(to)
  if (!one || !other) return 0
  const apart = Math.round((other - one) / 86_400_000)
  return Number.isFinite(apart) && apart > 0 ? apart : 0
}

/**
 * The days a span covers, from `from` through `covers` days after it.
 *
 * `window` is `{since, until}` as the grid last reported it, and narrows the
 * answer to what is on screen. A span entirely outside it still gets its first
 * day: the row was fetched, it belongs to this screen, and a page of rows over
 * an empty month reads as a broken screen rather than as a span you have
 * scrolled past.
 */
export function daysCovered(from, covers = 0, window = {}) {
  const start = asDate(from)
  if (!start) return []
  if (!covers || covers < 0) return [asText(start)]

  const since = String(window?.since || '').slice(0, 10)
  const until = String(window?.until || '').slice(0, 10)

  const days = []
  const walking = new Date(start)
  for (let step = 0; step <= covers && days.length < MOST; step += 1) {
    const day = asText(walking)
    walking.setDate(walking.getDate() + 1)
    if (since && day < since) continue
    if (until && day > until) break
    days.push(day)
  }
  return days.length ? days : [asText(start)]
}

/** One day, `days` after `date`. Exported because the calendar shifts dates
 *  for its own reasons as well — an occurrence's end, for one. */
export function shiftDay(date, days) {
  const start = asDate(date)
  if (!start) return String(date || '')
  if (!days) return asText(start)
  start.setDate(start.getDate() + days)
  return asText(start)
}
