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
  <Panel ground="raised" pad="none" elevation="over" v-if="uploads.items.length" data-slot="upload-tray" class="fixed bottom-4 end-4 z-20 w-80 max-w-[calc(100vw-2rem)] overflow-hidden">
    <div class="flex items-center gap-2 border-b border-outline-gray-1 px-3 py-2">
      <p class="min-w-0 flex-1 truncate text-sm font-medium text-ink-primary">
        {{ heading }}
      </p>
      <Button
        :icon="open ? 'lucide-chevron-down' : 'lucide-chevron-up'"
        variant="ghost"
        :label="open ? __('Collapse uploads') : __('Expand uploads')"
        :tooltip="open ? __('Collapse') : __('Expand')"
        @click="open = !open"
      />
      <!-- Only once nothing is in flight. Closing mid-upload would leave four
           requests running with nothing on screen that could report them. -->
      <Button
        v-if="!uploads.active.value.length"
        icon="lucide-x"
        variant="ghost"
        :label="__('Dismiss uploads')"
        :tooltip="__('Dismiss')"
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
          <p class="truncate text-xs text-ink-secondary">{{ one.name }}</p>
          <!-- The error where the progress bar was: a row that failed has
               nothing left to say about how far it got. -->
          <p v-if="one.state === 'failed'" class="truncate text-xs text-ink-red-4">
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
          :label="__('Try {0} again', [one.name])"
          :tooltip="__('Try again')"
          @click="uploads.retry(one.id)"
        />
        <Button
          v-else-if="one.state === 'queued'"
          icon="lucide-x"
          variant="ghost"
          :label="__('Do not upload {0}', [one.name])"
          :tooltip="__('Remove')"
          @click="uploads.remove(one.id)"
        />
      </div>
    </div>
  </Panel>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Icon, Progress } from '@/ui'

import { useUploads } from '@/shared/composables/useUploads'
import { __ } from '@/shared/lib/runtime/translate'
import Panel from '@/shared/components/Panel.vue'

const uploads = useUploads()
const open = ref(true)

const heading = computed(() => {
  const going = uploads.active.value.length
  if (going) return going === 1 ? __('Uploading {0} file', [going]) : __('Uploading {0} files', [going])
  const failed = uploads.failed.value.length
  if (failed) {
    return failed === 1
      ? __('{0} file did not upload', [failed])
      : __('{0} files did not upload', [failed])
  }
  const done = uploads.done.value.length
  return done === 1 ? __('{0} file uploaded', [done]) : __('{0} files uploaded', [done])
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
  })[one.state] || 'text-ink-muted'
</script>
