<template>
  <!--
    A record that is somebody applying for a job.

    The second person-shaped entry in the record-view library and deliberately
    not the first one again: an employee is somebody you look up, and a
    candidate is somebody you are *deciding about*. So the page answers the
    decision — where they are in hiring, what the interviews scored, and what
    the opening was — rather than laying out their attributes.

    It replaces the showcase, which drew a 260-pixel black hero over a person
    with no photograph and a name in condensed capitals. That hero is right for
    a building and wrong for a face, and it was the last place in OneHR still
    using it.
  -->
  <section data-slot="candidate-record" class="-mx-4 -mt-4 mb-4 flex flex-col">
    <!-- Who, and where they stand. -->
    <div
      class="flex flex-col gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-5 md:flex-row md:items-center md:gap-6 md:px-6"
    >
      <div
        class="flex size-16 shrink-0 items-center justify-center rounded-full bg-surface-gray-2 text-2xl text-ink-muted ring-1 ring-outline-gray-2"
        aria-hidden="true"
      >{{ initial }}</div>

      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <p
          v-if="eyebrow"
          data-slot="candidate-eyebrow"
          class="truncate text-sm text-ink-muted"
        >{{ eyebrow }}</p>
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <h2
            data-slot="candidate-name"
            class="min-w-0 truncate text-xl-semibold text-ink-primary"
          >{{ title }}</h2>
          <StateBadge v-if="badge" :label="badge" :states="states" />
        </div>

        <!--
          What they applied for, as a line rather than as one of the facts. An
          application is *about* an opening the way a report is about a manager,
          and the page below already lists everything else they said.
        -->
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a line of prose under the name that happens to navigate; <Button> brings a height, a padding and a hover ground, and this has to sit in the run of text -->
        <button
          v-if="opening"
          type="button"
          data-slot="candidate-opening"
          class="mt-1 flex w-fit items-center gap-2 rounded-4 py-0.5 text-sm text-ink-secondary hover:text-ink-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-outline-gray-8"
          @click="emit('open', { screen: OPENINGS, name: opening.value })"
        >
          <Icon name="lucide-briefcase" class="size-3.5 shrink-0 text-ink-muted" />
          <span class="truncate">{{ __('Applied for {0}', [opening.label]) }}</span>
        </button>
      </div>

      <!--
        The rating, as stars rather than as `0.8`. Frappe stores a Rating as a
        fraction of one and frappe-ui's control counts whole stars — the
        conversion is `lib/screen/rating.js`, in one place, because getting it
        wrong once stored a rating of four hundred per cent.

        Read-only here. Rating somebody is an edit and edits happen in the form,
        which is the rule every record view follows.
      -->
      <div
        v-if="rating"
        data-slot="candidate-rating"
        class="flex shrink-0 flex-col items-start gap-1 md:items-end"
      >
        <p class="text-xs text-ink-muted">{{ ratingLabel }}</p>
        <Rating :model-value="rating" :max="STARS" disabled />
      </div>
    </div>

    <!--
      Where they came from and how to reach them, minus the opening the line
      above already says. The same quiet row the person page draws under the
      same kind of band.
    -->
    <FactRow :facts="facts" slot-name="candidate-facts" />

    <!--
      Where they are, along the pipeline everybody else is on too.

      The order is the manifest's — `view_settings.record.stages` — and not the
      doctype's, which lists Rejected between Shortlisted and Hold and would
      draw the bin in the middle of the run. The board reads the same constant,
      so the two cannot disagree about what hiring looks like.

      A rejection is not a stage further along, so the strip stops filling and
      says so: everything up to where they were is done, and the word beside it
      is the ending rather than a step.
    -->
    <div
      v-if="stages.length"
      data-slot="candidate-stages"
      class="flex flex-col gap-2 border-b border-outline-gray-2 px-4 py-4 md:px-6"
    >
      <div class="flex items-center gap-2">
        <p class="text-xs text-ink-muted">{{ __('Where they are') }}</p>
        <StateBadge v-if="ending" :label="ending" :states="states" />
      </div>
      <ol class="flex flex-wrap items-center gap-1.5">
        <li
          v-for="(stage, at) in stages"
          :key="stage.label"
          class="flex items-center gap-1.5"
          :data-stage="stage.label"
          :data-reached="stage.reached ? '1' : '0'"
        >
          <span
            class="h-1.5 w-10 rounded-full"
            :class="stage.reached ? reachedClass : 'bg-surface-gray-3'"
          />
          <span
            class="text-xs"
            :class="stage.here ? 'text-ink-primary' : 'text-ink-muted'"
          >{{ stage.label }}</span>
          <Icon
            v-if="at < stages.length - 1"
            name="lucide-chevron-right"
            class="size-3 shrink-0 text-ink-gray-4"
          />
        </li>
      </ol>
    </div>

    <!--
      What the interviews said, which is the whole of the decision and is four
      clicks away in every HR product we have looked at.

      A score per interview and the average under it: one strong round and one
      weak one is a different conversation from two middling ones, and an
      average alone cannot tell you which you have got.
    -->
    <div
      v-if="interviews.length"
      data-slot="candidate-interviews"
      class="flex flex-col gap-2 border-b border-outline-gray-2 px-4 py-4 md:px-6"
    >
      <p class="text-xs text-ink-muted">{{ __('Interviews') }}</p>
      <ul class="flex flex-col gap-2">
        <li
          v-for="one in interviews"
          :key="one.name"
          class="flex items-center gap-3 text-sm"
        >
          <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a row of text that opens the interview; a <Button> here brings a ground and a height into a line that has to read as prose -->
          <button
            type="button"
            class="min-w-0 flex-1 truncate rounded-4 text-start text-ink-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-outline-gray-8"
            @click="emit('open', { screen: INTERVIEWS, name: one.name })"
          >{{ one.label }}</button>
          <span class="shrink-0 text-xs tabular-nums text-ink-muted">{{ one.when }}</span>
          <Rating v-if="one.rating" :model-value="one.rating" :max="STARS" disabled />
          <span v-else class="shrink-0 text-xs text-ink-gray-4">{{ __('Not scored') }}</span>
          <StateBadge
            v-if="one.state"
            :label="one.state"
            :states="interviewStates"
          />
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Icon, Rating } from '@/ui'
import FactRow from '@/modules/onespace/components/people/FactRow.vue'
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'
import { cellText } from '@/modules/onespace/lib/screen/cells'
import { fieldSpec } from '@/modules/onespace/lib/screen/fields'
import { STARS, starsOf } from '@/modules/onespace/lib/screen/rating'
import * as related from '@/modules/onespace/lib/screen/related'
import { date as onDate } from '@/shared/lib/runtime/format'
import { session } from '@/modules/onespace/lib/shell/session'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** The record, as the form holds it. */
  record: { type: Object, required: true },
  /** What the screen says about itself — columns, states, title field. */
  spec: { type: Object, default: () => ({}) },
  /** The same declaration a showcase reads: eyebrow, badge, facts, tabs. */
  showcase: { type: Object, default: () => ({}) },
  title: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  revision: { type: Number, default: 0 },
  canWrite: { type: Boolean, default: false },
})

const emit = defineEmits(['open'])

/** How many facts a band carries. `showcase.FACTS`, and the same four. */
const FACTS = 4

/** HRMS's own field for how somebody scored, which the band draws as stars. */
const RATING = 'applicant_rating' 

/** Where the two lines on this page navigate to. Screens of this same space. */
const OPENINGS = 'openings'
const INTERVIEWS = 'interviews'

/** How many rounds a page shows before it is the tab's job. */
const ROUNDS = 6

/**
 * The one status that is not a place on the pipeline.
 *
 * An ending rather than a step — a candidate is not "further along" for having
 * been turned down — so the strip stops at wherever they had got to and the
 * word is drawn beside the heading instead of on the run.
 *
 * **Hold is not one of these.** It reads like a pause and is a stage: the
 * manifest puts it after Shortlisted and before anybody decides, because that
 * is where it happens. Taking it out of the strip would draw somebody on hold
 * as though they had not been shortlisted.
 */
const ENDINGS = ['Rejected']

const formats = computed(() => session.formats || {})
const columns = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const states = computed(() => props.spec?.states || [])

const column = (fieldname) =>
  columns.value.find((one) => one.fieldname === fieldname)

const linked = (fieldname) => props.record?._links?.[fieldname]

const initial = computed(() => {
  const name = (props.title || '').trim()
  if (!name) return '?'
  const first = typeof Intl?.Segmenter === 'function'
    ? [...new Intl.Segmenter().segment(name)][0]?.segment
    : name[0]
  return (first || '?').toUpperCase()
})

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

/**
 * The opening they applied for, off whichever Link the doctype has.
 *
 * Named here rather than read off the showcase's facts, because a fact is an
 * attribute and this is the record's subject: an application is *about* an
 * opening, the way a direct report is about a manager.
 */
const openingField = computed(() =>
  column('job_title') ? 'job_title' : '',
)

const opening = computed(() => {
  const field = openingField.value
  const value = field ? props.record?.[field] : ''
  if (!value) return null
  return { value, label: linked(field)?.label || value }
})

/** Whole stars, out of five, from Frappe's fraction of one. */
const rating = computed(() => starsOf(props.record?.[RATING]))

const ratingLabel = computed(() =>
  __('{0} of {1}', [String(rating.value), String(STARS)]),
)

/**
 * The facts, minus the two the band already says.
 *
 * A manifest written for the showcase lists the opening and the rating among
 * its four, because over there both are just values on a card. Here one is the
 * line under the name and the other is the stars beside it, and printing either
 * twice eight pixels apart is what makes a bespoke page look like a generic one
 * with extra steps.
 */
const said = computed(() => [
  opening.value ? openingField.value : '',
  rating.value ? RATING : '',
].filter(Boolean))

const facts = computed(() =>
  (props.showcase?.facts || [])
    .filter((fact) => !said.value.includes(fact.field))
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
        // column and wrong here: this row treats "nothing" as a state of its
        // own and draws it quieter than an answer.
        text: text === '—' ? '' : text,
        icon: fieldSpec(found).icon,
      }
    }),
)

/** Which of the declared stages is theirs, if any. */
const statusField = computed(() => props.spec?.status_field || 'status')
const standing = computed(() => String(props.record?.[statusField.value] || ''))

/** An ending, drawn beside the heading rather than on the run. */
const ending = computed(() =>
  ENDINGS.includes(standing.value) ? standing.value : '',
)

/**
 * The pipeline, filled up to wherever they got to.
 *
 * An ending is not a position on it, so somebody rejected after a shortlisting
 * keeps the shortlisting filled — which is the honest drawing: the strip says
 * how far they came, and the badge beside it says how it finished.
 */
const stages = computed(() => {
  const declared = (props.spec?.view_settings?.record?.stages || [])
    .filter((one) => !ENDINGS.includes(one))
  if (!declared.length) return []

  const at = declared.indexOf(standing.value)
  // Rejected or held: everything they had reached, which is one short of
  // wherever the ending interrupted. Not knowable from the status alone, so
  // the honest answer is "at least the first", which is applying at all.
  const reached = at >= 0 ? at : (ending.value ? 0 : -1)

  return declared.map((label, index) => ({
    label,
    reached: index <= reached,
    here: index === at,
  }))
})

const reachedClass = computed(() =>
  ending.value ? 'bg-surface-gray-5' : 'bg-surface-green-5',
)

const interviewStates = ref([])
const interviews = ref([])

/**
 * The rounds, through the same loader the showcase's tabs use.
 *
 * A record view may read the workspace and only through the engine's own
 * endpoints, so the space, the permissions and the filter are checked where
 * every list checks them. The tab declaring interviews is where the whole list
 * lives; this is the six that fit above it.
 */
const loadInterviews = async () => {
  interviews.value = []
  const name = props.record?.name
  if (!name) return

  const found = await related.loadChildren({
    spaceCode: props.spaceCode,
    screen: INTERVIEWS,
    field: 'job_applicant',
    name,
    formats: formats.value,
    limit: ROUNDS,
  })
  if (props.record?.name !== name) return

  interviewStates.value = found.spec?.states || []
  interviews.value = (found.rows || []).map((row, at) => ({
    name: row.name,
    label: String(row.interview_type || found.children[at]?.label || row.name),
    when: row.scheduled_on ? onDate(row.scheduled_on) : '',
    rating: starsOf(row.average_rating),
    state: String(row.status || ''),
  }))
}

watch(
  () => [props.record?.name, props.revision],
  loadInterviews,
  { immediate: true },
)
</script>
