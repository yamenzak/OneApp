<template>
  <!--
    One person, one day.

    The record behind a cell of the attendance grid, and the reason it needs a
    page of its own: an Attendance row is a verdict — Present, Absent, Half Day
    — and the question anybody opening one has is *why that verdict*. The form
    below answers it with twenty fields in four sections, of which the four that
    matter are the shift, the two times and the two flags.

    So this is the day laid out as a day: what the shift asked for, what
    actually happened, what the system marked it as, and the punches the verdict
    was computed from. That last part is the whole argument. When a day is
    marked Absent and somebody swears they were there, the check-ins settle it,
    and until now settling it meant leaving this record, finding the Check-ins
    screen and filtering it by hand.
  -->
  <RecordPage name="day">
    <RecordHead
      :eyebrow="eyebrow"
      eyebrow-slot="day-eyebrow"
      :title="title"
      title-slot="day-who"
      :badge="badge"
      :states="states"
    >
      <p data-slot="day-when" class="text-sm text-ink-secondary">{{ when }}</p>

      <!--
        The two marks the system makes on a day it otherwise counts as
        worked. Only when set: a row of greyed-out "not late" chips would
        make being on time look like a state somebody has to check.
      -->
      <div v-if="flags.length" data-slot="day-flags" class="mt-1 flex flex-wrap gap-2">
        <span
          v-for="flag in flags"
          :key="flag.label"
          class="flex items-center gap-1.5 rounded-full bg-surface-amber-2 px-2 py-0.5 text-xs text-ink-amber-3"
        >
          <Icon :name="flag.icon" class="size-3 shrink-0" />
          {{ flag.label }}
        </span>
      </div>

      <!--
        How long they were here, against how long the shift asked for. The one
        number a day is judged on, and the comparison is the reading: seven
        hours is a full day or an hour short depending on a field nobody looks
        at.
      -->
      <template #aside>
        <RecordTally
          v-if="worked || standard"
          name="day-worked"
          :value="worked || '—'"
          :caption="standard ? __('of {0}', [standard]) : __('worked')"
        />
      </template>
    </RecordHead>

    <!--
      A planned absence explains itself, and the explanation is a different
      record. Said as a line with a way through to it rather than as a fact in
      the row below, because it is the reason for the whole day.
    -->
    <div
      v-if="leave"
      data-slot="day-leave"
      class="flex flex-wrap items-center gap-2 border-b border-outline-gray-2 px-4 py-3 md:px-6"
    >
      <Icon name="lucide-palmtree" class="size-4 shrink-0 text-ink-blue-3" />
      <span class="text-sm text-ink-primary">{{ leave }}</span>
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a word in a line of prose that navigates; a <Button> brings a height and a ground into a sentence -->
      <button
        v-if="application"
        type="button"
        data-slot="day-application"
        class="rounded-4 text-sm text-ink-secondary underline-offset-2 hover:text-ink-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-outline-gray-8"
        @click="emit('open', { screen: LEAVE, name: application })"
      >{{ __('See the application') }}</button>
    </div>

    <FactRow :facts="facts" slot-name="day-facts" />

    <!--
      What the verdict was computed from.

      Through the same loader the candidate page reads interviews with, which
      is the ordinary list endpoint under a filter — a record view may read,
      and only the way every list reads.

      The empty case is drawn rather than hidden, and on most days it is the
      important one: a day marked Present with no punches behind it was written
      by hand or by a request, and a day marked Absent with punches on it is a
      mistake somebody has to correct. The exception is a day of leave, where
      nobody expected a punch and "nothing was punched" is a sentence about
      nothing — unless there *are* punches, which is the contradiction worth
      drawing.
    -->
    <div
      v-if="punched"
      data-slot="day-checkins"
      class="flex flex-col gap-2 border-b border-outline-gray-2 px-4 py-4 md:px-6"
    >
      <p class="text-xs text-ink-muted">{{ __('Check-ins') }}</p>
      <ul v-if="checkins.length" class="flex flex-col gap-1.5">
        <li
          v-for="one in checkins"
          :key="one.name"
          class="flex items-center gap-3 text-sm"
          :data-direction="one.direction"
        >
          <Icon
            :name="one.icon"
            class="size-4 shrink-0"
            :class="one.direction === INWARD ? 'text-ink-green-3' : 'text-ink-muted'"
          />
          <span class="w-16 shrink-0 tabular-nums text-ink-primary">{{ one.at }}</span>
          <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a row of text that opens the punch; a <Button> here brings a ground and a height into a line that has to read as a log -->
          <button
            type="button"
            class="min-w-0 flex-1 truncate rounded-4 text-start text-ink-secondary hover:text-ink-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-outline-gray-8"
            @click="emit('open', { screen: CHECKINS, name: one.name })"
          >{{ one.label }}</button>
        </li>
      </ul>
      <p v-else data-slot="day-no-checkins" class="text-sm text-ink-gray-4">
        {{ __('Nothing was punched. This day was written rather than clocked.') }}
      </p>
    </div>
  </RecordPage>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Icon } from '@/ui'
import FactRow from '@/modules/onespace/components/people/FactRow.vue'
import RecordHead from '@/modules/onespace/components/screen/records/RecordHead.vue'
import RecordPage from '@/modules/onespace/components/screen/records/RecordPage.vue'
import RecordTally from '@/modules/onespace/components/screen/records/RecordTally.vue'
import { cellText, humanDuration } from '@/modules/onespace/lib/screen/cells'
import { fieldSpec } from '@/modules/onespace/lib/screen/fields'
import { date as onDate, time as onTime } from '@/shared/lib/runtime/format'
import { session } from '@/modules/onespace/lib/shell/session'
import * as related from '@/modules/onespace/lib/screen/related'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  record: { type: Object, required: true },
  spec: { type: Object, default: () => ({}) },
  showcase: { type: Object, default: () => ({}) },
  title: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  revision: { type: Number, default: 0 },
  canWrite: { type: Boolean, default: false },
})

const emit = defineEmits(['open'])

/** How many facts a band carries. `showcase.FACTS`, and the same four. */
const FACTS = 4

/** Where the two lines on this page go. Screens of this same space. */
const LEAVE = 'leave'
const CHECKINS = 'checkins'

/** The field on a check-in that points back at the day it was counted into,
 *  and HRMS's own word for a punch that is an arrival. */
const MARKED = 'attendance'
const INWARD = 'IN'

/** How many punches a page draws. A day with more than this is a turnstile,
 *  and the Check-ins screen is where a turnstile is read. */
const PUNCHES = 12

/** HRMS's own names for what this page reads off the day. */
const DATE = 'attendance_date'
const SHIFT = 'shift'
const IN = 'in_time'
const OUT = 'out_time'
const WORKED = 'working_hours'
const STANDARD = 'standard_working_hours'
const OVERTIME = 'actual_overtime_duration'
const LATE = 'late_entry'
const EARLY = 'early_exit'
const LEAVE_TYPE = 'leave_type'
const APPLICATION = 'leave_application'
const HALF = 'half_day_status'
const STATUS_HALF = 'Half Day'
const STATUS_LEAVE = 'On Leave'

/** An hour, in seconds. `working_hours` is a Float of hours and the one
 *  duration formatter in this repository counts seconds. */
const HOUR = 3600

/** What `humanDuration` is told about a length of a working day: no days in
 *  it, and no seconds either — a shift is not measured to the second. */
const SPAN = { hide_days: true, hide_seconds: true }

const formats = computed(() => session.formats || {})
const columns = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const states = computed(() => props.spec?.states || [])

const column = (fieldname) => columns.value.find((one) => one.fieldname === fieldname)
const linked = (fieldname) => props.record?._links?.[fieldname]

const eyebrow = computed(() => {
  const field = props.showcase?.eyebrow_field
  const value = field ? props.record?.[field] : ''
  if (value === null || value === undefined || value === '') return ''
  const found = column(field)
  return found ? cellText(found, value, formats.value, linked(field)) : String(value)
})

const badge = computed(() => {
  const field = props.spec?.status_field || 'status'
  return String(props.record?.[field] || '')
})

/** The day, and which shift of it. */
const when = computed(() => {
  const day = props.record?.[DATE] ? onDate(props.record[DATE]) : ''
  const shift = linked(SHIFT)?.label || props.record?.[SHIFT] || ''
  if (day && shift) return `${day} · ${shift}`
  return day || String(shift)
})

const span = (hours) => {
  const value = Number(hours) || 0
  return value ? humanDuration(Math.round(value * HOUR), SPAN) : ''
}

const worked = computed(() => span(props.record?.[WORKED]))
const standard = computed(() => span(props.record?.[STANDARD]))

/**
 * The marks against an otherwise-worked day, and the half-day's other half.
 *
 * Amber rather than red for all three, which is the same reading the presence
 * pill argues for: arriving late is something to know about and not something
 * that went wrong, and a page that shouts at somebody's morning is a page a
 * manager learns to skim past.
 */
const flags = computed(() => {
  const found = []
  if (props.record?.[LATE]) {
    found.push({ label: __('Arrived late'), icon: 'lucide-clock-alert' })
  }
  if (props.record?.[EARLY]) {
    found.push({ label: __('Left early'), icon: 'lucide-log-out' })
  }
  const half = String(props.record?.[HALF] || '')
  if (badge.value === STATUS_HALF && half) {
    found.push({ label: __('Other half: {0}', [half]), icon: 'lucide-contrast' })
  }
  return found
})

/** The planned absence, where the day is one. */
const leave = computed(() => {
  const type = linked(LEAVE_TYPE)?.label || props.record?.[LEAVE_TYPE] || ''
  return type ? __('On {0}', [String(type)]) : ''
})

const application = computed(() => String(props.record?.[APPLICATION] || ''))

/**
 * When they arrived, when they left, and whatever the day ran over by.
 *
 * Read off the record rather than from the showcase's declaration, because
 * this page is about these four fields and a manifest that failed to list one
 * of them would draw a day with no times on it.
 */
const facts = computed(() => {
  // To the minute, not to the second: somebody arrived at 09:41, not at
  // 09:41:07, and the two extra digits are the difference between a fact about
  // a morning and a log line. The punches below keep their seconds, because a
  // log is what they are.
  const clock = (field) => (props.record?.[field]
    ? onTime(props.record[field], { toTheMinute: true })
    : '')

  const found = [
    { field: IN, label: __('In'), text: clock(IN), icon: 'lucide-log-in' },
    { field: OUT, label: __('Out'), text: clock(OUT), icon: 'lucide-log-out' },
    {
      field: SHIFT,
      label: column(SHIFT)?.label || __('Shift'),
      text: linked(SHIFT)?.label || String(props.record?.[SHIFT] || ''),
      icon: fieldSpec(column(SHIFT)).icon,
    },
    {
      field: OVERTIME,
      label: __('Overtime'),
      text: span(props.record?.[OVERTIME]),
      icon: 'lucide-timer',
    },
  ]
  // Whatever there is nothing to say about goes, rather than being drawn as
  // an em dash. `FactRow` follows the count, so three facts is a row of three
  // — and on a day of leave nothing is left, which is right: there are no
  // times on a day nobody worked, and a row of three dashes reads as a page
  // that failed to load rather than as a day off.
  return found.filter((one) => one.text).slice(0, FACTS)
})

const checkins = ref([])

/**
 * Whether the punches are worth a block at all.
 *
 * Always when there are some. Otherwise only where one was expected, which is
 * every verdict except a day of leave: "nothing was punched" explains an
 * Absent and says nothing at all about a holiday.
 */
const punched = computed(() =>
  checkins.value.length > 0 || badge.value !== STATUS_LEAVE,
)

/**
 * The punches this day was computed from.
 *
 * Filtered by the link HRMS itself writes back onto a check-in when auto
 * attendance marks a day — which is the honest join: a punch that was never
 * counted into this record does not belong on its page, and a day with none
 * is the fact worth drawing.
 */
const loadCheckins = async () => {
  checkins.value = []
  const name = props.record?.name
  if (!name) return

  const found = await related.loadChildren({
    spaceCode: props.spaceCode,
    screen: CHECKINS,
    field: MARKED,
    name,
    formats: formats.value,
    limit: PUNCHES,
  })
  if (props.record?.name !== name) return

  checkins.value = (found.rows || [])
    .map((row) => {
      const direction = String(row.log_type || '')
      const arriving = direction === INWARD
      return {
        name: row.name,
        direction,
        at: row.time ? onTime(row.time) : '',
        when: String(row.time || ''),
        icon: arriving ? 'lucide-log-in' : 'lucide-log-out',
        label: arriving ? __('Clocked in') : __('Clocked out'),
      }
    })
    // The log's own order, earliest first: a day is read forwards, and the
    // screen this comes from is sorted newest-first because a log is not.
    .sort((a, b) => a.when.localeCompare(b.when))
}

watch(() => [props.record?.name, props.revision], loadCheckins, { immediate: true })
</script>
