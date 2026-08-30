<template>
  <!--
    Filters, sort and columns for one screen — and remembering them.

    Everything offered here comes from the same metadata the columns do, so a
    filter can only name a field the screen shows and a sort can only name one
    it can order by. What a person saves narrows the screen; it never widens it,
    which is checked on the server too.
  -->
  <div class="flex flex-wrap items-center gap-2">
    <Dropdown :options="sortOptions">
      <Button icon-left="lucide-arrow-up-down" :label="sortLabel" variant="ghost" />
    </Dropdown>

    <Popover v-model:open="showFilters">
      <template #trigger>
        <Button
          icon-left="lucide-list-filter"
          :label="filterCount ? `Filters (${filterCount})` : 'Filter'"
          :variant="filterCount ? 'subtle' : 'ghost'"
        />
      </template>
      <template #default>
        <div class="flex w-80 flex-col gap-3 p-3">
          <p class="text-p-xs text-ink-gray-5">
            Only fields this screen shows. Blank clears the filter.
          </p>
          <FormControl
            v-for="field in filterable"
            :key="field.fieldname"
            v-model="draft[field.fieldname]"
            :type="field.fieldtype === 'Select' ? 'select' : 'text'"
            :label="field.label"
            :options="field.fieldtype === 'Select' ? selectOptions(field) : undefined"
            :placeholder="field.fieldtype === 'Select' ? undefined : 'Contains…'"
          />
          <div class="flex items-center gap-2">
            <Button variant="solid" label="Apply" @click="applyFilters" />
            <Button label="Clear" variant="ghost" @click="clearFilters" />
          </div>
        </div>
      </template>
    </Popover>

    <Popover v-model:open="showColumns">
      <template #trigger>
        <Button icon-left="lucide-columns-3" label="Columns" variant="ghost" />
      </template>
      <template #default>
        <div class="flex w-64 flex-col gap-2 p-3">
          <p class="text-p-xs text-ink-gray-5">Which columns, and in what order.</p>
          <Checkbox
            v-for="field in offered"
            :key="field.fieldname"
            :model-value="chosen.includes(field.fieldname)"
            :label="field.label"
            @update:model-value="toggleColumn(field.fieldname)"
          />
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
import { computed, reactive, ref, watch } from 'vue'
import { Button, Dropdown, Popover, FormControl, Checkbox } from '@/ui'
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

const offered = computed(() => props.spec?.all_columns || props.spec?.columns || [])
const chosen = ref([])
const draft = reactive({})
const order = ref('')

// Text and choice fields only. A "contains" box over a Date or a Currency is a
// control that looks like it works and does not.
const FILTERABLE = ['Data', 'Select', 'Link', 'Small Text', 'Text', 'Phone', 'Read Only']
const filterable = computed(() => offered.value.filter((c) => FILTERABLE.includes(c.fieldtype)))

const filterCount = computed(
  () => Object.values(draft).filter((v) => v !== '' && v !== null && v !== undefined).length,
)

const sortOptions = computed(() =>
  offered.value.flatMap((column) =>
    ['desc', 'asc'].map((direction) => ({
      label: `${column.label} ${direction === 'desc' ? '↓' : '↑'}`,
      onClick: () => {
        order.value = `${column.fieldname} ${direction}`
        dirty.value = true
        emit('changed', payload())
      },
    })),
  ),
)

const sortLabel = computed(() => {
  const current = order.value || props.spec?.order_by || ''
  const [fieldname] = current.split(' ')
  const column = offered.value.find((c) => c.fieldname === fieldname)
  return column ? `Sorted by ${column.label}` : 'Sort'
})

const selectOptions = (field) => ['', ...(field.options || '').split('\n').filter(Boolean)]

const payload = () => ({
  filters: Object.fromEntries(
    Object.entries(draft).filter(([, v]) => v !== '' && v !== null && v !== undefined),
  ),
  order_by: order.value,
  columns: chosen.value,
})

const toggleColumn = (fieldname) => {
  const at = chosen.value.indexOf(fieldname)
  if (at === -1) chosen.value.push(fieldname)
  else chosen.value.splice(at, 1)
  dirty.value = true
  emit('changed', payload())
}

const applyFilters = () => {
  dirty.value = true
  showFilters.value = false
  emit('changed', payload())
}

const clearFilters = () => {
  Object.keys(draft).forEach((key) => delete draft[key])
  dirty.value = true
  showFilters.value = false
  emit('changed', payload())
}

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
    Object.keys(draft).forEach((key) => delete draft[key])
    for (const [key, value] of Object.entries(spec.saved?.filters || {})) draft[key] = value
    dirty.value = false
  },
  { immediate: true },
)
</script>
