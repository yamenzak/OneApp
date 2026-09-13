<!--
  The one trail, and the subject after it.

  Ten surfaces drew their own breadcrumb nav around their own frappe-ui
  `Breadcrumbs`, and the markup was the only thing they agreed on: nine of
  them disagreed about what the first crumb should be.

  Two things this owns that a bare `Breadcrumbs` at a call site did not:

  * **The root is a house**, and its accessible name is the workspace's own —
    the name is a `<span>` rather than the icon's `aria-label`, because
    frappe-ui's `Icon` hard-codes `aria-hidden` after the attrs it forwards,
    which leaves a link with no accessible name at all.
  * **The subject is after the trail, not in it.** A crumb is a line of text
    and a subject is a block: a record's face, name, id and badges; a
    document's title; a thread's subject. Put in the trail it wraps, and the
    trail stops being scannable.
  * **A trail with a subject is its root and the subject, nothing between.**
    Opening a document gave you `🏠 / Files / This folder / Untitled.py`,
    where three of the four are the route you took rather than the thing you
    came to look at. What a person wants above an open document is its name
    and one press out; the folder it happens to live in is the Drive's
    business, and you are not in the Drive any more.

  `docs/UNIFICATION.md` §C1.
-->
<template>
  <nav
    data-slot="breadcrumb"
    :aria-label="__('Breadcrumb')"
    class="flex min-w-0 flex-1 items-center gap-1"
  >
    <!-- A phone's place picker, where a surface has one: the shell draws a
         sidebar only on a desktop, so on a phone the trail is also how you
         change place. Before the crumbs because it is the wider place. -->
    <slot name="before" />

    <!--
      frappe-ui collapses this to the last two with an ellipsis menu when it
      runs out of room, which is what makes an extra root crumb safe on a
      phone.
    -->
    <Breadcrumbs :items="shown">
      <template #prefix="{ item }">
        <Tooltip v-if="item.home" :text="item.home">
          <span class="flex items-center">
            <Icon name="lucide-house" class="size-4 text-ink-muted" />
            <span class="sr-only">{{ item.home }}</span>
          </span>
        </Tooltip>
      </template>
    </Breadcrumbs>

    <!-- What you are looking at. -->
    <div v-if="$slots.subject" class="flex min-w-0 items-center">
      <span class="mx-0.5 text-base text-ink-gray-4" aria-hidden="true">/</span>
      <slot name="subject" />
    </div>

    <!-- And anything that belongs beside the trail rather than in it — the
         view switcher is the one caller, and it is a control, not a place. -->
    <slot />
  </nav>
</template>

<script setup>
import { computed, useSlots } from 'vue'

import { Breadcrumbs, Icon, Tooltip } from '@/ui'

import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** From `composables/useCrumbs.js`, and from nowhere else. */
  items: { type: Array, default: () => [] },
})

const slots = useSlots()

/*
 * The root, and then the subject — or the whole trail when there is none.
 *
 * Decided here rather than at the two call sites that fill `#subject`, because
 * it is one rule about what a trail *is* and they would have been two copies
 * of it that agreed for a month. `ScreenHeader` fills the slot only when the
 * record has the whole width — beside a list on a desktop the record has its
 * own header over the pane, and the trail there is still the list's.
 */
const shown = computed(() => (slots.subject ? props.items.slice(0, 1) : props.items))
</script>
