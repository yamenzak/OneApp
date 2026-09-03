<template>
  <!--
    The things you do to a record rather than to one of its fields.

    Its own component because it is drawn in two places and must be the same
    row in both: in the record's own header, where the record has one — a pane
    beside the list, a drawer over a page, a phone — and on the page header's
    line, where it does not. See `merged` in `RecordView`.

    Not eight buttons in a row. The record's other verbs — print, follow,
    like — are inside `RecordActions`' menu, and assignment is not here at all:
    the Meta tab offers it one tab away, so it was the same control twice.
  -->
  <div data-slot="record-controls" class="flex shrink-0 items-center gap-1">
    <!-- What this screen can do to this record beyond editing its fields.
         Declared by the space and resolved server-side, so a screen that
         declares none renders nothing here. -->
    <ScreenActions
      :actions="spec.actions || []"
      scope="record"
      :space-code="spaceCode"
      :screen="screen"
      :names="[record.name]"
      @ran="emit('reload')"
    />
    <!--
      The step this record is waiting for, and one menu holding everything else
      you can do to it — print it, follow it, like it, and the steps that unwind
      a submitted document.
    -->
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
      Save lives up here rather than in a footer, and the reason is the corner:
      the toast that says a save worked is fixed to the bottom right of the
      window, which is exactly where a pane's footer button sits — so saving
      twice in a row meant clicking through the confirmation of the first one.
      frappe-ui's ToastProvider hard-codes that position, so the button moved
      instead.

      Only while there is something to save. It shares its place with the
      document's own actions, which are offered only while there is not: one
      slot, and whichever of the two is the real next step is in it.
    -->
    <Button
      v-if="canWrite && dirty"
      variant="solid"
      label="Save"
      :loading="saving"
      @click="emit('save')"
    />
    <!--
      How much of the window this record gets. The manifest has an opinion — a
      screen that draws a hero over a photograph is asking for the width, a
      screen that draws a form is not — and this is the reader overruling it,
      remembered per screen so it is a preference rather than a click you make
      every time.

      Not on a phone, where there is only ever one surface, and not in the
      drawer, where the record is a thing you are peeking at from another one
      and the width is that argument, not this one.
    -->
    <Button
      v-if="canResize"
      :icon="wide ? 'lucide-minimize-2' : 'lucide-maximize-2'"
      variant="ghost"
      :label="wide ? 'Show beside the list' : 'Fill the window'"
      :tooltip="wide ? 'Show beside the list' : 'Fill the window'"
      @click="emit('surface', wide ? 'pane' : 'page')"
    />
    <!--
      A peek is not always enough. This is the way from one to the other: the
      same record, on its own screen, with its list behind it — which is where
      you go when the answer to "what is this line" turns out to be a job of its
      own.
    -->
    <Button
      v-if="drawer"
      icon="lucide-arrow-up-right"
      variant="ghost"
      label="Open on its own screen"
      tooltip="Open on its own screen"
      @click="emit('expand')"
    />
    <!--
      Out. What it means depends on where you are: in a drawer it puts the
      record you came from back, everywhere else it goes back to the list — and
      the tooltip should say which, because they are different enough that
      guessing wrong loses your place.
    -->
    <Button
      icon="lucide-x"
      variant="ghost"
      :label="drawer ? 'Close and go back' : 'Close the record'"
      :tooltip="drawer ? 'Close and go back' : 'Close the record'"
      @click="emit('close')"
    />
  </div>
</template>

<script setup>
import { Button } from '@/ui'
import ScreenActions from './ScreenActions.vue'
import RecordActions from './RecordActions.vue'

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
  /** Whether this record already fills the window. */
  wide: { type: Boolean, default: false },
  /** Whether it is being peeked at from another record. */
  drawer: { type: Boolean, default: false },
  /** Whether the reader may choose between the pane and the page. */
  canResize: { type: Boolean, default: false },
})

const emit = defineEmits(['save', 'close', 'reload', 'renamed', 'surface', 'expand'])
</script>
