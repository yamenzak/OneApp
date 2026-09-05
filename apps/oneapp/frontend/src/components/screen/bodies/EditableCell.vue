<template>
  <!--
    A list cell you can type into.

    The report view's whole reason for being: forty records whose status is
    wrong are forty round trips through a record pane, and the person fixing
    them is doing data entry with a form in the way.

    Not a second editor. The control is `FieldControl` — the same one the
    record form draws, with the same fieldtype mapping, the same Link picker
    and the same Select options — and the write is the same `saveRecord` a form
    does, so the doctype's rules, its permissions and its `fetch_from` all
    still happen. What is here is only *when* the control appears.
  -->
  <div v-if="!editable" class="contents">
    <slot />
  </div>

  <!-- Not editing: the cell as every other view draws it, with an affordance
       on hover. `w-full` so the whole cell is the target and not just the text
       in it — a five-character status is otherwise a five-character target. -->
  <!--
    A raw button, the same exception `RecordCard` takes: what is pressed is a
    value inside somebody else's cell, and a `<Button>` would draw a control
    where the design asks for a value.
  -->
  <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
  <button
    v-else-if="!editing"
    type="button"
    data-slot="editable"
    class="flex w-full min-w-0 items-center rounded-4 px-1 text-start hover:bg-surface-gray-2"
    :class="align"
    @click.stop="start"
  >
    <slot />
  </button>

  <!-- Editing. `focusout` rather than `blur`: the Link picker and the Select
       put their menu in a portal, so the input loses focus to something that
       is logically inside this cell — `relatedTarget` is how a wrapper tells
       "moved within" from "left". -->
  <div v-else class="w-full min-w-0" @focusout="leaving" @keydown.esc.stop="cancel">
    <FieldControl
      ref="control"
      v-model="draft"
      :field="column.column"
      :space-code="spec.space"
      :screen="spec.screen"
      :states="spec.states || []"
      :doctype="spec.doctype"
      :docname="row.name"
      :doc="row"
      @keyup.enter="commit"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, ref } from 'vue'
import FieldControl from '../fields/FieldControl.vue'

const props = defineProps({
  /** The column, as `ListBody` shaped it — `column.column` is the DocField. */
  column: { type: Object, required: true },
  row: { type: Object, required: true },
  /** The resolved screen: doctype, states, permissions. */
  spec: { type: Object, required: true },
  /** Off in every view but the report, where a click opens the record. */
  enabled: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])

const editing = ref(false)
const draft = ref(null)
const control = ref(null)

/**
 * Whether this cell may be typed into.
 *
 * `editable` is the server's answer and already carries the three questions
 * worth asking — is the fieldtype one a control writes, is the field read-only,
 * and is its permlevel one this person may write. What is added here is the
 * row: a submitted or cancelled document is not edited in a table, whatever its
 * fields say.
 */
const editable = computed(
  () =>
    props.enabled &&
    !!props.column?.column?.editable &&
    props.spec?.can_write !== false &&
    !Number(props.row?.docstatus || 0),
)

// Numbers sit against the right edge in the cell, so the control that replaces
// one has to as well or the value jumps sideways on the way into edit.
const align = computed(() => (props.column?.align === 'end' ? 'justify-end' : ''))

const start = async () => {
  draft.value = props.row[props.column.key]
  editing.value = true
  await nextTick()
  // The control is a wrapper; the thing that takes a cursor is the input in it.
  control.value?.$el?.querySelector?.('input, textarea, select')?.focus()
}

const cancel = () => {
  editing.value = false
}

const commit = () => {
  editing.value = false
  // Nothing sent where nothing changed. A cell somebody clicked into and out of
  // is not an edit, and writing it anyway puts a version on the record and a
  // line in its timeline saying nothing happened.
  if (draft.value === props.row[props.column.key]) return
  emit('change', { row: props.row, field: props.column.key, value: draft.value })
}

/** Left the cell entirely, rather than moved between the control's own parts. */
const leaving = (event) => {
  if (event.currentTarget.contains(event.relatedTarget)) return
  commit()
}
</script>
