<template>
  <!--
    The calendar: the same rows, on a grid of days.

    The one body that does not read a *page*. A month drawn from whichever
    hundred rows sorted first is a month with holes in it, and the holes move as
    you page — so the visible range is the request.

    The grid is frappe-ui's, from `frappe-ui/experimental`. Ours is the mapping:
    which field is the start, which is the end, and what a row is called.
  -->
  <div class="min-h-0 flex-1 overflow-auto p-3" data-slot="calendar">
    <EmptyState
      v-if="!field"
      icon="lucide-calendar"
      :title="__('No date to draw')"
      :description="__('This screen shows a calendar, but no field on it says when a record happens.')"
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
import { computed, ref } from 'vue'
import { Calendar } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'
import { occurrencesOf } from '@/modules/onespace/lib/screen/recurrence'
import EmptyState from '@/shared/components/EmptyState.vue'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The records in the range on screen, fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /**
   * Which fields the dates are, as the last page came back for them. The shell
   * owns this because it owns the request: a calendar drawn from the spec while
   * rows arrive for another pair is a month of nothing.
   */
  calendar: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['open', 'range'])

/**
 * Read-only, deliberately. The grid can drag, resize and create, and every one
 * of those writes a field — which this screen already does properly, through
 * the record dialog with the doctype's rules in front of it. Clicking an event
 * opens the record instead.
 */
const CONFIG = { isEditMode: false, defaultMode: 'Month' }

const field = computed(() => props.calendar?.start_field || '')
const endField = computed(() => props.calendar?.end_field || '')
const repeatField = computed(() => props.calendar?.repeat_field || '')
const untilField = computed(() => props.calendar?.until_field || '')

/**
 * The days on screen, as the grid last reported them. The shell fetches by this
 * range and so does the repeating: an occurrence exists only for as long as the
 * month showing it does, which is what makes a rule a *drawing* rather than
 * four hundred rows nobody can delete.
 */
const shown = ref({})

/** What a record is called, from the doctype's own title field. */
const titleOf = (row) => {
  const title = props.spec?.title_field
  return String((title && row[title]) || row.name || '')
}

/**
 * A day, and a time where there is one. Frappe writes a Date as `YYYY-MM-DD`
 * and a Datetime as `YYYY-MM-DD HH:mm:ss`, so the split is the space — no
 * parsing, no timezone, no date library.
 */
const split = (value) => {
  const said = String(value || '').trim()
  if (!said) return null
  const [date, time = ''] = said.split(' ')
  return { date, time: time.slice(0, 5) }
}

/** How many days a record covers, so a repeat of it covers the same. */
const daysBetween = (from, to) => {
  const one = new Date(`${from}T00:00:00`)
  const other = new Date(`${to}T00:00:00`)
  const apart = Math.round((other - one) / 86_400_000)
  return Number.isFinite(apart) && apart > 0 ? apart : 0
}

const shift = (date, days) => {
  if (!days) return date
  const made = new Date(`${date}T00:00:00`)
  made.setDate(made.getDate() + days)
  const pad = (one) => String(one).padStart(2, '0')
  return `${made.getFullYear()}-${pad(made.getMonth() + 1)}-${pad(made.getDate())}`
}

const events = computed(() => {
  if (!field.value) return []
  const found = []
  for (const row of props.rows) {
    const from = split(row[field.value])
    if (!from) continue
    const to = endField.value ? split(row[endField.value]) : null
    // A record with no end is a moment on its own day rather than a span
    // running to whenever the next one happens to be.
    const covers = daysBetween(from.date, to?.date || from.date)

    // Every day this record falls on. One, unless the screen names a rule field
    // and the record carries a value — see `lib/screen/recurrence.js`.
    const on = repeatField.value
      ? occurrencesOf(
          from.date,
          row[repeatField.value],
          untilField.value ? row[untilField.value] : '',
          shown.value,
        )
      : [from.date]

    for (const day of on) {
      found.push({
        // The record's id for the first, and the day appended after that: the
        // grid keys events by id, and four Tuesdays sharing one would draw one
        // Tuesday.
        id: day === from.date ? row.name : `${row.name}@${day}`,
        title: titleOf(row),
        fromDate: day,
        toDate: shift(day, covers),
        fromTime: from.time || undefined,
        toTime: to?.time || from.time || undefined,
        isFullDay: !from.time,
      })
    }
  }
  return found
})

const open = (event) => {
  // An occurrence opens the record it is an occurrence of. There is only one
  // record: a rule is a drawing.
  const id = String(event?.id || '').split('@')[0]
  const row = props.rows.find((one) => one.name === id)
  if (row) emit('open', row)
}

/**
 * The days now on screen. `rangeChange` fires on mount as well as on every
 * move, which is what makes this the only fetch the calendar needs.
 */
const moved = ({ startDate, endDate }) => {
  if (!startDate || !endDate) return
  shown.value = { since: startDate, until: endDate }
  emit('range', { since: startDate, until: endDate })
}
</script>
