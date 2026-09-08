/**
 * Merged diary entries, as the grid wants them — and which calendars are on.
 *
 * The mapping is its own module because it is the piece with rules worth
 * testing on their own. The state below is here for a different reason: the
 * grid and the rail beside it are two components asking the same question, and
 * passing it through the shell's slot would mean the shell knowing what a diary
 * is. `onecalendar/diary.py` is the other half.
 */
import { reactive } from 'vue'

/**
 * The colours a calendar entry may be, in the order sources take them —
 * frappe-ui's own palette, and the whole of it. Red is deliberately absent: the
 * palette has no red, and pressing pink into service would make every overdue
 * thing look like a category.
 */
export const COLOURS = ['blue', 'green', 'violet', 'amber', 'cyan', 'orange', 'pink']

/** Which colour a source takes: its position, wrapping past seven. */
export const colourFor = (key, sources) => {
  const at = (sources || []).findIndex((one) => one.key === key)
  return COLOURS[(at < 0 ? 0 : at) % COLOURS.length]
}

/**
 * A day, and a time where there is one. Frappe writes a Date as `YYYY-MM-DD`
 * and a Datetime as `YYYY-MM-DD HH:mm:ss`, so the split is the space.
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
        // for it.
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
 * Which calendars there are, and which the reader has switched off. `off` and
 * not `on`: a source added tomorrow should appear, and a list of what is *on*
 * would silently leave it out.
 */
export const diary = reactive({ sources: [], off: [] })

export const isOn = (key) => !diary.off.includes(key)

export function toggle(key) {
  diary.off = isOn(key) ? [...diary.off, key] : diary.off.filter((one) => one !== key)
}

/** The rows still showing, after the rail's switches. */
export const showing = (rows) => (rows || []).filter((row) => isOn(keyOf(row)))
