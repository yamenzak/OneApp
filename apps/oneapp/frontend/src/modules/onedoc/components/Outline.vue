<template>
  <!-- Where you are in a long document, on a screen with room for a rail. The
       phone gets the same list from the same composable, as a dropdown in the
       header — see `DocEditor`. -->
  <nav
    v-if="worthShowing"
    aria-label="Outline"
    class="hidden w-56 shrink-0 border-e border-outline-gray-1 lg:block"
  >
    <FadedScroll class="max-h-full">
      <div class="flex flex-col gap-0.5 p-3">
        <p class="px-2 pb-1 text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
          Outline
        </p>
        <Button
          v-for="one in headings"
          :key="one.id"
          variant="ghost"
          class="w-full !justify-start !px-2"
          :label="one.text"
          @click="go(one)"
        >
          <span
            class="w-full truncate text-start text-p-sm"
            :class="[
              one.level > 2 ? 'ps-3 text-ink-gray-6' : 'text-ink-gray-7',
              one.id === active ? 'font-medium text-ink-gray-8' : '',
            ]"
          >{{ one.text }}</span>
        </Button>
      </div>
    </FadedScroll>
  </nav>
</template>

<script setup>
import { toRef } from 'vue'

import { Button } from '@/ui'
import FadedScroll from '@/shared/components/FadedScroll.vue'
import { useOutline } from '@/shared/composables/useOutline'

const props = defineProps({
  editor: { type: Object, default: null },
  // Bumped by the host on every transaction.
  revision: { type: Number, default: 0 },
})

const { headings, worthShowing, active, go } = useOutline(
  toRef(props, 'editor'),
  toRef(props, 'revision'),
)
</script>
