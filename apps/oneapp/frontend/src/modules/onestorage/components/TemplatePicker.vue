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
  <Picker
    v-model="open"
    :title="__('Load a template')"
    :said="said"
    :source="rows"
    :searchable="rows.length > SEARCH_FROM"
    :placeholder="__('Search templates')"
    empty-icon="lucide-file"
    :empty-title="__('No templates yet')"
    :empty-description="__('Any file can be made one from its own menu.')"
    @pick="pick"
  >
    <template #option="{ one }">
      <span class="flex items-center gap-2" data-slot="template-row">
        <Icon :name="icon" class="size-4 shrink-0 text-ink-muted" />
        <span class="truncate text-sm text-ink-primary">{{ one.file_name }}</span>
      </span>
    </template>
  </Picker>
</template>

<script setup>
import { Icon } from '@/ui'
import Picker from '@/shared/components/Picker.vue'
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

//: Below this a search box is furniture: you can see every row at once, and
//: the field is the first thing the eye lands on for nothing.
const SEARCH_FROM = 8

// The dialog closes on the choice and the caller shows what happens next.
//
// There used to be a per-row spinner here, and it had never once been seen:
// it was cleared in the `finally` of an `await emit(...)`, and `emit` returns
// undefined, so the row went busy and un-busy inside one tick.
const pick = (row) => emit('pick', row)
</script>
