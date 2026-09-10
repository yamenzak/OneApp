<!--
  What this file reads, and everything you can put in it from there.

  Shared by both editors, because it is one question — a document and a
  workbook both read a *set* of records (`shared/binding.py`) and both need
  the same four things: which records, what each one offers, is it fresh, and
  give me that field. What differs is only what a click *does*, which is an
  event rather than a branch: the document inserts a token, the workbook
  writes a `RECORD()` formula into the current cell.

  A rail rather than a strip, and the reason is the shape of the thing: a
  document about a quotation is usually also about its customer and its
  project, and a strip that had to hold three records and their fields would
  be a strip with a menu inside a menu. Here each record is a section you open
  and browse, which is the browsing the design turns on.

  It also answers the question the design turns on before anybody asks it:
  *is this fresh?* Nothing is pushed. The footer says when the values on
  screen were read, and Refresh reads them again.

  A slot — a source with no record yet — is what a template hands over. The
  panel prompts for it here rather than in a dialog before the file exists,
  because a template is a starting point and the person filling it in usually
  wants to add a record of their own beside the ones it named.
-->
<template>
  <aside
    class="flex w-80 shrink-0 flex-col border-s border-outline-gray-1 bg-surface-base"
    :aria-label="__('Records')"
  >
    <div
      class="flex shrink-0 items-center justify-between gap-2 border-b border-outline-gray-1 px-4 py-3"
    >
      <p class="text-p-base font-medium text-ink-gray-8">{{ __('Records') }}</p>
      <div class="flex items-center gap-1">
        <Button
          variant="ghost"
          icon="lucide-refresh-cw"
          :label="__('Read the records again')"
          :tooltip="__('Read the records again')"
          :loading="busy"
          data-slot="fields-refresh"
          @click="emit('refresh')"
        />
        <Button
          variant="ghost"
          icon="lucide-x"
          :label="__('Close records')"
          :tooltip="__('Close')"
          @click="emit('close')"
        />
      </div>
    </div>

    <FadedScroll class="min-h-0 flex-1">
      <EmptyState
        v-if="!rows.length"
        icon="lucide-link"
        :title="__('This file is about nothing yet')"
        :description="__('Add a record and its fields become things you can drop in.')"
      />

      <div v-else class="flex flex-col gap-2 p-3">
        <section
          v-for="row in rows"
          :key="row.key"
          class="rounded-6 border border-outline-gray-1"
          :data-slot="`source-${row.key}`"
        >
          <!-- Who this source is: the kind on one line, the record on the
               next. Two lines rather than one because both matter and
               neither fits beside the other in a rail — somebody is looking
               for the Halloway job, and then for which of its two
               quotations. -->
          <div class="px-2 py-1.5">
            <div class="flex items-center gap-2">
              <Button
                variant="ghost"
                class="min-w-0 flex-1 !justify-start"
                :aria-expanded="open === row.key"
                :label="row.label"
                :icon-left="open === row.key ? 'lucide-chevron-down' : 'lucide-chevron-right'"
                @click="toggle(row)"
              />

              <Badge v-if="!row.reference_name" theme="amber" :label="__('Waiting')" />

              <Dropdown v-if="canWrite" :options="rowMenu(row)">
                <Button
                  variant="ghost"
                  size="sm"
                  icon="lucide-more-horizontal"
                  :label="__('What to do with this record')"
                  :tooltip="__('What to do with this record')"
                />
              </Dropdown>
            </div>

            <p class="truncate ps-8 text-p-xs text-ink-gray-5">{{ identity(row) }}</p>
          </div>

          <div v-if="open === row.key" class="border-t border-outline-gray-1 p-2">
            <!-- A slot the template left. Asked here, once, and then it is a
                 record like any other. -->
            <Button
              v-if="!row.reference_name"
              class="w-full"
              icon-left="lucide-search"
              :label="__('Choose a {0}', [row.label])"
              :disabled="!canWrite"
              @click="choose(row)"
            />

            <template v-else>
              <FormControl
                v-model="query"
                type="text"
                :placeholder="__('Search fields')"
                class="mb-2"
              />

              <div v-if="loading" class="flex flex-col gap-1">
                <Skeleton v-for="n in 6" :key="n" class="h-6 w-full" />
              </div>

              <div v-else>
                <p
                  v-if="!shownFields.length && !shownTables.length"
                  class="px-2 py-3 text-p-xs text-ink-gray-5"
                >
                  {{ __('Nothing matched') }}
                </p>

                <!--
                  Two to a row rather than one under another, and the reason
                  is the length of the list: a real doctype offers ninety
                  fields, and ninety full-width rows is a rail you scroll
                  rather than read. Each carries its type's glyph — the same
                  one the record's own label carries, from the same server
                  answer — so the shape of the thing is legible before the
                  word is: five calendars and a wallet.
                -->
                <div class="grid grid-cols-2 gap-0.5">
                  <Button
                    v-for="one in shownFields"
                    :key="one.fieldname"
                    variant="ghost"
                    size="sm"
                    class="min-w-0 !justify-start"
                    :icon-left="one.icon"
                    :label="one.label"
                    :tooltip="tip(row, one)"
                    :disabled="!canWrite"
                    :data-slot="`insert-${one.fieldname}`"
                    @click="insertField(row, one)"
                  />
                </div>

                <!-- The blocks, under a rule of their own: inserting one puts
                     a real table in the prose, which is a different act from
                     putting a phrase in a sentence. So a row each, full
                     width, rather than in the grid above. -->
                <template v-if="blocks && shownTables.length">
                  <p class="mt-2 px-2 pb-1 text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
                    {{ __('Tables') }}
                  </p>
                  <Button
                    v-for="one in shownTables"
                    :key="one.fieldname"
                    variant="ghost"
                    size="sm"
                    class="w-full !justify-start"
                    :icon-left="one.icon || 'lucide-table'"
                    :label="one.label"
                    :disabled="!canWrite"
                    :data-slot="`insert-table-${one.fieldname}`"
                    @click="insertTable(row, one)"
                  />
                </template>
              </div>
            </template>
          </div>
        </section>
      </div>
    </FadedScroll>

    <!-- Out of the scroller on purpose: a doctype has ninety fields, and the
         other thing this panel does must not be ninety rows down. -->
    <div v-if="canWrite" class="shrink-0 border-t border-outline-gray-1 p-3">
      <Button
        class="w-full"
        icon-left="lucide-plus"
        :label="__('Add a record')"
        :disabled="rows.length >= MAX_SOURCES"
        data-slot="source-add"
        @click="adding = true"
      />
    </div>

    <footer
      class="flex shrink-0 items-center justify-between gap-2 border-t border-outline-gray-1 px-3 py-2"
    >
      <span class="min-w-0 truncate text-p-xs text-ink-gray-5">{{ read }}</span>
      <!-- Whatever this editor can do with what it just read. The document
           puts "Fix the fields" here; a workbook has nothing to put, because
           its cells already hold what the browser computed. -->
      <slot name="footer" :rows="rows" />
    </footer>

    <!-- Which kind, then which one. Two steps rather than one dialog with a
         doctype in it, because the second list cannot exist until the first
         is answered. -->
    <Dialog v-model="adding" :title="__('Add a record')">
      <template #default>
        <div class="flex flex-col gap-3">
          <p class="text-p-sm text-ink-gray-6">
            {{ __('The document will read this record, and its fields become phrases you can put in the prose.') }}
          </p>
          <Combobox
            v-model="kind"
            v-model:query="kindQuery"
            :options="kindOptions"
            :placeholder="__('Which kind of record?')"
            :loading="looking"
            :filterable="false"
            :empty-text="looking ? __('Looking…') : __('Nothing matched')"
          />
        </div>
      </template>
      <template #actions>
        <Button
          variant="solid"
          :label="__('Next')"
          :disabled="!kind"
          :loading="saving"
          @click="pickFor"
        />
      </template>
    </Dialog>

    <RecordPicker
      v-model="picking"
      :doctype="wanted?.doctype || ''"
      :said="said"
      @pick="took"
    />
  </aside>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  Badge,
  Button,
  Combobox,
  Dialog,
  Dropdown,
  FormControl,
  Skeleton,
} from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import FadedScroll from '@/shared/components/FadedScroll.vue'
import RecordPicker from '@/shared/components/RecordPicker.vue'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The file this reads for — a document or a workbook, both are `File`. */
  name: { type: String, required: true },
  /** `binding.file_sources`'s answer, held by whoever opened the file. */
  sources: { type: Array, default: () => [] },
  /** `{"key.field": text}` — what each field says now, for the previews. */
  values: { type: Object, default: () => ({}) },
  /** Whether a read is in flight, so the control can say so. */
  busy: { type: Boolean, default: false },
  /** When the values on screen were read. The whole freshness answer. */
  readAt: { type: [Date, null], default: null },
  /**
   * Whether a child table is something this editor can take.
   *
   * The document can: a block is a real table in the prose. A workbook
   * cannot, and not for want of trying — a child table *is* a sheet in this
   * product (`docs/SHEETS.md` §3), so the answer to "put the quotation's
   * lines in a workbook" is the sheet already bound to them rather than a
   * second reader beside `RECORD()`.
   */
  blocks: { type: Boolean, default: true },
  /** One sentence saying what choosing a record will do, in the owner's words. */
  said: { type: String, default: '' },
  canWrite: { type: Boolean, default: false },
})

const emit = defineEmits([
  'insert-field', 'insert-table', 'refresh', 'changed', 'close',
])

//: `quotation.grand_total`. The key both halves of the answer use — see
//: `shared/binding.py` and the editors' own resolvers.
const at = (source, field) => `${source || 'record'}.${field}`

//: What the server will hold — `binding.MAX_SOURCES`. Repeated rather than
//: fetched, because it only decides whether a button is greyed out and the
//: server refuses either way.
const MAX_SOURCES = 12

const rows = ref([...props.sources])
const open = ref(props.sources.find((one) => !one.reference_name)?.key
  || props.sources[0]?.key
  || '')

const loading = ref(false)
const saving = ref(false)
const query = ref('')

// What each doctype offers, kept by doctype rather than by source: two
// sources of the same kind ask the same question and one answer serves both.
const offered = ref({})

const read = computed(() =>
  (props.readAt ? __('Read at {0}', [props.readAt.toLocaleTimeString()]) : ''),
)

const current = computed(() => rows.value.find((one) => one.key === open.value) || null)

const shownFields = computed(() => {
  const found = offered.value[current.value?.reference_doctype]?.fields || []
  return match(found)
})

const shownTables = computed(() => {
  const found = offered.value[current.value?.reference_doctype]?.tables || []
  return match(found)
})

/** Which record this source is, in one line: the title and then the id.
 *  Both, because a title identifies the job and an id identifies which of
 *  its quotations, and a rail that showed only one of them made somebody
 *  open the record to find out. */
function identity(row) {
  if (!row.reference_name) return __('No record chosen')
  if (!row.title || row.title === row.reference_name) return row.reference_name
  return `${row.title} · ${row.reference_name}`
}

function match(list) {
  const asked = query.value.trim().toLowerCase()
  if (!asked) return list
  return list.filter((one) =>
    (one.label || '').toLowerCase().includes(asked)
    || one.fieldname.toLowerCase().includes(asked))
}

/** The whole label, and what the field says now.
 *
 *  Two columns cost the room a preview used to sit in, and a truncated label
 *  is the one thing a picker must not have — so both move into the tooltip.
 *  The value only once something has resolved it: a field the prose does not
 *  name yet has no answer, and "Grand Total — " reads as a bug. */
function tip(row, field) {
  const text = props.values[at(row.key, field.fieldname)] || ''
  return text ? `${field.label} — ${text}` : field.label
}

function toggle(row) {
  open.value = open.value === row.key ? '' : row.key
  query.value = ''
  if (open.value) load(row)
}

async function load(row) {
  if (!row?.reference_doctype || offered.value[row.reference_doctype]) return
  loading.value = true
  try {
    const answer = await workspace.bindableFields(row.reference_doctype)
    offered.value = {
      ...offered.value,
      [row.reference_doctype]: {
        fields: answer?.fields || [],
        tables: answer?.tables || [],
      },
    }
  } catch {
    // A doctype somebody cannot read is a section with nothing in it, not a
    // panel that fails to draw.
    offered.value = { ...offered.value, [row.reference_doctype]: { fields: [], tables: [] } }
  } finally {
    loading.value = false
  }
}

/*
 * An event, not a branch.
 *
 * What a click puts where is the one thing the two editors do not share: the
 * document inserts a token that renders the field, the workbook writes a
 * `RECORD()` formula into the cell somebody is standing on. Both are a few
 * lines in their own page, and neither belongs in a rail whose job is to say
 * what a record offers.
 */
function insertField(row, field) {
  emit('insert-field', {
    source: row.key,
    field: field.fieldname,
    label: field.label,
    text: props.values[at(row.key, field.fieldname)] || '',
  })
}

function insertTable(row, table) {
  emit('insert-table', {
    source: row.key,
    table: table.fieldname,
    label: table.label,
    // The columns the child doctype itself puts in a grid — `in_list_view`,
    // worked out by `binding.tables`. A schedule with twenty columns does not
    // fit across a page, and the first six in schema order are Item Code and
    // five checkboxes.
    columns: table.default || [],
  })
}

// --- adding, choosing and dropping a record --------------------------------

const adding = ref(false)
const kind = ref('')
const kindQuery = ref('')
const kindOptions = ref([])
const looking = ref(false)

const picking = ref(false)
// The source being filled, or `{doctype}` for one being added.
const wanted = ref(null)

//: Long enough that typing a name is one search rather than eleven.
const PAUSE = 250
let waiting = null

async function lookForKinds() {
  looking.value = true
  try {
    const found = await workspace.bindableKinds(kindQuery.value)
    kindOptions.value = (found || []).map((one) => ({
      label: one.label || one.name,
      value: one.name,
      description: one.module || '',
    }))
  } catch {
    kindOptions.value = []
  } finally {
    looking.value = false
  }
}

watch(kindQuery, () => {
  window.clearTimeout(waiting)
  waiting = window.setTimeout(lookForKinds, PAUSE)
})

watch(adding, (showing) => {
  if (!showing) return
  kind.value = ''
  kindQuery.value = ''
  lookForKinds()
})

/** The kind is answered; ask which one. */
function pickFor() {
  wanted.value = { doctype: kind.value }
  adding.value = false
  picking.value = true
}

/** Fill a slot the template left. */
function choose(row) {
  wanted.value = { doctype: row.reference_doctype, key: row.key }
  picking.value = true
}

async function took({ doctype, name }) {
  const asked = wanted.value
  wanted.value = null
  if (!asked) return

  saving.value = true
  try {
    if (asked.key) {
      await workspace.setSource(props.name, asked.key, name)
    } else {
      const made = await workspace.addSource(props.name, doctype, name, '')
      open.value = made?.key || open.value
    }
    await reload()
  } finally {
    saving.value = false
  }
}

function rowMenu(row) {
  return [
    {
      label: row.reference_name ? __('Use a different record') : __('Choose a record'),
      icon: 'search',
      onClick: () => choose(row),
    },
    {
      // The tokens that named it are left alone and answer nothing, which
      // shows as a blank rather than as a document that will not open —
      // removing them is a decision about the prose.
      label: __('Stop reading this record'),
      icon: 'trash-2',
      onClick: () => drop(row),
    },
  ]
}

async function drop(row) {
  await workspace.dropSource(props.name, row.key)
  if (open.value === row.key) open.value = ''
  await reload()
}

async function reload() {
  rows.value = (await workspace.fileSources(props.name)) || []
  const showing = rows.value.find((one) => one.key === open.value)
  if (showing) await load(showing)
  // The owner holds the sources too — it opened the file with them — and it
  // is the one that knows how to read the records again.
  emit('changed', rows.value)
  emit('refresh')
}

// Whatever section is open needs its field list, and the panel is drawn
// before anybody clicks anything.
watch(() => props.sources, (next) => {
  rows.value = [...(next || [])]
  if (!rows.value.some((one) => one.key === open.value)) {
    open.value = rows.value.find((one) => !one.reference_name)?.key
      || rows.value[0]?.key
      || ''
  }
  if (current.value) load(current.value)
}, { immediate: true })
</script>
