<template>
  <!--
    Filters, sort and columns for one screen — and remembering them.

    The shapes are Frappe's desk, because a customer who has seen one list
    should not have to learn a second: a stack of [field][operator][value] rows,
    a sort that is a field plus a direction rather than every field twice, and a
    column picker that is the chosen columns in their order.

    What a person picks here narrows the screen and never widens it. The server
    checks the same thing again — the operator menu below and the allow list it
    is checked against are generated from one table.
  -->
  <div class="flex flex-wrap items-center gap-2">
    <Popover v-model:open="showFilters">
      <template #trigger>
        <Button
          icon-left="lucide-list-filter"
          :label="filters.length ? `Filter (${filters.length})` : 'Filter'"
          :variant="filters.length ? 'subtle' : 'ghost'"
        />
      </template>
      <template #default>
        <div class="flex w-[min(34rem,90vw)] flex-col gap-3 p-3">
          <p v-if="!filters.length" class="text-p-sm text-ink-gray-5">
            No filters yet. Add one to narrow the list.
          </p>

          <div v-else class="flex flex-col gap-2">
            <FilterRow
              v-for="(filter, index) in filters"
              :key="index"
              :filter="filter"
              :columns="offered"
              :app-code="appCode"
              :view="view"
              @update:filter="replaceFilter(index, $event)"
              @remove="removeFilter(index)"
            />
          </div>

          <div class="flex items-center gap-2 border-t border-outline-gray-1 pt-3">
            <Button
              icon-left="lucide-plus"
              label="Add filter"
              :disabled="!filterable.length"
              @click="addFilter"
            />
            <Button v-if="filters.length" variant="ghost" label="Clear all" @click="clearFilters" />
            <Button class="ml-auto" variant="solid" label="Apply" @click="applyFilters" />
          </div>
        </div>
      </template>
    </Popover>

    <!--
      A field and a direction, not a list of every field in both directions.
      Twelve entries for six columns is a menu nobody reads.
    -->
    <div class="flex items-center gap-1">
      <Dropdown :options="sortOptions">
        <Button icon-left="lucide-arrow-up-down" :label="sortLabel" variant="ghost" />
      </Dropdown>
      <Button
        v-if="sortField"
        :icon="ascending ? 'lucide-arrow-up-narrow-wide' : 'lucide-arrow-down-wide-narrow'"
        :label="ascending ? 'Sort descending' : 'Sort ascending'"
        variant="ghost"
        @click="flipDirection"
      />
    </div>

    <Popover v-model:open="showColumns">
      <template #trigger>
        <Button icon-left="lucide-columns-3" label="Columns" variant="ghost" />
      </template>
      <template #default>
        <div class="flex w-72 flex-col gap-2 p-3">
          <p class="text-p-xs text-ink-gray-5">Which columns, and in what order.</p>

          <!--
            Drag to reorder, and buttons that do the same thing: a pointer drag
            reaches neither a keyboard nor a phone, and this is the only way to
            set column order.
          -->
          <ul class="flex flex-col gap-1">
            <li
              v-for="(column, index) in chosen"
              :key="column"
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
              <span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-7">
                {{ labelFor(column) }}
              </span>
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
                @click="removeColumn(column)"
              />
            </li>
          </ul>

          <Dropdown v-if="unused.length" :options="addOptions">
            <Button icon-left="lucide-plus" label="Add a column" variant="ghost" class="w-full" />
          </Dropdown>
        </div>
      </template>
    </Popover>

    <div class="ml-auto flex items-center gap-1">
      <Button
        v-if="dirty"
        icon-left="lucide-bookmark"
        label="Save this view"
        :loading="saving"
        @click="save"
      />
      <Button
        v-if="spec.saved"
        icon="lucide-rotate-ccw"
        label="Back to the default view"
        variant="ghost"
        :loading="resetting"
        @click="reset"
      />
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dropdown, Popover, Icon } from '@/ui'
import FilterRow from './FilterRow.vue'
import { defaultOperator, operatorsFor, valueShape } from '../../lib/fields'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  spec: { type: Object, required: true },
  appCode: { type: String, required: true },
  view: { type: String, required: true },
})
const emit = defineEmits(['changed'])

const showFilters = ref(false)
const showColumns = ref(false)
const saving = ref(false)
const resetting = ref(false)
const dirty = ref(false)
const dragging = ref(null)

const offered = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const filterable = computed(() => offered.value.filter((c) => operatorsFor(c).length))

const filters = ref([])
const chosen = ref([])
const order = ref('')

// A list can be sorted by when it changed even when nothing shows that, which
// is the screen's own default — and the server allows exactly these three
// beyond the columns, so offering more would be offering a sort that resets.
const SORT_EXTRAS = [
  { fieldname: 'modified', label: 'Last Updated' },
  { fieldname: 'creation', label: 'Created' },
  { fieldname: 'name', label: 'ID' },
]

const sortable = computed(() => [...offered.value, ...SORT_EXTRAS])

const labelFor = (fieldname) =>
  sortable.value.find((c) => c.fieldname === fieldname)?.label || fieldname

// --- sort -------------------------------------------------------------------

const sortField = computed(() => (order.value || props.spec?.order_by || '').split(' ')[0] || '')
const ascending = computed(
  () => (order.value || props.spec?.order_by || '').split(' ')[1] === 'asc',
)

const sortLabel = computed(() =>
  sortField.value ? `Sorted by ${labelFor(sortField.value)}` : 'Sort',
)

const setOrder = (fieldname, direction) => {
  order.value = `${fieldname} ${direction}`
  dirty.value = true
  emit('changed', payload())
}

const sortOptions = computed(() =>
  sortable.value.map((column) => ({
    label: column.label,
    onClick: () => setOrder(column.fieldname, ascending.value ? 'asc' : 'desc'),
  })),
)

const flipDirection = () => setOrder(sortField.value, ascending.value ? 'desc' : 'asc')

// --- filters ----------------------------------------------------------------

const blankFilter = () => {
  const column = filterable.value[0]
  const operator = defaultOperator(column)
  const shape = valueShape(column, operator)
  const value = shape === 'range' ? ['', ''] : shape === 'multi' ? [] : shape === 'set' ? 'set' : ''
  return [column.fieldname, operator, value]
}

const addFilter = () => {
  filters.value = [...filters.value, blankFilter()]
}

const replaceFilter = (index, next) => {
  filters.value = filters.value.map((filter, at) => (at === index ? next : filter))
}

const runFilters = () => {
  dirty.value = true
  emit('changed', payload())
}

// Removing one applies immediately, and leaves the panel open: there is nothing
// left to type into, so waiting for Apply would leave a filter showing that is
// no longer there — but a person removing one of three is usually about to
// remove another.
const removeFilter = (index) => {
  filters.value = filters.value.filter((_filter, at) => at !== index)
  runFilters()
}

const clearFilters = () => {
  filters.value = []
  showFilters.value = false
  runFilters()
}

// Apply closes it. The point of asking is to see the answer, and the panel is
// sitting on top of it.
const applyFilters = () => {
  showFilters.value = false
  runFilters()
}

// --- columns ----------------------------------------------------------------

const unused = computed(() => offered.value.filter((c) => !chosen.value.includes(c.fieldname)))

const addOptions = computed(() =>
  unused.value.map((column) => ({
    label: column.label,
    onClick: () => {
      chosen.value = [...chosen.value, column.fieldname]
      dirty.value = true
      emit('changed', payload())
    },
  })),
)

const removeColumn = (fieldname) => {
  chosen.value = chosen.value.filter((f) => f !== fieldname)
  dirty.value = true
  emit('changed', payload())
}

const move = (index, by) => {
  const next = [...chosen.value]
  const to = index + by
  if (to < 0 || to >= next.length) return
  ;[next[index], next[to]] = [next[to], next[index]]
  chosen.value = next
  dirty.value = true
  emit('changed', payload())
}

const dropOn = (index) => {
  if (dragging.value === null || dragging.value === index) return
  const next = [...chosen.value]
  const [moved] = next.splice(dragging.value, 1)
  next.splice(index, 0, moved)
  chosen.value = next
  dragging.value = null
  dirty.value = true
  emit('changed', payload())
}

// --- saving -----------------------------------------------------------------

const payload = () => ({
  filters: filters.value,
  order_by: order.value,
  columns: chosen.value,
})

const save = async () => {
  saving.value = true
  try {
    await workspace.saveView(props.appCode, props.view, payload())
    dirty.value = false
    emit('changed', payload(), { reload: true })
  } finally {
    saving.value = false
  }
}

const reset = async () => {
  resetting.value = true
  try {
    await workspace.resetView(props.appCode, props.view)
    dirty.value = false
    emit('changed', null, { reload: true })
  } finally {
    resetting.value = false
  }
}

// Seeded from whatever the screen resolved to — which already includes this
// person's saved view, so the controls open showing what they are looking at.
watch(
  () => props.spec,
  (spec) => {
    if (!spec) return
    chosen.value = (spec.columns || []).map((c) => c.fieldname)
    order.value = spec.order_by || ''
    filters.value = (spec.saved?.filters || []).map((filter) => [...filter])
    dirty.value = false
  },
  { immediate: true },
)
</script>
