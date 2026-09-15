<template>
  <!--
    The things you do to a record rather than to one of its fields.

    Its own component because it is drawn in two places and must be the same row
    in both: in the record's own header, where the record has one, and on the
    page header's line, where it does not. See `merged` in `RecordView`.

    What is left here is deliberately not much. The screen's declared verbs and
    the step forward are in the band above the record (`RecordBand.vue`), where
    the state they act on is; what stays is the menu holding the two kinds of
    verb nobody wants beside a green button — the ones that unwind the record
    and the one that destroys it — plus print, like and copy, which belong with
    them because they are about the record rather than about its progress.

    Assignment is not here at all: the About popover beside the record's name
    offers it.
  -->
  <div data-slot="record-controls" class="flex shrink-0 items-center gap-1">
    <!--
      One menu, holding everything the band is not about — and not at all in a
      window, which draws the one control below and nothing else.

      Cancel, Delete and Amend unwind or destroy a document. A window is a look
      at a record something *else* points at, opened with one press and closed
      by clicking past it, and those three verbs do not belong behind a press
      that casual. They are a door away, on the record's own screen, where the
      thing they act on is what the page is about. `lib/screen/previewing.js`.
    -->
    <RecordActions
      v-if="!windowed"
      :space-code="spaceCode"
      :screen="screen"
      :name="record.name"
      :state="record._state"
      :extras="extras"
      :dirty="dirty"
      :banded="banded"
      @moved="emit('reload')"
      @opened="emit('renamed', $event)"
    />
    <!--
      Save is not here any more. It is in `RecordUnsaved.vue`, the bar that
      appears while there is something to save — under the list of what is
      about to change, which is the thing worth reading before pressing it.

      It was here for a good reason and the reason has not gone: the toast that
      says a save worked is fixed to the bottom right, where a footer button
      would sit, so saving twice meant clicking through the first confirmation.
      The bar is at the top, so that stays true.
    -->
    <!--
      There was a control here for how much of the window a record gets — the
      manifest's opinion, the reader overruling it, remembered per screen. There
      is nothing to choose any more: a record is a page. `docs/DESKTOP.md`.

      The window's own shell draws its fill, fold and close, so the two that
      are left here are the ones that are about the *record* rather than about
      the frame around it.
    -->
    <!-- The document's own steps, where no pipeline band is drawing them: a
         doctype that neither submits nor flows has no band, and `RecordActions`
         still has its menu of verbs for it. -->
    <!--
      And the way out of a preview, which is the only control a window draws.

      Everything a person cannot do in here they can do through this: the same
      record, on its own screen, with its list behind it and every verb, field
      and tab live.
    -->
    <Button
      v-if="windowed"
      icon="lucide-arrow-up-right"
      variant="ghost"
      :label="__('Open it properly')"
      :tooltip="__('Open it properly')"
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
  /**
   * Whether this record is in a window over another one, rather than the page
   * it came from — which is to say, whether it is a preview.
   *
   * It is the whole of this row's answer: in a window there is one button, the
   * door out, and no menu behind it. `lib/screen/previewing.js` says why.
   */
  windowed: { type: Boolean, default: false },
  /**
   * Whether the pipeline band is drawing this record's steps, in which case
   * this row draws only the verbs behind its menu.
   *
   * Declared, which sounds like nothing and is the whole of a bug that took a
   * screenshot to find: its predecessor was read in this template and declared
   * on a *different* component, and an undeclared prop is `undefined` for ever
   * — so the Save it was meant to stand down for went on being drawn beside
   * the other one. Vue says nothing; it becomes a fallthrough attribute. That
   * is the silence `test_no_unknown_props` catches for frappe-ui's components
   * and nothing catches for ours.
   */
  banded: { type: Boolean, default: false },
})

const emit = defineEmits(['save', 'close', 'reload', 'renamed', 'expand'])
</script>
