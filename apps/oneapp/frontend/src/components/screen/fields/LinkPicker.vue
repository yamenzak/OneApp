<template>
  <!--
    A Link field, rendered the way the desk renders one: type to search, and
    every result reads as a record — a face, a name, the id underneath — rather
    than as the primary key it is stored as.

    The search is the server's: `filterable` is off deliberately, because
    frappe-ui otherwise runs a second literal substring pass over what came back
    and silently drops rows the server matched on `search_fields`. The rows are
    `RecordChip`, the same component the list cell uses. Create is an option in
    the menu, and only when the server says this person may create one.
  -->
  <!-- Nothing is fetched until somebody touches this — see `prime`.
       `focusin` precedes every way of opening the menu; `pointerdown` catches
       the mouse on the chevron, which does not always focus the input. -->
  <div @focusin="prime" @pointerdown="prime">
    <Combobox
      :model-value="modelValue"
      v-model:query="query"
      :options="options"
      :label="label"
      :description="description"
      :disabled="disabled"
      :placeholder="prompt"
      :required="required"
      :loading="loading"
      :filterable="false"
      :empty-text="emptyText"
      @update:model-value="pick"
    >
      <!-- The field's label, forwarded: this component is a wrapper, so a slot
           given to it has to be handed on or it is silently dropped. -->
      <!-- `#label` before `v-if`, deliberately: `test_content_goes_somewhere`
           recognises a named-slot block by `<template` followed immediately by
           `#`. The order is free in Vue and not free here. -->
      <template #label="slotProps" v-if="$slots.label">
        <div class="flex min-w-0 items-center justify-between gap-2">
          <slot name="label" v-bind="slotProps" />

          <!--
            Where this link goes, as the two things a person wants: read it
            beside what I am doing, or go and work on it.

            On the label's row rather than inside the box, whose right-hand side
            is the chevron that opens the menu — overriding that slot would stop
            the chevron opening the picker, and a row beside the input would
            have to guess how tall the label and description are.
          -->
          <span v-if="destination" class="flex shrink-0 items-center gap-0.5">
            <Button
              variant="ghost"
              size="sm"
              icon="lucide-panel-right"
              :label="`Open ${named} beside this`"
              :tooltip="`Open ${named} beside this`"
              data-slot="link-peek"
              @click="peek"
            />
            <Button
              variant="ghost"
              size="sm"
              icon="lucide-arrow-up-right"
              :label="`Open ${named}`"
              :tooltip="`Open ${named}`"
              data-slot="link-open"
              @click="open"
            />
          </span>
        </div>
      </template>

      <!-- The chosen record's face, in the box itself. -->
      <template #prefix>
        <Avatar
          v-if="chosen?.image"
          :image="chosen.image"
          :label="String(chosen.label || chosen.value || '')"
          shape="square"
          size="sm"
        />
      </template>

      <!-- Shared across every row, so the Create row is told apart here: it
           carries an icon, a record carries a face. -->
      <template #item-prefix="{ item }">
        <Avatar
          v-if="item.record"
          :image="item.record.image"
          :label="String(item.record.label || item.record.value || '')"
          shape="square"
          size="sm"
        />
        <Icon v-else-if="item.icon" :name="item.icon" class="size-4 text-ink-gray-6" />
      </template>

      <!-- A name, and the id and searchable detail beneath it — the same three
           things the list's title column shows. -->
      <template #item-label="{ item }">
        <div class="flex min-w-0 flex-col">
          <span class="truncate">{{ item.record ? item.record.label : item.label }}</span>
          <span
            v-if="item.record && detail(item.record)"
            class="truncate text-p-sm text-ink-gray-5"
          >
            {{ detail(item.record) }}
          </span>
        </div>
      </template>
    </Combobox>

    <!--
      Frappe's quick entry, in our vocabulary. The server decides what it asks
      for — `allow_in_quick_entry` plus anything mandatory.
    -->
    <Dialog v-model="creating" :title="`New ${spec?.label || 'record'}`" size="lg">
      <div class="flex flex-col gap-4">
        <div v-for="one in spec?.fields || []" :key="one.fieldname" class="flex gap-2">
          <Icon
            :name="one.icon"
            class="mt-5 size-3.5 shrink-0 text-ink-gray-4"
            :aria-hidden="true"
          />
          <FieldControl
            v-model="draft[one.fieldname]"
            :field="one"
            :space-code="spaceCode"
            :screen="screen"
            class="min-w-0 flex-1"
          />
        </div>
        <ErrorMessage v-if="error" :message="error" />
      </div>

      <template #actions>
        <Button variant="solid" label="Create" :loading="saving" @click="create" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Combobox, Avatar, Icon, Dialog, Button, ErrorMessage } from '@/ui'
import { workspace } from '../../../lib/workspace'
import { screenFor } from '@/lib/shell/nav'

// The quick-create form renders whatever the target doctype asks for, and one
// of those fields can itself be a Link — so this component and FieldControl
// each need the other. Async breaks the cycle at load rather than at import.
const FieldControl = defineAsyncComponent(() => import('./FieldControl.vue'))

const props = defineProps({
  modelValue: { type: [String, Number], default: null },
  /** The field this picks for, and the screen that bounds what it may see. */
  fieldname: { type: String, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  label: { type: String, default: '' },
  description: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  required: { type: Boolean, default: false },
  /** Whether Create belongs in the menu. A form offers it; a filter does not. */
  allowCreate: { type: Boolean, default: false },
  /**
   * Whether this link offers to open what it points at. A form does; a filter
   * row does not — a control inside a popover that navigates out from under
   * itself loses what was being typed.
   */
  allowOpen: { type: Boolean, default: false },
  /**
   * The docfield, for the handful of properties this picker reads —
   * `remember_last_selected_value` today. Optional: a filter row builds a
   * picker without one.
   */
  field: { type: Object, default: () => ({}) },
  /**
   * A record being made rather than edited. Only a new one may be seeded from
   * the remembered choice: filling a blank on an existing record would change
   * it without anybody asking.
   */
  isNew: { type: Boolean, default: false },
  /**
   * Which doctype this points at, for a Dynamic Link only. Its target lives in
   * another field on the record, which only the form holds, so the form hands
   * it here and the server validates it against the space's grant.
   */
  target: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const route = useRoute()
const router = useRouter()

/**
 * The screen this link's target lives on in this space, or nothing.
 *
 * The doctype alone opens nothing — a screen is what this product has routes
 * for — so the space's own manifest decides, out of the session rather than
 * over the wire. Nothing, and therefore no buttons, for an empty field, a
 * filter's picker, and a link to a master no screen shows.
 */
const destination = computed(() => {
  if (!props.allowOpen || !props.modelValue) return ''
  return screenFor(props.spaceCode, props.target || props.field?.options || '')
})

/**
 * Open it beside this one, in the drawer. Written into the URL rather than into
 * a ref: that makes the drawer a place with a link, and the host is already
 * watching `peek` and `peekScreen`.
 */
/** What to call the thing these two open: the record's name where it has been
 *  resolved, its id until then. */
const named = computed(() => chosen.value?.label || props.modelValue || 'this')

const peek = () => {
  if (!destination.value) return
  router.push({
    query: { ...route.query, peek: String(props.modelValue), peekScreen: destination.value },
  })
}

/**
 * Go to it, on its own screen. The view type and any saved view are dropped:
 * they belong to the screen being left, and `layout=my-overdue` on a different
 * screen is a view that is not its.
 */
const open = () => {
  if (!destination.value) return
  router.push({ query: { screen: destination.value, record: String(props.modelValue) } })
}

const query = ref('')
const found = ref([])
const loading = ref(false)
const spec = ref(null)

const detail = (record) => [record.id, record.description].filter(Boolean).join(' · ')

/**
 * What the empty box says — and nothing, when nobody may write it.
 *
 * A disabled Combobox still draws its placeholder, so a `read_only` Link sat
 * saying "Search…" over a control that would not open.
 */
const prompt = computed(() => (props.disabled ? '' : props.placeholder || 'Search…'))

/**
 * `remember_last_selected_value` — a Link that reopens on your last choice.
 *
 * Per person and per browser, which is what localStorage is: a typing
 * convenience, not a default worth storing on the server. Keyed by screen and
 * fieldname rather than by doctype — the same doctype behind two screens is two
 * different habits.
 */
const REMEMBERED = 'onespace.link'
const memoryKey = computed(() => `${REMEMBERED}.${props.spaceCode}.${props.screen}.${props.fieldname}`)

function remember(value) {
  if (!props.field?.remember_last_selected_value || !value) return
  try {
    window.localStorage.setItem(memoryKey.value, String(value))
  } catch {
    // A private window, or storage that is full. Forgetting is the whole cost.
  }
}

function remembered() {
  if (!props.field?.remember_last_selected_value) return ''
  try {
    return window.localStorage.getItem(memoryKey.value) || ''
  } catch {
    return ''
  }
}

function pick(value) {
  remember(value)
  emit('update:modelValue', value)
}

// Offered once, when a new record's field opens empty. Not `pick` — that would
// write the value back to the storage it just came from.
onMounted(() => {
  if (!props.isNew || props.modelValue) return
  const last = remembered()
  if (last) emit('update:modelValue', last)
})

// The record behind the current value. It is not always in `found` — a value
// chosen yesterday is not in today's first twenty rows — so it is fetched once
// and kept.
const chosen = ref(null)

const options = computed(() => {
  const rows = [...found.value]
  if (chosen.value && !rows.some((r) => r.value === chosen.value.value)) {
    rows.unshift(chosen.value)
  }

  const list = rows.map((record) => ({
    value: record.value,
    label: record.label,
    record,
  }))

  if (props.allowCreate && spec.value?.can_create) {
    list.push({
      type: 'custom',
      key: '__create',
      icon: 'lucide-plus',
      label: query.value
        ? `Create "${query.value}"`
        : `Create a new ${spec.value.label || 'record'}`,
      onClick: () => openCreate(),
    })
  }
  return list
})

const emptyText = computed(() =>
  query.value ? `Nothing matches “${query.value}”` : 'Nothing to choose from',
)

const search = async () => {
  // Nothing to search for a picker that cannot be opened. `resolveChosen` still
  // runs, so the box still shows a name rather than an id.
  if (props.disabled) {
    found.value = []
    return
  }
  loading.value = true
  try {
    found.value =
      (await workspace.linkOptions(
        props.spaceCode,
        props.screen,
        props.fieldname,
        query.value,
        props.target,
      )) || []
  } finally {
    loading.value = false
  }
}

/**
 * A Dynamic Link whose target has changed points at nothing, so it is cleared —
 * a value left over from the doctype you just stopped pointing at is a link
 * into the wrong table.
 *
 * The first sight of a target is not a change: an existing record opens with
 * both fields set, and clearing then would empty the field by looking at it.
 */
watch(
  () => props.target,
  (now, before) => {
    if (before === undefined || now === before) return
    found.value = []
    chosen.value = null
    if (props.modelValue) emit('update:modelValue', null)
    search()
  },
)

const resolveChosen = async () => {
  const value = props.modelValue
  if (!value) {
    chosen.value = null
    return
  }
  if (chosen.value?.value === value) return
  const known = found.value.find((r) => r.value === value)
  if (known) {
    chosen.value = known
    return
  }
  // Searching by the id is how the server finds one record: `name like` is the
  // first clause of the same search the picker already uses.
  const rows = await workspace.linkOptions(props.spaceCode, props.screen, props.fieldname, value)
  chosen.value = (rows || []).find((r) => r.value === value) || null
}

const loadSpec = async () => {
  if (!props.allowCreate) {
    spec.value = null
    return
  }
  spec.value = await workspace.linkNewSpec(props.spaceCode, props.screen, props.fieldname, props.target)
}

/**
 * The first page of options, and whether Create is offered — on first touch,
 * not on mount.
 *
 * A picker that fetched both on render is fine for the two on a form and
 * ruinous in a grid: six invoice lines with two Link columns fired thirty-eight
 * requests before anybody clicked anything.
 *
 * The value's own label is still resolved eagerly, and has to be: that is what
 * the closed box *shows*.
 */
const primed = ref(false)

const prime = () => {
  if (primed.value || props.disabled) return
  primed.value = true
  search()
  loadSpec()
}

watch(query, search)
watch(() => props.modelValue, resolveChosen, { immediate: true })
watch(
  () => [props.spaceCode, props.screen, props.fieldname],
  () => {
    // A different field is a different set of options, so what was fetched is
    // dropped and the next touch fetches again.
    found.value = []
    spec.value = null
    primed.value = false
  },
  { immediate: true },
)

// ----- Create ------------------------------------------------------------ //

const creating = ref(false)
const draft = reactive({})
const saving = ref(false)
const error = ref('')

const openCreate = () => {
  error.value = ''
  for (const key of Object.keys(draft)) delete draft[key]
  // What was typed was meant as the record's name — Frappe's quick entry makes
  // the same assumption, and throwing it away asks somebody to type it twice.
  const seed = seedField()
  if (seed && query.value) draft[seed] = query.value
  creating.value = true
}

const seedField = () => {
  const fields = spec.value?.fields || []
  const title = spec.value?.title_field
  if (title && fields.some((f) => f.fieldname === title)) return title
  const text = fields.find((f) => f.fieldtype === 'Data' && f.reqd)
  return (text || fields.find((f) => f.fieldtype === 'Data'))?.fieldname || null
}

const create = async () => {
  saving.value = true
  error.value = ''
  try {
    const record = await workspace.linkNew(
      props.spaceCode,
      props.screen,
      props.fieldname,
      JSON.stringify({ ...draft }),
      props.target,
    )
    // Adopt it straight away: the point of creating one here was to pick it.
    chosen.value = record
    found.value = [record, ...found.value.filter((r) => r.value !== record.value)]
    pick(record.value)
    creating.value = false
  } catch (err) {
    error.value = err?.message || String(err)
  } finally {
    saving.value = false
  }
}
</script>
