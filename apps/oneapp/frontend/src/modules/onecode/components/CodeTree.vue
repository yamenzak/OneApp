<template>
  <!--
    The other files in this folder, beside the one that is open.

    `docs/UNIFICATION.md` §E9's first rail says a project is a folder of `File`
    rows and nothing else — no second store, no project doctype, no row to keep
    in step with the Drive. Which means a file tree is not a new thing to build:
    it is the folder's own listing, narrowed to what opens in this editor, in
    the panel beside it. Moving between two files of one project is a route
    change like any other, so the back button works and a link to a file is a
    link to that file.

    One level. A folder inside a project is a folder you walk into from the
    Drive; a tree that recursed would be a second file manager growing beside
    the first, which is the shape §E9 says must not happen.
  -->
  <aside
    data-slot="code-tree"
    class="flex w-56 shrink-0 flex-col border-s border-outline-gray-1 bg-surface-base"
  >
    <div class="flex h-10 shrink-0 items-center gap-2 border-b border-outline-gray-2 px-3">
      <span class="min-w-0 flex-1 truncate text-sm font-medium text-ink-primary">
        {{ folderName }}
      </span>
      <Button
        variant="ghost"
        size="sm"
        icon="lucide-x"
        :label="__('Close')"
        :tooltip="__('Close')"
        @click="emit('close')"
      />
    </div>

    <!-- The frame is `DataList` — §B1. No search and no sort: a project folder
         is a handful of files and a box over six rows answers nothing. -->
    <div class="min-h-0 flex-1 overflow-auto p-1.5">
      <DataList :source="source" :skeleton="4" skeleton-class="h-8 w-full">
        <template #row="{ row: file }">
          <RouterLink
            :to="{ name: 'Doc', params: { name: file.name } }"
            data-slot="code-tree-file"
            :class="[
              'flex items-center gap-2 rounded-4 px-2 py-1.5 text-sm',
              file.name === current
                ? 'bg-surface-gray-2 font-medium text-ink-primary'
                : ['text-ink-secondary', HOVER],
            ]"
          >
            <Icon name="lucide-file-code" class="size-4 shrink-0 text-ink-muted" />
            <span class="min-w-0 truncate">{{ file.file_name }}</span>
          </RouterLink>
        </template>
      </DataList>
    </div>
  </aside>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import { Button, Icon } from '@/ui'
import DataList from '@/shared/components/DataList.vue'
import { staticSource } from '@/shared/lib/list/source'
import { isCode } from '@/modules/onestorage/lib/languages'
import { HOVER } from '@/shared/lib/rowstate'
import { __ } from '@/shared/lib/runtime/translate'
import { workspace } from '@/shared/lib/workspace'

const props = defineProps({
  /** The `File` row of the folder these are in. */
  folder: { type: String, required: true },
  /** Which of them is open, so the row for it is marked rather than a link. */
  current: { type: String, default: '' },
  /** What it is called, for the case where the listing does not return it. */
  title: { type: String, default: '' },
})

const emit = defineEmits(['close'])

const rows = ref([])
const loading = ref(true)
const folderName = ref(__('This folder'))

const source = computed(() => staticSource({
  rows: rows.value,
  loading: loading.value,
  key: (file) => file.name,
  empty: {
    icon: 'lucide-file-code',
    title: __('No other files here'),
    description: __('Files you add to this folder appear here.'),
  },
}))

/**
 * The folder's own listing, narrowed to what this editor opens.
 *
 * Narrowed here rather than by a filter on the request: the server's `kind` is
 * `Code`, and a project's folder also holds the `onecode.json` that makes it a
 * project — which is a `.json`, which is Code, so one filter covers both. What
 * it must not show is the folders and the images, because clicking one of
 * those would open something this editor cannot edit.
 */
async function load() {
  loading.value = true
  try {
    const answer = await workspace.driveList({ place: 'home', folder: props.folder })
    const found = (answer?.files || []).filter(
      (file) => !file.is_folder && isCode(file.file_name),
    )
    // The open file first, whether or not the folder's listing returned it.
    // It does not always: a file attached to a record lives in a folder and is
    // deliberately absent from that folder's own listing, and a tree that did
    // not contain the file you are looking at is a tree that reads as the
    // wrong folder.
    rows.value = found.some((file) => file.name === props.current)
      ? found
      : [{ name: props.current, file_name: props.title || __('This file') }, ...found]
    // The folder's own name, from the trail the listing already answers with
    // — rather than a second call for one string, and rather than `details`,
    // which stamps `custom_opened` and would put every project folder in
    // Recents because somebody opened a file inside it.
    const trail = answer?.path || []
    if (trail.length) folderName.value = trail[trail.length - 1].label || folderName.value
  } catch {
    // A tree that will not load is a panel with nothing in it, which the empty
    // state already says. Nothing here is worth a toast over the editor.
    rows.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.folder, load, { immediate: true })
</script>
