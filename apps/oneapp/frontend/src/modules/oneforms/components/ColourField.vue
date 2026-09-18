<template>
  <!--
    A colour, picked rather than typed.

    Two controls over one value on purpose: the swatch is how somebody chooses
    and the text is how they paste the hex their brand guidelines gave them.
    The server takes `#rgb` and `#rrggbb` and nothing else — `theming.COLOUR` —
    so a named colour is refused, which is what keeps this from becoming a
    place to write `url(…)` a version later.
  -->
  <div class="flex flex-col gap-1">
    <span class="text-p-sm text-ink-secondary">{{ label }}</span>
    <div class="flex items-center gap-2">
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -- @/ui has no colour control, and a swatch is the whole point: <FormControl type="text"> beside it is the typed half -->
      <input
        type="color"
        class="size-8 shrink-0 cursor-pointer rounded-6 border border-outline-gray-2 p-0.5"
        :value="value || '#ffffff'"
        :aria-label="label"
        :data-slot="`look-${name}`"
        @input="value = $event.target.value"
      />
      <FormControl
        v-model="value"
        type="text"
        class="min-w-0 flex-1"
        :placeholder="__('#2563eb')"
        :aria-label="label"
      />
      <Button
        v-if="value"
        variant="ghost"
        icon="lucide-x"
        :label="__('Leave this one alone')"
        :tooltip="__('Leave it alone')"
        @click="value = ''"
      />
    </div>
  </div>
</template>

<script setup>
import { Button, FormControl } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  label: { type: String, default: '' },
  /** The theme key, so the swatch carries a slot a spec can reach. */
  name: { type: String, default: '' },
})

const value = defineModel({ type: String, default: '' })
</script>
