<template>
  <!--
    How the page is set: how wide, in what face, how far apart the lines.

    A reader's choice about *this* document, stored on it rather than in a
    workspace setting — a contract wants a narrow measure and a rate schedule
    wants the full width, and the same person wants both on the same afternoon.
  -->
  <Dialog v-model="open" :title="__('Page setup')">
    <template #default>
      <div class="flex flex-col gap-4">
        <FormControl
          v-model="draft.width"
          type="select"
          :label="__('Width')"
          :options="options(WIDTHS)"
        />
        <FormControl
          v-model="draft.font"
          type="select"
          :label="__('Typeface')"
          :options="options(FONTS)"
        />
        <FormControl
          v-model="draft.spacing"
          type="select"
          :label="__('Line spacing')"
          :options="options(SPACINGS)"
        />
      </div>
    </template>
    <template #actions>
      <Button variant="solid" :label="__('Apply')" class="w-full" @click="apply" />
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue'

import { Button, Dialog, FormControl } from '@/ui'
import { FONTS, SPACINGS, WIDTHS } from './toolbar'
import { __ } from '@/lib/runtime/translate'

const open = defineModel({ type: Boolean, default: false })
const settings = defineModel('settings', { type: Object, default: () => ({}) })

const emit = defineEmits(['change'])

const draft = ref({ ...settings.value })

const options = (from) =>
  Object.entries(from).map(([value, one]) => ({ label: one.label, value }))

function apply() {
  settings.value = { ...settings.value, ...draft.value }
  open.value = false
  emit('change')
}

// Opened again after a change elsewhere — the lock, say — so the draft starts
// from what the document actually says rather than from the last look at it.
watch(open, (showing) => {
  if (showing) draft.value = { ...settings.value }
})
</script>
