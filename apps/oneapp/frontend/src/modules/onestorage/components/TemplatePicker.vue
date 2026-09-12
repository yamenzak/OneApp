<!--
  Load a template, from inside the thing you would load it into.

  It used to be rows in the Drive's New menu — six of them, capped, with an
  "All 14 templates…" row under. Wrong place twice over: New is a menu of
  *kinds*, and a workspace's own files in it made the kinds hard to find; and
  the moment you want a template is the moment you are looking at a blank
  sheet, not the moment you decided to make one.

  So it is here, and what it does is deliberately safe: it opens the template
  as a *new* file and leaves what you have alone. Nothing is written over,
  nothing is merged in, and the thing you were working on is still there in
  the tab you came from. That is the whole reason this is not called "apply".
-->
<template>
  <Dialog v-model="open" :title="__('Load a template')" size="lg">
    <template #default>
      <div class="flex flex-col gap-3 py-2">
        <p class="text-p-sm text-ink-secondary">{{ said }}</p>

        <div v-if="!rows.length" class="rounded-6 bg-surface-gray-1 p-4 text-p-sm text-ink-secondary">
          {{ __('This workspace has no templates yet. Any file can be made one from its own menu.') }}
        </div>

        <ScrollArea v-else class="max-h-80">
          <div class="flex flex-col gap-1">
            <Button
              v-for="row in rows"
              :key="row.name"
              variant="ghost"
              class="!justify-start"
              data-slot="template-row"
              :icon-left="icon"
              :label="row.file_name"
              :loading="busy === row.name"
              :disabled="!!busy"
              @click="pick(row)"
            />
          </div>
        </ScrollArea>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref } from 'vue'
import { Button, Dialog, ScrollArea } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  /** The templates to choose from, as `File` rows. */
  rows: { type: Array, default: () => [] },
  /** The lucide name for the kind — a sheet and a document look different. */
  icon: { type: String, default: 'lucide-file' },
  /** One sentence saying what pressing a row will do, in this kind's words. */
  said: { type: String, default: '' },
})

const emit = defineEmits(['pick'])

const open = defineModel({ type: Boolean, default: false })

// Named rather than a plain boolean, so the row you pressed is the row that
// spins — a list of eight where all eight go busy says nothing about which one
// is being made.
const busy = ref('')

async function pick(row) {
  busy.value = row.name
  try {
    await emit('pick', row)
  } finally {
    busy.value = ''
    open.value = false
  }
}
</script>
