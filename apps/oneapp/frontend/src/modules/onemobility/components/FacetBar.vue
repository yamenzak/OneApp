<template>
  <!--
    What is narrowing this screen, and how to change it.

    One component and not one per screen, because the map and Insights ask the
    same question of different tables and two implementations of one idea is
    how a filter comes to mean something slightly different on two screens of
    one product. The vocabulary itself is the server's — `onemobility/facets.py`
    — so what can be narrowed and what the values are is one closed table read
    as the person asking, and never a list the browser assembled.

    A facet this screen's table cannot answer is shown disabled with the reason
    on it rather than hidden. Hiding it would make the two screens look like
    they offer different things, when what is actually true is that
    `serviceHour` has no vehicle column and Insights says so.
  -->
  <div class="flex flex-wrap items-center gap-1.5" data-slot="facet-bar">
    <template v-for="one in facets" :key="one.key">
      <div class="flex items-center">
        <Combobox
          :model-value="modelValue[one.key] || null"
          :options="one.options"
          :placeholder="one.label"
          :empty-text="__('Nothing to choose')"
          :disabled="unavailable.includes(one.key)"
          trigger="button"
          :variant="modelValue[one.key] ? 'outline' : 'subtle'"
          size="sm"
          @update:model-value="(value) => pick(one.key, value)"
        />
        <Button
          v-if="modelValue[one.key]"
          class="-ms-1"
          variant="ghost"
          size="sm"
          icon="lucide-x"
          :label="__('Clear this filter')"
          :tooltip="__('Clear this filter')"
          @click="pick(one.key, null)"
        />
      </div>
    </template>

    <Button
      v-if="chosen"
      variant="ghost"
      size="sm"
      :label="__('Clear all')"
      icon-left="lucide-filter-x"
      @click="emit('update:modelValue', {})"
    />

    <!--
      Said once, at the end, rather than repeated on every disabled control:
      six tooltips saying the same sentence is six chances to read it and one
      chance to notice it.
    -->
    <span v-if="unavailable.length" class="text-xs text-ink-muted">
      {{ __('Not available on this view: {0}', [unavailableNames]) }}
    </span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Combobox } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The offered facets, from `onemobility.offered`. */
  facets: { type: Array, default: () => [] },
  /** `{facetKey: value}` — what is chosen now. */
  modelValue: { type: Object, default: () => ({}) },
  /** Facet keys this screen's table has no column for. */
  unavailable: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue'])

const chosen = computed(() => Object.keys(props.modelValue || {}).length > 0)

const unavailableNames = computed(() =>
  props.facets
    .filter((one) => props.unavailable.includes(one.key))
    .map((one) => one.label)
    .join(', '),
)

/**
 * Chosen facets are rebuilt rather than mutated: the parent holds this object
 * and a watcher on it is what refetches, so writing a key in place would
 * change the value without the screen noticing.
 */
function pick(key, value) {
  const next = { ...props.modelValue }
  if (value) next[key] = value
  else delete next[key]
  emit('update:modelValue', next)
}
</script>
