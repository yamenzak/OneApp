<template>
  <!--
    A leave application, as the person deciding it reads one.

    The form has every field and not the one thing the decision turns on. An
    approver looking at "five days of annual leave in October" is really asking
    two questions — does it clash, and do they have the days — and the second
    has no answer anywhere on the record. It lives in Leave Allocation minus
    what has been taken against it, which is two doctypes and an arithmetic,
    and until now it meant leaving the request to go and work it out.

    So the balance is the page. Every type this person has, what is left of
    each, and the one they are asking for pulled out and measured against the
    days in front of you — including the case that matters, which is a request
    longer than the balance behind it.

    Read through `onehr/history.py`, the same call the person page's band
    makes. It gates itself on `own.may_read`: your own always, anybody else's
    only with the grant the people officer holds. A seat that cannot see the
    numbers draws the band without them rather than a refusal.
  -->
  <section data-slot="absence-record" class="-mx-4 -mt-4 mb-4 flex flex-col">
    <div
      class="flex flex-col gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-5 md:flex-row md:items-center md:gap-6 md:px-6"
    >
      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <p
          v-if="kind"
          data-slot="absence-kind"
          class="truncate text-sm text-ink-muted"
        >{{ kind }}</p>
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <h2
            data-slot="absence-who"
            class="min-w-0 truncate text-xl-semibold text-ink-primary"
          >{{ title }}</h2>
          <StateBadge v-if="badge" :label="badge" :states="states" />
        </div>
        <p data-slot="absence-when" class="text-sm text-ink-secondary">{{ when }}</p>
      </div>

      <!-- How many days are being asked for. The number the whole page is a
           judgement about. -->
      <div
        v-if="days"
        data-slot="absence-days"
        class="flex shrink-0 flex-col gap-0.5 md:items-end"
      >
        <p class="text-2xl-semibold tabular-nums text-ink-primary">{{ days }}</p>
        <p class="text-xs text-ink-muted">{{ __('days') }}</p>
      </div>
    </div>

    <FactRow :facts="facts" slot-name="absence-facts" />

    <!--
      What they have left, by type.

      Drawn only where there is something to draw: a seat without the grant to
      read somebody else's numbers gets no band, which is the same thing the
      person page does and is not a refusal — the request is still readable.
    -->
    <div
      v-if="balance.length"
      data-slot="absence-balance"
      class="flex flex-col gap-2 border-b border-outline-gray-2 px-4 py-4 md:px-6"
    >
      <p class="text-xs text-ink-muted">{{ __('What they have left') }}</p>
      <ul class="flex flex-col">
        <li
          v-for="one in balance"
          :key="one.type"
          data-slot="absence-left"
          :data-asked="one.asked ? 'yes' : 'no'"
          class="flex items-center gap-3 border-b border-outline-gray-1 py-2 last:border-b-0"
        >
          <span
            class="min-w-0 flex-1 truncate text-sm"
            :class="one.asked ? 'text-base-medium text-ink-primary' : 'text-ink-secondary'"
          >{{ one.type }}</span>
          <!--
            A bar rather than a second number: "12 of 25" is two numbers to
            hold and a bar is the same fact at a glance. Amber where this
            request would take somebody past what they have, which is the one
            reading an approver must not miss.
          -->
          <span class="h-1.5 w-24 shrink-0 overflow-hidden rounded-full bg-surface-gray-3">
            <span
              class="block h-full rounded-full"
              :class="one.short ? 'bg-surface-amber-3' : 'bg-surface-gray-6'"
              :style="{ width: one.width }"
            />
          </span>
          <span class="w-24 shrink-0 text-end text-sm tabular-nums text-ink-secondary">
            {{ __('{0} of {1}', [String(one.left), String(one.allocated)]) }}
          </span>
        </li>
      </ul>
      <p
        v-if="short"
        data-slot="absence-short"
        class="flex items-center gap-1.5 text-xs text-ink-amber-3"
      >
        <Icon name="lucide-triangle-alert" class="size-3.5 shrink-0" />
        {{ short }}
      </p>
    </div>

    <!-- Why, in their own words, where they gave one. -->
    <div
      v-if="because"
      data-slot="absence-because"
      class="border-b border-outline-gray-2 px-4 py-4 text-sm text-ink-secondary md:px-6"
    >{{ because }}</div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Icon } from '@/ui'
import FactRow from '@/modules/onespace/components/people/FactRow.vue'
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'
import { cellText } from '@/modules/onespace/lib/screen/cells'
import { fieldSpec } from '@/modules/onespace/lib/screen/fields'
import { date as onDate } from '@/shared/lib/runtime/format'
import { session } from '@/modules/onespace/lib/shell/session'
import { workspace } from '@/shared/lib/workspace'
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

/** HRMS's own names for what this page reads. */
const EMPLOYEE = 'employee'
const TYPE = 'leave_type'
const FROM = 'from_date'
const TO = 'to_date'
const DAYS = 'total_leave_days'
const APPROVER = 'leave_approver'
const POSTED = 'posting_date'
const HALF = 'half_day'
const HALF_DAY = 'half_day_date'
const WHY = 'description'

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

const kind = computed(() => text(TYPE))
const badge = computed(() => String(props.record?.[props.spec?.status_field || 'status'] || ''))
const days = computed(() => {
  const value = Number(props.record?.[DAYS])
  return Number.isFinite(value) && value ? String(value) : ''
})

/** The span, and the half day where there is one. */
const when = computed(() => {
  const from = props.record?.[FROM]
  const to = props.record?.[TO]
  if (!from) return ''
  const span = to && to !== from
    ? `${onDate(from)} – ${onDate(to)}`
    : onDate(from)
  return props.record?.[HALF]
    ? __('{0} · half day on {1}', [span, onDate(props.record[HALF_DAY] || from)])
    : span
})

const because = computed(() => String(props.record?.[WHY] || '').trim())

const facts = computed(() => {
  const found = [
    {
      field: APPROVER,
      label: column(APPROVER)?.label || __('Approver'),
      text: text(APPROVER),
      icon: fieldSpec(column(APPROVER)).icon,
    },
    {
      field: POSTED,
      label: __('Asked on'),
      text: props.record?.[POSTED] ? onDate(props.record[POSTED]) : '',
      icon: 'lucide-calendar-check',
    },
  ]
  return found.filter((one) => one.text).slice(0, FACTS)
})

const balance = ref([])

/** Whichever type is short, said once under the bars. */
const short = computed(() => {
  const asked = balance.value.find((one) => one.asked && one.short)
  if (!asked) return ''
  return __('This is {0} days and there are {1} of {2} left.',
            [days.value, String(asked.left), asked.type])
})

/**
 * Their allocations, minus what has been taken — `onehr/history.py`.
 *
 * The same call the person page's band makes, and gated the same way: it
 * answers with nothing rather than refusing, so a seat that may read the
 * request and not the numbers gets the request.
 */
const load = async () => {
  balance.value = []
  const employee = String(props.record?.[EMPLOYEE] || '')
  if (!employee) return

  const found = await workspace.personHistory(employee).catch(() => null)
  if (String(props.record?.[EMPLOYEE] || '') !== employee) return

  const asking = String(props.record?.[TYPE] || '')
  const wanted = Number(props.record?.[DAYS]) || 0
  balance.value = (found?.balance || []).map((one) => {
    const left = Number(one.left) || 0
    const allocated = Number(one.allocated) || 0
    const asked = String(one.leave_type || '') === asking
    return {
      type: String(one.leave_type || ''),
      left,
      allocated,
      asked,
      // Short only against the request in front of you: a type nobody is
      // asking about being low is not this page's business.
      short: asked && wanted > left,
      width: `${allocated ? Math.max(0, Math.min(100, Math.round((left / allocated) * 100))) : 0}%`,
    }
  })
}

watch(() => [props.record?.name, props.revision], load, { immediate: true })
</script>
