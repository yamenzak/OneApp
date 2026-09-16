<template>
  <!-- `frame` is what `upright` measures: how wide this record actually is,
       which is not a question about the viewport. -->
  <div ref="frame" class="flex h-full min-h-0 flex-col">
    <!--
      Who this is, and what you can do to it.

      On a desktop the line above already names the record — the trail on a
      page, the title bar in a window — so the controls go onto it and this band
      does not render at all. Only a phone, which has neither, keeps it.
    -->
    <header
      v-if="!merged"
      class="flex shrink-0 items-center gap-2 border-b border-outline-gray-1 px-4 py-3"
    >
      <RecordChip
        v-if="names"
        data-slot="record-identity"
        :record="identity"
        class="min-w-0 flex-1"
      >
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
      <!-- Who else has this open: Frappe's own open-doc room, which the
           server only admits a reader who may see the document to. -->
      <div v-if="others.length" class="ms-auto flex shrink-0 items-center">
        <AvatarStack :people="watching" slot-name="viewer" />
      </div>

      <RecordControls
        v-if="!windowed"
        :class="!others.length && 'ms-auto'"
        :record="record"
        :spec="spec"
        :space-code="spaceCode"
        :screen="screen"
        :extras="extras"
        :can-write="canWrite"
        :dirty="dirty"
        :saving="saving"
        :banded="banded"
        @save="save"
        @close="emit('close')"
        @reload="emit('reload')"
        @renamed="emit('renamed', $event)"
      />
    </header>

    <!--
      The same row, on the page header's line. `defer` because the target is
      rendered by the host in the same pass as this.
    -->
    <Teleport v-if="merged" defer :to="`#${target}`">
      <!--
        Where this document stands, in a window only.

        On a page the trail carries these beside the name and the band carries
        the pipeline under it. A window has neither — its title bar says the
        name and nothing else, and a preview that will not say whether the
        invoice in it was submitted is a preview of the wrong half. It is also
        the one thing a window lost by becoming read-only, so it is the one
        thing worth putting back.
      -->
      <template v-if="windowed">
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

      <AvatarStack v-if="others.length" :people="watching" slot-name="viewer" />

      <!--
        What this record *is* — who made it, who has it, what it is tagged.
        A popover off the line that already names it, because that is what it is
        about: it was a *tab*, which is the strangest place for it, since it is
        not somewhere you go but a paragraph about the thing you are looking at.

        Not a column either. A sidebar drawn always to hold something read
        occasionally is three hundred pixels the form does not get —
        `RecordBand.vue` has the arithmetic.
      -->
      <Popover :bare="true" align="end" :offset="6">
        <template #trigger="{ open }">
          <Button
            variant="ghost"
            icon="lucide-info"
            data-slot="record-about"
            :label="__('About this record')"
            :tooltip="__('About this record')"
            :class="open ? '!bg-surface-gray-3' : ''"
          />
        </template>
        <template #default>
          <Panel ground="raised" pad="normal" elevation="floating" class="max-h-overlay w-80 overflow-y-auto">
            <RecordMeta
              :record="record"
              :space-code="spaceCode"
              :screen="screen"
              :doctype="spec.doctype || ''"
              :label="identity.label"
              :image-field="spec.image_field || ''"
              :image="form[spec.image_field] || ''"
              :assigned="assigned"
              :tags="tags"
              :shares="shares"
              :files="fileCount"
              :can-write="canWrite"
              :can-rename="!!spec.can_rename && canWrite"
              @update:image="form[spec.image_field] = $event"
              @renamed="renamed"
              @assigned="assigned = $event"
              @tagged="tags = $event"
              @shared="shares = $event"
              @files="openFiles"
            />
          </Panel>
        </template>
      </Popover>

      <!--
        And the verbs — on a page only. A window draws none of them: what it
        holds is read-only, and the one control it does have is at its foot,
        away from the chrome. See `previewFoot` below.
      -->
      <RecordControls
        v-if="!windowed"
        :record="record"
        :spec="spec"
        :space-code="spaceCode"
        :screen="screen"
        :extras="extras"
        :can-write="canWrite"
        :dirty="dirty"
        :saving="saving"
        :banded="banded"
        @save="save"
        @close="emit('close')"
        @reload="emit('reload')"
        @renamed="emit('renamed', $event)"
      />
    </Teleport>

    <!-- Somebody else saved it while this was open. Said rather than done:
         the reader may be halfway through typing. -->
    <PrintDialog
      v-model="showPrint"
      :space-code="spaceCode"
      :screen="screen"
      :name="record.name"
    />

    <!-- A copy, as a draft: Frappe's Duplicate opens an unsaved form rather
         than inserting a second document. -->
    <!--
      Mounted rather than `v-if`-ed into existence. The dialog fills its form
      from `preset` in a watcher on *opening*, and a component that appears
      already open never sees that transition.
    -->
    <CreateDialog
      v-if="spec?.can_create"
      v-model="copying"
      :spec="spec"
      :space-code="spaceCode"
      :screen="screen"
      :preset="copy"
      @created="emit('open', { screen, name: $event })"
    />

    <!--
      Deleting the record you are looking at.

      It lived only in the selection bar, which meant deleting one record was:
      close it, find its row, tick the box, use the bulk bar. The verb belongs
      wherever the object is — see `ScreenActions`, which has said so about
      *declared* actions since it was written.

      The same sentence the bulk dialog uses, because it is the same fact: a
      record still linked to elsewhere is kept and named.
    -->
    <Dialog v-model="confirmDelete" :title="__('Delete this record for ever?')">
      <p class="text-p-base text-ink-secondary">
        {{ __('This cannot be undone. Anything still linked to elsewhere is kept, and named.') }}
      </p>
      <template #actions>
        <Button
          theme="red"
          variant="solid"
          :loading="deleting"
          :label="__('Delete for ever')"
          @click="remove"
        />
      </template>
    </Dialog>

    <Alert
      v-if="staleSince"
      class="mx-4 mt-3"
      theme="amber"
      :title="__('Someone else changed this')"
    >
      <template #description>
        {{ __('It was saved {0}. Reloading takes what is on the server; anything typed here and not saved goes with it.', [when(staleSince)]) }}
      </template>
      <template #actions>
        <Button :label="__('Reload it')" @click="emit('reload')" />
      </template>
    </Alert>

    <!--
      Where this document stands, and the step available from it.

      A band rather than a column, and that is the second answer to this. The
      first was a 288px sidebar holding the pipeline, the verbs and the meta —
      and a rail on the left plus a sidebar on the right is five hundred pixels
      of chrome on a 1280-wide window, which left the form four hundred and
      ninety. That is the pane's arithmetic in a different coat, and the pane is
      the thing this arc removed. So: height, once, and only where there is a
      pipeline to draw.
    -->
    <RecordBand
      v-if="banded"
      :pipeline="record?._state?.pipeline || []"
    >
      <!-- What this screen can do to this record beyond editing its fields.
           Declared by the space and resolved server-side — and here rather
           than in the header, because these are the verbs that move the record
           along and the header is where the ones that end it live. -->
      <ScreenActions
        :actions="spec.actions || []"
        :space-code="spaceCode"
        :screen="screen"
        :names="[record?.name || '']"
        @ran="emit('reload')"
      />
      <!-- And the step the document itself is waiting for. Only the steps: its
           menu is the header's, because Cancel and Delete are not things to
           put beside a green button. -->
      <RecordActions
        :space-code="spaceCode"
        :screen="screen"
        :name="record?.name || ''"
        :state="record?._state || null"
        :extras="[]"
        :dirty="dirty"
        @moved="emit('reload')"
      />
    </RecordBand>

    <!-- And what is about to change, while something is. Height again, and only
         while it exists — `RecordUnsaved.vue`. -->
    <RecordUnsaved
      v-if="unsaved.length"
      :changes="unsaved"
      :saving="saving"
      @save="save"
      @discard="discard"
    />

    <div class="min-h-0 flex-1 overflow-y-auto px-4 py-4">
      <!--
        The top of the record: a photograph, the name over it, the two or three
        numbers worth reading. Declared rather than coded —
        `view_settings.showcase` in the manifest is the whole of it.
      -->
      <!--
        Which one is `view_settings.record.as`, a name out of
        `lib/screen/recordViews.js` — the same shape as `view_types`, one level
        down. `record` is the default and mounts nothing: it *is* the form and
        the tabs below.

        One `<component>` rather than a `v-if` per record view, which is the point
        of a registry: the fifth people-shaped doctype in some other space adds
        a line to the table and nothing here.
      -->
      <component
        :is="recordBody"
        v-if="recordBody"
        :space-code="spaceCode"
        :screen="screen"
        :record="living"
        :spec="spec"
        :showcase="showcase"
        :title="identity.label"
        :compact="windowed"
        :revision="revision"
        :can-write="canWrite"
        @open="emit('open', $event)"
        @add="emit('add', $event)"
        @update:image="form[spec.image_field] = $event"
        @update:field="form[$event.field] = $event.value"
      />

      <!--
        Upright on a desktop page, along the top everywhere else.

        A row runs out of room and a column does not, which is the whole of it:
        an Employee is pointed at by ten screens in this space and every one of
        them is a place worth going, so the answer to fifteen tabs is not fewer
        tabs, it is an axis with room for them. The doctype's own tabs inside
        Details then read as what they are — a level down — instead of as a
        second strip competing with the first.

        Only where there is width for a 12rem rail. A window is narrower than
        the page and sits over the record you came from, so it keeps the row.
      -->
      <Tabs
        v-model="tab"
        :vertical="upright"
        :class="upright ? 'flex items-start gap-6' : undefined"
      >
        <!--
          The strip stays put on a showcase screen: the hero is most of a
          screenful, and this is the one control that must not scroll away.
          A wrapper rather than a class on `TabList`, whose own root is
          `relative`.
        -->
        <!-- And it scrolls sideways rather than squeezing: eight tabs in a
             window put the last two off the edge with nothing to say so. -->
        <div
          v-if="upright"
          data-slot="record-tabs-rail"
          class="sticky top-0 z-10 w-48 shrink-0 bg-surface-base pt-1"
        >
          <TabList class="w-full">
            <RecordTabs
              :groups="groups"
              :related="shownTabs"
              :more="moreTabOptions"
              :comment-count="commentCount"
              :meta="phone"
              @files="openFiles"
            />
          </TabList>
        </div>
        <div
          v-else
          class="-mx-4 overflow-x-auto overflow-y-hidden px-4"
          :class="showcase ? 'sticky top-0 z-10 bg-surface-base' : ''"
        >
          <TabList>
            <RecordTabs
              :related="shownTabs"
              :more="moreTabOptions"
              :comment-count="commentCount"
              :meta="phone"
              @files="openFiles"
            />
          </TabList>
        </div>

        <!-- The panels, in their own column beside the rail when there is one.
             `min-w-0` because a form, a timeline and a table all have children
             that would otherwise push this column wider than the page. -->
        <div :class="upright ? 'min-w-0 flex-1' : undefined">
        <!--
          The fields. One panel where the doctype groups nothing and the strip
          inside the form is doing the work, one per group where the rail has
          taken them over — same component either way, told which group to draw.
        -->
        <TabPanel v-for="one in fieldPanels" :key="one.value" :value="one.value">
          <div class="flex flex-col gap-4 pt-4">
            <RecordForm
              v-model:values="form"
              :spec="spec"
              :space-code="spaceCode"
              :screen="screen"
              :disabled="!canWrite"
              :docname="record?.name || ''"
              :ai="record?._ai || {}"
              :only="one.group"
              @reload="emit('reload')"
            />
            <ErrorMessage v-if="error" :message="error" />
          </div>
        </TabPanel>

        <!-- One per declared tab. A `TabPanel` mounts when it is chosen, so
             six related screens cost six requests only if all six are opened. -->
        <TabPanel
          v-for="one in related"
          :key="one.screen"
          :value="`related:${one.screen}`"
        >
          <RelatedRows
            :space-code="spaceCode"
            :screen="one.screen"
            :field="one.field"
            :where="one.where || []"
            :name="record.name"
            :label="one.label || ''"
            @open="emit('open', $event)"
          />
        </TabPanel>

        <TabPanel v-if="related.length" value="calendar">
          <RecordCalendar
            :space-code="spaceCode"
            :screen="screen"
            :name="record.name"
            @open="emit('open', $event)"
          />
        </TabPanel>

        <TabPanel value="activity">
          <RecordActivity
            :space-code="spaceCode"
            :screen="screen"
            :name="record.name"
            :record="record"
            :comments="comments"
            :changes="changes"
            :count="commentCount"
            :more="moreComments"
            :loading="loadingTimeline"
            @added="loadTimeline"
          />
        </TabPanel>

        <TabPanel value="mail">
          <RecordMail
            :space-code="spaceCode"
            :screen="screen"
            :name="record.name"
            :doctype="spec.doctype || ''"
          />
        </TabPanel>

        <!-- Meta is not a tab any more — it is a popover off the line that
             names the record, and it never was a place you *went*. Drawn here
             only on a phone, which has no line with room for it. -->
        <TabPanel v-if="phone" value="meta">
          <RecordMeta
            :record="record"
            :space-code="spaceCode"
            :screen="screen"
            :doctype="spec.doctype || ''"
            :label="identity.label"
            :image-field="spec.image_field || ''"
            :image="form[spec.image_field] || ''"
            :assigned="assigned"
            :tags="tags"
            :shares="shares"
            :files="fileCount"
            :can-write="canWrite"
            :can-rename="!!spec.can_rename && canWrite"
            @update:image="form[spec.image_field] = $event"
            @renamed="renamed"
            @assigned="assigned = $event"
            @tagged="tags = $event"
            @shared="shares = $event"
            @files="openFiles"
          />
        </TabPanel>
        </div>
      </Tabs>
    </div>

    <!--
      The way out of a preview, at its foot and in words.

      It was an icon on the title bar, one seat along from "Fill the desk" —
      an arrow pointing up and right beside a pair of arrows pointing up-right
      and down-left. Two glyphs that look alike doing entirely different
      things: one changes the size of the box, the other changes what page you
      are on. Nothing about either icon said which.

      So it comes off the chrome. The bar also says what the window is, which
      is the other question this raises: somebody who tries to type in here
      and cannot deserves a sentence rather than a shrug.
    -->
    <div
      v-if="windowed"
      data-slot="preview-foot"
      class="flex shrink-0 items-center justify-between gap-3 border-t border-outline-gray-2 bg-surface-sidebar px-4 py-2"
    >
      <span class="min-w-0 truncate text-sm text-ink-muted">
        {{ __('A preview — read only') }}
      </span>
      <Button
        variant="subtle"
        icon-right="lucide-arrow-up-right"
        :label="__('Open it properly')"
        @click="emit('expand')"
      />
    </div>

  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, provide, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Alert,
  Button,
  Dialog,
  ErrorMessage,
  Popover,
  Tabs,
  TabList,
  TabPanel,
} from '@/ui'
import Panel from '@/shared/components/Panel.vue'
import AvatarStack from '@/modules/onespace/components/screen/fields/AvatarStack.vue'
import RecordChip from '@/modules/onespace/components/screen/record/RecordChip.vue'
import RecordTabs from '@/modules/onespace/components/screen/record/RecordTabs.vue'
import RecordForm from '@/modules/onespace/components/screen/record/RecordForm.vue'
import RecordActions from '@/modules/onespace/components/screen/record/RecordActions.vue'
import RecordBand from '@/modules/onespace/components/screen/record/RecordBand.vue'
import ScreenActions from '@/modules/onespace/components/screen/views/ScreenActions.vue'
import RecordUnsaved from '@/modules/onespace/components/screen/record/RecordUnsaved.vue'
import RecordActivity from '@/modules/onespace/components/screen/record/RecordActivity.vue'
import RecordMail from '@/modules/onespace/components/screen/record/RecordMail.vue'
import RecordControls from '@/modules/onespace/components/screen/record/RecordControls.vue'
import RecordCalendar from '@/modules/onespace/components/screen/record/RecordCalendar.vue'
import RelatedRows from '@/modules/onespace/components/screen/record/RelatedRows.vue'
import StateBadge from '@/modules/onespace/components/screen/fields/StateBadge.vue'
import PrintDialog from '@/modules/onespace/components/screen/record/PrintDialog.vue'
import CreateDialog from '@/modules/onespace/components/screen/record/CreateDialog.vue'
import RecordMeta from '@/modules/onespace/components/screen/record/RecordMeta.vue'
import { workspace } from '@/shared/lib/workspace'
import { roomOf, showDrive } from '@/modules/onestorage/lib/window'
import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { MERGE_TARGET, PAGE, WINDOW, WINDOW_TARGET } from '@/modules/onespace/lib/screen/surfaces'
import { recordBodyFor, recordViewOf } from '@/modules/onespace/lib/screen/recordViews'
import { RETURN_TO } from '@/modules/onespace/lib/screen/returnTo'
import { PREVIEWING } from '@/modules/onespace/lib/screen/previewing'
import { identityOf } from '@/modules/onespace/lib/screen/identity'
import { cellText } from '@/modules/onespace/lib/screen/cells'
import { docBadge } from '@/modules/onespace/lib/screen/docstate'
import { tabIcon } from '@/modules/onespace/lib/screen/fields'
import { onDocChange, onDocViewers } from '@/shared/lib/runtime/socket'
import { session } from '@/modules/onespace/lib/shell/session'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'
import { ago } from '@/shared/lib/runtime/format'

const props = defineProps({
  record: { type: Object, required: true },
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** Whether the pane is the page. The pane knows; this does not ask. */
  phone: { type: Boolean, default: false },
  /**
   * Which of the two surfaces this is drawn on — see `lib/screen/surfaces.js`.
   * Passed rather than worked out here: the host knows whether another record
   * is underneath this one.
   */
  surface: { type: String, default: PAGE },
  /** Bumped by the host when the showcase's rail gained something. Passed
   *  through; nothing here reads it. */
  revision: { type: Number, default: 0 },
})
const route = useRoute()

const emit = defineEmits([
  'saved', 'close', 'reload', 'renamed', 'open', 'expand', 'add',
  // Gone, rather than closed. The host has to reload the list as well as shut
  // the pane, and `close` alone cannot say which of the two happened.
  'removed',
])

/** In a window over another record, rather than being the page. */
const windowed = computed(() => props.surface === WINDOW)

/**
 * Whether the band above the record is drawn at all.
 *
 * Whenever there is something for it to hold: a pipeline to show, a step to
 * take, or a verb this screen declares. A doctype that is none of those — most
 * of them — has no band, and a row drawn to say nothing is a row.
 *
 * Never in a window, whatever the document offers. A window is a preview and
 * submitting a document from inside one is the thing `previewing.js` argues
 * nobody asked for.
 */
const banded = computed(() => !windowed.value && !!(
  props.record?._state?.pipeline?.length
  || props.record?._state?.actions?.length
  || props.spec?.actions?.length
))

/**
 * Whether the header says who this record is. Once each, never twice.
 *
 * The trail says it wherever this record *is* the page, the hero says it
 * wherever there is a showcase, and a window's own title bar says it wherever
 * this is in one. What is left is the phone, which has none of the three.
 */
const names = computed(() => !showcase.value && props.phone)

/**
 * Whether this record's controls belong on the line above rather than in a band
 * of their own, and which line that is.
 *
 * Everywhere but a phone. As a page the trail is already naming this record; in
 * a window the window's title bar is. A band under either of those is a second
 * row holding two buttons, which is what it looked like the first time a
 * peeked record came up in a window.
 */
const merged = computed(() => !props.phone)
const target = computed(() => (windowed.value ? WINDOW_TARGET : MERGE_TARGET))

const tab = ref('fields')

/**
 * How this screen says a record should be drawn, where it says anything.
 * Already checked server-side by `showcase.shape`, so this is read, not
 * validated.
 */
const showcase = computed(() => props.spec?.view_settings?.showcase || null)

/**
 * Which surface draws this record, and what it is allowed to replace.
 *
 * The name is the server's — `onespace/surfaces.py` has already narrowed it to
 * one this build draws, and to `showcase` where a screen declared one and never
 * heard of surfaces. So this reads rather than decides, for the same reason
 * `viewTypesOf` does: two halves that decide separately drift, and the drift is
 * a page that is one thing in the rail and another when opened.
 */
/**
 * The record as it stands, edits included.
 *
 * A record view is handed this rather than the saved record, and the
 * difference is the whole of what makes its controls work: the two on the
 * place page fill in fields, and a page reading the *saved* record would show
 * nothing until somebody pressed Save and looked again. `form` is seeded from
 * every field of the record, so spreading it over the record keeps what is not
 * a field — the id, the resolved links, the activity — and takes what is.
 */
const living = computed(() => ({ ...props.record, ...form }))

const recordView = computed(() => recordViewOf(props.spec))
const recordBody = computed(() => recordBodyFor(recordView.value))

/**
 * The screens that point back at this record, as tabs.
 *
 * A showcase's own declared four first, because somebody chose them; then
 * everything derived — every other screen in this space whose doctype links to
 * this one. See `spaceview/connections.py`.
 */
// How many screens-that-point-here the strip carries before the rest go behind
// a menu. Past this it stops being a row of destinations and becomes a ruler:
// an Employee had fifteen tabs over the doctype's own eight, which is two
// strips stacked and neither of them readable.
const STRIP = 4

/**
 * The doctype's own groups, as places in the rail rather than a strip inside
 * Details.
 *
 * Only where the rail has room for them — see `upright`, which measures it.
 * Where there is not, the nested strip comes back, because a rail with no room
 * for a form beside it is worse than the strip it replaced. `RecordForm` draws
 * whichever group is chosen and no strip of its own — see `only` there.
 *
 * Empty for a doctype that groups nothing. Frappe gives such a doctype one tab
 * called Details, and promoting a group of one into the rail beside Details
 * would be two entries saying the same word.
 */
const groups = computed(() => {
  const found = props.spec?.form || []
  return upright.value && found.length > 1 ? found : []
})

/** Every screen in this space that is about this record, declared ones first. */
const related = computed(() => [
  ...(showcase.value?.tabs || []),
  ...(props.spec?.connections || []),
])

/**
 * The ones with a tab of their own.
 *
 * A manifest that declared tabs chose them, so those are never the ones pushed
 * out — `showcase.tabs` is somebody saying "these four are what this record is
 * for", and burying one of them under a menu to make room for a connection
 * nobody named would be the derivation overruling the declaration.
 */
/**
 * Whether the strip is a column beside the content rather than a row above it.
 *
 * Measured, not assumed. This used to read "a desktop page, and not a window",
 * which made the window the one place in the product still drawing the nested
 * strip stage 5 removed — Details / Payments / Address & Contact sitting under
 * Details / Quotations / Payments, two rows of tabs where the page has one
 * rail. A preview of a record should be that record, drawn the way it is
 * drawn.
 *
 * So the question is the one it always really was: is there room for a rail
 * *and* a column of form beside it. That is `RAIL` plus the 280px a field
 * needs (measured in stage 5 — "Is Rate Adjustment Entry (Debit Note)" lays
 * out at 268 and does not wrap) plus the gutters. A page clears it at every
 * width above a phone, which is what it did before; a window at its default
 * size clears it; a window dragged down to its 520px minimum does not, and
 * falls back to the row, which is the honest answer at that width.
 *
 * `ResizeObserver` rather than a media query because the thing being asked
 * about is this element, not the viewport — the same reason the form's columns
 * became a container query. `Tabs` takes `vertical` as a prop, so this cannot
 * be CSS.
 */
const RAIL = 192
const COLUMN = 280
const GUTTERS = 32
const roomy = ref(true)
const frame = ref(null)

const upright = computed(() => !props.phone && roomy.value)

let watcher = null
onMounted(() => {
  if (!frame.value || typeof ResizeObserver === 'undefined') return
  watcher = new ResizeObserver(([entry]) => {
    roomy.value = entry.contentRect.width >= RAIL + COLUMN + GUTTERS
  })
  watcher.observe(frame.value)
})
onBeforeUnmount(() => watcher?.disconnect())

const shownTabs = computed(() => {
  // All of them, where there is an axis with room. Fifteen tabs was never too
  // many destinations, it was too many for a row.
  if (upright.value) return related.value

  const declared = showcase.value?.tabs || []
  const base = declared.length ? declared : related.value.slice(0, STRIP)
  // Plus whichever one is open, if it came from the menu. A `Tabs` value with
  // no trigger to match is not a selection reka will keep — it reverts to the
  // first tab, so choosing from the menu did nothing and looked like a bug in
  // the menu. Promoting the chosen one is also what a reader expects: the
  // thing they picked is now a place they can get back to.
  const open = related.value.find((one) => tab.value === `related:${one.screen}`)
  return open && !base.some((one) => one.screen === open.screen)
    ? [...base, open]
    : base
})

/**
 * And the rest, behind one control.
 *
 * Not dropped: a connection is a real list and the only way to it from here.
 * `RecordView` keeps the panel for every one of them — choosing from the menu
 * selects the tab, which is why these are `TabTrigger`s inside a dropdown
 * rather than links.
 */
const moreTabs = computed(() => {
  const shown = new Set(shownTabs.value.map((one) => one.screen))
  return related.value.filter((one) => !shown.has(one.screen))
})

const moreTabOptions = computed(() =>
  moreTabs.value.map((one) => ({
    label: one.label || one.screen,
    icon: one.icon || tabIcon(one.label || ''),
    onClick: () => { tab.value = `related:${one.screen}` },
  })),
)

/**
 * One panel per field group, or the single one that holds the whole form.
 *
 * `fields` stays the value of the ungrouped panel rather than becoming `g0`,
 * because it is what every other caller opens a record on — `tab.value` is set
 * to it from the create dialog, from a related row, and by `Tabs` itself when
 * nothing matches.
 */
const fieldPanels = computed(() =>
  (groups.value.length
    ? groups.value.map((one, at) => ({ value: at === 0 ? 'fields' : `group:${one.key}`, group: one.key }))
    : [{ value: 'fields', group: '' }]),
)

// Read the panel's own two lists once per record: every write from inside it
// answers with the state that followed.
//
// The sidebar draws the same thing a Meta tab did, and draws it always — so
// where there is one, this is asked for as soon as the record is.
watch(tab, (now) => {
  if (now === 'meta' && !collabLoaded.value) {
    collabLoaded.value = true
    loadCollab()
  }
})

const form = reactive({})
const error = ref('')
const saving = ref(false)
const loadingTimeline = ref(false)
const comments = ref([])
// How many there are, which is not how many are loaded: the timeline is paged
// at fifty.
const commentCount = ref(0)
const moreComments = ref(false)
const changes = ref([])
const likes = ref([])
const liked = ref(false)
const tags = ref([])
const shares = ref({})
// Null while nothing has counted them. The Files tab reports what it found, so
// this costs nothing on a record nobody asks about.
const fileCount = ref(null)
const collabLoaded = ref(false)
const showPrint = ref(false)
const following = ref(false)
const canFollow = ref(false)
// Everybody in the room but this reader: a face saying "you are here" says
// nothing.
const others = ref([])
// The room carries ids and no more — Frappe's open-doc room is a list of users
// — so the id is the label too.
const watching = computed(() =>
  others.value.map((who) => ({ value: who, label: who, image: null })),
)

// Who the record is assigned to, as the server resolved it. A ref rather than a
// computed, because the control writes it back.
const assigned = ref([])
// When somebody else last saved it, from the document's own room.
const staleSince = ref('')

const when = (value) => (value ? ago(value) : '')

// The screen's whole field list, not the columns someone chose to see: hiding a
// column is a statement about the list. Read here only to seed the form.
const fields = computed(() => props.spec?.all_columns || props.spec?.columns || [])
/**
 * Whether the fields on this record may be typed into — the server's grant, and
 * then the surface's answer over it.
 *
 * A window says no however generous the grant is. It is the one computed that
 * does it: the form, the showcase, the meta popover and rename all read this,
 * so a preview is read-only everywhere at once rather than in four places that
 * have to agree. `lib/screen/previewing.js` is why.
 */
const canWrite = computed(() => !!props.spec?.can_write && !windowed.value)

/**
 * One value, flattened to a string that can be compared to another.
 *
 * `!==` is wrong for all three shapes a field holds: a child table is a fresh
 * array every render, a Currency arrives as a number and comes back as a
 * string, and empty is spelled `null`, `undefined` and `''`. Keys are sorted so
 * a row rebuilt in another order is still the same row.
 */
const flat = (value) => {
  if (Array.isArray(value)) return `[${value.map(flat).join(',')}]`
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map((key) => `${key}:${flat(value[key])}`).join(',')}}`
  }
  return value === null || value === undefined ? '' : String(value)
}

// Whether the form holds something the server has not seen. Read from the
// record rather than tracked with a flag, which has to be cleared in every path
// that saves, reloads or switches record.
//
// The header turns on it both ways — Save only while it is true, the document's
// own actions only while it is false.
const dirty = computed(() => changed.value.length > 0)

/**
 * The fields the form holds that the server does not.
 *
 * None of them in a window: the form there is disabled, so this would already
 * be empty — but a default seeded on mount is a change nobody typed, and a
 * preview that grows a Save bar is a preview that can be worked in. Said once,
 * here, so `dirty` and the bar both follow from it.
 */
const changed = computed(() => {
  if (windowed.value) return []
  return fields.value.filter(
    (field) => flat(form[field.fieldname]) !== flat(props.record?.[field.fieldname]),
  )
})

/**
 * The same, as something to read: a label, what it was, what it is about to be.
 *
 * `unsaved` rather than the obvious name: `changes` is the *timeline's* — the
 * versions the server has kept — and two lists of changes on one record is one
 * of them being read as the other.
 *
 * Said in words rather than raw values, because a Link's value is an id and a
 * Check's is 0 — "Reports to: HR-EMP-00007" is not what anybody picked, and
 * "Active: 1" is not a sentence. `cellText` is the reading the list already
 * makes of a cell, and `all_columns` carries the `cell` it needs, so a change
 * is shown the way that value is shown everywhere else in the product.
 *
 * Two shapes are named rather than shown. **Long text**, because the diff of
 * two paragraphs of markup is not a line in a sidebar and the field itself is
 * on screen. And a **child table**, because a change to one is rows rather
 * than a value — saying which table moved is the useful half.
 */
const SAID = new Set(['Text Editor', 'Markdown Editor', 'HTML Editor', 'Code', 'JSON'])

/** The site's number settings, and what a Link is called rather than keyed by
 *  — both the same two `cellText` is handed everywhere else it is called. */
const formats = computed(() => session.data?.formats || {})
const linked = (field) => props.record?._links?.[field] || null

const unsaved = computed(() =>
  changed.value.map((field) => {
    const name = field.fieldname
    if (SAID.has(field.fieldtype) || field.fieldtype === 'Table') {
      return { field: name, label: field.label || name, was: '', now: __('Rewritten') }
    }
    return {
      field: name,
      label: field.label || name,
      // The record's own resolved links, which is what makes a Link read as a
      // name: `_links` is what the server sends beside the ids.
      was: cellText(field, props.record?.[name], formats.value, linked(name)),
      now: cellText(field, form[name], formats.value, linked(name)),
    }
  }),
)

/** Back to what the server holds. The other half of showing a diff: a change
 *  you can see is one you can decide against. */
const discard = () => {
  for (const field of fields.value) form[field.fieldname] = props.record?.[field.fieldname]
}

// Lifted out when the window's title bar needed the same four things from
// outside the component that was computing them — `lib/screen/identity.js`.
const identity = computed(() => identityOf(props.record, props.spec))

// The way back, for the editors this record can open. A sheet or a document
// opened from here is still a page — see `lib/screen/returnTo.js` — but it
// carries the record's name and address so closing it comes back.
provide(RETURN_TO, computed(() => ({
  label: identity.value.label || identity.value.value || '',
  path: route.fullPath,
})))

// And whether this is a preview, for the controls inside it that lead further
// out — a Link field's peek, which in here would open a window over a window.
// `lib/screen/previewing.js`.
provide(PREVIEWING, windowed)

const statusValue = computed(() => {
  const field = props.spec?.status_field
  return (field && props.record?.[field]) || ''
})
// Where the framework stands, beside the doctype's own status field and de-duped
// against it. Only the phone draws the pair; a desktop trail already says it.
const docState = computed(() =>
  docBadge(props.record?._state, props.spec?.status_field || '', statusValue.value),
)

const loadTimeline = async () => {
  if (!props.record?.name) return
  loadingTimeline.value = true
  try {
    const found = await workspace.timeline(props.spaceCode, props.screen, props.record.name)
    comments.value = found?.comments || []
    commentCount.value = found?.comment_count ?? comments.value.length
    moreComments.value = !!found?.more_comments
    changes.value = found?.changes || []
    likes.value = found?.likes || []
    liked.value = !!found?.liked
    following.value = !!found?.following
    canFollow.value = !!found?.can_follow
  } finally {
    loadingTimeline.value = false
  }
}

/**
 * How many files this record has, for the line in its panel that says so.
 *
 * It used to arrive as a side effect of the Files tab having been opened,
 * which is why the number appeared a moment after somebody went looking for
 * it — and never at all if they did not. The tab is a door now, so the count
 * is asked for on its own: one `count` over the filters the list would have
 * used, a page of one row, on opening the record.
 */
const loadFileCount = async () => {
  if (!props.record?.name) return
  const found = await workspace
    .attachments(props.spaceCode, props.screen, props.record.name, null, { limit: 1 })
    .catch(() => null)
  fileCount.value = found?.total ?? null
}

/**
 * This record's files, in the one file manager this product has.
 *
 * `docs/DRIVE.md` §13: a record's room is a folder whose id is the record's
 * own address, so this is not a search — the window opens *at* it, with the
 * trail, the New menu, uploads, sharing and every verb the Drive has. What it
 * replaces is four hundred lines that drew a smaller file manager inside a
 * tab and had to be kept in step with the real one.
 */
const openFiles = () => {
  const room = roomOf(props.spec?.doctype || '', props.record?.name || '')
  if (room) showDrive(room)
}

/**
 * Tags and shares, on opening the Meta tab rather than on opening the record:
 * two requests most records never need.
 */
const loadCollab = async () => {
  if (!props.record?.name) return
  const [found, given] = await Promise.all([
    workspace.tags(props.spaceCode, props.screen, props.record.name),
    workspace.shares(props.spaceCode, props.screen, props.record.name),
  ])
  tags.value = found?.tags || []
  shares.value = given || {}
}

const like = async () => {
  const result = await workspace.toggleLike(props.spaceCode, props.screen, props.record.name)
  liked.value = !!result?.liked
  likes.value = result?.likes || []
}

// What the server says afterwards, not what was asked for: a refused follow
// would otherwise light a bell over a subscription that does not exist.
const follow = async () => {
  const result = await workspace.toggleFollow(props.spaceCode, props.screen, props.record.name)
  following.value = !!result?.following
}

/**
 * The verbs that are not the framework's, as menu entries — print, follow, like.
 * As buttons in the header they competed with the one button that mattered.
 *
 * The like keeps its count in the label: a number nobody can see is not one.
 */
/**
 * A copy of this record, as values, and the dialog holding them. Fetched on the
 * click: `copy_doc` on a forty-line invoice is not a cost to pay on every read.
 */
const copying = ref(false)
const confirmDelete = ref(false)
const deleting = ref(false)

/**
 * Delete this one.
 *
 * The same endpoint the selection bar calls — `remove` has taken one name or
 * a list since it was written — so there is no second delete path and no
 * second answer about what a refusal means.
 *
 * Closed rather than reloaded on success: the record this pane is drawing no
 * longer exists, and the host reloads the list behind it.
 */
const remove = async () => {
  deleting.value = true
  try {
    const answer = await workspace.removeRecords(props.spaceCode, props.screen, [
      props.record.name,
    ])
    const refused = answer?.refused?.[0]
    if (refused) {
      // Named rather than counted: one record and one reason, which is almost
      // always something else linking to it.
      notifyError(refused.reason)
      return
    }
    confirmDelete.value = false
    notifySuccess(__('Deleted'))
    emit('removed', props.record.name)
  } catch (raised) {
    notifyError(raised)
  } finally {
    deleting.value = false
  }
}
const copy = ref({})

const startCopy = async () => {
  try {
    copy.value = (await workspace.duplicateRecord(props.spaceCode, props.screen, props.record.name)) || {}
  } catch {
    copy.value = {}
  }
  copying.value = true
}

/**
 * The address of what is on screen, for somebody to paste into a message.
 *
 * `clipboard` is unavailable over plain HTTP and in some private modes, and
 * there is no useful fallback — so it says it could not rather than pretending.
 */
const copyLink = async () => {
  try {
    await navigator.clipboard.writeText(window.location.href)
    notifySuccess(__('Link copied'))
  } catch {
    notifyError(__('This browser would not let the page copy to the clipboard.'))
  }
}

const extras = computed(() => {
  const found = []
  if (props.spec?.can_print) {
    found.push({
      key: 'print',
      label: __('Print'),
      icon: 'lucide-printer',
      onClick: () => (showPrint.value = true),
    })
  }
  if (canFollow.value) {
    found.push({
      key: 'follow',
      label: following.value ? __('Stop following') : __('Follow'),
      icon: 'lucide-bell',
      onClick: follow,
    })
  }
  // The word, and how many, which is a count beside it rather than part of
  // the sentence.
  const likeWord = liked.value ? __('Liked') : __('Like')
  found.push({
    key: 'like',
    label: likes.value.length ? `${likeWord} · ${likes.value.length}` : likeWord,
    icon: 'lucide-heart',
    onClick: like,
  })
  // The three the desk has had forever. Last, because they are the ones
  // somebody goes looking for.
  if (props.spec?.can_create) {
    found.push({
      key: 'duplicate',
      label: __('Duplicate'),
      icon: 'lucide-copy-plus',
      onClick: startCopy,
    })
  }
  found.push({
    key: 'link',
    label: __('Copy link'),
    icon: 'lucide-link',
    onClick: copyLink,
  })
  found.push({
    key: 'reload',
    label: __('Reload'),
    icon: 'lucide-refresh-cw',
    onClick: () => emit('reload'),
  })
  // Last, and the only one in red. A menu whose destructive entry sits among
  // the others is a menu somebody presses by accident.
  if (props.spec?.can_delete) {
    found.push({
      key: 'delete',
      label: __('Delete for ever'),
      icon: 'lucide-trash-2',
      theme: 'red',
      onClick: () => (confirmDelete.value = true),
    })
  }
  return found
})

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    await workspace.saveRecord(props.spaceCode, props.screen, { ...form }, props.record.name)
    emit('saved')
  } catch (e) {
    error.value = errorText(e)
  } finally {
    saving.value = false
  }
}

// No Escape key. A pane is not modal, and the controls inside it — the link
// picker above all — do not mark their own Escape as handled, so closing a
// dropdown closed the record under it. The way out is the X.

// --- the room ---------------------------------------------------------------
//
// Two rooms per record, both Frappe's: the document's own events, and who has
// it open. Re-joined whenever the record changes.
let leaveRoom = null

const enterRoom = () => {
  if (leaveRoom) leaveRoom()
  leaveRoom = null
  others.value = []
  staleSince.value = ''

  const doctype = props.spec?.doctype
  const name = props.record?.name
  if (!doctype || !name) return

  const stopViewers = onDocViewers(doctype, name, (users) => {
    // Frappe's rooms carry user ids — an email — which is `name` on the
    // session's user rather than the object itself.
    others.value = users.filter((who) => who && who !== session.user?.name)
  })
  const stopChanges = onDocChange(doctype, name, (data) => {
    // Our own save comes back through the same room, and telling somebody their
    // own change arrived is noise.
    if (saving.value) return
    staleSince.value = data?.modified || new Date().toISOString()
  })
  leaveRoom = () => {
    stopViewers()
    stopChanges()
  }
}

onBeforeUnmount(() => {
  if (leaveRoom) leaveRoom()
})

// Set by the Meta tab just before a rename lands: a rename is the same record
// with a new id, and being thrown back to Details for it is a small rudeness.
const renamedInPlace = ref(false)

const renamed = (name) => {
  renamedInPlace.value = true
  emit('renamed', name)
}

watch(
  () => props.record,
  () => {
    enterRoom()
    if (!renamedInPlace.value) tab.value = 'fields'
    renamedInPlace.value = false
    // Cleared rather than left standing, or the panel shows the last record's
    // for as long as the request takes.
    tags.value = []
    shares.value = {}
    fileCount.value = null
    collabLoaded.value = false
    error.value = ''
    Object.keys(form).forEach((key) => delete form[key])
    for (const field of fields.value) form[field.fieldname] = props.record?.[field.fieldname]
    assigned.value = props.record?._assigned || []
    loadTimeline()
    loadFileCount()
    // Tags and shares come with the record rather than when a tab is opened,
    // because the thing that draws them is a popover now: waiting until it is
    // pressed would mean pressing it and reading an empty panel.
    if (!props.phone) {
      collabLoaded.value = true
      loadCollab()
    }
  },
  { immediate: true },
)
</script>
