<template>
  <!--
    A job that is open, drawn as the question a hiring manager actually has.

    Not "what does this Job Opening record say" — the form below still says all
    of that — but "how is it going": how long it has been open, how many people
    are in the pipe, and where they have got stuck. That last one is the whole
    reason this page exists. The funnel is on the Applicants dashboard too, for
    every opening at once; the one thing nobody could see was a single role's.

    It replaces the showcase, which drew a 260-pixel black hero with a job title
    in condensed capitals over a page whose only fact was a closing date. That
    hero is right for a building, and `openings` was the last screen in OnePeople
    still using it — `docs/UNIFICATION.md` F1, which is that a surface kept for
    want of a better one is how the drawing stops matching the product.
  -->
  <section data-slot="opening-record" class="-mx-4 -mt-4 mb-4 flex flex-col">
    <div
      class="flex flex-col gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-5 md:flex-row md:items-start md:gap-6 md:px-6"
    >
      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <p
          v-if="eyebrow"
          data-slot="opening-eyebrow"
          class="truncate text-sm text-ink-muted"
        >{{ eyebrow }}</p>
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <h2
            data-slot="opening-title"
            class="min-w-0 truncate text-xl-semibold text-ink-primary"
          >{{ title }}</h2>
          <StateBadge v-if="badge" :label="badge" :states="states" />
        </div>
        <!--
          How long it has been open, and when it stops being. Two facts that
          are a sentence rather than two cells: "posted three weeks ago,
          closes on Friday" is one thought, and a role that has been open since
          January is the thing somebody should notice on arriving here.
        -->
        <p
          v-if="when"
          data-slot="opening-when"
          class="mt-0.5 flex items-center gap-2 text-sm text-ink-secondary"
        >
          <Icon name="lucide-calendar" class="size-3.5 shrink-0 text-ink-muted" />
          <span class="truncate">{{ when }}</span>
        </p>
        <!--
          What it pays, beside the dates rather than down in the facts.

          A range is two amounts and a word, which is twice the width of any
          other fact and came out as "AED 14,000.00 – AED 19,0…" in a quarter
          of a row. It also belongs here: it is the first thing anybody asks
          about a role, and it is not a column on any screen.
        -->
        <p
          v-if="pay"
          data-slot="opening-pay"
          class="flex items-center gap-2 text-sm text-ink-secondary"
        >
          <Icon name="lucide-banknote" class="size-3.5 shrink-0 text-ink-muted" />
          <span class="truncate">{{ pay }}</span>
        </p>
        <!--
          Said only when it has been and gone, because that is the state
          nobody notices: a role still collecting applications past the date it
          said it would stop.
        -->
        <p
          v-if="overdue"
          data-slot="opening-overdue"
          class="flex items-center gap-2 text-sm text-ink-amber-3"
        >
          <Icon name="lucide-triangle-alert" class="size-3.5 shrink-0" />
          {{ __('Still open past its closing date.') }}
        </p>
      </div>

      <!-- How many of these there are to fill. The number the funnel below is
           measured against, so it stands beside it rather than in the facts. -->
      <div
        v-if="vacancies"
        data-slot="opening-vacancies"
        class="flex shrink-0 flex-col gap-0.5 md:items-end"
      >
        <p class="text-2xl-semibold tabular-nums text-ink-primary">{{ vacancies }}</p>
        <p class="text-xs text-ink-muted">{{ __('to fill') }}</p>
      </div>
    </div>

    <FactRow :facts="facts" slot-name="opening-facts" />

    <!--
      Where the people are.

      The order is the manifest's — the same `APPLICANT_STAGES` the board
      arranges its columns by and the candidate page fills its strip from — so
      the three cannot disagree about what hiring looks like. Counted through
      the tally endpoint under a filter, which is the ordinary list's own
      narrowing: a record view may read, and only the way every list reads.

      Every declared stage is drawn, empty ones included. A funnel that hides
      its zeroes cannot show you the gap, and the gap is the reading — fourteen
      replied and nobody shortlisted is a recruiter who has stopped looking.
    -->
    <div
      v-if="funnel.length"
      data-slot="opening-funnel"
      class="flex flex-col gap-3 border-b border-outline-gray-2 px-4 py-4 md:px-6"
    >
      <div class="flex items-baseline gap-2">
        <p class="text-xs text-ink-muted">{{ __('Applicants') }}</p>
        <p data-slot="opening-applicants" class="text-sm tabular-nums text-ink-secondary">
          {{ applicants }}
        </p>
      </div>
      <ol class="flex flex-col gap-1.5">
        <li
          v-for="stage in funnel"
          :key="stage.label"
          class="flex items-center gap-3"
          :data-stage="stage.label"
          :data-count="stage.count"
        >
          <span class="w-24 shrink-0 truncate text-sm text-ink-secondary">{{ stage.label }}</span>
          <span class="h-2 min-w-0 flex-1 rounded-full bg-surface-gray-2">
            <span
              class="block h-2 rounded-full"
              :class="stage.ending ? 'bg-surface-gray-5' : 'bg-surface-green-5'"
              :style="{ width: stage.width }"
            />
          </span>
          <span
            class="w-8 shrink-0 text-end text-sm tabular-nums"
            :class="stage.count ? 'text-ink-primary' : 'text-ink-gray-4'"
          >{{ stage.count }}</span>
        </li>
      </ol>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Icon } from '@/ui'
import FactRow from '@/modules/onespace/components/people/FactRow.vue'
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'
import { cellText } from '@/modules/onespace/lib/screen/cells'
import { fieldSpec } from '@/modules/onespace/lib/screen/fields'
import { ago, date as onDate, money } from '@/shared/lib/runtime/format'
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

/** How many facts a band carries. `showcase.FACTS`, and the same four. */
const FACTS = 4

/**
 * Which screen the people applying are on, the field that points back here,
 * and what their stage is called on it.
 *
 * Named rather than read off this screen's `status_field`, which is the Job
 * Opening's own Open-or-Closed and has nothing to do with where an applicant
 * stands.
 */
const APPLICANTS = 'applicants'
const APPLIED_FOR = 'job_title'
const APPLICANT_STATUS = 'status'

/**
 * The one status that is an ending rather than a place in the queue.
 *
 * Drawn grey rather than green and kept at the bottom where the manifest puts
 * it: forty rejections is not forty people further along, and a green bar as
 * long as the row above it would read as though it were.
 */
const ENDINGS = ['Rejected']

/** HRMS's own field names for the numbers this page reads off the record. */
const VACANCIES = 'vacancies'
const POSTED = 'posted_on'
const CLOSES = 'closes_on'
const CLOSED = 'closed_on'
const LOWER = 'lower_range'
const UPPER = 'upper_range'
const CURRENCY = 'currency'
const PER = 'salary_per'
const STATUS_CLOSED = 'Closed'

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
  const field = props.showcase?.badge_field
  return field ? String(props.record?.[field] || '') : ''
})

const vacancies = computed(() => Number(props.record?.[VACANCIES]) || 0)

const closed = computed(() => badge.value === STATUS_CLOSED)

/**
 * The life of the posting, as one line.
 *
 * `ago` is relative under a week and a date over it, which is the right split
 * here for the same reason it is everywhere else: "posted 3 days ago" is how
 * somebody thinks about this week's role, and "12 Jan 2026" is how they think
 * about the one that has been open since the winter.
 */
const when = computed(() => {
  if (closed.value) {
    const on = props.record?.[CLOSED]
    return on ? __('Closed on {0}', [onDate(on)]) : __('Closed')
  }
  const posted = props.record?.[POSTED]
  const closes = props.record?.[CLOSES]
  // Three sentences rather than two halves joined, because a capital letter is
  // not something a caller can put back: `charAt(0).toUpperCase()` is right in
  // English and wrong in any language whose first word is not capitalised, or
  // whose clause order is not this one.
  if (posted && closes) {
    return __('Posted {0} · closes {1}', [ago(posted), onDate(closes)])
  }
  if (posted) return __('Posted {0}', [ago(posted)])
  return closes ? __('Closes {0}', [onDate(closes)]) : ''
})

/**
 * Open, and the date it said it would stop has been and gone.
 *
 * Compared in the reader's own day rather than through `toISOString`, which is
 * UTC: west of Greenwich that turns the evening of the closing date into the
 * morning after it, and draws a warning on a role that closes tomorrow.
 */
const overdue = computed(() => {
  const on = props.record?.[CLOSES]
  if (closed.value || !on) return false
  const now = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
  return String(on).slice(0, 10) < today
})

/**
 * What it pays, where somebody filled it in.
 *
 * Through `money`, which writes the currency the workspace writes it in — a
 * range printed as `40000 - 55000` is two numbers nobody can compare against
 * the salary they are about to offer.
 */
const pay = computed(() => {
  const lower = Number(props.record?.[LOWER]) || 0
  const upper = Number(props.record?.[UPPER]) || 0
  if (!lower && !upper) return ''
  const currency = props.record?.[CURRENCY] || ''
  const range = lower && upper
    ? `${money(lower, currency)} – ${money(upper, currency)}`
    : money(lower || upper, currency)
  const per = String(props.record?.[PER] || '')
  return per ? __('{0} a {1}', [range, per.toLowerCase()]) : range
})

/**
 * The facts, minus the closing date the band already carries.
 *
 * Printing a date twice eight pixels apart is what makes a bespoke page look
 * like a generic one with extra steps — the same rule the candidate page
 * follows for the opening and the rating.
 */
const facts = computed(() =>
  (props.showcase?.facts || [])
    .filter((fact) => ![CLOSES, CLOSED].includes(fact.field))
    .slice(0, FACTS)
    .map((fact) => {
      const found = column(fact.field)
      const text = found
        ? cellText(found, props.record?.[fact.field], formats.value, linked(fact.field))
        : ''
      return {
        field: fact.field,
        label: fact.label || found?.label || fact.field,
        // `cellText` writes an em dash for an empty value, which is right in a
        // column and wrong here: this row draws "nothing" quieter than an
        // answer rather than in the same weight.
        text: text === '—' ? '' : text,
        icon: fieldSpec(found).icon,
      }
    }),
)

const tally = ref([])

const applicants = computed(() => {
  const total = tally.value.reduce((sum, one) => sum + one.count, 0)
  if (!vacancies.value) return __('{0} so far', [String(total)])
  return __('{0} for {1} to fill', [String(total), String(vacancies.value)])
})

/**
 * Every declared stage with its count, and a bar measured against the fullest.
 *
 * Against the fullest rather than against the total: a pipeline is forty open
 * and three shortlisted, and bars drawn as shares of forty-three make the
 * three invisible — which is the one number somebody came here to read.
 */
const funnel = computed(() => {
  const declared = props.spec?.view_settings?.record?.stages || []
  if (!declared.length) return []
  const counts = new Map(tally.value.map((one) => [String(one.value || ''), one.count]))
  const most = Math.max(1, ...declared.map((label) => counts.get(label) || 0))
  return declared.map((label) => {
    const count = counts.get(label) || 0
    return {
      label,
      count,
      ending: ENDINGS.includes(label),
      width: `${Math.round((count / most) * 100)}%`,
    }
  })
})

/**
 * How many applicants each stage holds, through the endpoint the list's own
 * narrowing menu uses.
 *
 * A count rather than a page of rows: the Applicants tab below is where the
 * people are, and pulling two hundred records to count six numbers is the
 * thing a record view is not allowed to do. The filter is the ordinary one —
 * checked against this screen's filterable columns on the server, the same as
 * anything somebody types into the controls.
 */
const loadFunnel = async () => {
  tally.value = []
  const name = props.record?.name
  if (!name) return
  const found = await workspace.screenTally(
    props.spaceCode, APPLICANTS, APPLICANT_STATUS,
    { filters: [[APPLIED_FOR, '=', name]] },
  )
  if (props.record?.name !== name) return
  tally.value = (found?.values || []).map((one) => ({
    value: String(one.value || ''),
    count: Number(one.count) || 0,
  }))
}

watch(() => [props.record?.name, props.revision], loadFunnel, { immediate: true })
</script>
