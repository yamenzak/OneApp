/**
 * Merged diary entries, as the grid wants them — and which calendars are on.
 *
 * The mapping is its own module rather than a computed in the page, because it
 * is the piece with rules worth testing on their own: what a whole-day entry
 * is, what an entry with no end is, and which of seven colours a source gets.
 *
 * The state below is here for a different reason: the grid and the rail beside
 * it are two components asking the same question — which calendars are there,
 * and which are switched on — and passing that through the shell's slot would
 * mean the shell knowing what a diary is.
 *
 * `oneapp_core/diary.py` is the other half.
 */
import { reactive } from 'vue'

/**
 * The colours a calendar entry may be, in the order sources take them.
 *
 * frappe-ui's own palette (`CalendarColorMap`), and the whole of it: an entry's
 * colour is what says which calendar it came from, so the list has to be a
 * fixed set that the sidebar can draw the same way. Red is deliberately absent
 * — the palette has no red, and pressing pink into service for one would make
 * every overdue thing look like a category.
 */
export const COLOURS = ['blue', 'green', 'violet', 'amber', 'cyan', 'orange', 'pink']

/** Which colour a source takes: its position, wrapping past seven. */
export const colourFor = (key, sources) => {
  const at = (sources || []).findIndex((one) => one.key === key)
  return COLOURS[(at < 0 ? 0 : at) % COLOURS.length]
}

/**
 * A day, and a time where there is one.
 *
 * Frappe writes a Date as `YYYY-MM-DD` and a Datetime as `YYYY-MM-DD HH:mm:ss`,
 * so the split is the space — no parsing, no timezone, no date library. A value
 * with no time is a whole day, which is what the fieldtype already said.
 */
export function split(value) {
  const said = String(value || '').trim()
  if (!said) return null
  const [date, time = ''] = said.split(' ')
  return { date, time: time.slice(0, 5) }
}

/** The source key an entry belongs to, matching what `_sources` returns. */
export const keyOf = (row) =>
  row?.kind === 'event' ? 'event' : `${row?.space}/${row?.screen}`

/** Merged rows, as `CalendarEvent`s. */
export function diaryEvents(rows, sources) {
  return (rows || [])
    .map((row) => {
      const from = split(row.start)
      if (!from) return null
      const to = split(row.end)
      return {
        id: row.id,
        title: row.title,
        // Which calendar it came from, said in the one place a grid event has
        // for it. The colour says the same thing without the words.
        venue: row.screen_label || '',
        fromDate: from.date,
        // No end is a moment on its own day, not a span running to whenever
        // the next thing happens to be.
        toDate: to?.date || from.date,
        fromTime: from.time || undefined,
        toTime: to?.time || from.time || undefined,
        isFullDay: !from.time,
        color: colourFor(keyOf(row), sources),
      }
    })
    .filter(Boolean)
}


/**
 * Which calendars there are, and which the reader has switched off.
 *
 * `off` and not `on`: a source added tomorrow — somebody declares a calendar
 * on another screen — should appear, and a list of what is *on* would silently
 * leave it out.
 */
export const diary = reactive({ sources: [], off: [] })

export const isOn = (key) => !diary.off.includes(key)

export function toggle(key) {
  diary.off = isOn(key) ? [...diary.off, key] : diary.off.filter((one) => one !== key)
}

/** The rows still showing, after the rail's switches. */
export const showing = (rows) => (rows || []).filter((row) => isOn(keyOf(row)))
