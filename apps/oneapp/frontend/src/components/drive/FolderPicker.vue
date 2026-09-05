<!--
  Where to put it.

  A flat list of folders and not a tree, deliberately. A tree is the right shape
  for browsing and the wrong one for choosing: the person moving a file already
  knows the folder's name, and making them expand three levels to find it is a
  worse answer than typing two letters. The path under each name is what keeps
  two folders called "Drawings" apart.
-->
<template>
  <Dialog v-model="open" title="Move to a folder">
    <template #default>
      <div class="flex flex-col gap-3 py-2">
        <p class="text-p-sm text-ink-gray-6">
          {{ what }}
        </p>

        <FormControl
          v-model="query"
          type="text"
          placeholder="Search folders"
          @input="onSearch"
        />

        <div v-if="loading" class="flex flex-col gap-2">
          <Skeleton v-for="n in 5" :key="n" class="h-9 w-full" />
        </div>

        <div v-else class="flex max-h-80 min-h-0 flex-col overflow-y-auto">
          <!-- The top of the drive is a destination like any other, and the one
               people want most: it is where something goes when it should not
               be filed anywhere in particular. -->
          <Button
            variant="ghost"
            class="!justify-start"
            icon-left="lucide-hard-drive"
            label="All files"
            @click="choose('Home')"
          />
          <Button
            v-for="one in folders"
            :key="one.name"
            variant="ghost"
            class="!h-auto !justify-start !py-2"
            :label="one.file_name"
            @click="choose(one.name)"
          >
            <span class="flex min-w-0 flex-col text-left">
              <span class="truncate text-p-sm text-ink-gray-8">{{ one.file_name }}</span>
              <span class="truncate text-p-xs text-ink-gray-5">{{ trail(one) }}</span>
            </span>
          </Button>

          <EmptyState
            v-if="!folders.length"
            class="!py-6"
            icon="lucide-folder"
            title="No folders"
            description="Make one from the header, then move things into it."
          />
        </div>

        <ErrorMessage :message="error" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dialog, ErrorMessage, FormControl, Skeleton } from '@/ui'
import EmptyState from '../EmptyState.vue'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  // What is being moved, so the dialog can say so rather than making the
  // person remember what they selected before they opened it.
  moving: { type: Array, default: () => [] },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['chosen'])

const folders = ref([])
const query = ref('')
const loading = ref(false)
const error = ref('')

const what = computed(() => {
  const count = props.moving.length
  if (count === 1) return `Moving ${props.moving[0].file_name}.`
  return `Moving ${count} things.`
})

// `Home/Drawings` reads as "in All files"; a nested one keeps its parent.
const trail = (one) => {
  const parent = (one.folder || 'Home').split('/').pop()
  return parent === 'Home' ? 'In All files' : `In ${parent}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const found = await workspace.driveList({
      place: 'all',
      kind: 'Folder',
      search: query.value,
      limit: 50,
    })
    // A thing cannot be moved into itself, and a folder cannot be moved into
    // its own child — the server refuses that second one, but offering it is
    // still offering a mistake.
    const excluded = new Set(props.moving.map((one) => one.name))
    folders.value = (found?.files || []).filter((one) => !excluded.has(one.name))
  } catch (raised) {
    error.value = raised.message || String(raised)
  } finally {
    loading.value = false
  }
}

let typing = null
function onSearch() {
  clearTimeout(typing)
  typing = setTimeout(load, 300)
}

function choose(folder) {
  emit('chosen', folder)
  open.value = false
}

watch(open, (showing) => {
  if (showing) {
    query.value = ''
    load()
  }
})
</script>
