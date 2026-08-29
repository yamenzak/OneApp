<template>
  <div class="grid h-full place-items-center p-8">
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
import { Button } from '@/ui'
import EmptyState from '../components/EmptyState.vue'
</script>
