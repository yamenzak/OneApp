<template>
  <PageHeader>
    <template #title>
      <Breadcrumbs :items="crumbs" />
    </template>
  </PageHeader>

  <div class="p-5">
    <EmptyState
      v-if="!app && session.loaded"
      icon="lucide-circle-help"
      title="App not available"
      description="This app is not enabled for your workspace, or you do not have access to it."
    />

    <EmptyState
      v-else-if="app"
      icon="lucide-hammer"
      title="Not built yet"
      :description="`${app.app_label} is enabled for this workspace, but its interface is still being built.`"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PageHeader, Breadcrumbs } from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import { session } from '../lib/session'

const props = defineProps({ appCode: { type: String, required: true } })

const app = computed(() =>
  (session.apps || []).find((a) => a.app_code === props.appCode),
)

const crumbs = computed(() => [
  { label: 'Apps', route: { name: 'Launcher' } },
  { label: app.value?.app_label || props.appCode },
])
</script>
