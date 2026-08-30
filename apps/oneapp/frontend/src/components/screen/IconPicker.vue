<template>
  <!--
    An icon for a view. Two kinds, and the reason for both is the build:

    * **A lucide icon from an offered set.** Tailwind's lucide plugin only
      emits CSS for the class names it can see in the source, so a name chosen
      at runtime renders as nothing at all. The set is `SPACE_ICONS` — the same
      one the rail offers — which is what makes it safe to store.
    * **Any emoji.** An emoji is text, so it needs no build step and cannot be
      the one that fails to draw. Frappe CRM tolerates an emoji here for legacy
      reasons; for us it is the more capable of the two, which is why it gets a
      box rather than a migration path.

    The server checks the same two rules on the way in — a value here reaches
    the DOM as a class name.
  -->
  <div class="flex flex-col gap-1.5">
    <FormLabel :label="label" />
    <Popover v-model:open="open">
      <template #trigger>
        <Button class="w-full !justify-start" :label="chosen ? 'Change the icon' : 'Pick an icon'">
          <template #prefix>
            <Icon v-if="chosen" :name="chosen" class="size-4 text-ink-gray-7" />
            <Icon v-else name="lucide-smile" class="size-4 text-ink-gray-4" />
          </template>
          <span class="flex-1 truncate text-start">
            {{ chosen ? 'Icon chosen' : 'None' }}
          </span>
        </Button>
      </template>

      <template #default>
        <div class="flex w-[min(22rem,90vw)] flex-col gap-3 p-3">
          <div class="grid grid-cols-8 gap-1">
            <Button
              v-for="name in SPACE_ICONS"
              :key="name"
              :icon="name"
              :label="name.replace('lucide-', '').replace(/-/g, ' ')"
              :tooltip="name.replace('lucide-', '').replace(/-/g, ' ')"
              :variant="chosen === name ? 'subtle' : 'ghost'"
              @click="pick(name)"
            />
          </div>

          <!-- Anything the set does not have. One box rather than a second
               picker, because an emoji keyboard is the operating system's. -->
          <FormControl
            type="text"
            label="Or an emoji"
            :model-value="emoji"
            placeholder="📦"
            @update:model-value="pick($event)"
          />

          <Button v-if="chosen" variant="ghost" label="No icon" @click="pick('')" />
        </div>
      </template>
    </Popover>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, FormControl, FormLabel, Icon, Popover } from '@/ui'
import { SPACE_ICONS } from '../../lib/icons'

const props = defineProps({
  label: { type: String, default: 'Icon' },
})

const chosen = defineModel({ type: String, default: '' })
const open = ref(false)

// What is in the emoji box: whatever was chosen that is not one of ours.
const emoji = computed(() => (SPACE_ICONS.includes(chosen.value) ? '' : chosen.value))

// Two code points at most: enough for a flag or a skin-toned figure, short
// enough that nobody pastes a sentence into a menu row. Trimmed here so the
// box cannot show more than will be stored — the server drops the rest either
// way, and a control that accepts what is about to be thrown away is a control
// that lies.
const MAX_EMOJI = 2

const pick = (value) => {
  chosen.value = SPACE_ICONS.includes(value)
    ? value
    : [...(value || '')].slice(0, MAX_EMOJI).join('')
  // A grid choice is a decision; typing an emoji is not finished until the
  // person stops, so only the grid closes the popover.
  if (SPACE_ICONS.includes(value) || !value) open.value = false
}
</script>
