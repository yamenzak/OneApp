<template>
  <!--
    Somebody arriving, or somebody leaving — and the list of things that have to
    happen either way.

    Both are the same document with a different sign on the date, which is why
    one page draws both: an onboarding is a person, a joining date and a
    checklist; a separation is a person, a last day and a checklist. HRMS models
    them as one controller for the same reason.

    The reason it needs a page at all is the checklist. It is a child table, and
    a child table is a spreadsheet: seven columns, one of them called "Begin On
    (Days)" holding the number 3, one holding a Task id, and the activity names
    truncated to a dozen characters because the grid gave them a fifth of the
    width. Nobody can read their own first week out of that. Here each step is a
    line — what it is, who it is for, the day it actually falls on — and the two
    facts that were arithmetic are done.

    What is deliberately *not* here is a tick. Each step carries a Task, and
    whether that Task is finished is what a checklist is for — but a record view
    reads through the screens of its own space and OneHR has no screen over
    Task, and inventing a second way to read is the one thing this contract
    forbids (`lib/screen/recordViews.js`). The steps are drawn in the order they
    fall instead, which is the other half of the question.
  -->
  <RecordPage name="boarding">
    <RecordHead
      :eyebrow="eyebrow"
      eyebrow-slot="boarding-eyebrow"
      :title="title"
      title-slot="boarding-who"
      :badge="badge"
      :states="states"
    >
      <p
        v-if="when"
        data-slot="boarding-when"
        class="text-sm text-ink-secondary"
      >{{ when }}</p>

      <!--
        How many steps and how long they run. The one reading a person wants
        before they read the list: four things over a fortnight is a plan, four
        things on one morning is a problem.
      -->
      <template #aside>
        <RecordTally
          v-if="steps.length"
          name="boarding-span"
          :value="steps.length"
          :caption="through"
        />
      </template>
    </RecordHead>

    <FactRow :facts="facts" slot-name="boarding-facts" />

    <!--
      The checklist.

      Drawn even when it is empty, and that is the important case: a boarding
      document with no activities is one somebody submitted without a template,
      and it will quietly never ask anybody to do anything.
    -->
    <div
      data-slot="boarding-steps"
      class="flex flex-col gap-2 border-b border-outline-gray-2 px-4 py-4 md:px-6"
    >
      <p class="text-xs text-ink-muted">{{ __('What has to happen') }}</p>

      <ol v-if="steps.length" class="flex flex-col">
        <li
          v-for="step in steps"
          :key="step.key"
          data-slot="boarding-step"
          class="flex items-baseline gap-3 border-b border-outline-gray-1 py-2 last:border-b-0"
        >
          <span
            class="w-5 shrink-0 text-end text-xs tabular-nums text-ink-gray-4"
          >{{ step.at }}</span>
          <div class="flex min-w-0 flex-1 flex-col gap-0.5">
            <p class="text-base-medium text-ink-primary">{{ step.label }}</p>
            <p
              v-if="step.who || step.gate"
              class="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-muted"
            >
              <span v-if="step.who" class="flex items-center gap-1">
                <Icon name="lucide-user" class="size-3 shrink-0" />
                {{ step.who }}
              </span>
              <!--
                The steps that gate the Employee record. HRMS refuses to make
                one until every activity marked this way is closed, and the
                refusal names none of them — so the page that can say which
                ones they are should.
              -->
              <span v-if="step.gate" class="flex items-center gap-1 text-ink-amber-3">
                <Icon name="lucide-flag" class="size-3 shrink-0" />
                {{ __('Before the record is made') }}
              </span>
            </p>
          </div>
          <span
            v-if="step.on"
            class="shrink-0 text-xs tabular-nums text-ink-secondary"
          >{{ step.on }}</span>
        </li>
      </ol>

      <p v-else data-slot="boarding-no-steps" class="text-sm text-ink-gray-4">
        {{ __('Nothing is on this checklist. It was submitted without a template, so it will ask nobody for anything.') }}
      </p>
    </div>
  </RecordPage>
</template>

<script setup>
import { computed } from 'vue'

import { Icon } from '@/ui'
import FactRow from '@/modules/onespace/components/people/FactRow.vue'
import RecordHead from '@/modules/onespace/components/screen/records/RecordHead.vue'
import RecordPage from '@/modules/onespace/components/screen/records/RecordPage.vue'
import RecordTally from '@/modules/onespace/components/screen/records/RecordTally.vue'
import { cellText } from '@/modules/onespace/lib/screen/cells'
import { fieldSpec } from '@/modules/onespace/lib/screen/fields'
import { date as onDate } from '@/shared/lib/runtime/format'
import { session } from '@/modules/onespace/lib/shell/session'
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

defineEmits(['open'])

/** How many facts a band carries. `showcase.FACTS`, and the same four. */
const FACTS = 4

/** How many steps a page draws. A checklist longer than this is a project,
 *  and a project is what the thing underneath it already is. */
const STEPS = 30

/** HRMS's own names. `boarding_begins_on` is on both doctypes; the date that
 *  the checklist is *about* is one of the other two, and which one is what
 *  tells an arrival from a departure. */
const BEGINS = 'boarding_begins_on'
const JOINS = 'date_of_joining'
const RESIGNED = 'resignation_letter_date'
const ACTIVITIES = 'activities'
const DEPARTMENT = 'department'

/** And the child row's own. `begin_on` is a number of days after `BEGINS`,
 *  which is the field this page exists to turn back into a date. */
const STEP_NAME = 'activity_name'
const STEP_AFTER = 'begin_on'
const STEP_USER = 'user'
const STEP_ROLE = 'role'
const STEP_GATE = 'required_for_employee_creation'

const DAY = 86_400_000

const formats = computed(() => session.formats || {})
const columns = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const states = computed(() => props.spec?.states || [])

const column = (fieldname) => columns.value.find((one) => one.fieldname === fieldname)
const linked = (fieldname) => props.record?._links?.[fieldname]

const text = (fieldname) => {
  const value = props.record?.[fieldname]
  if (value === null || value === undefined || value === '') return ''
  const found = column(fieldname)
  return found ? cellText(found, value, formats.value, linked(fieldname)) : String(value)
}

const eyebrow = computed(() => {
  const field = props.showcase?.eyebrow_field || 'designation'
  return text(field)
})

const badge = computed(() => {
  const field = props.spec?.status_field || 'boarding_status'
  return String(props.record?.[field] || '')
})

/**
 * The day this is about, said the way round it happens.
 *
 * Not a fact in the row below, because it is the only date on the page anybody
 * came for — and "Joins" and "Last day" are two different sentences about the
 * same field position.
 */
const when = computed(() => {
  const joins = props.record?.[JOINS]
  if (joins) return __('Joins {0}', [onDate(joins)])
  const left = props.record?.[RESIGNED]
  return left ? __('Resigned {0}', [onDate(left)]) : ''
})

/**
 * A step's date, from the day the checklist begins and the offset it carries.
 *
 * Built out of the parts rather than read off the Task, which holds the same
 * date: a Task is a doctype this space cannot read, and the two numbers that
 * make the date are already here.
 *
 * Parsed by hand rather than through `Date.parse`, which reads a bare
 * `YYYY-MM-DD` as UTC — west of Greenwich that is the day before, and a
 * checklist quietly one day early is worse than one with no dates at all.
 */
const on = (after) => {
  const from = String(props.record?.[BEGINS] || '')
  const parts = from.split('-').map(Number)
  if (parts.length !== 3 || parts.some((one) => !Number.isFinite(one))) return ''
  const start = new Date(parts[0], parts[1] - 1, parts[2])
  const days = Number(after)
  return onDate(new Date(start.getTime() + (Number.isFinite(days) ? days : 0) * DAY))
}

const steps = computed(() => {
  const rows = props.record?.[ACTIVITIES]
  if (!Array.isArray(rows)) return []
  return rows.slice(0, STEPS).map((row, at) => ({
    key: row.name || `${at}`,
    at: at + 1,
    label: String(row[STEP_NAME] || ''),
    // A person if one was named, otherwise whichever role the step is for —
    // HRMS assigns the Task to either, and "the HR Manager" is as much of an
    // answer to "whose is this" as a name is.
    who: String(row[STEP_USER] || row[STEP_ROLE] || ''),
    gate: !!row[STEP_GATE],
    on: on(row[STEP_AFTER]),
  })).filter((step) => step.label)
})

/** The last day anything on the list falls on, said under the count. */
const through = computed(() => {
  const last = steps.value[steps.value.length - 1]?.on
  return last ? __('steps, through {0}', [last]) : __('steps')
})

const facts = computed(() => {
  const found = [
    {
      field: BEGINS,
      label: __('Checklist begins'),
      text: props.record?.[BEGINS] ? onDate(props.record[BEGINS]) : '',
      icon: 'lucide-calendar-check',
    },
    {
      field: DEPARTMENT,
      label: column(DEPARTMENT)?.label || __('Department'),
      text: text(DEPARTMENT),
      icon: fieldSpec(column(DEPARTMENT)).icon,
    },
  ]
  return found.filter((one) => one.text).slice(0, FACTS)
})
</script>
