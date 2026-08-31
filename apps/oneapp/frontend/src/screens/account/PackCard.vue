<template>
  <div class="flex flex-col justify-between rounded-6 border border-outline-gray-2 p-3">
    <div>
      <p class="text-base-medium text-ink-gray-8">{{ title }}</p>
      <p class="mt-0.5 text-p-sm text-ink-gray-5">{{ money(price, currency) }} once</p>
      <p v-if="description" class="mt-1 text-p-sm text-ink-gray-5">{{ description }}</p>
    </div>
    <Button class="mt-3 w-full" label="Buy" :loading="busy" @click="$emit('buy')" />
  </div>
</template>

<script setup>
import { Button } from '@/ui'

defineProps({
  title: { type: String, required: true },
  price: { type: [Number, String], required: true },
  // The currency comes from the catalogue rather than being assumed. A hard
  // coded `$` reads as a price in the wrong currency, which is worse than no
  // symbol at all — it is a number somebody plans around.
  currency: { type: String, default: 'USD' },
  description: { type: String, default: '' },
  busy: { type: Boolean, default: false },
})
defineEmits(['buy'])

const money = (amount, currency) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: (currency || 'USD').toUpperCase(),
    maximumFractionDigits: 2,
  }).format(Number(amount) || 0)
</script>
