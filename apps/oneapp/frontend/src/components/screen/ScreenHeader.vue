<!--
  Where the reader is, and the two things they can do about it from up here.

  The trail is Frappe CRM's, and its shape is the argument: a house for the
  space, the screen, and then the thing you are actually looking at — which is
  the view, or the record when one is open.

  It is a component rather than a block in `ScreenHost` because it is the one
  part of that page with no state of its own: everything here is read from the
  screen or handed over by `useSavedViews`, and the only decision it makes is
  which of the last two elements to draw.
-->
<template>
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center">
      <Breadcrumbs :items="crumbs">
        <template #prefix="{ item }">
          <!--
            The name is a span, not the icon's `aria-label`: frappe-ui's Icon
            hard-codes `aria-hidden` after the attrs it forwards, which is the
            right call — an icon is decoration — and it leaves a link whose
            only content is one with no accessible name at all.
          -->
          <Tooltip v-if="item.home" :text="`${item.space} home`">
            <span class="flex items-center">
              <Icon name="lucide-house" class="size-4 text-ink-gray-5" />
              <span class="sr-only">{{ item.space }} home</span>
            </span>
          </Tooltip>
        </template>
      </Breadcrumbs>

      <!--
        A record is a record wherever it is shown: the same face, name and id
        the list cell and the link picker draw, from the same component — with
        the status beside the name, because "where does this stand" is the
        second thing anybody asks about a record and the first thing they look
        for.

        Its own element rather than a crumb, for the same reason the view
        switcher is one: a crumb is a line of text, and this is a block two
        lines tall.
      -->
      <div v-if="recordCrumb" class="flex min-w-0 items-center">
        <span class="mx-0.5 text-base text-ink-gray-4" aria-hidden="true">/</span>
        <RecordChip :record="recordCrumb">
          <template #badge>
            <!-- The colours and glyphs are the doctype's own Document States —
                 the same ones the cell in the list reads — so a status is not
                 one colour here and another there. The manifest says which
                 field; it does not repeat the palette. -->
            <StateBadge
              v-if="statusValue"
              data-slot="record-status"
              :label="statusValue"
              :states="spec?.states || []"
            />
            <!-- And where the framework stands on it, which is a different
                 question from the doctype's own status field and used to be
                 answered a screen-width away among the buttons. Absent unless
                 the doctype is submittable or runs on a workflow. -->
            <StateBadge
              v-if="docState"
              data-slot="doc-state"
              :label="docState.label"
              :theme="docState.theme"
            />
          </template>
        </RecordChip>
      </div>

      <!-- The last crumb, when no record is open: which view of the screen
           this is, and every other view of it. -->
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
    </nav>

    <!--
      In the default slot, not a `#right` one: PageHeader has exactly one slot
      and lays it out as a `justify-between` row, so the trail goes left and
      this goes right by being second. It spent this long in a slot that does
      not exist, rendering nowhere — `test_no_unknown_slots` now catches the
      shape that hid it.
    -->
    <div class="flex shrink-0 items-center gap-2">
      <!--
        Where an open record's own controls land when it is a page — see
        `merged` in `RecordView`. Empty the rest of the time, and an empty flex
        child costs nothing; rendered unconditionally so the teleport always has
        somewhere to go rather than racing the condition that creates it.
      -->
      <div :id="MERGE_TARGET" class="flex shrink-0 items-center gap-2" />

      <!--
        New stands down while a record fills the page. The list it would add a
        row to is not on screen, so the button is offering to make a second
        thing in a place that is showing exactly one.
      -->
      <Button
        v-if="spec?.can_create && !page"
        variant="solid"
        icon-left="lucide-plus"
        label="New"
        @click="emit('create')"
      />
    </div>
  </PageHeader>
</template>

<script setup>
import { PageHeader, Breadcrumbs, Icon, Tooltip, Button } from '@/ui'
import RecordChip from './RecordChip.vue'
import StateBadge from './StateBadge.vue'
import ViewSwitcher from './ViewSwitcher.vue'
import { MERGE_TARGET } from '../../lib/surfaces'

defineProps({
  // The screen, for what the switcher offers and whether New is allowed.
  spec: { type: Object, default: null },
  // The trail itself, and the record at the end of it — both from `useCrumbs`,
  // which is also where `viewLabel`, `statusValue` and `docState` come from.
  crumbs: { type: Array, default: () => [] },
  recordCrumb: { type: Object, default: null },
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
  // events: the switcher's menu *is* that composable, and a header that
  // forwards each of its verbs one at a time is thirty lines of plumbing that
  // says nothing.
  views: { type: Object, required: true },
})

const emit = defineEmits(['create'])
</script>
