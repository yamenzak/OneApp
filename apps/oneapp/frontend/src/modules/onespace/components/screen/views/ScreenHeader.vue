<!--
  Where the reader is, and the two things they can do about it from up here.

  The trail is Frappe CRM's, and its shape is the argument: a house for the
  space, the screen, and then the thing you are looking at — the view, or the
  record when one is open.

  A component rather than a block in `ScreenHost` because it is the one part of
  that page with no state of its own.
-->
<template>
  <PageHeader>
    <Trail :items="crumbs">
      <!--
        A record is a record wherever it is shown: the same face, name and id the
        list cell and the link picker draw, with the status beside the name.

        The subject slot rather than a crumb, for the same reason the view
        switcher is beside the trail: a crumb is a line of text, and this is a
        block two lines tall.
      -->
      <template v-if="subject && !split" #subject>
        <RecordChip :record="subject">
          <template #badge>
            <!-- The colours and glyphs are the doctype's own Document States,
                 so a status is not one colour here and another there. -->
            <StateBadge
              v-if="statusValue"
              data-slot="record-status"
              :label="statusValue"
              :states="spec?.states || []"
            />
            <!-- And where the framework stands on it, which is a different
                 question from the doctype's own status field. Absent unless the
                 doctype is submittable or runs on a workflow. -->
            <StateBadge
              v-if="docState"
              data-slot="doc-state"
              :label="docState.label"
              :theme="docState.theme"
            />
          </template>
        </RecordChip>
      </template>

      <!-- Which view of the screen this is, and every other view of it.
           Beside the trail rather than in it: it is a control. -->
      <!-- Shown beside the record when the two are side by side: the list is
           still there, still in a view, and the trail over it should say which
           one. Hidden only when the record has taken the whole area. -->
      <ViewSwitcher
        v-if="spec?.doctype && (!record || split)"
        :layouts="spec.layouts || []"
        :active="spec.layout || ''"
        :view-label="viewLabel"
        :can-share="!!spec.can_share"
        :dirty="dirty"
        :hidden="spec.hidden || 0"
        :busy="saving"
        @open="views.openLayout"
        @save-as="views.saveAs"
        @save-into="views.saveIntoLayout"
        @rename="views.renameLayout"
        @share="views.shareLayout"
        @default="views.defaultLayout"
        @remove="views.deleteLayout"
        @hide="views.hideLayout"
        @show="views.showLayouts"
      />
    </Trail>

    <!--
      In the default slot, not a `#right` one: PageHeader has exactly one slot
      and lays it out as a `justify-between` row. It spent this long in a slot
      that does not exist, rendering nowhere — `test_no_unknown_slots` now
      catches the shape that hid it.
    -->
    <div class="flex shrink-0 items-center gap-2">
      <!--
        Where an open record's own controls land — see `merged` in `RecordView`.
        Here when the record is the whole area; over in the pane's own block
        when it is a column beside the list, so that each panel's controls sit
        above that panel.
      -->
      <div v-if="!split" :id="MERGE_TARGET" class="flex shrink-0 items-center gap-2" />

      <!--
        New stands down while a record fills the page: the list it would add a
        row to is not on screen.
      -->
      <Button
        v-if="spec?.can_create && !page"
        variant="solid"
        icon-left="lucide-plus"
        :label="__('New')"
        @click="emit('create')"
      />
    </div>

    <!--
      The pane's own half of the bar, exactly as wide as the pane under it and
      starting where it starts. Two panels, two trails: the left one says which
      view of the list you are looking at, this one says which record — and a
      header that is not the width of the panel it belongs to reads as
      belonging to something else.
    -->
    <div
      v-if="split"
      data-slot="pane-header"
      class="ms-2 flex shrink-0 items-center gap-2 ps-3"
      :style="{ width: `${paneWidth}px` }"
    >
      <span class="shrink-0 text-base text-ink-muted">{{ screenLabel }}</span>
      <span class="shrink-0 text-base text-ink-gray-4" aria-hidden="true">/</span>
      <div class="flex min-w-0 items-center">
        <RecordChip :record="subject">
          <template #badge>
            <StateBadge
              v-if="statusValue"
              data-slot="record-status"
              :label="statusValue"
              :states="spec?.states || []"
            />
            <StateBadge
              v-if="docState"
              data-slot="doc-state"
              :label="docState.label"
              :theme="docState.theme"
            />
          </template>
        </RecordChip>
      </div>
      <div :id="MERGE_TARGET" class="ms-auto flex shrink-0 items-center gap-1" />
    </div>
  </PageHeader>
</template>

<script setup>
import { computed } from 'vue'
import { PageHeader, Button } from '@/ui'
import Trail from '@/shared/components/Trail.vue'
import { useRecordPane } from '@/modules/onespace/lib/screen/pane'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import RecordChip from '@/modules/onespace/components/screen/record/RecordChip.vue'
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'
import ViewSwitcher from '@/modules/onespace/components/screen/views/ViewSwitcher.vue'
import { MERGE_TARGET } from '@/modules/onespace/lib/screen/surfaces'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  // The screen, for what the switcher offers and whether New is allowed.
  spec: { type: Object, default: null },
  // The trail, from `composables/useCrumbs.js` — one root for every surface.
  crumbs: { type: Array, default: () => [] },
  // And what it is looking at, from `composables/useSubject.js`. A record is
  // not a crumb, so the two come from different places — §C1.
  subject: { type: Object, default: null },
  viewLabel: { type: String, default: '' },
  statusValue: { type: String, default: '' },
  docState: { type: Object, default: null },
  // The open record, which is what decides between the switcher and the chip.
  record: { type: Object, default: null },
  // Whether it fills the page, in which case New stands down.
  page: { type: Boolean, default: false },
  // Unsaved changes, and a save in flight — the switcher's own two states.
  dirty: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  // Everything `useSavedViews` returns. One prop rather than nine re-emitted
  // events: the switcher's menu *is* that composable.
  views: { type: Object, required: true },
})

const emit = defineEmits(['create'])

const phone = useIsMobile()
const { width: paneWidth } = useRecordPane()

/**
 * Whether the bar is two trails rather than one.
 *
 * Only when the record is genuinely a column beside the list: as a page it has
 * the whole area and one trail is the truth, and on a phone there is one
 * surface at a time.
 */
const split = computed(() => !!props.record && !props.page && !phone.value)

// The screen's own name, which is the last crumb the list's trail carries. Read
// off the crumbs rather than passed again: two props for one string is two
// places for it to be wrong.
const screenLabel = computed(() => props.crumbs[props.crumbs.length - 1]?.label || '')
</script>
