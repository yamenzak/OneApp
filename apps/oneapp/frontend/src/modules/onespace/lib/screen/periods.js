/**
 * The spans a dashboard can be narrowed to.
 *
 * A dashboard answers "how many, how much, which way is it going", and almost
 * every one of those questions has an unspoken "…lately" on the end. Asking it
 * through the ordinary Filter control means picking a field, picking an
 * operator, and typing two dates — three decisions to say "this quarter".
 *
 * So a screen names the date its dashboard is about and gets these. They are
 * **shortcuts that write an ordinary filter**, not a second kind of narrowing:
 * the filter shows up in the Filter control afterwards, where it can be read,
 * changed or taken off. That is the same thing the tally menu does with a
 * click, for the same reason.
 *
 * Computed in the reader's own days rather than through `toISOString`, which is
 * UTC — west of Greenwich that starts a month on the last day of the one
 * before, and a dashboard that quietly drops a day is worse than no control.
 */

import { __ } from '@/shared/lib/runtime/translate'

/** `YYYY-MM-DD` for a Date, in the reader's own day. */
export function stamp(when) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`
}

/** The last day of the month `when` is in. Day 0 of the next one. */
function endOfMonth(when) {
  return new Date(when.getFullYear(), when.getMonth() + 1, 0)
}

/**
 * Each period as the two days it runs between, or null for all of time.
 *
 * `to_date` is the *end* of the span rather than today, so "this year" keeps
 * counting a leave application booked for December — a dashboard clipped at
 * today would answer a different question from the calendar beside it.
 */
export const PERIODS = [
  {
    value: 'month',
    get label() { return __('This month') },
    span: (now) => [
      stamp(new Date(now.getFullYear(), now.getMonth(), 1)),
      stamp(endOfMonth(now)),
    ],
  },
  {
    value: 'quarter',
    get label() { return __('This quarter') },
    span: (now) => {
      const first = Math.floor(now.getMonth() / 3) * 3
      return [
        stamp(new Date(now.getFullYear(), first, 1)),
        stamp(endOfMonth(new Date(now.getFullYear(), first + 2, 1))),
      ]
    },
  },
  {
    value: 'year',
    get label() { return __('This year') },
    span: (now) => [
      stamp(new Date(now.getFullYear(), 0, 1)),
      stamp(new Date(now.getFullYear(), 11, 31)),
    ],
  },
  {
    value: 'rolling',
    get label() { return __('The last 12 months') },
    span: (now) => [
      stamp(new Date(now.getFullYear() - 1, now.getMonth(), now.getDate() + 1)),
      stamp(now),
    ],
  },
  {
    // The default, because it is the only one that cannot mislead: a dashboard
    // that opened on "this month" would answer a narrower question than the
    // screen's own list beside it, and nothing on it would say so. Last in the
    // list rather than first, because the four above it read as a sequence
    // from narrow to wide and this is the end of it.
    value: 'all',
    get label() { return __('All time') },
    span: () => null,
  },
]

export const DEFAULT_PERIOD = 'all'

/** The two days a period runs between, or null. */
export function spanOf(value, now = new Date()) {
  return (PERIODS.find((one) => one.value === value) || {}).span?.(now) ?? null
}
