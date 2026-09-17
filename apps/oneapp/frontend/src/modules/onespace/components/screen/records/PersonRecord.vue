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
  <RecordPage name="person">
    <!--
      The band. A portrait rather than a photograph across the top: a building
      fills a hero and a person does not, and a face stretched to 400px of
      bleed is the thing that makes an HR product look like a CRM.
    -->
    <RecordHead
      :eyebrow="eyebrow"
      eyebrow-slot="person-eyebrow"
      :title="title"
      title-slot="person-name"
      :badge="badge"
      :states="states"
    >
      <template #portrait>
      <!--
        A portrait, which is not an avatar. An avatar is an identity marker in a
        row and tops out at 46 pixels; this is the subject of the page. So it is
        drawn here rather than through `Avatar`, and the one thing it borrows is
        the initial-on-a-tint fallback, because a page with a grey square where
        a face goes reads as a broken image rather than as a record with no
        photograph yet.
      -->
      <div class="relative shrink-0" data-slot="person-portrait">
        <img
          v-if="portrait"
          :src="portrait"
          :alt="title"
          class="size-24 rounded-full object-cover ring-1 ring-outline-gray-2 md:size-28"
        >
        <div
          v-else
          class="flex size-24 items-center justify-center rounded-full bg-surface-gray-2 text-4xl text-ink-muted ring-1 ring-outline-gray-2 md:size-28"
          aria-hidden="true"
        >{{ initial }}</div>

        <!--
          And the one control it needs, on the portrait rather than three lines
          below it: setting somebody's photograph is a thing you do *to the
          face*, and the Meta tab's copy of this is where you go when you did
          not find it here.
        -->
        <Dropdown v-if="canWrite" :options="portraitOptions">
          <Button
            variant="subtle"
            data-slot="person-portrait-edit"
            icon="lucide-camera"
            class="!absolute bottom-0 end-0 !rounded-full shadow-raised"
            :label="portrait ? __('Change the photograph') : __('Add a photograph')"
            :tooltip="portrait ? __('Change the photograph') : __('Add a photograph')"
          />
        </Dropdown>
      </div>

      <!--
        The picker every attach surface in the product uses, so a photograph can
        come from the workspace's own files as easily as from a device — which
        is most of why the Drive was built.
      -->
      <FilePicker
        v-if="canWrite"
        v-model="picking"
        kind="Image"
        :attached-to="{
          doctype: spec?.doctype || '',
          docname: record?.name || '',
          fieldname: spec?.image_field || '',
        }"
        @picked="(file) => emit('update:image', file.file_url)"
      />

      </template>

      <template #badges>
        <!--
            Where they are *now*, which is the question this page is opened for
            and which no field on an Employee answers. Four HRMS doctypes,
            ranked once on the server — `oneapp/onehr/presence.py`.

            Beside the employment status rather than instead of it: Active and
            In are different sentences, and a page that showed only the second
            would have nothing to say about somebody who left in March.
          -->
        <Badge
          v-if="presence"
          data-slot="person-presence"
          :theme="look.theme"
          variant="subtle"
          :label="presenceLabel"
        />
      </template>

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

      <!--
        Their people, as faces. The same `children` declaration the showcase
        draws as a strip of cards — a card per direct report is a filing
        cabinet, and eight faces is an answer.
      -->
      <template #aside>
        <div
          v-if="reports.length"
          data-slot="person-reports"
          class="flex shrink-0 flex-col items-start gap-1.5 md:items-end"
        >
          <p class="text-xs text-ink-muted">{{ reportsLabel }}</p>
          <AvatarStack :people="reportFaces" :limit="6" slot-name="report" />
        </div>
      </template>
    </RecordHead>

    <!--
      The facts, in a quiet row under the band rather than in cards over it.
      Four at most and they wrap, which is `FactRow` — the same row the
      candidate page draws under the same kind of band.
    -->
    <FactRow :facts="facts" slot-name="person-facts" />

    <!--
      Their last eight weeks, and the leave they have left.

      On the record rather than on the screen's dashboard, and the line is
      worth stating because it is the one everybody gets wrong: a screen's
      dashboard measures the *workforce* — how many are on leave this week, the
      attendance rate by department — and a dashboard over one row is a number
      with nothing to compare it to. So the population is answered there and the
      person is answered here, and neither answers the other's question twice.

      A row of days rather than a chart of them: fifty-six values with no axis
      worth drawing is a strip, and a run of red in the third week is the thing
      somebody is looking for.
    -->
    <div
      v-if="days.length || balance.length"
      data-slot="person-year"
      class="flex flex-col gap-4 border-b border-outline-gray-2 px-4 py-4 md:flex-row md:items-start md:gap-10 md:px-6"
    >
      <DayStrip :days="days" :weeks="weeks" />

      <!--
        And what is left, per type. Beside the strip rather than under it: how
        a person has been and what they are owed are read together, and two
        bands is two headings for one answer.
      -->
      <LeaveBalance :balance="balance" :label="__('Leave left')" />
    </div>
  </RecordPage>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Badge, Button, Dropdown, Icon } from '@/ui'
import AvatarStack from '@/modules/onespace/components/screen/fields/AvatarStack.vue'
import DayStrip from '@/modules/onespace/components/people/DayStrip.vue'
import FactRow from '@/modules/onespace/components/people/FactRow.vue'
import LeaveBalance from '@/modules/onespace/components/people/LeaveBalance.vue'
import FilePicker from '@/modules/onestorage/components/FilePicker.vue'
import RecordHead from '@/modules/onespace/components/screen/records/RecordHead.vue'
import RecordPage from '@/modules/onespace/components/screen/records/RecordPage.vue'
import { cellText } from '@/modules/onespace/lib/screen/cells'
import { fieldSpec } from '@/modules/onespace/lib/screen/fields'
import { presenceLook, presenceSince } from '@/modules/onespace/lib/screen/presence'
import * as related from '@/modules/onespace/lib/screen/related'
import { workspace } from '@/shared/lib/workspace'
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
  /** Whether this reader may change the record, which decides whether the
   *  portrait offers a control at all. */
  canWrite: { type: Boolean, default: false },
})

// `update:image` goes to the host, which owns the form and the save loop — a
// record view places the control and never writes through it.
const emit = defineEmits(['open', 'update:image'])

const picking = ref(false)

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

/**
 * The initial, for a record with no photograph.
 *
 * `Intl.Segmenter` where there is one: a name in Arabic or an emoji is not one
 * UTF-16 code unit, and `title[0]` on either is half a character.
 */
const initial = computed(() => {
  const name = (props.title || '').trim()
  if (!name) return '?'
  const first = typeof Intl?.Segmenter === 'function'
    ? [...new Intl.Segmenter().segment(name)][0]?.segment
    : name[0]
  return (first || '?').toUpperCase()
})

/** Set, replace, or take away — the three things a photograph can have done. */
const portraitOptions = computed(() => [
  {
    label: props.portraitLabel || (portrait.value ? __('Replace it') : __('Add a photograph')),
    icon: 'lucide-image-plus',
    onClick: () => { picking.value = true },
  },
  ...(portrait.value
    ? [{
      label: __('Remove it'),
      icon: 'lucide-trash-2',
      onClick: () => emit('update:image', ''),
    }]
    : []),
])

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

/**
 * Where they are now, and how they have been.
 *
 * Two calls because they are two questions with two lifetimes: presence is
 * about this minute and history is about two months, and merging them would
 * mean re-reading eight weeks of attendance to find out whether somebody has
 * since badged out. Both silent — a workspace without HRMS answers nothing and
 * this band simply does not draw.
 */
const presence = ref(null)
const days = ref([])
const balance = ref([])
const weeks = ref(0)

const look = computed(() => presenceLook(presence.value))

/**
 * The pill's words: the state, and the time it started where there is one.
 *
 * "In · 09:41" rather than "In": the hour is most of what somebody wants from
 * this, and a leave type or a shift name goes in the same place for the states
 * that have one instead.
 */
const presenceLabel = computed(() => {
  const found = presence.value
  if (!found) return ''
  const at = presenceSince(found)
  const extra = at || found.detail || ''
  return extra ? `${look.value.label} · ${extra}` : look.value.label
})

const loadPerson = async () => {
  presence.value = null
  days.value = []
  balance.value = []
  const name = props.record?.name
  if (!name) return

  const [now, past] = await Promise.all([
    workspace.presence(name),
    workspace.personHistory(name),
  ])
  // Guard the assignment rather than the call: a reader who clicked through
  // three people while the first was in flight should not get the first one's
  // days under the third one's name.
  if (props.record?.name !== name) return
  presence.value = now?.state ? now : null
  days.value = past?.days || []
  balance.value = past?.balance || []
  weeks.value = past?.weeks || 0
}

watch(() => props.record?.name, loadPerson, { immediate: true })
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
