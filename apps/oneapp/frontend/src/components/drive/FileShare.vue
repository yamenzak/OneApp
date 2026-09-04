<!--
  Giving a file to a colleague.

  The same `DocShare` the record surface writes, over `File`, and therefore the
  same `SharePanel` — a file and a record are shared by the same three
  questions, so this component is the endpoint and nothing else.

  Sharing a *folder* shares everything under it, because `File.folder` is what
  the breadcrumb walks and `get_list` resolves the share at read time. Nothing
  is written per descendant, which is why moving a file into a shared folder
  needs no second thought.
-->
<template>
  <Dialog v-model="open" :title="`Share ${file?.file_name || 'this file'}`">
    <template #default>
      <SharePanel
        :people="shares.people || []"
        :everyone="shares.everyone"
        :can-share="!!shares.can_share"
        :empty-text="emptyText"
        :offer="offer"
        :save="save"
        :remove="remove"
        @shared="settled"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Dialog } from '@/ui'
import SharePanel from '../SharePanel.vue'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  file: { type: Object, default: null },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['shared'])

const shares = ref({})

const emptyText = computed(() =>
  props.file?.is_folder
    ? 'Nobody else can open this folder, or anything inside it.'
    : 'Only people who can open the record this is filed against can see it.',
)

const offer = (query) => workspace.driveColleagues(query)
const save = (what) => workspace.driveShare(props.file.name, what)
const remove = (what) => workspace.driveUnshare(props.file.name, what)

const settled = (result) => {
  shares.value = result
  emit('shared', result)
}

watch(open, async (showing) => {
  if (!showing || !props.file?.name) return
  shares.value = (await workspace.drivePeople(props.file.name)) || {}
})
</script>
