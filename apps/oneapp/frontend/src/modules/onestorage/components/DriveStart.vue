<template>
  <!--
    A way to start, across the top of the editors' rooms.

    OneWriter and OneWorkbook open on a list of what exists, which answers
    "where is the thing I wrote" and not "I need to write something". Docs and
    Sheets both put a strip of what you could *start* above that list, and it
    is the first thing on the screen because starting is the commoner errand:
    a list of forty documents is somewhere you search, and a blank page is
    somewhere you press.

    Blank first and always. Then the workspace's own templates, which are a
    flag on a file rather than a second store — `TemplatePicker` says why at
    length — so a workspace that has marked none sees the blank alone and
    nothing explaining what a template is. The feature arrives when somebody
    makes one, which is the right direction for it to arrive from.

    Only in a room that is one kind. In All files "start something" has no
    answer: the New menu's whole job there is asking which kind, and a strip
    that had to ask the same question would be that menu drawn flat.
  -->
  <section v-if="kind" data-slot="drive-start" class="shrink-0 pb-4">
    <h2 class="mb-2 text-p-sm font-medium text-ink-secondary">{{ __('Start something') }}</h2>

    <div class="flex gap-3 overflow-x-auto pb-1">
      <!-- The blank, drawn as the thing it makes: a page, with nothing on it.
           A tile the same size as the templates beside it, because it is the
           same choice — this one just has no writing in it yet. -->
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -- a tile: a 120px preview with its name under it, and the whole thing is the target. <Button> is a label in a ground and cannot host either -->
      <button
        type="button"
        data-slot="drive-start-blank"
        class="group flex shrink-0 flex-col gap-1.5 text-start"
        :disabled="making"
        @click="emit('blank')"
      >
        <Panel pad="none" class="grid h-24 w-[7.5rem] place-items-center" :class="HOVER">
          <Icon name="lucide-plus" class="size-6 text-ink-muted" />
        </Panel>
        <span class="w-[7.5rem] truncate text-sm text-ink-primary">{{ blank }}</span>
      </button>

      <!-- eslint-disable-next-line vue/no-restricted-html-elements -- the same tile as the blank beside it, for the same reason -->
      <button
        v-for="one in few"
        :key="one.name"
        type="button"
        data-slot="drive-start-template"
        class="flex shrink-0 flex-col gap-1.5 text-start"
        :disabled="making"
        @click="emit('template', one)"
      >
        <Panel
          pad="none"
          class="grid h-24 w-[7.5rem] place-items-center overflow-hidden"
          :class="HOVER"
        >
          <img :src="artForKind(kind)" :alt="''" aria-hidden="true" class="size-8" />
        </Panel>
        <span class="w-[7.5rem] truncate text-sm text-ink-primary">{{ one.file_name }}</span>
      </button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

import { Icon } from '@/ui'
import Panel from '@/shared/components/Panel.vue'
import { artForKind } from '@/modules/onestorage/lib/art'
import { HOVER } from '@/shared/lib/rowstate'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** Which kind this room is — `Doc`, `Sheet`, `Code`. Empty draws nothing. */
  kind: { type: String, default: '' },
  /** What the blank one is called here: a document, a sheet, a code file. */
  blank: { type: String, default: '' },
  /** The workspace's own, already fetched by the host's New menu. */
  templates: { type: Array, default: () => [] },
  /** Whether one is being made, so the strip stops taking presses. */
  making: { type: Boolean, default: false },
})

/**
 * Six, and the rest through the editor's own Load a template.
 *
 * A strip is a glance. A workspace that has marked fourteen files as templates
 * would otherwise get fourteen tiles scrolling sideways off the window, which
 * is a list — and the place for a list of templates is the picker inside the
 * blank page, where somebody who did not find what they wanted here is already
 * looking. `TemplatePicker` has that argument.
 */
const FEW = 6
const few = computed(() => props.templates.slice(0, FEW))

const emit = defineEmits(['blank', 'template'])
</script>
