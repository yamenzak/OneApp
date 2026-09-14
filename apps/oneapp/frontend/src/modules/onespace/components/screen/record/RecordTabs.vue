<template>
  <!--
    Every place this record goes, as triggers.
    
    A component rather than the same twenty lines twice: the strip is a row
    along the top on a phone and in a pane, and a column beside the content on a
    desktop page, and those are two wrappers around one list. Keeping the list
    in `RecordView` meant writing it out per wrapper, which is how the two drift
    until one of them is missing the Mail tab.
  -->
  <!-- A glyph on every one, from the derivation the doctype's own tabs use, or
       the strip reads as two strips. -->
  <TabTrigger value="fields" :label="__('Details')" :icon-left="tabIcon('Details')" />

  <!--
    The other screens in this space that point back at this record. Second, not
    last: on a screen that declares them these are what the record is *for*.
  -->
  <TabTrigger
    v-for="one in related"
    :key="one.screen"
    :value="`related:${one.screen}`"
    :label="one.label || one.screen"
    :icon-left="one.icon || tabIcon(one.label || '')"
  />

  <!--
    And the rest behind one control, where there is a rest — which is only ever
    the row, because a column does not run out of room. Choosing one puts it
    *into* the strip, so the menu shrinks by one and the thing somebody just
    picked is a place they can get back to.
  -->
  <Dropdown v-if="more.length" :options="more">
    <Button
      variant="ghost"
      data-slot="record-more-tabs"
      icon-right="lucide-chevron-down"
      :label="__('{0} more', [String(more.length)])"
      class="text-ink-muted"
    />
  </Dropdown>

  <!-- The count as a badge rather than inside the word. `#suffix` is the slot
       for it; the default slot replaces the label. -->
  <!-- One tab, not two: answering "what happened on Tuesday" from separate
       places meant merging them by eye. -->
  <TabTrigger value="activity" :label="__('Activity')" :icon-left="tabIcon('Activity')">
    <template #suffix>
      <Badge
        v-if="commentCount"
        :label="String(commentCount)"
        theme="gray"
        variant="subtle"
      />
    </template>
  </TabTrigger>

  <!-- The mail about this record. Beside Activity rather than in it: a message
       is something said from outside. -->
  <TabTrigger value="mail" :label="__('Mail')" :icon-left="tabIcon('Mail')" />
  <TabTrigger value="files" :label="__('Files')" :icon-left="tabIcon('Files')" />
  <!-- What the record *is* rather than what it says. Last, because it is the
       tab you go to on purpose. -->
  <TabTrigger value="meta" :label="__('Meta')" :icon-left="tabIcon('Meta')" />
</template>

<script setup>
import { Badge, Button, Dropdown, TabTrigger } from '@/ui'
import { tabIcon } from '@/modules/onespace/lib/screen/fields'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  /** The screens that point back at this record and have a tab of their own. */
  related: { type: Array, default: () => [] },
  /** The ones that did not fit, as `Dropdown` options. Empty in a column. */
  more: { type: Array, default: () => [] },
  /** How many comments, for the badge on Activity. */
  commentCount: { type: Number, default: 0 },
})
</script>
