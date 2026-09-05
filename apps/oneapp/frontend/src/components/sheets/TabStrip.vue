<template>
  <!--
    The tabs, along the foot, where a spreadsheet has kept them since 1993.

    A rename is a double-click on the tab rather than a menu item, because that
    is where everybody already tries it first.
  -->
  <div
    data-slot="sheet-tabs"
    class="flex shrink-0 items-center gap-1 overflow-x-auto border-t border-outline-gray-2 px-3 py-1.5"
  >
    <Button
      v-if="sheet.canWrite.value"
      icon="lucide-plus"
      label="Add a tab"
      tooltip="Add a tab"
      variant="ghost"
      @click="$emit('add')"
    />

    <template v-for="tab in sheet.tabs.value" :key="tab.tab_name">
      <FormControl
        v-if="renaming === tab.tab_name"
        v-model="draft"
        type="text"
        class="w-32"
        aria-label="Tab name"
        @keydown.enter="finishRename"
        @keydown.esc="renaming = ''"
        @blur="finishRename"
      />
      <Dropdown v-else :options="menuFor(tab)" side="top">
        <Button
          :label="tab.tab_name"
          variant="ghost"
          :class="tab.tab_name === sheet.active.value
            ? 'bg-surface-gray-3 font-medium text-ink-gray-9'
            : 'text-ink-gray-6'"
          @click="sheet.show(tab.tab_name)"
          @dblclick="startRename(tab)"
        />
      </Dropdown>
    </template>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { Button, Dropdown, FormControl } from '@/ui'

const props = defineProps({
  sheet: { type: Object, required: true },
})

const emit = defineEmits(['add', 'rename', 'remove'])

const sheet = props.sheet
const renaming = ref('')
const draft = ref('')

function startRename(tab) {
  if (!sheet.canWrite.value) return
  renaming.value = tab.tab_name
  draft.value = tab.tab_name
  nextTick()
}

function finishRename() {
  const from = renaming.value
  renaming.value = ''
  const to = draft.value.trim()
  if (!from || !to || to === from) return
  emit('rename', from, to)
}

function menuFor(tab) {
  if (!sheet.canWrite.value) return []
  return [
    { label: 'Rename', icon: 'lucide-pencil', onClick: () => startRename(tab) },
    {
      label: 'Delete',
      icon: 'lucide-trash-2',
      // Never the last one: a workbook with no tab is a grid with nowhere to
      // type. The server refuses it too; this is so the menu does not offer
      // something that will only fail.
      condition: () => sheet.tabs.value.length > 1,
      onClick: () => emit('remove', tab.tab_name),
    },
  ]
}
</script>
