<!--
  What this document reads, and everything you can put in the prose from it.

  A rail rather than a strip, and the reason is the shape of the thing: a
  document about a quotation is usually also about its customer and its
  project, and a strip that had to hold three records and their fields would
  be a strip with a menu inside a menu. Here each record is a section you open
  and browse — its fields as phrases, its child tables as blocks — which is
  the browsing the design turns on.

  It also answers the question the design turns on before anybody asks it:
  *is this fresh?* Nothing is pushed. The footer says when the numbers on
  screen were read, and Refresh reads them again. See `shared/binding.py` and
  `oneapp/onedoc/fields.py`.

  A slot — a source with no record yet — is what a template hands over. The
  panel prompts for it here rather than in a dialog before the document
  exists, because a template is a starting point and the person filling it in
  usually wants to add a record of their own beside the ones it named.
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
          :loading="asking"
          data-slot="fields-refresh"
          @click="refresh"
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
        :title="__('This document is about nothing yet')"
        :description="__('Add a record and its fields become phrases you can drop into the prose.')"
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
                <template v-if="shownTables.length">
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
      <Button
        v-if="canWrite && rows.length"
        variant="ghost"
        size="sm"
        :label="__('Fix the fields')"
        :tooltip="__('Stop asking, and keep what they say now')"
        data-slot="fields-settle"
        @click="settle"
      />
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
          :loading="busy"
          @click="pickFor"
        />
      </template>
    </Dialog>

    <RecordPicker
      v-model="picking"
      :doctype="wanted?.doctype || ''"
      :said="picked"
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
import {
  applyRecordFields,
  applyRecordTables,
  at,
  namedFields,
} from '@/modules/onedoc/lib/recordField'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The document's File id. */
  name: { type: String, required: true },
  /** The sources the server sent with the document — `binding.file_sources`. */
  sources: { type: Array, default: () => [] },
  /** The tiptap instance the tokens and blocks live in. */
  editor: { type: Object, default: null },
  canWrite: { type: Boolean, default: false },
})

const emit = defineEmits(['settled', 'patching', 'patched', 'close'])

//: What the server will hold — `binding.MAX_SOURCES`. Repeated rather than
//: fetched, because it only decides whether a button is greyed out and the
//: server refuses either way.
const MAX_SOURCES = 12

const rows = ref([...props.sources])
const open = ref(props.sources.find((one) => !one.reference_name)?.key
  || props.sources[0]?.key
  || '')

const asking = ref(false)
const loading = ref(false)
const busy = ref(false)
const query = ref('')
const readAt = ref(null)

// What each doctype offers, kept by doctype rather than by source: two
// sources of the same kind ask the same question and one answer serves both.
const offered = ref({})

// The last answers, so a field in the list can show what it would insert.
const said = ref({})
const drawn = ref({})

const read = computed(() =>
  (readAt.value ? __('Read at {0}', [readAt.value.toLocaleTimeString()]) : ''),
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
  const text = said.value[at(row.key, field.fieldname)] || ''
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

/**
 * Ask every record again, and patch what is on screen.
 *
 * What is in the editor, not what is on disk: the save is debounced, and a
 * token somebody inserted a second ago is only in the editor.
 */
async function refresh() {
  asking.value = true
  try {
    const answer = await workspace.docFields(props.name, namedFields(props.editor))
    said.value = answer?.fields || {}
    drawn.value = answer?.tables || {}
    if (answer?.sources) rows.value = answer.sources
    // Bracketed, and the two events have to stay in the same tick: patching
    // is a ProseMirror transaction, the editor calls that a change, and a
    // change starts the save loop. Opening a document would then write it.
    emit('patching')
    applyRecordFields(props.editor, said.value)
    applyRecordTables(props.editor, drawn.value)
    emit('patched')
    readAt.value = new Date()
  } finally {
    asking.value = false
  }
}

/*
 * Insert first, focus after — and never `focus()` inside the chain. The
 * reason cost an afternoon.
 *
 * Tiptap's `focus` command builds a transaction, calls `view.focus()`, and
 * then dispatches. From a control *inside* the editor that is fine, because
 * the prose already had focus and nothing happens in between. From this rail
 * it is not: the click moved focus out, so `view.focus()` really does move it
 * back, the browser fires a selection change, ProseMirror dispatches for it —
 * and the command is left holding a transaction against a document that has
 * moved. "Applying a mismatched transaction", and nothing inserted.
 *
 * So the insert goes in against the selection ProseMirror still remembers,
 * and the caret is put back afterwards through the view, which writes no
 * transaction of its own.
 */
function put(run) {
  const editor = props.editor
  if (!editor) return
  run(editor.commands)
  editor.view?.focus()
  // Straight away, so the token shows a number rather than an em dash for as
  // long as it takes somebody to notice.
  refresh()
}

function insertField(row, field) {
  put((commands) => commands.insertRecordField({
    source: row.key,
    field: field.fieldname,
    label: field.label,
    text: said.value[at(row.key, field.fieldname)] || undefined,
  }))
}

function insertTable(row, table) {
  put((commands) => commands.insertRecordTable({
    source: row.key,
    table: table.fieldname,
    label: table.label,
    // The columns the child doctype itself puts in a grid — `in_list_view`,
    // worked out by `binding.tables`. A schedule with twenty columns does not
    // fit across a page, and the first six in schema order are Item Code and
    // five checkboxes.
    columns: table.default || [],
  }))
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

const picked = computed(() =>
  __('The document will read this record. Every field you have already put in the prose fills itself in.'),
)

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

  busy.value = true
  try {
    if (asked.key) {
      await workspace.setSource(props.name, asked.key, name)
    } else {
      const made = await workspace.addSource(props.name, doctype, name, '')
      open.value = made?.key || open.value
    }
    await reload()
  } finally {
    busy.value = false
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
  await refresh()
}

async function settle() {
  const answer = await workspace.docSettleFields(props.name)
  if (answer?.content) emit('settled', answer.content)
}

// Read once when the panel appears, so the numbers are this minute's rather
// than the last save's — a document saved on Friday and opened on Monday is
// the ordinary case, not the strange one.
watch(
  () => props.editor,
  (instance) => {
    if (!instance) return
    refresh()
    if (current.value) load(current.value)
  },
  { immediate: true },
)

watch(() => props.sources, (next) => { rows.value = [...(next || [])] })

defineExpose({ refresh })
</script>
