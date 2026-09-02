<template>
  <!--
    How records are named, before anybody types an id.

    One doctype at a time rather than a form, because that is what it is: a
    list of prefixes and a counter under each. Only the doctypes this
    workspace's spaces granted, and only those named by a series a workspace
    may set — a doctype named by a hash or by `field:title` is named that way
    because whoever wrote the app decided so, and a settings page is not the
    place to overrule them.
  -->
  <SettingsHeader
    title="Naming"
    description="What a record's id looks like before anybody types one."
    :class="PANEL_HEADER"
  />
  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" text="Loading" />

    <EmptyState
      v-else-if="!rows.length"
      icon="lucide-hash"
      title="Nothing to name"
      description="No app in this workspace names its records by a series."
    />

    <div v-else class="flex flex-col gap-4 py-4">
      <Select
        v-model="chosen"
        label="Records"
        :options="rows.map((row) => ({ label: row.label, value: row.doctype }))"
      />

      <div v-if="current" class="flex flex-col gap-3">
        <!--
          The prefixes, one per line. A textarea rather than a row editor: this
          is exactly how Frappe stores it and how anybody who has met it
          expects to edit it, and a list of five short strings is not worth a
          drag handle.
        -->
        <FormControl
          v-model="draft"
          type="textarea"
          label="Series"
          :rows="5"
          :disabled="!editable"
          :description="editable ? EDITABLE : FIXED"
        />

        <div class="flex items-center gap-2">
          <Button
            v-if="editable"
            variant="solid"
            label="Save series"
            :loading="saving"
            :disabled="!draft.trim()"
            @click="save"
          />
          <Button label="Preview" :loading="previewing" @click="look" />
        </div>

        <ErrorMessage v-if="error" :message="error" />

        <!-- What the first of them would actually issue next. Frappe's own
             preview, against the doctype's last record — a series with a field
             in it means nothing without one to read it from. -->
        <div
          v-if="sample.length"
          class="flex flex-col gap-1 rounded-6 bg-surface-gray-2 p-3 font-mono text-p-xs text-ink-gray-7"
        >
          <span v-for="one in sample" :key="one">{{ one }}</span>
        </div>

        <!--
          Where each series has got to, and moving it. The one destructive
          control here: a counter moved backwards re-issues ids that already
          exist, so it says so and Frappe writes a Version row for the change.
        -->
        <ul class="flex flex-col border-t border-outline-gray-1">
          <li
            v-for="one in current.series"
            :key="one.prefix"
            data-slot="series-row"
            class="flex items-center gap-3 border-b border-outline-gray-1 py-2"
          >
            <span class="min-w-0 flex-1 truncate font-mono text-p-sm text-ink-gray-8">
              {{ one.prefix }}
            </span>
            <Badge v-if="one.default" label="Default" theme="blue" variant="subtle" />
            <span class="text-p-xs text-ink-gray-5">at</span>
            <FormControl
              type="number"
              class="w-28"
              :model-value="counters[one.prefix] ?? one.current ?? 0"
              @update:model-value="counters[one.prefix] = $event"
            />
            <Button
              label="Set"
              :loading="moving === one.prefix"
              @click="move(one)"
            />
          </li>
        </ul>
        <p class="text-p-xs text-ink-gray-5">
          Moving a counter backwards will re-issue ids that already exist. The
          change is recorded against the series.
        </p>
      </div>
    </div>
  </SettingsBody>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  Badge,
  Button,
  ErrorMessage,
  FormControl,
  LoadingText,
  Select,
  SettingsBody,
  SettingsHeader,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'

// Said under the textarea. Two sentences rather than one, because the second
// case is the one people will not expect and the first is the one they will.
const EDITABLE =
  'One per line. The first is what new records use. `#` is a digit, so ACME-.YYYY.-.##### counts up within the year.'
const FIXED =
  'This app names its own records. The series is part of what it is, so it is shown rather than set — the counter under it can still be moved.'

const rows = ref([])
const chosen = ref('')
const draft = ref('')
const sample = ref([])
const counters = reactive({})

const loading = ref(false)
const saving = ref(false)
const previewing = ref(false)
const moving = ref('')
const error = ref('')

const current = computed(() => rows.value.find((row) => row.doctype === chosen.value) || null)

// Whether the prefixes themselves may be changed, or only the counter under
// them. The server refuses a series write on a doctype named by its own
// `autoname`, so the browser must not offer one: a Save that is always
// refused is worse than no Save at all.
const editable = computed(() => !!current.value?.editable)

const load = async () => {
  loading.value = true
  try {
    rows.value = (await workspace.naming()) || []
    if (!chosen.value) chosen.value = rows.value[0]?.doctype || ''
  } finally {
    loading.value = false
  }
}

// The textarea follows the doctype, and only the doctype: retyping a series
// and then switching away and back should not quietly keep the old draft.
watch(current, (row) => {
  draft.value = (row?.series || []).map((one) => one.prefix).join('\n')
  sample.value = []
  error.value = ''
}, { immediate: true })

const settle = (series) => {
  const row = rows.value.find((one) => one.doctype === chosen.value)
  if (row) row.series = series
}

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    settle(
      await workspace.setNaming(
        chosen.value,
        draft.value.split('\n').map((one) => one.trim()).filter(Boolean),
      ),
    )
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    saving.value = false
  }
}

const look = async () => {
  previewing.value = true
  error.value = ''
  try {
    const first = draft.value.split('\n').map((one) => one.trim()).filter(Boolean)[0]
    sample.value = first ? await workspace.namingPreview(chosen.value, first) : []
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    previewing.value = false
  }
}

const move = async (one) => {
  moving.value = one.prefix
  error.value = ''
  try {
    settle(
      await workspace.setNamingCounter(
        chosen.value,
        one.prefix,
        counters[one.prefix] ?? one.current ?? 0,
      ),
    )
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    moving.value = ''
  }
}

load()
</script>
