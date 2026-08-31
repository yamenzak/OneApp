<template>
  <div class="flex flex-col gap-4 pt-4">
    <!--
      Uploading attaches in the same request. Frappe's own upload endpoint
      takes the doctype and the name and files the row against them, so there
      is no second call to make and no window where a file exists but belongs
      to nothing.
    -->
    <FileUploader
      v-if="canWrite"
      :doctype="doctype"
      :docname="name"
      @success="reload"
      @failure="failed"
    >
      <template #default="{ openFileSelector, uploading, progress }">
        <Button
          class="w-full"
          icon-left="lucide-paperclip"
          :label="uploading ? `Uploading ${progress}%` : 'Attach a file'"
          :loading="uploading"
          @click="openFileSelector"
        />
      </template>
    </FileUploader>

    <LoadingText v-if="loading" text="Loading files" />

    <EmptyState
      v-else-if="!files.length"
      class="!py-8"
      icon="lucide-paperclip"
      title="No files"
      description="Nothing is filed against this one yet."
    />

    <ul v-else class="flex flex-col gap-1">
      <li
        v-for="file in files"
        :key="file.name"
        class="flex items-center gap-2 rounded-4 px-2 py-1.5 hover:bg-surface-gray-2"
      >
        <Icon :name="iconFor(file)" class="size-4 shrink-0 text-ink-gray-5" />
        <!--
          A link and not a button: a file is a URL, and the browser's own
          "open in a new tab" and "save as" are worth more than anything a
          click handler could offer.
        -->
        <a
          :href="file.file_url"
          target="_blank"
          rel="noopener"
          class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-8 hover:underline"
        >
          {{ file.file_name || file.file_url }}
        </a>
        <span class="shrink-0 text-p-xs tabular-nums text-ink-gray-5">{{ size(file) }}</span>
        <Button
          v-if="canWrite"
          icon="lucide-trash-2"
          variant="ghost"
          theme="red"
          :label="`Remove ${file.file_name || 'this file'}`"
          :tooltip="`Remove ${file.file_name || 'this file'}`"
          @click="remove(file)"
        />
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, FileUploader, Icon, LoadingText } from '@/ui'
import EmptyState from '../EmptyState.vue'
import { workspace } from '../../lib/workspace'
import { humanSize as size, iconFor } from '../../lib/files'
import { notifyError } from '../../lib/notify'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, default: '' },
  canWrite: { type: Boolean, default: false },
})

const files = ref([])
const doctype = ref('')
const loading = ref(false)

const reload = async () => {
  if (!props.name) {
    files.value = []
    return
  }
  loading.value = true
  try {
    const found = await workspace.attachments(props.spaceCode, props.screen, props.name)
    files.value = found?.files || []
    doctype.value = found?.doctype || ''
  } finally {
    loading.value = false
  }
}

const failed = (error) => notifyError(error?.message || String(error))

const remove = async (file) => {
  await workspace.removeAttachment(props.spaceCode, props.screen, props.name, file.name)
  await reload()
}

watch(() => props.name, reload, { immediate: true })
</script>
