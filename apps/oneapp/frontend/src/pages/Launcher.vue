<template>
  <PageHeader>
    <div>
      <span class="text-base-medium text-ink-gray-8">Your spaces</span>
      <p class="text-p-sm text-ink-gray-5">
        Everything enabled for {{ session.tenant?.name || 'this workspace' }}.
      </p>
    </div>
  </PageHeader>

  <div class="p-5">
    <div v-if="!session.loaded" class="grid place-items-center py-20">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else-if="spaces.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <router-link
        v-for="space in spaces"
        :key="space.space_code"
        :to="{ name: 'Screen', params: { spaceCode: space.space_code } }"
        class="rounded-6 border border-outline-gray-2 bg-surface-base p-4 transition hover:border-outline-gray-3 hover:bg-surface-gray-1"
      >
        <div class="flex items-start gap-3">
          <!-- The manifest's logo where there is one; initials otherwise, which
               is what Avatar draws from a label on its own. -->
          <Avatar :label="space.space_label" :image="space.logo" shape="square" size="lg" />
          <div class="min-w-0">
            <p class="truncate text-base-medium text-ink-gray-8">{{ space.space_label }}</p>
            <p v-if="space.description" class="mt-0.5 line-clamp-2 text-p-sm text-ink-gray-6">
              {{ space.description }}
            </p>
          </div>
        </div>
      </router-link>
    </div>

    <EmptyState
      v-else
      icon="lucide-layout-grid"
      title="No spaces yet"
      description="Nothing has been enabled for this workspace. If you were expecting something here, get in touch and we will sort it out."
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { PageHeader, Avatar, LoadingIndicator } from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import { session } from '../lib/session'

const spaces = computed(() => session.spaces)
</script>
