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

    The server checks the same two rules on the way in — a lucide name reaches
    the DOM as a class.

    A square button rather than a row of its own, so it can sit against the
    name box the way CRM's does: an icon is one glyph, and a full-width control
    saying "Icon chosen" is a sentence where a picture would do.
  -->
  <Popover v-model:open="open">
    <template #trigger>
      <Button
        class="w-8 !px-0"
        size="md"
        :label="chosen ? 'Change the icon' : 'Pick an icon'"
        :tooltip="chosen ? 'Change the icon' : 'Pick an icon'"
      >
        <Icon
          :name="chosen || 'lucide-smile'"
          class="size-4"
          :class="chosen ? 'text-ink-gray-7' : 'text-ink-gray-4'"
        />
      </Button>
    </template>

    <template #default>
      <div class="flex w-[17.5rem] flex-col gap-3 p-3">
        <div class="grid grid-cols-8 gap-1">
          <Button
            v-for="name in SPACE_ICONS"
            :key="name"
            :icon="name"
            :label="labelFor(name)"
            :tooltip="labelFor(name)"
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
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, FormControl, Icon, Popover } from '@/ui'
import { SPACE_ICONS } from '../../lib/icons'

const chosen = defineModel({ type: String, default: '' })
const open = ref(false)

const labelFor = (name) => name.replace('lucide-', '').replace(/-/g, ' ')

// What is in the emoji box: whatever was chosen that is not one of ours.
const emoji = computed(() => (SPACE_ICONS.includes(chosen.value) ? '' : chosen.value))

// Eight code points at most. A single emoji can be several — a flag is two, a
// skin tone adds one, a family joined by zero-width joiners is seven — so a
// bound of one or two would reject emoji people actually use. Eight is short
// enough that nobody pastes a sentence into a menu row.
//
// Trimmed here so the box cannot show more than will be stored: the server
// applies the same bound, and a control that accepts what is about to be
// thrown away is a control that lies.
const MAX_EMOJI = 8

const pick = (value) => {
  chosen.value = SPACE_ICONS.includes(value) ? value : [...(value || '')].slice(0, MAX_EMOJI).join('')
  // A grid choice is a decision; typing an emoji is not finished until the
  // person stops, so only the grid closes the popover.
  if (SPACE_ICONS.includes(value) || !value) open.value = false
}
</script>
