<template>
  <!--
    Where something stands, drawn one way everywhere.

    A status was three badges before this: the list cell's, which carried a
    glyph; the crumb's and the record header's, which did not; and the document
    state's, off in the action row with its own colour. Same question, three
    answers, and the one in the trail was the one missing the icon that makes a
    column of them scannable.

    So the label decides the glyph and, unless something knows better, the
    colour — through `valueIcon` and `valueTheme`, which are the doctype's own
    Document States first and Frappe's word lists after. `theme` overrides only
    where something really does know better: a `Workflow State` carries its own
    style, and a workflow that calls a state Danger means it whatever the word
    is.
  -->
  <Badge :theme="shown" :label="String(label)" variant="subtle">
    <template #prefix>
      <Icon :name="glyph" class="size-3" :aria-hidden="true" />
    </template>
  </Badge>
</template>

<script setup>
import { computed } from 'vue'
import { Badge, Icon } from '@/ui'
import { valueIcon, valueTheme } from '../../../lib/fields'

const props = defineProps({
  /** The words on the badge. Also what the glyph and the colour are read from. */
  label: { type: [String, Number], required: true },
  /** The doctype's own Document States, where the value comes from a Select. */
  states: { type: Array, default: () => [] },
  /** A colour something else already decided — a workflow's own style. */
  theme: { type: String, default: '' },
})

const shown = computed(() => props.theme || valueTheme(props.label, props.states))
const glyph = computed(() => valueIcon(props.label, props.states))
</script>
