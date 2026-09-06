<template>
  <!--
    Fill these rows from a spreadsheet.

    The stage the whole of Sheets exists for: somebody prices a job in a grid,
    names the rectangle that is the answer, and presses this. What lands is line
    items on a document; what stays behind is their working.

    Replace, never append. The confirmation is the preview: a pull rewrites
    these rows, and pressing it twice must not double the quotation.
  -->
  <Button
    icon-left="lucide-table-2"
    variant="ghost"
    size="sm"
    :label="props.from ? 'Fill again' : 'Fill from a sheet'"
    tooltip="Fill these rows from a spreadsheet"
    @click="start"
  />

  <Dialog v-model="open" title="Fill from a sheet">
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
          label="Sheet"
          :options="options"
        />
        <Alert v-else-if="!loading" theme="gray" title="There are no sheets here yet">
          <template #description>
            Make one in Files, price the job in it, then name the rows you want
            back.
          </template>
        </Alert>

        <!-- Only named ranges. Not "pick a rectangle": the name is the
             contract, and a pull aimed at coordinates breaks the first time
             somebody inserts a row above them. -->
        <Select
          v-if="ranges.length"
          v-model="label"
          label="Named range"
          :options="rangeOptions"
        />
        <Alert
          v-else-if="picked"
          theme="gray"
          title="This sheet has nothing named yet"
        >
          <template #description>
            Open it, select the rows including their headings, and press Name
            this range.
          </template>
        </Alert>

        <Alert v-if="error" theme="red" title="This could not be read">
          <template #description>{{ error }}</template>
        </Alert>

        <div v-if="shape" class="flex flex-col gap-2">
          <FormLabel :label="`${shape.count} ${shape.count === 1 ? 'row' : 'rows'}, from ${shape.tab}!${shape.ref}`" />
          <!-- A named range whose first row is its headings and which has
               nothing under them. Said plainly, because the button below is
               about to be disabled. -->
          <p v-if="!shape.count" class="text-p-xs text-ink-gray-5">
            The first row of a range is its headings; there is nothing under
            them to bring in.
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
          <p v-if="unknown.length" class="text-p-xs text-ink-gray-5">
            {{ unknown.join(', ') }} {{ unknown.length === 1 ? 'has' : 'have' }}
            no matching field here and will be left out.
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
                class="truncate border-b border-outline-gray-2 bg-surface-gray-2 px-2 py-1.5 font-medium text-ink-gray-7"
              >
                {{ track.label }}
              </div>
              <template v-for="line in sample" :key="line._at">
                <div
                  v-for="track in tracks"
                  :key="`${line._at}-${track.key}`"
                  class="truncate border-b border-outline-gray-2 px-2 py-1.5 text-ink-gray-7"
                >
                  {{ line[track.key] }}
                </div>
              </template>
            </div>
          </div>
          <p v-if="shape.count > sample.length" class="text-p-xs text-ink-gray-5">
            and {{ shape.count - sample.length }} more.
          </p>
        </div>
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        :label="shape ? `Replace these rows with ${shape.count}` : 'Fill'"
        :disabled="!shape || !shape.count"
        :loading="filling"
        @click="fill"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Alert, Badge, Button, Dialog, FormLabel, Select } from '@/ui'

import { workspace } from '../../lib/workspace'
import { errorText } from '@/lib/runtime/errors'
import { useSaving } from '@/composables/useSaving'

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

const open = ref(false)
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

async function start() {
  open.value = true
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
    shape.value = await workspace.sheetPreview(picked.value, { label: wanted })
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
