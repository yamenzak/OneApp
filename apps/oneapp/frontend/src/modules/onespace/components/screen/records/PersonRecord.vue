<template>
  <!--
    A record that is a person.

    The first entry in the record-view library that is not a project's hero —
    see `lib/screen/recordViews.js`. A person is a face, a job title, who they
    answer to and who answers to them, and four facts. The rest of what is
    known about them is the form, and it stays where it has always been: in the
    Details tab under this.

    It reads the same declaration a showcase does — eyebrow, badge, facts,
    children — deliberately. The vocabulary is shared and the *layout* is what
    differs, which is the whole argument for a library: a second people-shaped
    doctype in some other space says `"record": {"as": "person"}` and gets
    this, with no new words to learn and no second component to keep in step.
  -->
  <section data-slot="person-record" class="-mx-4 -mt-4 mb-4 flex flex-col">
    <!--
      The band. A portrait rather than a photograph across the top: a building
      fills a hero and a person does not, and a face stretched to 400px of
      bleed is the thing that makes an HR product look like a CRM.
    -->
    <div
      class="flex flex-col gap-4 border-b border-outline-gray-2 bg-surface-gray-1 px-4 py-5 md:flex-row md:items-center md:gap-6 md:px-6"
    >
      <Avatar
        :image="portrait"
        :label="title"
        shape="circle"
        :size="compact ? '2xl' : '3xl'"
        class="shrink-0"
      />

      <div class="flex min-w-0 flex-1 flex-col gap-1">
        <p
          v-if="eyebrow"
          data-slot="person-eyebrow"
          class="truncate text-sm text-ink-muted"
        >{{ eyebrow }}</p>
        <div class="flex min-w-0 flex-wrap items-center gap-2">
          <h2
            data-slot="person-name"
            class="min-w-0 truncate text-xl-semibold text-ink-primary"
          >{{ title }}</h2>
          <StateBadge v-if="badge" :label="badge" :states="states" />
        </div>

        <!--
          Who they answer to, as a line rather than as one of the facts below.
          A reporting line is a *relationship* and the facts are attributes, and
          putting a person's manager in the same row as their branch is how an
          org chart stops being visible in a product that has one.
        -->
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a line of prose under the name that happens to navigate; <Button> brings a height, a padding and a hover ground, and this has to sit in the run of text -->
        <button
          v-if="manager"
          type="button"
          data-slot="person-manager"
          class="mt-1 flex w-fit items-center gap-2 rounded-4 py-0.5 text-sm text-ink-secondary hover:text-ink-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-outline-gray-8"
          @click="emit('open', { screen, name: manager.value })"
        >
          <Icon name="lucide-corner-left-up" class="size-3.5 shrink-0 text-ink-muted" />
          <span class="truncate">{{ __('Reports to {0}', [manager.label]) }}</span>
        </button>
      </div>

      <!--
        Their people, as faces. The same `children` declaration the showcase
        draws as a strip of cards — a card per direct report is a filing
        cabinet, and eight faces is an answer.
      -->
      <div
        v-if="reports.length"
        data-slot="person-reports"
        class="flex shrink-0 flex-col items-start gap-1.5 md:items-end"
      >
        <p class="text-xs text-ink-muted">{{ reportsLabel }}</p>
        <AvatarStack :people="reportFaces" :limit="6" slot-name="report" />
      </div>
    </div>

    <!--
      The facts, in a quiet row under the band rather than in cards over it.
      Four at most, which is `showcase.FACTS`, and they wrap rather than
      scrolling: a phone gets two rows of two.
    -->
    <dl
      v-if="facts.length"
      data-slot="person-facts"
      class="grid grid-cols-2 gap-x-6 gap-y-3 border-b border-outline-gray-2 px-4 py-3 md:grid-cols-4 md:px-6"
    >
      <div v-for="fact in facts" :key="fact.field" class="flex min-w-0 flex-col">
        <dt class="truncate text-xs text-ink-muted">{{ fact.label }}</dt>
        <dd class="truncate text-base text-ink-secondary">{{ fact.text || '—' }}</dd>
      </div>
    </dl>

  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Avatar, Icon } from '@/ui'
import AvatarStack from '@/modules/onespace/components/screen/fields/AvatarStack.vue'
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'
import { cellText } from '@/modules/onespace/lib/screen/cells'
import * as related from '@/modules/onespace/lib/screen/related'
import { session } from '@/modules/onespace/lib/shell/session'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** The record, as the form holds it. */
  record: { type: Object, required: true },
  /** What the screen says about itself — columns, states, image field. */
  spec: { type: Object, default: () => ({}) },
  /**
   * The same declaration a showcase reads. Shared on purpose: see the comment
   * at the top of this file.
   */
  showcase: { type: Object, default: () => ({}) },
  title: { type: String, default: '' },
  /** Opened over a list rather than on a page of its own. */
  compact: { type: Boolean, default: false },
  /** Bumped by the host when something was added from outside this component,
   *  which it has no other way to hear about. */
  revision: { type: Number, default: 0 },
})

const emit = defineEmits(['open'])

// Enough faces to know who somebody's team is. Past this it is a list, and the
// list is the tab the children declaration already names.
const FACES = 8

const columns = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const states = computed(() => props.spec?.states || [])
const formats = computed(() => session.data?.formats || {})

const column = (fieldname) => columns.value.find((one) => one.fieldname === fieldname)

/** What a Link on this record is called, rather than what it is keyed by. */
const linked = (field) => props.record?._links?.[field] || null

/** The doctype's own answer to "which field is the face of this". */
const portrait = computed(() => {
  const field = props.spec?.image_field
  return field ? props.record?.[field] || '' : ''
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
 * The facts, minus the one the line above already says.
 *
 * A manifest written for the showcase lists `reports_to` among its four,
 * because over there a manager is just another number on a card. Here it is the
 * reporting line under the name, and printing it twice — once as a relationship
 * and once as an attribute, eight pixels apart — is the sort of thing that
 * makes a bespoke page look like a generic one with extra steps.
 */
const facts = computed(() =>
  (props.showcase?.facts || [])
    .filter((fact) => !(manager.value && fact.field === managerField.value))
    .map((fact) => {
      const found = column(fact.field)
      return {
        field: fact.field,
        label: fact.label || found?.label || fact.field,
        text: found
          ? cellText(found, props.record?.[fact.field], formats.value, linked(fact.field))
          : '',
      }
    }),
)

/**
 * Who this person reports to, off the field the children declaration already
 * names — the same Link, read the other way round. A manifest that says "the
 * people under this one hang off `reports_to`" has also said which field points
 * up, and asking for it twice would be two words for one fact.
 */
const managerField = computed(() => props.showcase?.children?.field || '')

const manager = computed(() => {
  const field = managerField.value
  const value = field ? props.record?.[field] : ''
  if (!value) return null
  // `_links` holds `_link_row`'s shape — `{value, label, …}` — so the label is
  // a property of it and not the thing itself. Printed raw it reads
  // "Reports to [object Object]", which is what it did.
  return { value, label: linked(field)?.label || value }
})

const children = ref([])

/**
 * Their people, through the same loader the showcase uses — which is the rule
 * that matters: a record view may read the workspace, and only through the
 * engine's own endpoints, so the space, the permissions and the filter are checked where
 * every other list checks them.
 */
const loadReports = async () => {
  children.value = []
  const asked = props.showcase?.children
  if (!asked) return
  const found = await related.loadChildren({
    spaceCode: props.spaceCode,
    screen: asked.screen,
    field: asked.field,
    name: props.record?.name,
    formats: formats.value,
    limit: FACES,
  })
  children.value = found.children
}

watch(
  () => [props.record?.name, props.showcase, props.revision],
  loadReports,
  { immediate: true, deep: true },
)

const reports = computed(() => children.value.slice(0, FACES))
const reportsLabel = computed(() => props.showcase?.children?.label || __('Reports'))

/** The faces, in the shape `AvatarStack` reads: value, label, image. */
const reportFaces = computed(() =>
  reports.value.map((one) => ({
    value: one.name,
    label: one.label || one.name,
    image: one.image || '',
  })),
)
</script>
