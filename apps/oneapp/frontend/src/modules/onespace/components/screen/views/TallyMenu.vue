<template>
  <!--
    How many of each, and a way to narrow to one.

    Frappe's list sidebar, which this product has nowhere to put — the sidebar
    is the space's own navigation. So it is a menu instead: pick a field, see
    its values with counts, click one to filter.

    Under the filters that are already on, which is what makes it a shortcut
    rather than a second opinion: a tally of everything, above a list of twelve,
    is a menu of numbers that do not match what is on screen.
  -->
  <Popover v-model:open="open">
    <template #trigger>
      <Button
        :icon="compact ? 'lucide-chart-bar-decreasing' : undefined"
        :icon-left="compact ? undefined : 'lucide-chart-bar-decreasing'"
        :label="__('How many')"
        :tooltip="__('How many of each')"
        variant="ghost"
      />
    </template>

    <template #default>
      <div class="flex w-[min(20rem,90vw)] flex-col gap-2 p-2">
        <Select
          v-model="field"
          :options="fields"
          :label="__('Count by')"
          :placeholder="__('Which field')"
        />

        <LoadingText v-if="loading" :text="__('Counting')" />

        <p v-else-if="field && !values.length" class="px-1 py-2 text-p-sm text-ink-muted">
          {{ __('Nothing to count — every record here leaves this field empty.') }}
        </p>

        <!-- The values, largest first. A tally is read from the top. -->
        <div v-else-if="values.length" class="flex max-h-80 flex-col overflow-y-auto">
          <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
          <button
            v-for="one in values"
            :key="String(one.value)"
            type="button"
            data-slot="tally-value"
            class="flex items-center gap-2 rounded-4 px-2 py-1.5 text-start hover:bg-surface-gray-2"
            @click="pick(one)"
          >
            <span class="min-w-0 flex-1 truncate text-sm text-ink-secondary">
              {{ said(one.value) }}
            </span>
            <span class="tabular-nums text-p-sm text-ink-muted">{{ one.count }}</span>
          </button>
        </div>

        <p v-if="more" class="px-2 pt-1 text-p-xs text-ink-muted">
          {{ __('The {0} most common. Use Filter for the rest.', [values.length]) }}
        </p>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, LoadingText, Popover, Select } from '@/ui'
import { useIsMobile } from '@/modules/onespace/lib/shell/breakpoint'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** Everything the screen could show — the same list the picker offers. */
  columns: { type: Array, default: () => [] },
  /** The screen's own status field, which is the field to open on. */
  statusField: { type: String, default: '' },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  layout: { type: String, default: '' },
  /** The filters and sort as they stand, so the counts match the list. */
  overrides: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['narrow'])

// Icon-only on a phone, the way the filter beside it is: a labelled button
// pushed the operator's chevron under the next control, which is a button
// nobody could press.
const compact = useIsMobile()

const open = ref(false)
const field = ref('')
const values = ref([])
const more = ref(false)
const loading = ref(false)

/**
 * The fields a tally means something for: a closed set of values, or something
 * that resolves to one. `TALLIED` on the server is the same list and refuses
 * anything else, so a Data field with one value per row cannot be asked for.
 */
const TALLIED = ['Select', 'Link', 'Check']

const fields = computed(() =>
  (props.columns || [])
    .filter((one) => TALLIED.includes(one.fieldtype))
    .map((one) => ({ label: one.label, value: one.fieldname })),
)

/** An empty value is a fact about the records, so it is drawn as one. */
const said = (value) => {
  if (value === null || value === undefined || value === '') return __('Not set')
  if (value === 1 || value === 0) return value ? __('Yes') : __('No')
  return String(value)
}

const count = async () => {
  if (!field.value) {
    values.value = []
    return
  }
  loading.value = true
  try {
    const answer = await workspace.screenTally(
      props.spaceCode,
      props.screen,
      field.value,
      props.overrides,
      props.layout,
    )
    values.value = answer?.values || []
    more.value = !!answer?.more
  } finally {
    loading.value = false
  }
}

watch(field, count)

// The status field is the one somebody almost always means, so the menu opens
// on it. Only on the first open: a reader who chose another field meant to.
watch(open, (showing) => {
  if (!showing) return
  if (!field.value) field.value = props.statusField || fields.value[0]?.value || ''
  else count()
})

const pick = (one) => {
  open.value = false
  emit('narrow', { field: field.value, value: one.value })
}
</script>
