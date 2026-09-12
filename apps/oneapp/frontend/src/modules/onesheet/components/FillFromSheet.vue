<template>
  <!--
    Point these rows at a sheet somebody already made.

    The stage the whole of Sheets exists for: somebody prices a job in a grid,
    names the rectangle that is the answer, and it lands as line items on a
    document while their working stays behind.

    A picker rather than a button now, and in the overflow rather than the
    header, because a table has one sheet — `sheets/feed.py` binds it — and the
    ordinary path is Open, price, send. This is the other case: the estimator
    was made last week, in the Drive, before anybody opened the quotation. It
    is a once-per-table act and it rebinds.

    Replace, never append. The confirmation is the preview: a pull rewrites
    these rows, and pressing it twice must not double the quotation.
  -->
  <Dialog v-model="open" :title="__('Use a different sheet')">
    <template #default>
      <div class="flex flex-col gap-4">
        <!--
          A select rather than the file picker: a dialog inside a dialog puts the
          outer one behind `aria-hidden`. Two lists in a row is also the better
          answer here — what is being chosen is one of a handful of sheets.
        -->
        <Select
          v-if="options.length"
          v-model="picked"
          :label="__('Sheet')"
          :options="options"
        />
        <Alert v-else-if="!loading" theme="gray" :title="__('There are no sheets here yet')">
          <template #description>
            {{ __('Make one in Files, price the job in it, then name the rows you want back.') }}
          </template>
        </Alert>

        <!-- Only named ranges. Not "pick a rectangle": the name is the
             contract, and a pull aimed at coordinates breaks the first time
             somebody inserts a row above them. -->
        <Select
          v-if="ranges.length"
          v-model="label"
          :label="__('Named range')"
          :options="rangeOptions"
        />
        <Alert
          v-else-if="picked"
          theme="gray"
          :title="__('This sheet has nothing named yet')"
        >
          <template #description>
            {{ __('Open it, select the rows including their headings, and choose Name this range.') }}
          </template>
        </Alert>

        <Alert v-if="error" theme="red" :title="__('This could not be read')">
          <template #description>{{ error }}</template>
        </Alert>

        <!-- What the pull would refuse. Said here rather than thrown there:
             a refusal after the button is a refusal you have to remember,
             and every one of these is a cell somebody has to go and fix. -->
        <Alert
          v-if="problems.length"
          theme="amber"
          :title="__('These rows are not ready')"
          data-slot="fill-problems"
        >
          <template #description>
            <ul class="list-inside list-disc">
              <li v-for="(one, at) in problems" :key="at">{{ one }}</li>
            </ul>
          </template>
        </Alert>

        <div v-if="shape" class="flex flex-col gap-2">
          <FormLabel
            :label="
              shape.count === 1
                ? __('{0} row, from {1}!{2}', [shape.count, shape.tab, shape.ref])
                : __('{0} rows, from {1}!{2}', [shape.count, shape.tab, shape.ref])
            "
          />
          <!-- A named range whose first row is its headings and which has
               nothing under them. Said plainly, because the button below is
               about to be disabled. -->
          <p v-if="!shape.count" class="text-p-xs text-ink-muted">
            {{ __('The first row of a range is its headings; there is nothing under them to bring in.') }}
          </p>
          <!-- The headings, and what each one will fill. A heading with nowhere
               to go is said out loud rather than dropped quietly. -->
          <div class="flex flex-wrap gap-1">
            <Badge
              v-for="head in headings"
              :key="head.field"
              :theme="known(head.field) ? 'green' : 'amber'"
              variant="subtle"
              :label="head.unit ? `${head.field} [${head.unit}]` : head.field"
            />
          </div>
          <p v-if="unknown.length" class="text-p-xs text-ink-muted">
            {{
              unknown.length === 1
                ? __('{0} has no matching field here and will be left out.', [unknown.join(', ')])
                : __('{0} have no matching field here and will be left out.', [unknown.join(', ')])
            }}
          </p>

          <!--
            The first few rows, as they will land. Its own little grid rather
            than `RecordTable`: that one measures the width it has been given,
            and inside a dialog it measures nothing and stacks every column onto
            its own line.
          -->
          <div
            v-if="sample.length"
            class="mt-1 overflow-x-auto rounded-6 border border-outline-gray-2"
          >
            <div
              class="grid min-w-max text-p-xs"
              :style="{ gridTemplateColumns: `repeat(${tracks.length}, minmax(120px, 1fr))` }"
            >
              <div
                v-for="track in tracks"
                :key="`h-${track.key}`"
                class="truncate border-b border-outline-gray-2 bg-surface-gray-2 px-2 py-1.5 font-medium text-ink-secondary"
              >
                {{ track.label }}
              </div>
              <template v-for="line in sample" :key="line._at">
                <div
                  v-for="track in tracks"
                  :key="`${line._at}-${track.key}`"
                  class="truncate border-b border-outline-gray-2 px-2 py-1.5 text-ink-secondary"
                >
                  {{ line[track.key] }}
                </div>
              </template>
            </div>
          </div>
          <p v-if="shape.count > sample.length" class="text-p-xs text-ink-muted">
            {{ __('and {0} more.', [shape.count - sample.length]) }}
          </p>
        </div>
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        :label="shape ? __('Replace these rows with {0}', [shape.count]) : __('Fill')"
        :disabled="!shape || !shape.count || problems.length > 0"
        :loading="filling"
        @click="fill"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Alert, Badge, Button, Dialog, FormLabel, Select } from '@/ui'

import { workspace } from '@/shared/lib/workspace'
import { errorText } from '@/shared/lib/runtime/errors'
import { useSaving } from '@/shared/composables/useSaving'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  doctype: { type: String, required: true },
  docname: { type: String, required: true },
  // The child table's fieldname, and the fields it has — so a heading with
  // nowhere to go can be said before the pull rather than discovered after.
  into: { type: String, required: true },
  fields: { type: Array, default: () => [] },
  /**
   * The feed already standing on this table, when there is one. Opening the
   * dialog then lands on the same sheet and the same range.
   */
  from: { type: Object, default: null },
})

const emit = defineEmits(['filled'])

// Owned by the parent: the trigger is a menu item in the child table's
// overflow now, so what opens this is not in this file.
const open = defineModel({ type: Boolean, default: false })
const { saving: loading, error, attempt: attemptLoad } = useSaving()
const { saving: filling, attempt: attemptFill } = useSaving(error)
const sheets = ref([])
const picked = ref('')
const ranges = ref([])
const label = ref('')
const shape = ref(null)

const options = computed(() =>
  sheets.value.map((one) => ({ label: one.file_name, value: one.name })))

const rangeOptions = computed(() =>
  ranges.value.map((one) => ({ label: `${one.label} — ${one.tab}!${one.ref}`, value: one.label })))

/** Headings that match a field on the child doctype, by fieldname or label. */
const names = computed(() => {
  const out = new Set()
  for (const field of props.fields) {
    out.add(String(field.fieldname || '').toLowerCase())
    out.add(String(field.label || '').toLowerCase())
  }
  return out
})

function known(heading) {
  const wanted = String(heading || '').toLowerCase()
  return names.value.has(wanted) || names.value.has(wanted.replace(/ /g, '_'))
}

// Headings that are actually headings. A named range whose first row has a gap
// produces a blank one, and a badge with no text is a grey pill that says
// nothing.
const headings = computed(() =>
  (shape.value?.headers || []).filter((one) => (one.field || '').trim()))

const unknown = computed(() =>
  headings.value.filter((one) => !known(one.field)).map((one) => one.field))

//: What the pull would refuse — `sheets/rules.py`'s answer, run by the same
//: preview. Empty is the ordinary case and draws nothing.
const problems = computed(() => shape.value?.problems || [])

const tracks = computed(() =>
  (shape.value?.headers || [])
    .map((head, index) => ({ head, index }))
    .filter(({ head }) => (head.field || '').trim())
    .map(({ head, index }) => ({
      key: String(index),
      label: head.unit ? `${head.field} [${head.unit}]` : head.field,
      // Pixels as a number, which is what `RecordTable` measures in — a string
      // here lays every column out on a line of its own.
      width: 160,
    })))

/** The first few rows, as objects the table can render. */
const sample = computed(() =>
  (shape.value?.rows || []).slice(0, 8).map((row, at) => {
    const out = { _at: at }
    row.forEach((value, index) => { out[String(index)] = value })
    return out
  }))

// The sheets to choose from, read when the dialog opens rather than on mount:
// most of these tables are never pointed at a different sheet.
watch(open, (showing) => {
  if (showing) start()
})

async function start() {
  if (sheets.value.length) return
  await attemptLoad(async () => {
    // `all` and not `home`: a sheet made against this record lives in the
    // attachments folder, and the root would show none of them.
    const found = await workspace.driveList({ place: 'all', kind: 'Sheet', limit: 50 })
    sheets.value = found?.files || []
    // Where these rows already come from; then the record's own sheet; then
    // whatever is newest. Each is a better guess than the one after it.
    const again = props.from && sheets.value.find((one) => one.name === props.from.sheet)
    const mine = sheets.value.find((one) => one.attached_to_name === props.docname)
    picked.value = (again || mine || sheets.value[0])?.name || ''
  })
}

// Choosing a sheet loads its named ranges and nothing else: a workbook is a
// big thing to fetch to fill a dropdown.
watch(picked, async (name) => {
  shape.value = null
  label.value = ''
  ranges.value = []
  error.value = ''
  if (!name) return
  try {
    ranges.value = (await workspace.sheetRanges(name)) || []
    const standing = props.from && ranges.value.find((one) => one.label === props.from.label)
    label.value = (standing || ranges.value[0])?.label || ''
  } catch (raised) {
    error.value = errorText(raised)
  }
})

// Changing the range re-previews. The preview and the pull run the same code
// on the server, so what is shown here is what will land.
watch(label, async (wanted) => {
  shape.value = null
  error.value = ''
  if (!wanted || !picked.value) return
  try {
    // Told which table these rows are for, the preview runs the same check
    // the pull runs — so what would be refused is said here, beside the
    // button, rather than by the button.
    shape.value = await workspace.sheetPreview(picked.value, {
      label: wanted,
      doctype: props.doctype,
      docname: props.docname,
      into: props.into,
    })
  } catch (raised) {
    error.value = errorText(raised)
  }
})

async function fill() {
  await attemptFill(async () => {
    const done = await workspace.sheetPull(picked.value, {
      label: label.value,
      doctype: props.doctype,
      docname: props.docname,
      into: props.into,
    })
    open.value = false
    emit('filled', done)
  })
}
</script>
