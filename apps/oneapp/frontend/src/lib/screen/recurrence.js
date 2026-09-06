/**
 * A record that happens again, as the days it happens on.
 *
 * Frappe's own Event carries `repeat_on` beside a `repeat_till`, and that is
 * the model a screen names two fields for. Nothing here writes anything: one
 * record with a rule stays one record, and the occurrences exist only for as
 * long as a month is on screen — which is what makes "delete the series"
 * possible at all.
 *
 * Deliberately not an RRULE engine: four intervals is what Frappe's own Event
 * offers, and it is what the fixture, the screens and the desk agree on.
 *
 * Dates are `YYYY-MM-DD` strings in and out, which a calendar can compare
 * without a timezone.
 */

/** The intervals, as Frappe's Event spells them. */
export const EVERY = ['daily', 'weekly', 'monthly', 'yearly']

/**
 * A ceiling on how many occurrences one record contributes to one window: a
 * daily rule with no end over a year view is three hundred and sixty-five
 * entries for one record. Only ever reached by a rule somebody wrote wrong.
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

const step = (date, every, times) => {
  const next = new Date(date)
  if (every === 'daily') next.setDate(next.getDate() + times)
  else if (every === 'weekly') next.setDate(next.getDate() + times * 7)
  else if (every === 'monthly') next.setMonth(next.getMonth() + times)
  else next.setFullYear(next.getFullYear() + times)
  return next
}

/**
 * The days this record falls on inside `[since, until]`.
 *
 * The first is always the record's own date, whether or not it is in the
 * window: a rule that hid the original would be a rule that moved it. `until`
 * on the rule ends the series, the window ends the drawing, and both are
 * inclusive.
 */
export function occurrencesOf(from, every, ends, window = {}) {
  const start = asDate(from)
  if (!start) return []

  const rule = String(every || '').trim().toLowerCase()
  if (!EVERY.includes(rule)) return [asText(start)]

  const last = asDate(window.until)
  const first = asDate(window.since)
  // No window is no repeat: a caller without one is asking what the record
  // itself says, which is one day.
  if (!last) return [asText(start)]

  const stops = asDate(ends)
  const found = []
  for (let at = 0; at < MOST; at += 1) {
    const on = step(start, rule, at)
    if (on > last) break
    if (stops && on > stops) break
    // Everything before the window is skipped rather than stopping the walk: a
    // weekly meeting that began in 2019 is fifty occurrences before the month
    // on screen.
    if (!first || on >= first || at === 0) found.push(asText(on))
  }
  return found.length ? found : [asText(start)]
}
