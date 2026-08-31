<template>
  <div>
    <div v-if="state.loading && !state.loaded" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <!-- Named rather than blank. "Frappe Cloud is unreachable" is worth more
         than an empty table, which reads as "there is nothing here". -->
    <Alert v-else-if="state.error" theme="amber" title="Frappe Cloud did not answer">
      <template #description>{{ state.error }}</template>
      <template #actions>
        <Button label="Try again" :loading="state.loading" @click="$emit('retry')" />
      </template>
    </Alert>

    <EmptyState v-else-if="isEmpty" icon="lucide-inbox" :title="empty" />

    <slot v-else />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Alert, Button, LoadingIndicator } from '@/ui'
import EmptyState from '../../components/EmptyState.vue'

const props = defineProps({
  /** The object usePress() returns. */
  state: { type: Object, required: true },
  /** What to say when the call worked and there is nothing in it. */
  empty: { type: String, default: 'Nothing here yet.' },
})

defineEmits(['retry'])

// A panel is empty when the payload's one list is empty, or when the endpoint
// declined with a reason (no site yet, say) rather than a failure.
const isEmpty = computed(() => {
  const data = props.state.data
  if (!data) return true
  if (data.reason) return true
  const list = Object.values(data).find((value) => Array.isArray(value))
  if (list) return list.length === 0
  return !data.site
})
</script>
