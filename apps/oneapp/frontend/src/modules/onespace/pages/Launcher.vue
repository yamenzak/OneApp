<template>
  <!--
    A trail of one, which is the same thing every other surface's header is:
    the workspace name it used to carry as a second line is in the rail's own
    header now, and two lines here made this the one page whose content
    started lower than the rest.
  -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center">
      <Breadcrumbs :items="[{ label: __('Spaces'), route: { name: 'Launcher' } }]" />
    </nav>
  </PageHeader>

  <div class="p-5">
    <div v-if="!session.loaded" class="grid place-items-center py-20">
      <LoadingIndicator class="size-5 text-ink-muted" />
    </div>

    <div v-else-if="spaces.length" class="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
      <Panel as="router-link" v-for="space in spaces" :key="space.space_code" :to="{ name: 'Screen', params: { spaceCode: space.space_code } }" :class="['transition hover:border-outline-gray-3', HOVER]">
        <div class="flex items-start gap-3">
          <!-- Its mark, its logo, or its letter — `SpaceFace` decides, so the
               rail and the marketplace decide the same way. -->
          <SpaceFace :space="space" size="xl" />
          <div class="min-w-0">
            <p class="truncate text-base-medium text-ink-primary">{{ space.space_label }}</p>
            <p v-if="space.description" class="mt-0.5 line-clamp-2 text-p-sm text-ink-secondary">
              {{ space.description }}
            </p>
          </div>
        </div>
      </Panel>
    </div>

    <EmptyState
      v-else
      icon="lucide-layout-grid"
      :title="__('No spaces yet')"
      :description="__('Nothing has been added to your workspace. An admin can add a space, and it appears here.')"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Breadcrumbs, PageHeader, LoadingIndicator } from '@/ui'
import SpaceFace from '@/shared/components/brand/SpaceFace.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { session } from '@/modules/onespace/lib/shell/session'
import { __ } from '@/shared/lib/runtime/translate'
import Panel from '@/shared/components/Panel.vue'
import { HOVER } from '@/shared/lib/rowstate'

const spaces = computed(() => session.spaces)
</script>
