<!--
  What a message being written is drawn inside.

  Two answers, because the composer has two homes and they want different
  things. On a record's Mail tab it is a **dialog**: the tab is a list of what
  was said, a few hundred pixels of it, and there is nowhere in that column a
  message could be written without pushing the thing it is about off screen.

  In OneMail it is the **reading pane** — the column a message's body is drawn
  in, which is the only column on that surface wide enough for prose and is
  otherwise showing the thing being answered. A dialog there covered the
  conversation with the reply to it, which is the one thing you want to look at
  while writing one, and it made every attachment, every quoted line and every
  address in the thread something to remember rather than read.

  The frame and not the composer, so the composer itself knows nothing about
  which one it is in: one set of fields, one draft, one Send. The slots are
  Dialog's — `default` and `actions` — so the same body fills either.
-->
<template>
  <Dialog v-if="!pane" v-model="open" :title="title" :size="size">
    <template #default>
      <div :data-slot="SLOT">
        <slot />
      </div>
    </template>
    <template #actions>
      <slot name="actions" />
    </template>
  </Dialog>

  <!--
    The pane. A heading rather than a title bar: it is inside a column that
    already has one, and what it has to say is which message this is — a new
    one, a reply, a forward.
  -->
  <!--
    Escape puts it down, which is what a dialog did for free. On the section
    rather than on the window, so it is the composer's own key while somebody
    is in it: the page's `escape` answers for the case where focus is not —
    `useShortcuts` steps aside for anything being typed into, which is most of
    what is in here.
  -->
  <section
    v-else-if="open"
    class="flex min-h-0 flex-1 flex-col"
    :data-slot="SLOT"
    :aria-label="title"
    @keydown.esc.stop="open = false"
  >
    <header class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-5 py-3">
      <h2 class="min-w-0 truncate text-lg font-semibold text-ink-gray-9">{{ title }}</h2>
      <!--
        Closing is not discarding. What was typed is kept the way it always
        was — `mailKept` on the server — so this is "put it down", and the
        label says so rather than asking somebody to guess which of the two
        an ✕ means.
      -->
      <Button
        variant="ghost"
        icon="lucide-x"
        :label="__('Put it down')"
        :tooltip="__('Put it down')"
        data-slot="composer-close"
        @click="open = false"
      />
    </header>

    <div class="min-h-0 flex-1 overflow-y-auto p-5">
      <slot />
    </div>

    <footer class="flex items-center justify-end gap-2 border-t border-outline-gray-1 px-5 py-3">
      <slot name="actions" />
    </footer>
  </section>
</template>

<script setup>
import { Button, Dialog } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

/** The same handle in both frames, so nothing outside has to know which. */
const SLOT = 'mail-composer'

defineProps({
  /** Drawn in the reading pane rather than over everything. */
  pane: { type: Boolean, default: false },
  /** Which message this is: new, a reply, a forward. */
  title: { type: String, default: '' },
  /** Dialog's own, ignored by the pane, which is as wide as its column. */
  size: { type: String, default: 'xl' },
})

const open = defineModel({ type: Boolean, default: false })
</script>
