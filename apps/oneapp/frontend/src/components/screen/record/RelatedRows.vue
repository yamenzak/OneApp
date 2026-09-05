<template>
  <!--
    Another screen's records, narrowed to the one being read.

    A project's invoices are the invoices screen with `project = this one` —
    not a second invoices list written for projects. So this asks `rows` for
    that screen with that filter, and everything the invoices screen knows
    about drawing an invoice comes with it: its columns, its widths, its title
    field, its states, its links.

    Which is the point of declaring a tab as a screen and a fieldname rather
    than as a query. `rows` is where the space, the permissions and the filter
    are checked, and it does not care that a hero asked it — a person who may
    not see the invoices screen gets an empty tab here for the same reason
    they get no invoices in the rail.
  -->
  <div class="flex flex-col gap-3 pt-4">
    <div class="flex items-center gap-2">
      <span class="text-p-sm text-ink-gray-6">{{ counted }}</span>
      <span v-if="more" class="text-p-xs text-ink-gray-5">
        showing the first {{ rows.length }}
      </span>
      <!--
        Frappe's "New linked document", where it belongs: on the tab that is
        already about the link. The field this tab filtered on arrives filled
        in, so making an invoice against a project is one button rather than a
        trip to the invoices screen and a picker.
      -->
      <Button
        v-if="spec.can_create"
        class="ms-auto"
        data-slot="related-new"
        icon-left="lucide-plus"
        :label="`New ${spec.singular || 'record'}`"
        @click="creating = true"
      />
    </div>

    <CreateDialog
      v-if="spec.can_create"
      v-model="creating"
      :spec="spec"
      :space-code="spaceCode"
      :screen="screen"
      :preset="preset"
      @created="made"
    />

    <RecordTable
      v-if="rows.length"
      :columns="visible"
      :rows="rows"
      :row-height="52"
      :fill="spec.title_field"
      :virtual-from="VIRTUAL_FROM"
      extra-class="rounded-6 border border-outline-gray-2"
      @row-click="emit('open', { screen, name: $event.name })"
    >
      <template #cell="{ column, row }">
        <TitleCell
          v-if="column.cell === 'title'"
          :row="row"
          :title-field="spec.title_field"
          :image-field="spec.image_field"
          @open="emit('open', { screen, name: row.name })"
        />
        <RowMeta v-else-if="column.cell === 'meta'" :meta="row._meta || {}" />
        <FieldCell
          v-else
          :column="column.column"
          :value="row[column.key]"
          :row="row"
          :links="row._links || {}"
          :states="spec.states || []"
          :space-code="spaceCode"
          :screen="screen"
        />
      </template>
    </RecordTable>

    <LoadingText v-else-if="loading" text="Loading" />

    <!--
      Nothing filed against it. Said in the words of the thing that is missing
      rather than "No records": a person on a project's Invoices tab knows what
      an invoice is, and "Nothing here yet" is a sentence that could be under
      anything.
    -->
    <p v-else class="py-6 text-center text-p-sm text-ink-gray-5">
      No {{ (label || 'records').toLowerCase() }} against this yet.
    </p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, LoadingText } from '@/ui'
import CreateDialog from './CreateDialog.vue'
import RecordTable from '../bodies/RecordTable.vue'
import FieldCell from '../bodies/FieldCell.vue'
import TitleCell from '../bodies/TitleCell.vue'
import RowMeta from '../bodies/RowMeta.vue'
import { workspace } from '../../../lib/workspace'

const props = defineProps({
  spaceCode: { type: String, required: true },
  /** The screen whose records these are — not the one being read. */
  screen: { type: String, required: true },
  /** The field on that screen pointing back at the record being read. */
  field: { type: String, required: true },
  /**
   * What else has to be true, which for a Dynamic Link is the doctype.
   *
   * `about` on a Correspondence holds an id and `about_doctype` holds what kind
   * of thing it is, and filtering on the id alone would put a licence's letters
   * on a project that happens to share its name. Empty for a plain Link, which
   * is most of them.
   */
  where: { type: Array, default: () => [] },
  /** The record being read, by id. */
  name: { type: String, required: true },
  /** What they are called, for the count and the empty line. */
  label: { type: String, default: '' },
})

const emit = defineEmits(['open'])

// A tab, not a list: past this many the answer is the screen itself, and a
// project with four hundred invoices is not a page anybody scrolls.
const PAGE = 50

// The same threshold the list uses. It will not be reached at a page of fifty
// — it is here so the two tables cannot disagree about the number.
const VIRTUAL_FROM = 200

// What a new one starts with: the link back, and for a Dynamic Link the
// doctype beside it — without which the row would be about a name and nothing
// else, and would not come back to this tab.
const preset = computed(() =>
  Object.fromEntries([
    [props.field, props.name],
    ...(props.where || []).map(([field, , value]) => [field, value]),
  ]),
)

const creating = ref(false)
const spec = ref({})
const rows = ref([])
const columns = ref([])
const more = ref(false)
const loading = ref(false)

const counted = computed(() => {
  const many = rows.value.length
  const what = props.label || 'record'
  if (!many) return ''
  // The label is a plural already — "Invoices" — so the singular is the one
  // that has to be made, and only where the count is one.
  return `${many}${more.value ? '+' : ''} ${many === 1 ? singular(what) : what.toLowerCase()}`
})

const singular = (word) => {
  const one = word.toLowerCase()
  return one.endsWith('s') ? one.slice(0, -1) : one
}

/**
 * The columns the rows came back with, as tracks. Same model as the list, less
 * the one that is the question.
 *
 * Every row here has the same value in the field the tab filtered on — that is
 * what the tab *is* — so a Project column on a project's Invoices tab is the
 * project's own name written down six times. Kept only where it is the screen's
 * title field, because then dropping it leaves rows with no name.
 */
const visible = computed(() => {
  const titleField = spec.value?.title_field
  return (columns.value || [])
    .filter((column) => column.fieldname !== props.field || column.fieldname === titleField)
    .map((column) => ({
      key: column.fieldname,
      label: column.label,
      icon: column.icon,
      track: `${column.width}px`,
      width: column.width,
      cell:
        column.fieldname === '__activity'
          ? 'meta'
          : column.fieldname === titleField
            ? 'title'
            : column.cell,
      column,
    }))
})

const load = async () => {
  if (!props.name || !props.screen || !props.field) return
  loading.value = true
  try {
    // Both at once. The spec answers what a row of this screen looks like —
    // its title field, its states — and the rows answer which rows; neither
    // waits on the other.
    const [found, page] = await Promise.all([
      workspace.screenSpec(props.spaceCode, props.screen),
      workspace.screenRows(
        props.spaceCode,
        props.screen,
        { filters: [[props.field, '=', props.name], ...(props.where || [])] },
        '',
        { start: 0, limit: PAGE },
      ),
    ])
    spec.value = found || {}
    rows.value = page?.rows || []
    // The columns the rows were fetched with, not the spec's — the same reason
    // the list reads them off the page.
    columns.value = page?.columns || found?.columns || []
    more.value = !!page?.has_more
  } finally {
    loading.value = false
  }
}

// Opened rather than only listed: somebody who just made an invoice against
// this project means to be in it, and a tab that silently grew a row leaves
// them hunting for the one they made.
const made = (name) => {
  load()
  if (name) emit('open', { screen: props.screen, name })
}

watch(() => [props.screen, props.field, props.name, props.where], load, { immediate: true })
</script>
