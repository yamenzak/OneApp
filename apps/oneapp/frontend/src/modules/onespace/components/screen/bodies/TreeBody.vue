<template>
  <!--
    The Tree: the same rows, nested by what they point at. The view for a
    register that has a shape — which certificates descend from which.

    The component is frappe-ui's `Tree`, which owns the disclosure, the
    indentation guides and the WAI-ARIA keyboard. What is ours is the forest.
  -->
  <div class="min-h-0 flex-1 overflow-auto p-3" data-slot="tree">
    <EmptyState
      v-if="!field"
      icon="lucide-list-tree"
      :title="__('Nothing to nest by')"
      :description="__('This screen shows a tree, but no field on it points one record at another.')"
    />
    <!--
      Open by default: a tree that arrives collapsed is a list of roots with the
      answer behind however many clicks the hierarchy is deep.

      Dragging reparents, and what it writes is one field — the same `save` a
      form uses, so permissions and `read_only` apply and the list is re-read
      rather than trusted.

      `move` is the gate. frappe-ui already refuses a drop on the node itself
      and inside its own descendants; ours is the domain rule, `is_group`.
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
          A folder or a leaf, which is a fact about the record rather than about
          how many children happen to be on this page: an empty cost centre that
          may hold others is somewhere to put something.
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
          pressed is a record's name inside somebody else's row. `.stop` is the
          whole interaction model — the label opens the record, the rest of the
          row toggles.
        -->
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
        <button
          type="button"
          class="truncate text-start"
          :class="node.orphan ? 'text-ink-gray-5' : 'text-ink-gray-8'"
          @click.stop="emit('open', node.row)"
        >
          {{ node.label }}
        </button>
      </template>
      <template #empty>
        <EmptyState
          icon="lucide-list-tree"
          :title="__('Nothing here yet')"
          :description="__('No {0} to nest.', [(spec.screen_label || '').toLowerCase()])"
        />
      </template>
    </Tree>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon, Tree } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'
import EmptyState from '@/shared/components/EmptyState.vue'
import { forestOf } from '@/modules/onespace/lib/screen/tree'

const props = defineProps({
  /** The resolved screen: columns, title field, states, permissions. */
  spec: { type: Object, required: true },
  /** The page of records, already fetched and shaped by the shell. */
  rows: { type: Array, default: () => [] },
  /** Which field nests, as the last page came back for it — handed down for the
   *  same reason the board's column field is: the shell owns the request. */
  tree: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['open', 'change'])

const field = computed(() => props.tree?.parent_field || '')
const groupField = computed(() => props.tree?.group_field || '')

// The page as roots and children. What it does with a record whose parent is
// not on the page, and with data that points in a circle, is `lib/screen/tree.js`.
const forest = computed(() =>
  forestOf(props.rows, field.value, props.spec, groupField.value),
)

// Write on the doctype *and* on the field: a screen over a doctype whose parent
// link is read-only is a tree to read rather than one to rearrange, and a drag
// that always fails is worse than no drag.
const canMove = computed(() => {
  if (!props.spec?.can_write || !field.value) return false
  return (props.spec?.all_columns || []).some(
    (one) => one.fieldname === field.value && one.editable,
  )
})

/**
 * Whether this drop is allowed. Only the domain rule — frappe-ui has already
 * refused the two drops that would build a cycle, and what is left is
 * `is_group`.
 *
 * A drop *beside* a node is a reorder among siblings, which this view has
 * nothing to order by, so it lands under the same parent the target has.
 */
const allowed = ({ target, position }) => {
  if (!groupField.value) return true
  if (position !== 'inside') return true
  return !!target?.group
}

/**
 * A drop that landed. `to` is the key of the new parent, or null at the root.
 * Nothing to save where the parent did not change: a write that changes nothing
 * still bumps `modified`, which reorders the page under the reader.
 */
const moved = (info) => {
  if (!info?.node?.row) return
  const now = info.to || ''
  if (String(info.node.row[field.value] || '') === now) return
  emit('change', { row: info.node.row, field: field.value, value: now })
}
</script>
