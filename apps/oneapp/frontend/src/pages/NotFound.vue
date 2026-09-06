<template>
  <!-- A header even here: the page somebody mistyped their way to is still a
       page, and one that starts where none of the others do reads as the shell
       having broken rather than the route being wrong. -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center">
      <Breadcrumbs :items="[{ label: __('Not found'), route: $route.fullPath }]" />
    </nav>
  </PageHeader>

  <div class="grid place-items-center p-8 py-24">
    <EmptyState
      icon="lucide-compass"
      :title="__('Nothing at this address')"
      :description="__('Your spaces are all still where you left them.')"
    >
      <template #action>
        <Button :label="__('Back to your spaces')" @click="$router.push({ name: 'Launcher' })" />
      </template>
    </EmptyState>
  </div>
</template>

<script setup>
import { Breadcrumbs, Button, PageHeader } from '@/ui'
import EmptyState from '../components/EmptyState.vue'
import { __ } from '@/lib/runtime/translate'
</script>
