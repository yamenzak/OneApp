<template>
  <!--
    Give a selection to somebody.

    Assignment is not a field — Frappe keeps it in `_assign`, and the whole
    machinery around it (the notification, the ToDo, the sidebar count) hangs
    off `assign_to.add` — so it cannot ride on the bulk field change and needs
    its own two lines.

    Added and never replaced, which is the opposite of what the single-record
    control does and is right for both: one record's assignment is a list
    somebody is looking at and editing whole, and a selection's is not on
    screen at all. Replacing forty assignments with one name is a way to take
    work off thirty-nine people by accident.
  -->
  <Dialog v-model="showing" :title="`Assign ${count} ${count === 1 ? 'record' : 'records'}`">
    <div class="flex flex-col gap-4">
      <!-- The same control the record's own assignment draws, and the same
           endpoint behind it — so who this workspace can assign to is one
           answer rather than two. -->
      <MultiSelect
        v-model="chosen"
        v-model:query="query"
        :options="options"
        :loading="loading"
        :filterable="false"
        label="People"
        placeholder="Somebody on this workspace"
        empty-text="Nobody by that name"
      />
      <p class="text-p-sm text-ink-gray-6">
        They are <span class="font-medium text-ink-gray-8">added</span> to whoever
        is already on these records rather than replacing them.
      </p>
    </div>

    <template #actions>
      <Button label="Never mind" @click="showing = false" />
      <Button
        variant="solid"
        label="Assign"
        :disabled="!people.length"
        :loading="working"
        @click="emit('apply', people)"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dialog, MultiSelect } from '@/ui'
import { workspace } from '../../../lib/workspace'

const props = defineProps({
  count: { type: Number, default: 0 },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  working: { type: Boolean, default: false },
})

const emit = defineEmits(['apply'])

const showing = defineModel({ type: Boolean, default: false })

const chosen = ref([])
const query = ref('')
const options = ref([])
const loading = ref(false)

const people = computed(() =>
  (Array.isArray(chosen.value) ? chosen.value : [chosen.value])
    .filter(Boolean)
    .map((one) => one.value || one),
)

/**
 * Who could be assigned, from the same endpoint the record's own control asks.
 *
 * Fetched when the dialog opens rather than with the list: a workspace's user
 * list is not part of reading a page of rows, and most lists are read without
 * anybody assigning anything.
 */
const search = async () => {
  loading.value = true
  try {
    options.value =
      (await workspace.assignees(props.spaceCode, props.screen, query.value)) || []
  } finally {
    loading.value = false
  }
}

// The list narrows as somebody types, from the server rather than in the
// browser: `filterable` is off because a workspace's people are paged.
watch(query, search)

watch(showing, (open) => {
  if (!open) return
  // Empty rather than showing the last people somebody chose, which is a
  // selection they might apply twice without meaning to.
  chosen.value = []
  search()
})
</script>
