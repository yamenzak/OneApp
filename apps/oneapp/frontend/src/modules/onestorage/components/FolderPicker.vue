<!--
  Where to put it.

  A flat list of folders and not a tree, deliberately. A tree is the right shape
  for browsing and the wrong one for choosing: the person moving a file already
  knows the folder's name, and making them expand three levels to find it is a
  worse answer than typing two letters. The path under each name is what keeps
  two folders called "Drawings" apart.
-->
<template>
  <Picker
    v-model="open"
    :title="__('Move to a folder')"
    :said="what"
    :source="look"
    :placeholder="__('Search folders')"
    empty-icon="lucide-folder"
    :empty-title="__('No folders')"
    :empty-description="__('Make one from the header, then move things into it.')"
    @pick="(one) => choose(one.name)"
  >
    <!-- The top of the drive is a destination like any other, and the one
         people want most: it is where something goes when it should not be
         filed anywhere in particular. Above the search rather than in the
         list, because it is not a folder and so is not there to be found. -->
    <template #before>
      <Row edge="rounded" pad="tight" @click="choose('Home')">
        <template #lead>
          <Icon name="lucide-hard-drive" class="size-4 text-ink-muted" />
        </template>
        <span class="text-sm text-ink-primary">{{ __('All files') }}</span>
      </Row>
    </template>

    <template #option="{ one }">
      <span class="flex min-w-0 flex-col">
        <span class="truncate text-sm text-ink-primary">{{ one.file_name }}</span>
        <span class="truncate text-xs text-ink-muted">{{ trail(one) }}</span>
      </span>
    </template>

    <template #after><ErrorMessage :message="error" /></template>
  </Picker>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Icon, ErrorMessage } from '@/ui'
import Picker from '@/shared/components/Picker.vue'
import Row from '@/shared/components/Row.vue'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const props = defineProps({
  // What is being moved, so the dialog can say so rather than making the
  // person remember what they selected before they opened it.
  moving: { type: Array, default: () => [] },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['chosen'])

const error = ref('')

const what = computed(() => {
  const count = props.moving.length
  if (count === 1) return __('Moving {0}.', [props.moving[0].file_name])
  return __('Moving {0} things.', [count])
})

// `Home/Drawings` reads as "in All files"; a nested one keeps its parent.
const trail = (one) => {
  const parent = (one.folder || 'Home').split('/').pop()
  return parent === 'Home' ? __('In All files') : __('In {0}', [parent])
}

//: The search, the debounce and the skeleton are the picker's; this is only
//: the query. `driveList` already searches server-side, which is why the
//: source is a function and not the array of folders.
async function look(asked) {
  error.value = ''
  try {
    const found = await workspace.driveList({
      place: 'all',
      kind: 'Folder',
      search: asked,
      limit: 50,
    })
    // A thing cannot be moved into itself, and a folder cannot be moved into
    // its own child — the server refuses that second one, but offering it is
    // still offering a mistake.
    const excluded = new Set(props.moving.map((one) => one.name))
    return (found?.files || []).filter((one) => !excluded.has(one.name))
  } catch (raised) {
    error.value = errorText(raised)
    return []
  }
}

function choose(folder) {
  emit('chosen', folder)
  open.value = false
}
</script>
