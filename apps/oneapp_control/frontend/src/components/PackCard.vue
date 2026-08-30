<template>
  <div class="flex flex-col justify-between rounded-6 border border-outline-gray-2 p-3">
    <div>
      <p class="text-base-medium text-ink-gray-8">{{ title }}</p>
      <p class="mt-0.5 text-p-sm text-ink-gray-5">${{ price }} once</p>
    </div>
    <Button class="mt-3 w-full" label="Buy" :loading="busy" @click="$emit('buy')" />
  </div>
</template>

<script setup>
import { Button } from '@/ui'

defineProps({
  title: { type: String, required: true },
  price: { type: [Number, String], required: true },
  busy: { type: Boolean, default: false },
})
defineEmits(['buy'])
</script>
