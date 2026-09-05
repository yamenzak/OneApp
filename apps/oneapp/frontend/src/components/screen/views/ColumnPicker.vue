<template>
  <!--
    Which columns, in what order, and how each one sits.

    Frappe's list settings, in a dialog: the chosen columns as an ordered list
    with a grip to drag, and an add menu for everything else. What "everything
    else" means changed — it is the doctype's own fields now rather than the
    ones a manifest named, so wanting the due date on your list is a choice
    rather than a deploy.

    Laid out as two rows per column rather than one, which is the whole of the
    redesign. A column carries four answers now — where it sits, which edge it
    sticks to, which edge its values sit against, and how wide — and nine
    controls on one line was already the most crowded row in the product before
    alignment needed three more. The name and the destructive controls are the
    line you read; the settings are the quieter line under it, each behind a
    word rather than a bare icon.
  -->
  <Dialog v-model="open" title="Columns" size="2xl">
    <div class="flex flex-col gap-5">
      <!-- Grouping belongs here rather than in a control of its own: it is a
           question about the columns, and this is where the columns are. -->
      <FormControl
        type="select"
        label="Group rows by"
        :model-value="groupBy"
        :options="groupOptions"
        description="Rows are sorted by this first, so each group arrives whole."
        @update:model-value="emit('update:groupBy', $event)"
      />

      <div class="flex flex-col gap-2">
        <div class="flex items-baseline justify-between">
          <h3 class="text-p-sm font-medium text-ink-gray-8">On this list</h3>
          <p class="text-p-xs text-ink-gray-5">
            Drag to reorder, or use the arrows
          </p>
        </div>

        <!-- Scrolls rather than growing: a doctype with twenty columns on the
             list would otherwise push the add box off the bottom of a laptop. -->
        <FadedScroll class="max-h-[26rem]">
          <ul class="flex flex-col gap-1.5 pe-1">
            <li
              v-for="(column, index) in chosen"
              :key="column.fieldname"
              draggable="true"
              data-slot="column-row"
              class="flex flex-col gap-2 rounded-6 border border-outline-gray-2 bg-surface-base p-2"
              :class="dragging === index && 'opacity-50'"
              @dragstart="dragging = index"
              @dragend="dragging = null"
              @dragover.prevent
              @drop="dropOn(index)"
            >
              <!-- What it is, and what can be done to it whole. -->
              <div class="flex items-center gap-1.5">
                <Icon
                  name="lucide-grip-vertical"
                  class="size-3.5 shrink-0 cursor-grab text-ink-gray-4"
                />
                <Icon :name="iconFor(column)" class="size-3.5 shrink-0 text-ink-gray-5" />
                <span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-8">
                  {{ labelFor(column) }}
                </span>

                <!-- The arrows are not a nicety: a pointer drag reaches neither
                     a keyboard nor a phone, and order is the point of this
                     dialog. -->
                <Button
                  icon="lucide-chevron-up"
                  variant="ghost"
                  size="sm"
                  :label="`Move ${labelFor(column)} up`"
                  :tooltip="`Move ${labelFor(column)} up`"
                  :disabled="index === 0"
                  @click="move(index, -1)"
                />
                <Button
                  icon="lucide-chevron-down"
                  variant="ghost"
                  size="sm"
                  :label="`Move ${labelFor(column)} down`"
                  :tooltip="`Move ${labelFor(column)} down`"
                  :disabled="index === chosen.length - 1"
                  @click="move(index, 1)"
                />
                <Button
                  icon="lucide-x"
                  variant="ghost"
                  size="sm"
                  theme="red"
                  :label="`Remove ${labelFor(column)}`"
                  :tooltip="`Remove ${labelFor(column)}`"
                  :disabled="chosen.length === 1"
                  @click="remove(index)"
                />
              </div>

              <!--
                And how it sits. Three settings, each labelled: an unlabelled
                row of eight icons is a puzzle, and this one had two glyphs for
                pinning that most people read as "move to the edge".

                `TabButtons` rather than pairs of toggles, because every one of
                these is one answer out of a few — and a segmented control says
                that where two buttons that turn each other off do not.
              -->
              <div class="flex flex-wrap items-center gap-x-4 gap-y-2 ps-6">
                <div class="flex items-center gap-1.5">
                  <span class="text-p-xs text-ink-gray-5">Align</span>
                  <TabButtons
                    :model-value="column.align || ''"
                    :options="ALIGN"
                    size="sm"
                    @update:model-value="patch(index, { align: $event })"
                  />
                </div>

                <div class="flex items-center gap-1.5">
                  <span class="text-p-xs text-ink-gray-5">Pin</span>
                  <TabButtons
                    :model-value="column.pin || ''"
                    :options="PIN"
                    size="sm"
                    @update:model-value="patch(index, { pin: $event || null })"
                  />
                </div>

                <div class="flex items-center gap-1.5">
                  <span class="text-p-xs text-ink-gray-5">Width</span>
                  <!--
                    `aria-label` rather than `label`: FormControl renders a
                    label visibly above the field, which in a row this dense
                    wraps and pushes everything else out of shape.
                  -->
                  <FormControl
                    type="number"
                    size="sm"
                    :model-value="column.width"
                    :aria-label="`Width of ${labelFor(column)} in pixels`"
                    class="w-20"
                    @update:model-value="setWidth(index, $event)"
                  />
                </div>
              </div>
            </li>
          </ul>
        </FadedScroll>
      </div>

      <div v-if="unused.length" class="flex flex-col gap-2">
        <div class="flex items-baseline justify-between">
          <h3 class="text-p-sm font-medium text-ink-gray-8">Add a column</h3>
          <p class="text-p-xs text-ink-gray-5">
            {{ unused.length }} left — everything this record has, whether or not
            the app put it on the list
          </p>
        </div>
        <FormControl v-model="search" type="search" placeholder="Find a field" />
        <!-- Faded rather than clipped: a field name cut in half by a hard
             edge reads as a rendering fault, not as "there is more below". -->
        <FadedScroll class="max-h-56">
          <div class="flex flex-col gap-1 pe-1">
            <Button
              v-for="column in matching"
              :key="column.fieldname"
              variant="ghost"
              class="justify-start"
              :icon-left="column.icon"
              :label="column.label"
              @click="add(column)"
            />
            <p v-if="!matching.length" class="px-2 py-1 text-p-sm text-ink-gray-5">
              Nothing matches “{{ search }}”.
            </p>
          </div>
        </FadedScroll>
      </div>
    </div>

    <template #actions>
      <Button variant="solid" label="Done" @click="open = false" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Dialog, FormControl, Icon, TabButtons } from '@/ui'
import FadedScroll from '../../FadedScroll.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  chosen: { type: Array, required: true },
  offered: { type: Array, required: true },
  groupBy: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'update:chosen', 'update:groupBy'])

const open = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const META_FIELD = '__activity'

/**
 * Which edge the values sit against, and the header with them.
 *
 * Logical rather than physical — `start` and `end` rather than left and right —
 * because this product draws Arabic beside English in one list, and a column
 * aligned "left" in a right-to-left screen is aligned to the wrong side of the
 * words in it. The glyphs follow the reading direction for the same reason.
 *
 * Empty is the default and the first option: it means the fieldtype decides,
 * which is a number against the end and everything else at the start.
 * `spaceview.ALIGNMENTS` is the same set on the server.
 */
const ALIGN = [
  { value: '', label: 'Automatic', icon: 'lucide-wand-sparkles' },
  { value: 'start', label: 'Align to the start', icon: 'lucide-align-left' },
  { value: 'center', label: 'Align to the centre', icon: 'lucide-align-center' },
  { value: 'end', label: 'Align to the end', icon: 'lucide-align-right' },
]

/**
 * Which edge it sticks to while the table scrolls sideways.
 *
 * Nothing is pinned by default: which column you want to keep on screen depends
 * on what you are doing with the list, not on what the column is. Three
 * options rather than two toggles, because "not pinned" is an answer — a pair
 * of buttons where clicking the lit one turns it off is a control that has to
 * be discovered.
 */
const PIN = [
  { value: '', label: 'Not pinned', icon: 'lucide-minus' },
  { value: 'left', label: 'Pin to the left edge', icon: 'lucide-arrow-left-to-line' },
  { value: 'right', label: 'Pin to the right edge', icon: 'lucide-arrow-right-to-line' },
]

const dragging = ref(null)
const search = ref('')

const columnFor = (fieldname) => props.offered.find((c) => c.fieldname === fieldname)
const labelFor = (column) => columnFor(column.fieldname)?.label || column.fieldname
const iconFor = (column) => columnFor(column.fieldname)?.icon || 'lucide-circle-help'

// Not the activity column: it is not a field and has no value to group on.
const groupOptions = computed(() => [
  { value: '', label: 'Nothing' },
  ...props.offered
    .filter((c) => c.fieldname !== META_FIELD)
    .map((c) => ({ value: c.fieldname, label: c.label })),
])

const taken = computed(() => new Set(props.chosen.map((c) => c.fieldname)))
const unused = computed(() => props.offered.filter((c) => !taken.value.has(c.fieldname)))

// A doctype can have eighty fields, so the list of what is left needs a way in
// that is not scrolling.
const matching = computed(() => {
  const term = search.value.trim().toLowerCase()
  if (!term) return unused.value
  return unused.value.filter((c) => c.label.toLowerCase().includes(term))
})

const change = (next) => emit('update:chosen', next)

const patch = (index, values) =>
  change(props.chosen.map((column, at) => (at === index ? { ...column, ...values } : column)))

const add = (column) =>
  change([
    ...props.chosen,
    { fieldname: column.fieldname, width: column.width, pin: null, align: '' },
  ])

const remove = (index) => change(props.chosen.filter((_column, at) => at !== index))

const setWidth = (index, value) => {
  const width = Number(value)
  if (Number.isFinite(width) && width > 0) patch(index, { width })
}

const move = (index, by) => {
  const next = [...props.chosen]
  const to = index + by
  if (to < 0 || to >= next.length) return
  ;[next[index], next[to]] = [next[to], next[index]]
  change(next)
}

const dropOn = (index) => {
  if (dragging.value === null || dragging.value === index) return
  const next = [...props.chosen]
  const [moved] = next.splice(dragging.value, 1)
  next.splice(index, 0, moved)
  dragging.value = null
  change(next)
}
</script>
