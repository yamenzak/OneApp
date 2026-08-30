<template>
  <div class="flex flex-col gap-4 pt-4">
    <div class="flex items-start gap-2">
      <Textarea v-model="draft" :rows="2" placeholder="Add a comment" class="flex-1" />
      <Button
        label="Comment"
        :disabled="!draft.trim()"
        :loading="commenting"
        @click="addComment"
      />
    </div>

    <LoadingText v-if="loading" text="Loading comments" />

    <EmptyState
      v-else-if="!comments.length"
      class="!py-8"
      icon="lucide-message-square"
      title="No comments"
      description="Nothing has been said about this one yet."
    />

    <!-- The page is capped, and a list that silently stops at fifty reads as
         "that is all of them". -->
    <p v-if="more" class="text-p-xs text-ink-gray-5">
      Showing the {{ comments.length }} most recent of {{ count }}.
    </p>

    <div v-for="entry in comments" :key="entry.name" class="flex gap-3">
      <Avatar :label="entry.comment_by || entry.comment_email" size="sm" />
      <div class="min-w-0 flex-1">
        <div class="flex items-baseline gap-2">
          <span class="truncate text-p-sm font-medium text-ink-gray-8">
            {{ entry.comment_by || entry.comment_email }}
          </span>
          <span class="shrink-0 text-p-xs text-ink-gray-5">{{ when(entry.creation) }}</span>
        </div>
        <p class="whitespace-pre-wrap text-p-sm text-ink-gray-7">{{ entry.content }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Avatar, Button, LoadingText, Textarea, dayjsLocal } from '@/ui'
import EmptyState from '../EmptyState.vue'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, default: '' },
  comments: { type: Array, default: () => [] },
  /** How many there are, which is not how many came back. */
  count: { type: Number, default: 0 },
  more: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['added'])

const draft = ref('')
const commenting = ref(false)

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

const addComment = async () => {
  commenting.value = true
  try {
    await workspace.comment(props.spaceCode, props.screen, props.name, draft.value)
    draft.value = ''
    emit('added')
  } finally {
    commenting.value = false
  }
}
</script>
