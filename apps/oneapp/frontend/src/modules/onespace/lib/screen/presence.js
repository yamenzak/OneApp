/**
 * What a state of presence looks like, and what it is called.
 *
 * The words and the ranking are the server's — `oneapp/onehr/presence.py` — so
 * this is only the drawing: a colour, a glyph and a dot. Kept out of the
 * component because a second surface will want the same pill beside a name in a
 * list, and the day it does the vocabulary should not have to be agreed again.
 */

import { time } from '@/shared/lib/runtime/format'
import { __ } from '@/shared/lib/runtime/translate'

/**
 * Colour by what the reader should *do* about it, not by sentiment.
 *
 * Green for here, amber for here-but-something-to-know, blue for a planned
 * absence, grey for a day nobody works, red for an unplanned absence. On leave
 * is deliberately not red: it was approved, and a manager scanning a team for
 * problems should not have their eye pulled to the one person whose absence is
 * the only one that was agreed in advance.
 */
export const PRESENCE = {
  in: { theme: 'green', icon: 'lucide-circle-check', get label() { return __('In') } },
  late: { theme: 'amber', icon: 'lucide-clock-alert', get label() { return __('In, late') } },
  out: { theme: 'gray', icon: 'lucide-log-out', get label() { return __('Checked out') } },
  leave: { theme: 'blue', icon: 'lucide-palmtree', get label() { return __('On leave') } },
  holiday: { theme: 'gray', icon: 'lucide-calendar-off', get label() { return __('Holiday') } },
  absent: { theme: 'red', icon: 'lucide-circle-x', get label() { return __('Absent') } },
  unknown: { theme: 'gray', icon: 'lucide-circle-help', get label() { return __('Not known') } },
}

/**
 * Which entry draws this answer.
 *
 * `late` is a property of an `in` on the server and an entry of its own here,
 * which is the right split: the server should not have a sixth state that means
 * the same as one of the five, and the page should not have to say "green,
 * unless" in two places.
 */
export function presenceLook(found) {
  if (!found?.state) return PRESENCE.unknown
  if (found.state === 'in' && found.late) return PRESENCE.late
  return PRESENCE[found.state] || PRESENCE.unknown
}

/**
 * A time of day, where there is one. `since` is a stamp, not a duration.
 *
 * Through `lib/runtime/format`, which reads the workspace's own time format —
 * the browser's answer follows the reader's language, which nobody configured,
 * so two colleagues would see the same arrival written two ways.
 *
 * To the minute. The workspace's format carries seconds because a log wants
 * them; "In · 09:41:07" reads as a timestamp where "In · 09:41" reads as a
 * fact about somebody's morning.
 */
export function presenceSince(found) {
  return found?.since ? time(found.since, { toTheMinute: true }) : ''
}

/**
 * How a day in the strip is drawn.
 *
 * A token per state rather than a scale, because these are not degrees of one
 * thing: a holiday is not a worse present. `none` is the gap — a day with no
 * record, which is not the same as an absence and must not look like one.
 */
export const DAY_LOOK = {
  present: { class: 'bg-surface-green-3', get label() { return __('Present') } },
  half: { class: 'bg-surface-amber-3', get label() { return __('Half day') } },
  leave: { class: 'bg-surface-blue-3', get label() { return __('On leave') } },
  // A weekend has to be visibly *not* a working day and visibly not an
  // absence either. Darker than the gap and lighter than anything that means
  // something went wrong, which is the whole job of this square.
  holiday: { class: 'bg-surface-gray-4', get label() { return __('Holiday') } },
  absent: { class: 'bg-surface-red-3', get label() { return __('Absent') } },
  none: { class: 'bg-surface-gray-2', get label() { return __('No record') } },
}

export function dayLook(state) {
  return DAY_LOOK[state] || DAY_LOOK.none
}
