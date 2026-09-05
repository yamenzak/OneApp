<!--
  Every key this screen answers to.

  A shortcut nobody can find is a shortcut nobody uses, and the place people
  look is `?` — which is why `?` opens this and is itself in the list. Frappe
  Mail has the same dialog and it is the right shape: grouped by what somebody
  is trying to do, keys on the right, no search box for a page of twenty.
-->
<template>
  <Dialog v-model="open" title="Keyboard shortcuts" size="2xl">
    <template #default>
      <div class="grid gap-6 py-2 sm:grid-cols-2" data-slot="mail-shortcuts">
        <div v-for="group in groups" :key="group.title" class="flex flex-col gap-2">
          <h3 class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
            {{ group.title }}
          </h3>
          <div
            v-for="row in group.keys"
            :key="row[1]"
            class="flex items-baseline justify-between gap-4"
          >
            <span class="text-p-sm text-ink-gray-7">{{ row[1] }}</span>
            <span class="flex shrink-0 items-baseline gap-1">
              <!-- `or` and `then` sit between the keys unboxed, because they
                   are words about the keys rather than keys. -->
              <span
                v-for="(key, at) in row[0]"
                :key="at"
                class="text-p-xs text-ink-gray-6"
                :class="WORDS.includes(key) ? '' : KEY"
              >{{ key }}</span>
            </span>
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { Dialog } from '@/ui'

const open = defineModel({ type: Boolean, default: false })

defineProps({
  /** `[{ title, keys: [[['Shift', 'U'], 'Mark as read']] }]`. */
  groups: { type: Array, default: () => [] },
})

const WORDS = ['or', 'then']

// A key looks like a key: a small filled block at the control radius, which is
// what every shortcut sheet has drawn since the first one. Filled rather than
// outlined because an outlined block in this product is a card, and the radius
// guard is right to say so.
const KEY = 'rounded-4 bg-surface-gray-3 px-1.5 py-0.5 font-mono'
</script>
