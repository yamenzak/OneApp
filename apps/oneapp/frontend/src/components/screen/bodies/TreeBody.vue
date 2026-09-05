<template>
  <!--
    The Tree: the same rows, nested by what they point at.

    Same rows, same filters, same order as every other body — what changes is
    that a record naming another of its own kind is drawn *under* it. The view
    for a register that has a shape: which certificates descend from which,
    which cost codes roll up into which.

    The component is frappe-ui's `Tree`, which owns the disclosure, the
    indentation guides and the WAI-ARIA keyboard. What is ours is the forest:
    turning a flat page of rows into roots and children, and deciding what to
    do with a record whose parent is not on the page.
  -->
  <div class="min-h-0 flex-1 overflow-auto p-3" data-slot="tree">
    <EmptyState
      v-if="!field"
      icon="lucide-list-tree"
      title="Nothing to nest by"
      description="This screen offers a tree but names no field that points one record at another."
    />
    <!-- Open by default, which is the component's own default and the right
         one here: a tree that arrives collapsed is a list of roots with the
         answer behind however many clicks the hierarchy is deep, and the
         hierarchy is why somebody chose this view. -->
    <Tree v-else :nodes="forest" node-key="name" guides="connectors">
      <template #item-label="{ node }">
        <!--
          A raw button, and the same exception `RecordCard` takes: what is
          pressed here is a record's name inside somebody else's row, and a
          `<Button>` would draw a control where the design asks for a label.
          `.stop` is the whole interaction model — the label opens the record,
          the rest of the row toggles, which is what the desk's tree does too.
        -->
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
        <button
          type="button"
          class="truncate text-left"
          :class="node.orphan ? 'text-ink-gray-5' : 'text-ink-gray-8'"
          @click.stop="emit('open', node.row)"
        >
          {{ node.label }}
        </button>
      </template>
      <template #empty>
        <EmptyState
          icon="lucide-list-tree"
          title="Nothing here yet"
          :description="`No ${(spec.screen_label || '').toLowerCase()} to nest.`"
        />
      </template>
    </Tree>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Tree } from '@/ui'
import EmptyState from '../../EmptyState.vue'
import { forestOf } from '../../../lib/tree'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The page of records, already fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /**
   * Which field nests, as the last page came back for it — handed down for the
   * same reason the board's column field is: the shell owns the request.
   */
  tree: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['open'])

const field = computed(() => props.tree?.parent_field || '')

// The page as roots and children. What it does with a record whose parent is
// not on the page, and with data that points in a circle, is `lib/tree.js`.
const forest = computed(() => forestOf(props.rows, field.value, props.spec))
</script>
