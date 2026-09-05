<template>
  <!--
    The calendar: the same rows, on a grid of days.

    A calendar is not a different list — same filters, same order, same screen
    above it — but it is the one body that does not read a *page*. A month
    drawn from whichever hundred rows sorted first is a month with holes in it,
    and the holes move as you page. So the visible range is the request: the
    calendar says which days it is showing and the shell fetches those.

    The grid itself is frappe-ui's, from `frappe-ui/experimental` — month, week
    and day, with the event spans and the popover already in it. The part that
    is ours is the mapping: which field is the start, which is the end, and
    what a row is called.
  -->
  <div class="min-h-0 flex-1 overflow-auto p-3" data-slot="calendar">
    <EmptyState
      v-if="!field"
      icon="lucide-calendar"
      title="No date to draw"
      description="This screen offers a calendar but names no date field for it."
    />
    <Calendar
      v-else
      :events="events"
      :config="CONFIG"
      :on-click="({ calendarEvent }) => open(calendarEvent)"
      @range-change="moved"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Calendar } from '@/ui'
import EmptyState from '../../EmptyState.vue'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The records in the range on screen, fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /**
   * Which fields the dates are, as the last page came back for them. The shell
   * owns this for the same reason it owns the board's column field: it owns
   * the request, and a calendar drawn from the spec while rows arrive for
   * another pair is a month of nothing.
   */
  calendar: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['open', 'range'])

/**
 * Read-only, deliberately.
 *
 * The grid can drag, resize and create, and every one of those writes a field
 * on a record — which is a thing this screen already does properly, through
 * the record dialog, with the doctype's own rules and permissions in front of
 * it. Turning it on here would be a second way to write that has none of them.
 * Clicking an event opens the record instead; the second half of this is a
 * separate piece of work with `@change` behind it, the way the board's drag is.
 */
const CONFIG = { isEditMode: false, defaultMode: 'Month' }

const field = computed(() => props.calendar?.start_field || '')
const endField = computed(() => props.calendar?.end_field || '')

/** What a record is called, from the doctype's own title field. */
const titleOf = (row) => {
  const title = props.spec?.title_field
  return String((title && row[title]) || row.name || '')
}

/**
 * A day, and a time where there is one.
 *
 * Frappe writes a Date as `YYYY-MM-DD` and a Datetime as `YYYY-MM-DD HH:mm:ss`,
 * so the split is the space — no parsing, no timezone, no date library. A value
 * with no time is a whole day, which is what the fieldtype already said.
 */
const split = (value) => {
  const said = String(value || '').trim()
  if (!said) return null
  const [date, time = ''] = said.split(' ')
  return { date, time: time.slice(0, 5) }
}

const events = computed(() => {
  if (!field.value) return []
  return props.rows
    .map((row) => {
      const from = split(row[field.value])
      if (!from) return null
      const to = endField.value ? split(row[endField.value]) : null
      return {
        id: row.name,
        title: titleOf(row),
        fromDate: from.date,
        // A record with no end is a moment on its own day rather than a span
        // running to whenever the next one happens to be.
        toDate: to?.date || from.date,
        fromTime: from.time || undefined,
        toTime: to?.time || from.time || undefined,
        isFullDay: !from.time,
      }
    })
    .filter(Boolean)
})

const open = (event) => {
  const row = props.rows.find((one) => one.name === event?.id)
  if (row) emit('open', row)
}

/**
 * The days now on screen.
 *
 * `rangeChange` fires on mount as well as on every move, which is what makes
 * this the only fetch the calendar needs: the shell has no opinion about which
 * month you are in until the grid says.
 */
const moved = ({ startDate, endDate }) => {
  if (startDate && endDate) emit('range', { since: startDate, until: endDate })
}
</script>
