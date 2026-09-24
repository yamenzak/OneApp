<template>
  <!--
    Every place this record goes, as triggers.
    
    A component rather than the same twenty lines twice: the strip is a row
    along the top on a phone and in a pane, and a column beside the content on a
    desktop page, and those are two wrappers around one list. Keeping the list
    in `RecordView` meant writing it out per wrapper, which is how the two drift
    until one of them is missing a tab.
  -->
  <!-- A glyph on every one, from the derivation the doctype's own tabs use, or
       the strip reads as two strips. -->
  <!--
    The doctype's own groups, where the rail has taken them over — they were a
    second strip inside Details. Under a heading, and that is the whole reason
    there are headings at all: a group of *this record's fields* and a screen
    listing *other records* are different kinds of thing, and fifteen entries in
    one undifferentiated column is where "Address & Contact" sits beside
    "Invoices" and you have to read both to tell which is which.

    Empty everywhere else, and then the single Details trigger below is the one
    that opens the form with its own strip inside it.
  -->
  <template v-if="groups.length">
    <p :class="HEADING">{{ __('This record') }}</p>
    <TabTrigger
      v-for="(one, at) in groups"
      :key="one.key"
      :value="at === 0 ? 'fields' : `group:${one.key}`"
      :label="one.label"
      :icon-left="tabIcon(one.label)"
    />
    <p :class="HEADING">{{ __('Related') }}</p>
  </template>
  <TabTrigger v-else value="fields" :label="__('Details')" :icon-left="tabIcon('Details')" />

  <!--
    The other screens in this space that point back at this record. Second, not
    last: on a screen that declares them these are what the record is *for*.
  -->
  <TabTrigger
    v-for="one in related"
    :key="tabKey(one)"
    :value="tabKey(one)"
    :label="one.label || one.screen"
    :icon-left="one.icon || tabIcon(one.label || '')"
  />

  <!--
    This record's own month, where anything about it has a date —
    `docs/WORK.md` §6(c). After the related screens because it is made *of*
    them: the same list, read as a calendar rather than as tabs. Drawn only
    where there are any, because a record with nothing related has nothing
    dated either.
  -->
  <TabTrigger
    v-if="related.length"
    value="calendar"
    :label="__('Calendar')"
    :icon-left="tabIcon('Calendar')"
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

  <!--
    Files is a press, not a tab.

    It was a tab, and behind it was a second file manager: a path, a New menu,
    an upload button, a selection bar and four hundred lines that had to be
    kept in step with OneCloud's own — which is exactly the shape
    `docs/UNIFICATION.md` F1 names. There is one file manager in this product
    and this opens it, at the folder that holds this record's files.

    Drawn as a button rather than as a trigger *because* it is not a tab: the
    strip is places you go inside this record, and a press that opens a window
    somewhere else must not look like one of them. The arrow is the same one
    every door in this product wears.
  -->
  <Button
    variant="ghost"
    data-slot="record-files-door"
    :label="__('Files')"
    :icon-left="tabIcon('Files')"
    icon-right="lucide-arrow-up-right"
    :tooltip="__('Open this record\'s files in {0}', [nameOf('onestorage')])"
    class="text-ink-secondary"
    @click="emit('files')"
  />
  <!--
    What the record *is* rather than what it says — and only where there is no
    sidebar to hold it. It was never a place you went: it is a paragraph about
    the record that needed somewhere to live, and beside the record is where it
    lives now. `RecordAside.vue`.
  -->
  <TabTrigger v-if="meta" value="meta" :label="__('Meta')" :icon-left="tabIcon('Meta')" />
</template>

<script setup>
import { Badge, Button, Dropdown, TabTrigger } from '@/ui'
import { tabIcon } from '@/modules/onespace/lib/screen/fields'
import { tabKey } from '@/modules/onespace/lib/screen/related'
import { __ } from '@/shared/lib/runtime/translate'
import { nameOf } from '@/shared/lib/brand/naming'

const emit = defineEmits(['files'])

defineProps({
  /** The doctype's own field groups, where the rail is drawing them. Empty in a
   *  row, which has no width for them and keeps them inside the form. */
  groups: { type: Array, default: () => [] },
  /** The screens that point back at this record and have a tab of their own. */
  related: { type: Array, default: () => [] },
  /** The ones that did not fit, as `Dropdown` options. Empty in a column. */
  more: { type: Array, default: () => [] },
  /** How many comments, for the badge on Activity. */
  commentCount: { type: Number, default: 0 },
  /** Whether Meta is a tab here, which it is only where there is no sidebar. */
  meta: { type: Boolean, default: true },
})

// The same quiet heading the sidebar's blocks wear, so the two columns beside
// the record read as one product.
const HEADING = 'px-2 pb-1 pt-3 text-xs font-medium uppercase tracking-wide text-ink-muted first:pt-0'
</script>
