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
    <!--
      Open by default, which is the component's own default and the right one
      here: a tree that arrives collapsed is a list of roots with the answer
      behind however many clicks the hierarchy is deep, and the hierarchy is
      why somebody chose this view.

      Dragging reparents. It is the one thing a tree can do that a list cannot,
      and what it writes is one field — the same `save` a form uses, through
      the same door a board's card move goes through, so permissions and
      `read_only` apply and the list is re-read rather than trusted.

      `move` is the gate. frappe-ui already refuses a drop on the node itself
      and inside its own descendants; what is ours is the domain rule: a record
      may only go under one that may hold records. Where the doctype has no
      `is_group`, every record may, which is what a plain Link means.
    -->
    <Tree
      v-else
      :nodes="forest"
      node-key="name"
      guides="connectors"
      :draggable="canMove"
      :move="allowed"
      @drag-end="moved"
    >
      <template v-if="groupField" #item-prefix="{ node }">
        <!--
          A folder or a leaf, which is a fact about the record rather than
          about how many children happen to be on this page: an empty cost
          centre that may hold others is somewhere to put something, and drawn
          as a leaf it reads as the end of the line.
        -->
        <Icon
          :name="node.group ? 'lucide-folder' : 'lucide-file'"
          class="size-3.5 shrink-0 text-ink-gray-4"
          :aria-hidden="true"
        />
      </template>
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
import { Icon, Tree } from '@/ui'
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

const emit = defineEmits(['open', 'change'])

const field = computed(() => props.tree?.parent_field || '')
const groupField = computed(() => props.tree?.group_field || '')

// The page as roots and children. What it does with a record whose parent is
// not on the page, and with data that points in a circle, is `lib/tree.js`.
const forest = computed(() =>
  forestOf(props.rows, field.value, props.spec, groupField.value),
)

// Write on the doctype *and* on the field. A screen over a doctype whose
// parent link is read-only — a nested set the framework maintains itself — is
// a tree to read rather than one to rearrange, and a drag that always fails is
// worse than no drag.
const canMove = computed(() => {
  if (!props.spec?.can_write || !field.value) return false
  return (props.spec?.all_columns || []).some(
    (one) => one.fieldname === field.value && one.editable,
  )
})

/**
 * Whether this drop is allowed.
 *
 * Only the domain rule: frappe-ui has already refused a drop on the node
 * itself and inside its own descendants, which are the two that would build a
 * cycle. What is left is `is_group` — a record may only go under one that may
 * hold records — and only where the doctype has such a field.
 *
 * A drop *beside* a node is a reorder among siblings, and this view has
 * nothing to order by: the parent field holds one id and no position, and the
 * rows come back in the screen's own order. So a sibling drop lands under the
 * same parent the target has, which is what "beside" means here.
 */
const allowed = ({ target, position }) => {
  if (!groupField.value) return true
  if (position !== 'inside') return true
  return !!target?.group
}

/**
 * A drop that landed. `to` is the key of the new parent, or null at the root.
 *
 * Nothing to save where the parent did not change: a reorder among siblings is
 * a move this view cannot record, and a write that changes nothing still bumps
 * `modified` — which reorders the page under the reader.
 */
const moved = (info) => {
  if (!info?.node?.row) return
  const now = info.to || ''
  if (String(info.node.row[field.value] || '') === now) return
  emit('change', { row: info.node.row, field: field.value, value: now })
}
</script>
