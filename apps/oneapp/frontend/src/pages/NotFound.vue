<template>
  <!-- A header even here: the page somebody mistyped their way to is still a
       page, and one that starts where none of the others do reads as the shell
       having broken rather than the route being wrong. -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center">
      <Breadcrumbs :items="[{ label: 'Not found', route: $route.fullPath }]" />
    </nav>
  </PageHeader>

  <div class="grid place-items-center p-8 py-24">
    <EmptyState
      icon="lucide-compass"
      title="Page not found"
      description="That route does not exist. Your apps are all still where you left them."
    >
      <template #action>
        <Button label="Back to your apps" @click="$router.push({ name: 'Launcher' })" />
      </template>
    </EmptyState>
  </div>
</template>

<script setup>
import { Breadcrumbs, Button, PageHeader } from '@/ui'
import EmptyState from '../components/EmptyState.vue'
</script>
