<template>
  <PageHeader>
    <PageHeaderTitle>Apps</PageHeaderTitle>
    <Button
      v-if="data?.workspace_url"
      label="Open workspace"
      icon-left="lucide-external-link"
      @click="open"
    />
  </PageHeader>

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <div v-if="resource.loading && !data" class="grid place-items-center py-16">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else-if="data" class="py-5">
      <p class="mb-4 text-p-sm text-ink-gray-6">
        Everything here is already part of your workspace. Plans differ in how
        much you can store and how many people you can invite — never in which
        apps you get.
      </p>

      <div class="grid gap-3 sm:grid-cols-2">
        <div
          v-for="app in data.apps"
          :key="app.code"
          class="flex items-start gap-3 rounded-6 border border-outline-gray-2 p-4"
        >
          <Avatar :label="app.label" shape="square" size="lg" />
          <div class="min-w-0 flex-1">
            <p class="truncate text-base-medium text-ink-gray-8">{{ app.label }}</p>
            <p class="mt-0.5 text-p-sm text-ink-gray-5">
              {{ app.included ? 'Included with every plan' : 'Enabled for your workspace' }}
            </p>
          </div>
        </div>
      </div>

      <EmptyState
        v-if="!data.apps.length"
        icon="lucide-layout-grid"
        title="No apps yet"
        description="Nothing has been enabled for this workspace. Get in touch and we will sort it out."
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PageHeader, PageHeaderTitle, Avatar, Button, LoadingIndicator } from '@/ui'
import EmptyState from '../../components/EmptyState.vue'
import { useApps } from '../../lib/customer'

const props = defineProps({ workspace: { type: String, required: true } })
const workspace = computed(() => props.workspace)

const resource = useApps(workspace)
const data = computed(() => resource.data)

const open = () => window.open(data.value.workspace_url, '_blank', 'noopener')
</script>
