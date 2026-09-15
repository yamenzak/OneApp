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
      <!--
        The list this record came out of, as a control rather than a crumb.

        A record used to replace the trail — `🏠 / Ahmad` — so the list you
        were working through was gone from the page and from the address, and
        the only way back was the record's own Close. The pane answered that by
        keeping the list on screen and taking half the width to do it;
        `docs/DESKTOP.md` says why that stopped paying for itself. This is the
        other answer: the place is named again, and pressing it opens the list
        in a window over the record rather than navigating away from it.

        A chevron and not an arrow. The chevron is what this product's other
        openers wear — the switcher, the view menu — and an arrow would promise
        navigation, which is the one thing this does not do.
      -->
      <template v-if="subject && screenLabel" #waypoint>
        <Button
          variant="ghost"
          size="sm"
          :label="screenLabel"
          icon-right="lucide-chevron-down"
          :tooltip="__('{0}, without leaving this one', [screenLabel])"
          data-slot="crumb-peek"
          @click="emit('peek')"
        />
      </template>

      <template v-if="subject" #subject>
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
      <!-- Gone while a record is open: the record *is* the area now, and the
           view of a list nobody can see is a control about nothing. The
           waypoint beside it is how the list comes back. -->
      <ViewSwitcher
        v-if="spec?.doctype && !record"
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
        Always here, because a record is always the whole area: the trail on
        this line is about it, and these belong at the end of that line.
      -->
      <div :id="MERGE_TARGET" class="flex shrink-0 items-center gap-2" />

      <!--
        New stands down while a record fills the page: the list it would add a
        row to is not on screen.
      -->
      <Button
        v-if="spec?.can_create && !record"
        variant="solid"
        icon-left="lucide-plus"
        :label="__('New')"
        @click="emit('create')"
      />
    </div>

  </PageHeader>
</template>

<script setup>
import { computed } from 'vue'
import { PageHeader, Button } from '@/ui'
import Trail from '@/shared/components/Trail.vue'
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
  // The open record, which is what decides between the switcher and the chip —
  // and whether New stands down, because the list it would add a row to is not
  // on screen while one is open.
  record: { type: Object, default: null },
  // Unsaved changes, and a save in flight — the switcher's own two states.
  dirty: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  // Everything `useSavedViews` returns. One prop rather than nine re-emitted
  // events: the switcher's menu *is* that composable.
  views: { type: Object, required: true },
})

const emit = defineEmits(['create', 'peek'])

/**
 * The bar was two trails for a while — one over the list and one exactly as
 * wide as the pane beside it, because a header that is not the width of the
 * panel it belongs to reads as belonging to something else. There is one panel
 * now, so there is one trail. `docs/DESKTOP.md`.
 */

// The screen's own name, which is the last crumb the list's trail carries. Read
// off the crumbs rather than passed again: two props for one string is two
// places for it to be wrong.
const screenLabel = computed(() => props.crumbs[props.crumbs.length - 1]?.label || '')
</script>
