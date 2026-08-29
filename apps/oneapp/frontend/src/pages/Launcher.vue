<template>
  <PageHeader>
    <div>
      <span class="text-base-medium text-ink-gray-8">Your apps</span>
      <p class="text-p-sm text-ink-gray-5">
        Everything enabled for {{ session.tenant?.name || 'this workspace' }}.
      </p>
    </div>
</PageHeader>

  <div class="p-5">
    <div v-if="!session.loaded" class="grid place-items-center py-20">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else-if="apps.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <router-link
        v-for="app in apps"
        :key="app.app_code"
        :to="{ name: 'App', params: { appCode: app.app_code } }"
        class="rounded-6 border border-outline-gray-2 bg-surface-base p-4 transition hover:border-outline-gray-3 hover:bg-surface-gray-1"
      >
        <div class="flex items-start gap-3">
          <Avatar :label="app.app_label" shape="square" size="lg" />
          <div class="min-w-0">
            <p class="truncate text-base-medium text-ink-gray-8">{{ app.app_label }}</p>
            <p v-if="app.description" class="mt-0.5 line-clamp-2 text-p-sm text-ink-gray-6">
              {{ app.description }}
            </p>
          </div>
        </div>
      </router-link>
    </div>

    <EmptyState
      v-else
      icon="lucide-layout-grid"
      title="No apps yet"
      description="Nothing has been enabled for this workspace. If you were expecting something here, get in touch and we will sort it out."
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PageHeader, Avatar, LoadingIndicator } from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import { session } from '../lib/session'

const apps = computed(() => session.apps)
</script>
