<template>
  <!--
    One add-on, and how much of it this workspace holds.

    A stepper rather than a Buy button, because buying more and giving some back
    are the same operation at different quantities — and because what somebody
    wants to know first is what they already have, not what is for sale.
  -->
  <div class="flex flex-wrap items-center gap-3 rounded-6 border border-outline-gray-2 p-3">
    <div class="min-w-0 flex-1">
      <p class="text-base-medium text-ink-gray-8">{{ addon.name }}</p>
      <p class="mt-0.5 text-p-sm text-ink-gray-5">
        {{ money(rate, addon.currency) }} per {{ addon.unit_gb }} GB, per month
        <!-- What they are actually paying, when it is not what the catalogue
             says today. A grandfathered rate that shows as the new price is a
             billing surprise waiting on the next invoice. -->
        <span v-if="grandfathered" class="text-ink-gray-4">· your original rate</span>
      </p>
      <p v-if="held" class="mt-1 text-p-sm text-ink-gray-7">
        Holding {{ held }} × {{ addon.held_unit_gb || addon.unit_gb }} GB
        = {{ held * (addon.held_unit_gb || addon.unit_gb) }} GB
      </p>
    </div>

    <div v-if="addon.available" class="flex shrink-0 items-center gap-1">
      <Button
        icon="lucide-minus"
        :label="`One less ${addon.name}`"
        :tooltip="`One less ${addon.name}`"
        :disabled="!held || busy"
        @click="emit('set', held - 1)"
      />
      <span class="w-8 text-center text-base tabular-nums text-ink-gray-8">{{ held }}</span>
      <Button
        icon="lucide-plus"
        :label="`One more ${addon.name}`"
        :tooltip="`One more ${addon.name}`"
        :disabled="atCeiling || busy"
        @click="emit('set', held + 1)"
      />
    </div>
    <!-- Said rather than hidden. An add-on that vanishes between one visit and
         the next reads as a fault; this reads as a reason. -->
    <span v-else class="shrink-0 text-p-sm text-ink-gray-4">
      Not sold on a {{ interval.toLowerCase() }} plan
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button } from '@/ui'

const props = defineProps({
  addon: { type: Object, required: true },
  interval: { type: String, default: 'Monthly' },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['set'])

const held = computed(() => Number(props.addon.quantity) || 0)
const rate = computed(() =>
  props.addon.held_amount != null ? props.addon.held_amount : props.addon.amount,
)
const grandfathered = computed(
  () => props.addon.held_amount != null && props.addon.held_amount !== props.addon.amount,
)
const atCeiling = computed(
  () => Boolean(props.addon.max_units) && held.value >= props.addon.max_units,
)

const money = (amount, currency) =>
  new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency: (currency || 'USD').toUpperCase(),
    maximumFractionDigits: 2,
  }).format(Number(amount) || 0)
</script>
