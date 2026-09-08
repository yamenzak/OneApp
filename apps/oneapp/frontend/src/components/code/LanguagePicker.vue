<template>
  <!--
    Which language a new code file is.

    A dialog rather than a submenu under New. Twenty-one languages is a
    scrolling menu that covers the screen and buries the four kinds beside it,
    and the question is worth its own moment: the extension is the only thing
    that decides what a file is here, so picking it is picking the file.

    Searchable, because a person who knows they want Ruby should not read
    twenty rows to find it, and because the list is alphabetical by label —
    which puts `.rb` under R and nowhere near the top.
  -->
  <Dialog v-model="open" :title="__('New code file')" size="lg">
    <template #default>
      <div class="flex flex-col gap-3">
        <FormControl
          v-model="hunt"
          type="text"
          :placeholder="__('Search languages')"
          :aria-label="__('Search languages')"
        />

        <div
          v-if="found.length"
          class="grid max-h-80 grid-cols-2 gap-1 overflow-y-auto sm:grid-cols-3"
          data-slot="language-list"
        >
          <button
            v-for="one in found"
            :key="one.key"
            type="button"
            data-slot="language-option"
            class="flex items-center justify-between gap-2 rounded-4 px-3 py-2 text-start text-p-sm text-ink-gray-8 hover:bg-surface-gray-2"
            @click="pick(one)"
          >
            <span class="truncate">{{ one.label }}</span>
            <!-- The extension, because it is what the file will be called and
                 because two languages can read alike and write differently. -->
            <span class="shrink-0 font-mono text-p-xs text-ink-gray-4">.{{ one.key }}</span>
          </button>
        </div>

        <p v-else class="px-1 py-6 text-center text-p-sm text-ink-gray-5">
          {{ __('No language here goes by that name.') }}
        </p>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Dialog, FormControl } from '@/ui'
import { languageOptions } from '@/lib/files/languages'
import { __ } from '@/lib/runtime/translate'

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['pick'])

const hunt = ref('')

const ALL = languageOptions()

// The extension as well as the label, so `py` finds Python and `rb` finds Ruby
// — which is what somebody who writes code will actually type.
const found = computed(() => {
  const asked = hunt.value.trim().toLowerCase()
  if (!asked) return ALL
  return ALL.filter(
    (one) => one.label.toLowerCase().includes(asked) || one.key.includes(asked),
  )
})

function pick(one) {
  open.value = false
  emit('pick', one)
}

// Emptied on close rather than on open: a dialog that clears while it is
// fading out shows the whole list flashing back for a frame.
watch(open, (now) => { if (!now) hunt.value = '' })
</script>
