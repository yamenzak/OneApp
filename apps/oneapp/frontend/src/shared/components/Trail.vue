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
    <Breadcrumbs :items="items">
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
import { Breadcrumbs, Icon, Tooltip } from '@/ui'

import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  /** From `composables/useCrumbs.js`, and from nowhere else. */
  items: { type: Array, default: () => [] },
})
</script>
