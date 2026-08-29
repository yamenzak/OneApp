<template>
  <div class="grid h-full place-items-center p-8">
    <EmptyState title="Page not found" description="That route does not exist.">
      <template #action>
        <Button class="mt-4" label="Back to tenants" @click="$router.push({ name: 'Tenants' })" />
      </template>
    </EmptyState>
  </div>
</template>

<script setup>
import { Button } from '@/ui'
import EmptyState from '../components/EmptyState.vue'
</script>
