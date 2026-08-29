<template>
  <div class="grid place-items-center px-6 py-16 text-center">
    <div class="max-w-sm">
      <p class="text-base font-medium text-ink-gray-8">{{ title }}</p>
      <p v-if="description" class="mt-1.5 text-p-base text-ink-gray-6">
        {{ description }}
      </p>
      <slot name="action" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>
