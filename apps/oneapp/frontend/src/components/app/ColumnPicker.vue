<template>
  <!--
    Which columns, and in what order.

    Frappe's list settings, in a dialog: the chosen columns as an ordered list
    with a grip to drag, and an add menu for everything else. What "everything
    else" means changed — it is the doctype's own fields now rather than the
    ones a manifest named, so wanting the due date on your list is a choice
    rather than a deploy.
  -->
  <Dialog v-model="open" title="Columns" size="lg">
    <div class="flex flex-col gap-4">
      <p class="text-p-sm text-ink-gray-5">
        Drag to reorder, or use the arrows. Everything this record has is here, whether or not the
        app put it on the list to begin with.
      </p>

      <ul class="flex flex-col gap-1">
        <li
          v-for="(column, index) in chosen"
          :key="column.fieldname"
          draggable="true"
          class="flex items-center gap-1 rounded-4 bg-surface-gray-1 px-2 py-1"
          :class="dragging === index && 'opacity-50'"
          @dragstart="dragging = index"
          @dragend="dragging = null"
          @dragover.prevent
          @drop="dropOn(index)"
        >
          <Icon
            name="lucide-grip-vertical"
            class="size-3.5 shrink-0 cursor-grab text-ink-gray-4"
          />
          <Icon :name="iconFor(column)" class="size-3.5 shrink-0 text-ink-gray-4" />
          <span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-7">
            {{ labelFor(column) }}
          </span>

          <!--
            Where it sticks, and how wide. Both are the reader's call — we pin
            nothing by default, because which column you want to keep in view
            depends on what you are doing with the list, not on what the column
            is.
          -->
          <Button
            icon="lucide-arrow-left-to-line"
            :variant="column.pin === 'left' ? 'subtle' : 'ghost'"
            :label="`Pin ${labelFor(column)} to the left edge`"
            @click="setPin(index, 'left')"
          />
          <Button
            icon="lucide-arrow-right-to-line"
            :variant="column.pin === 'right' ? 'subtle' : 'ghost'"
            :label="`Pin ${labelFor(column)} to the right edge`"
            @click="setPin(index, 'right')"
          />
          <!--
            `aria-label` rather than `label`: FormControl renders a label
            visibly above the field, which in a row this dense wraps to three
            lines and pushes everything else out of shape.
          -->
          <FormControl
            type="number"
            :model-value="column.width"
            :aria-label="`Width of ${labelFor(column)} in pixels`"
            class="w-16"
            @update:model-value="setWidth(index, $event)"
          />

          <!-- The arrows are not a nicety: a pointer drag reaches neither a
               keyboard nor a phone, and order is the point of this dialog. -->
          <Button
            icon="lucide-chevron-up"
            variant="ghost"
            :label="`Move ${labelFor(column)} up`"
            :disabled="index === 0"
            @click="move(index, -1)"
          />
          <Button
            icon="lucide-chevron-down"
            variant="ghost"
            :label="`Move ${labelFor(column)} down`"
            :disabled="index === chosen.length - 1"
            @click="move(index, 1)"
          />
          <Button
            icon="lucide-x"
            variant="ghost"
            :label="`Remove ${labelFor(column)}`"
            :disabled="chosen.length === 1"
            @click="remove(index)"
          />
        </li>
      </ul>

      <div v-if="unused.length" class="flex flex-col gap-2">
        <FormControl
          v-model="search"
          type="search"
          placeholder="Find a field"
          :label="`Add a column (${unused.length} left)`"
        />
        <div class="flex max-h-64 flex-col gap-1 overflow-y-auto">
          <Button
            v-for="column in matching"
            :key="column.fieldname"
            variant="ghost"
            class="justify-start"
            :icon-left="column.icon"
            :label="column.label"
            @click="add(column)"
          />
          <p v-if="!matching.length" class="px-2 py-1 text-p-sm text-ink-gray-5">
            Nothing matches “{{ search }}”.
          </p>
        </div>
      </div>
    </div>

    <template #actions>
      <Button variant="solid" label="Done" @click="open = false" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Dialog, FormControl, Icon } from '@/ui'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  chosen: { type: Array, required: true },
  offered: { type: Array, required: true },
})
const emit = defineEmits(['update:modelValue', 'update:chosen'])

const open = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const dragging = ref(null)
const search = ref('')

const columnFor = (fieldname) => props.offered.find((c) => c.fieldname === fieldname)
const labelFor = (column) => columnFor(column.fieldname)?.label || column.fieldname
const iconFor = (column) => columnFor(column.fieldname)?.icon || 'lucide-circle-help'

const taken = computed(() => new Set(props.chosen.map((c) => c.fieldname)))
const unused = computed(() => props.offered.filter((c) => !taken.value.has(c.fieldname)))

// A doctype can have eighty fields, so the list of what is left needs a way in
// that is not scrolling.
const matching = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return unused.value
  return unused.value.filter((c) => c.label.toLowerCase().includes(term))
})

const change = (next) => emit('update:chosen', next)

const patch = (index, values) =>
  change(props.chosen.map((column, at) => (at === index ? { ...column, ...values } : column)))

const add = (column) =>
  change([...props.chosen, { fieldname: column.fieldname, width: column.width, pin: null }])

const remove = (index) => change(props.chosen.filter((_column, at) => at !== index))

// Clicking the edge a column is already pinned to unpins it, so one button is
// both the on and the off.
const setPin = (index, edge) =>
  patch(index, { pin: props.chosen[index].pin === edge ? null : edge })

const setWidth = (index, value) => {
  const width = Number(value)
  if (Number.isFinite(width) && width > 0) patch(index, { width })
}

const move = (index, by) => {
  const next = [...props.chosen]
  const to = index + by
  if (to < 0 || to >= next.length) return
  ;[next[index], next[to]] = [next[to], next[index]]
  change(next)
}

const dropOn = (index) => {
  if (dragging.value === null || dragging.value === index) return
  const next = [...props.chosen]
  const [moved] = next.splice(dragging.value, 1)
  next.splice(index, 0, moved)
  dragging.value = null
  change(next)
}
</script>
