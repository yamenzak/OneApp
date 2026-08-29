<template>
  <SettingsHeader :title="title" :description="description" :class="PANEL_HEADER">
    <template v-if="form.length" #actions>
      <Button icon-left="lucide-plus" label="New" @click="create" />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <div v-if="resource.loading && !rows.length" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState v-else-if="!rows.length" class="!py-12" :title="emptyTitle" :description="emptyHint" />

    <!-- A four-column table does not fit a 390px screen, and SettingsBody's
         ScrollArea is vertical-only, so reka-ui sets its viewport
         `overflow-x: hidden` and would simply clip the rest. Wide content owns
         its own horizontal scroller. -->
    <div v-else class="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <List
        :columns="columns"
        :row-height="52"
        class="mt-5 min-w-[32rem] list-row-px-3"
        divider="full"
      >
        <ListHeader>
          <ListHeaderCell v-for="c in headers" :key="c">{{ c }}</ListHeaderCell>
        </ListHeader>
        <ListRows :items="rows" row-key="name" v-slot="{ item: row, value }">
          <ListRow :value="value" @click="form.length && edit(row)">
            <ListCell v-for="(cell, i) in cellsFor(row)" :key="i">
              <Badge v-if="cell.badge" :theme="cell.theme" :label="cell.value" variant="subtle" />
              <span
                v-else
                class="truncate text-p-sm"
                :class="cell.muted ? 'text-ink-gray-5' : 'text-ink-gray-8'"
              >
                {{ cell.value }}
              </span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </div>
  </SettingsBody>

  <CatalogueForm
    v-if="form.length"
    v-model="showForm"
    :doctype="doctype"
    :fields="form"
    :record="editing"
    @saved="resource.reload()"
  />
</template>

<script setup>
import { computed } from 'vue'
import { ref } from 'vue'
import {
  Badge, Button, LoadingIndicator, SettingsHeader, SettingsBody,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell,
} from '@/ui'
import CatalogueForm from './CatalogueForm.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import EmptyState from '../EmptyState.vue'
import { useDocList } from '../../lib/api'

/**
 * A read-only catalogue panel.
 *
 * Plans, regions and buckets are configuration an operator reads far more often
 * than they change, and each is edited in exactly one place. Showing them here
 * removes the last reason to open the desk.
 */
const props = defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
  doctype: { type: String, required: true },
  fields: { type: Array, required: true },
  columns: { type: Array, required: true },
  headers: { type: Array, required: true },
  orderBy: { type: String, default: 'creation desc' },
  cells: { type: Function, required: true },
  emptyTitle: { type: String, default: 'Nothing here yet' },
  emptyHint: { type: String, default: '' },
  /**
   * Field specs for creating and editing. Empty leaves the panel read-only —
   * some catalogues are derived rather than typed, and offering a form for one
   * of those would invite an operator to fight the thing that maintains it.
   */
  form: { type: Array, default: () => [] },
})

const showForm = ref(false)
const editing = ref(null)

function create() {
  editing.value = null
  showForm.value = true
}

function edit(row) {
  editing.value = row
  showForm.value = true
}

const resource = useDocList(props.doctype, {
  fields: props.fields,
  orderBy: props.orderBy,
  limit: 100,
})

const rows = computed(() => resource.data || [])
const cellsFor = (row) => props.cells(row)
</script>
