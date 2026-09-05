<template>
  <!--
    What is going up, and how far it has got.

    Bottom right, over everything, and only while there is something to say —
    the shape Frappe Drive's `UploadTracker` uses and the shape every file
    manager uses, because an upload is the one action a person starts and then
    stops looking at.

    It is a panel and not a dialog on purpose: a dialog would block the folder
    somebody is dropping the next four files into.
  -->
  <div
    v-if="uploads.items.length"
    data-slot="upload-tray"
    class="fixed bottom-4 right-4 z-20 w-80 max-w-[calc(100vw-2rem)] overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-elevation-2 shadow-2xl"
  >
    <div class="flex items-center gap-2 border-b border-outline-gray-1 px-3 py-2">
      <p class="min-w-0 flex-1 truncate text-p-sm font-medium text-ink-gray-8">
        {{ heading }}
      </p>
      <Button
        :icon="open ? 'lucide-chevron-down' : 'lucide-chevron-up'"
        variant="ghost"
        :label="open ? 'Collapse uploads' : 'Expand uploads'"
        :tooltip="open ? 'Collapse' : 'Expand'"
        @click="open = !open"
      />
      <!-- Only once nothing is in flight. Closing mid-upload would leave four
           requests running with nothing on screen that could report them. -->
      <Button
        v-if="!uploads.active.value.length"
        icon="lucide-x"
        variant="ghost"
        label="Dismiss uploads"
        tooltip="Dismiss"
        @click="uploads.clearDone()"
      />
    </div>

    <div v-show="open" class="max-h-64 overflow-y-auto">
      <div
        v-for="one in uploads.items"
        :key="one.id"
        class="flex items-center gap-2 border-b border-outline-gray-1 px-3 py-2 last:border-b-0"
      >
        <Icon :name="iconFor(one)" class="size-4 shrink-0" :class="tintFor(one)" />

        <div class="min-w-0 flex-1">
          <p class="truncate text-p-xs text-ink-gray-7">{{ one.name }}</p>
          <!-- The error where the progress bar was: a row that failed has
               nothing left to say about how far it got. -->
          <p v-if="one.state === 'failed'" class="truncate text-p-xs text-ink-red-4">
            {{ one.error }}
          </p>
          <Progress
            v-else-if="one.state !== 'done'"
            class="mt-1"
            size="sm"
            :value="one.progress"
          />
        </div>

        <Button
          v-if="one.state === 'failed'"
          icon="lucide-rotate-ccw"
          variant="ghost"
          :label="`Try ${one.name} again`"
          tooltip="Try again"
          @click="uploads.retry(one.id)"
        />
        <Button
          v-else-if="one.state === 'queued'"
          icon="lucide-x"
          variant="ghost"
          :label="`Do not upload ${one.name}`"
          tooltip="Remove"
          @click="uploads.remove(one.id)"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Icon, Progress } from '@/ui'

import { useUploads } from '../../composables/useUploads'

const uploads = useUploads()
const open = ref(true)

const heading = computed(() => {
  const going = uploads.active.value.length
  if (going) return `Uploading ${going} file${going === 1 ? '' : 's'}`
  const failed = uploads.failed.value.length
  if (failed) return `${failed} file${failed === 1 ? '' : 's'} did not upload`
  const done = uploads.done.value.length
  return `${done} file${done === 1 ? '' : 's'} uploaded`
})

const iconFor = (one) =>
  ({
    done: 'lucide-circle-check',
    failed: 'lucide-circle-alert',
  })[one.state] || 'lucide-arrow-up-circle'

const tintFor = (one) =>
  ({
    done: 'text-ink-green-3',
    failed: 'text-ink-red-3',
  })[one.state] || 'text-ink-gray-5'
</script>
