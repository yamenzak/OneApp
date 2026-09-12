<template>
  <!-- A header even here: the page somebody mistyped their way to is still a
       page, and one that starts where none of the others do reads as the shell
       having broken rather than the route being wrong. -->
  <PageHeader>
    <Trail :items="crumbs" />
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
import { Button, PageHeader } from '@/ui'
import { useRoute } from 'vue-router'
import Trail from '@/shared/components/Trail.vue'
import { useCrumbs } from '@/shared/composables/useCrumbs'
import EmptyState from '@/shared/components/EmptyState.vue'
import { __ } from '@/shared/lib/runtime/translate'

// The root still works here, which is the whole of what a 404 needs to
// offer — §C1.
const route = useRoute()
const crumbs = useCrumbs(() => ({ label: __('Not found'), route: route.fullPath }))
</script>
