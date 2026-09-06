<template>
  <!--
    An icon for a view. Two kinds, and the reason for both is the build:

    * **A lucide icon from an offered set.** Tailwind's lucide plugin only emits
      CSS for class names it can see in the source, so a name chosen at runtime
      renders as nothing at all. The set is `SPACE_ICONS`, which is what makes
      it safe to store.
    * **Any emoji.** An emoji is text, so it needs no build step and cannot be
      the one that fails to draw.

    The server checks the same two rules on the way in.
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
        <!-- Type to narrow: twenty-six glyphs is a wall to scan, and the words
             each icon answers to were already written down as comments, which
             made them exactly as useful as no words at all. -->
        <!-- `aria-label` rather than `label`: FormControl's label is a visible
             one above the box. -->
        <FormControl
          type="text"
          size="sm"
          aria-label="Search icons"
          placeholder="Search"
          :model-value="query"
          @update:model-value="query = $event"
        >
          <template #prefix>
            <Icon name="lucide-search" class="size-3.5 text-ink-gray-4" />
          </template>
        </FormControl>

        <!-- A bounded scroller with faded edges rather than a list that runs
             off the bottom of the menu with nothing to say it does. -->
        <FadedScroll class="max-h-64">
          <div class="flex flex-col gap-2 pe-1">
            <section v-for="group in groups" :key="group.group" class="flex flex-col gap-1">
              <h4 class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
                {{ group.group }}
              </h4>
              <div class="grid grid-cols-8 gap-1">
                <Button
                  v-for="one in group.icons"
                  :key="one.icon"
                  :icon="one.icon"
                  :label="labelFor(one.icon)"
                  :tooltip="labelFor(one.icon)"
                  :variant="chosen === one.icon ? 'subtle' : 'ghost'"
                  @click="pick(one.icon)"
                />
              </div>
            </section>

            <p v-if="!groups.length" class="py-4 text-center text-p-sm text-ink-gray-5">
              No icon by that name
            </p>
          </div>
        </FadedScroll>

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
import { computed, ref, watch } from 'vue'
import { Button, FormControl, Icon, Popover } from '@/ui'
import FadedScroll from '../../FadedScroll.vue'
import { SPACE_ICONS, findSpaceIcons } from '@/lib/shell/icons'

const chosen = defineModel({ type: String, default: '' })
const open = ref(false)
const query = ref('')

// Filtered in group order. The matching is the library's, so the picker and
// anything else that offers these agree about what a word finds.
const groups = computed(() => findSpaceIcons(query.value))

const labelFor = (name) => name.replace('lucide-', '').replace(/-/g, ' ')

// What is in the emoji box: whatever was chosen that is not one of ours.
const emoji = computed(() => (SPACE_ICONS.includes(chosen.value) ? '' : chosen.value))

// Eight code points at most. A single emoji can be several — a flag is two, a
// family joined by zero-width joiners is seven — so a bound of one or two would
// reject emoji people actually use.
//
// Trimmed here so the box cannot show more than will be stored: a control that
// accepts what is about to be thrown away is a control that lies.
const MAX_EMOJI = 8

const pick = (value) => {
  chosen.value = SPACE_ICONS.includes(value) ? value : [...(value || '')].slice(0, MAX_EMOJI).join('')
  // A grid choice is a decision; typing an emoji is not finished until the
  // person stops, so only the grid closes the popover.
  if (SPACE_ICONS.includes(value) || !value) open.value = false
}

// A fresh search every time it opens: a picker that remembers the last thing
// somebody typed opens showing four of twenty-six icons and no reason why.
watch(open, (showing) => {
  if (showing) query.value = ''
})
</script>
