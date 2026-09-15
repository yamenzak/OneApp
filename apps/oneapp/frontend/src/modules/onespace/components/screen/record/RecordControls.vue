<template>
  <!--
    The things you do to a record rather than to one of its fields.

    Its own component because it is drawn in two places and must be the same row
    in both: in the record's own header, where the record has one, and on the
    page header's line, where it does not. See `merged` in `RecordView`.

    The record's other verbs — print, follow, like — are inside `RecordActions`'
    menu, and assignment is not here at all: the Meta tab offers it one tab
    away.
  -->
  <div data-slot="record-controls" class="flex shrink-0 items-center gap-1">
    <!-- What this screen can do to this record beyond editing its fields.
         Declared by the space and resolved server-side. -->
    <ScreenActions
      :actions="spec.actions || []"
      :space-code="spaceCode"
      :screen="screen"
      :names="[record.name]"
      @ran="emit('reload')"
    />
    <!-- The step this record is waiting for, and one menu holding everything
         else. -->
    <RecordActions
      :space-code="spaceCode"
      :screen="screen"
      :name="record.name"
      :state="record._state"
      :extras="extras"
      :dirty="dirty"
      @moved="emit('reload')"
      @opened="emit('renamed', $event)"
    />
    <!--
      Save lives up here rather than in a footer because of the corner: the toast
      that says a save worked is fixed to the bottom right, which is exactly
      where a pane's footer button sits, so saving twice meant clicking through
      the first confirmation. frappe-ui's ToastProvider hard-codes that
      position.

      Only while there is something to save. It shares its place with the
      document's own actions, which are offered only while there is not.
    -->
    <Button
      v-if="canWrite && dirty"
      variant="solid"
      :label="__('Save')"
      :loading="saving"
      @click="emit('save')"
    />
    <!--
      There was a control here for how much of the window a record gets — the
      manifest's opinion, the reader overruling it, remembered per screen. There
      is nothing to choose any more: a record is a page. `docs/DESKTOP.md`.

      The window's own shell draws its fill, fold and close, so the two that
      are left here are the ones that are about the *record* rather than about
      the frame around it.
    -->
    <!-- A window is not always enough. The way from one to the other: the same
         record, on its own screen, with its list behind it. -->
    <Button
      v-if="windowed"
      icon="lucide-arrow-up-right"
      variant="ghost"
      :label="__('Open on its own screen')"
      :tooltip="__('Open on its own screen')"
      @click="emit('expand')"
    />
    <!--
      Out, and not in a window: the window's own bar has a close on it, and two
      buttons one above the other doing the same thing is a person deciding
      which of them is the real one. The window's is the real one.
    -->
    <Button
      v-if="!windowed"
      icon="lucide-x"
      variant="ghost"
      :label="__('Close the record')"
      :tooltip="__('Close the record')"
      @click="emit('close')"
    />
  </div>
</template>

<script setup>
import { Button } from '@/ui'
import ScreenActions from '@/modules/onespace/components/screen/views/ScreenActions.vue'
import RecordActions from '@/modules/onespace/components/screen/record/RecordActions.vue'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  /** The record, for its id and its docstatus. */
  record: { type: Object, required: true },
  /** The resolved screen, for the actions it declares. */
  spec: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** The record's own verbs, as menu entries — print, follow, like. */
  extras: { type: Array, default: () => [] },
  canWrite: { type: Boolean, default: false },
  /** Whether the form holds something the server has not seen. */
  dirty: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  /** Whether this record is in a window over another one, rather than the page
   *  it came from. It changes two words and offers one control. */
  windowed: { type: Boolean, default: false },
})

const emit = defineEmits(['save', 'close', 'reload', 'renamed', 'expand'])
</script>
