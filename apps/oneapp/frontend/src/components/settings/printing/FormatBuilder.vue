<template>
  <!--
    Drawing a print format.

    Three columns, which is the shape every builder of this kind settles on:
    what you can add, what is on the page, and what the selected thing is. The
    middle one is the document — a header band, the body's sections, a footer
    band — laid out the way it will print rather than as a tree, because the
    question being answered all day is "where on the page is this".

    What it produces is Frappe's own `format_data`. Not a shape of ours that we
    then render: the server hands the layout to `PrintFormatGenerator`, the same
    renderer the desk uses, so what comes out of this prints identically
    everywhere the format is reached from.
  -->
  <Dialog v-model="showing" :title="title" size="6xl">
    <div class="flex flex-col gap-3">
      <div class="flex flex-wrap items-end gap-2">
        <FormControl v-model="label" class="w-56" label="Name" />
        <Select
          v-model="letterhead"
          class="w-44"
          label="Letter head"
          :options="letterheadOptions"
        />
        <span class="flex-1" />
        <Button
          :variant="preview ? 'solid' : 'subtle'"
          icon-left="lucide-eye"
          :label="preview ? 'Back to the canvas' : 'Preview'"
          :loading="rendering"
          @click="look"
        />
        <Button
          variant="solid"
          icon-left="lucide-check"
          label="Save"
          :loading="saving"
          :disabled="!label.trim()"
          @click="save"
        />
      </div>

      <ErrorMessage v-if="error" :message="error" />

      <!--
        The preview is an iframe and has to be: a print format's CSS is written
        to win against a blank page, so dropping its HTML into this document
        would restyle the app around it.
      -->
      <div
        v-if="preview"
        class="h-[62vh] overflow-hidden rounded-6 border border-outline-gray-2 bg-white"
      >
        <LoadingText v-if="rendering" class="p-6" text="Rendering" />
        <iframe
          v-show="!rendering"
          ref="frame"
          title="Print preview"
          sandbox=""
          class="h-full w-full"
        />
      </div>

      <div v-else class="flex h-[62vh] gap-3">
        <!-- What can go on the page. Dragged onto a column, or clicked to land
             in the last one that was touched. -->
        <div class="w-52 shrink-0 overflow-y-auto rounded-6 border border-outline-gray-2">
          <div v-for="group in groups" :key="group.key" class="flex flex-col">
            <span
              class="sticky top-0 bg-surface-gray-1 px-3 py-1.5 text-p-xs font-medium text-ink-gray-6"
            >
              {{ group.label }}
            </span>
            <!-- The drag lives on a wrapper rather than on the Button: a
                 Button takes no `draggable`, and giving it one would be a prop
                 the library does not have. -->
            <div
              v-for="entry in group.entries"
              :key="entry.key"
              draggable="true"
              @dragstart="carry($event, { add: entry })"
            >
              <Button
                variant="ghost"
                class="w-full !justify-start px-3"
                :icon-left="group.icon"
                :label="entry.label"
                @click="add(entry)"
              />
            </div>
          </div>
        </div>

        <!-- The page. -->
        <div class="flex-1 overflow-y-auto rounded-6 border border-outline-gray-2 bg-surface-gray-1 p-4">
          <div class="mx-auto flex max-w-3xl flex-col gap-3">
            <BuilderZone
              zone="header"
              label="Header"
              hint="Repeats at the top of every page."
              :section="layout.header"
              :selected="selected"
              @drop-on="place"
              @pick="pick"
              @carry="carry"
              @column="columnChange('header', 0, $event)"
              @justify="justify(layout.header, $event)"
            />

            <div class="flex flex-col gap-3 rounded-6 bg-surface-elevation-1 p-4 shadow-sm">
              <BuilderZone
                v-for="(section, index) in layout.sections"
                :key="index"
                zone="sections"
                :index="index"
                :label="`Section ${index + 1}`"
                :section="section"
                :selected="selected"
                :removable="layout.sections.length > 1"
                @drop-on="place"
                @pick="pick"
                @carry="carry"
                @column="columnChange('sections', index, $event)"
                @justify="justify(section, $event)"
                @remove="layout.sections.splice(index, 1)"
              />
              <Button
                icon-left="lucide-plus"
                label="Add a section"
                @click="layout.sections.push(emptySection())"
              />
            </div>

            <BuilderZone
              zone="footer"
              label="Footer"
              hint="Repeats at the bottom of every page."
              :section="layout.footer"
              :selected="selected"
              @drop-on="place"
              @pick="pick"
              @carry="carry"
              @column="columnChange('footer', 0, $event)"
              @justify="justify(layout.footer, $event)"
            />
          </div>
        </div>

        <div class="w-64 shrink-0 rounded-6 border border-outline-gray-2">
          <BuilderInspector
            :element="chosen"
            :setup="setup"
            :palette="palette"
            @set="setOn"
            @page="setPage"
            @remove="drop"
          />
        </div>
      </div>
    </div>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  LoadingText,
  Select,
} from '@/ui'
import BuilderZone from './BuilderZone.vue'
import BuilderInspector from './BuilderInspector.vue'
import {
  address,
  adopt,
  columnsOf,
  dropped,
  emptyLayout,
  emptySection,
  parse,
  stripped,
} from './layout'
import { workspace } from '../../../lib/workspace'
import { errorText } from '../../../lib/errors'

const props = defineProps({
  doctype: { type: String, required: true },
  // The format being edited, or '' for one that does not exist yet.
  name: { type: String, default: '' },
  letterHeads: { type: Array, default: () => [] },
})

const emit = defineEmits(['saved'])
const showing = defineModel({ type: Boolean, default: false })

const DEFAULT_SETUP = {
  margin_top: 15,
  margin_bottom: 15,
  margin_left: 15,
  margin_right: 15,
  font_size: 14,
  page_number: 'Hide',
  align_labels_right: false,
  show_label_colon: false,
}

const label = ref('')
const layout = reactive(emptyLayout())
const setup = reactive({ ...DEFAULT_SETUP })
const palette = ref({ fields: [], tables: [], elements: [] })

// Where the selection is, rather than which object is selected: an element
// moved between columns keeps its identity but changes its address, and the
// inspector has to follow the thing rather than the place.
const selected = ref('')

const preview = ref(false)
const rendering = ref(false)
const saving = ref(false)
const error = ref('')
const frame = ref(null)
const letterhead = ref('')

const title = computed(() => (props.name ? `Format: ${props.name}` : 'New print format'))

const letterheadOptions = computed(() => [
  { label: 'The default', value: '' },
  ...props.letterHeads.map((one) => ({ label: one.name, value: one.name })),
])

const groups = computed(() => [
  {
    key: 'fields',
    label: 'Fields',
    icon: 'lucide-type',
    entries: (palette.value.fields || []).map((one) => ({
      ...one,
      kind: 'field',
      key: `f:${one.fieldname}`,
    })),
  },
  {
    key: 'tables',
    label: 'Tables',
    icon: 'lucide-table',
    entries: (palette.value.tables || []).map((one) => ({
      ...one,
      kind: 'table',
      key: `t:${one.fieldname}`,
    })),
  },
  {
    key: 'elements',
    label: 'Elements',
    icon: 'lucide-shapes',
    entries: (palette.value.elements || []).map((one) => ({
      ...one,
      kind: 'element',
      key: `e:${one.fieldtype}`,
    })),
  },
])

/** The selected element itself, looked up from its address. */
const chosen = computed(() => {
  const at = parse(selected.value)
  if (!at) return null
  const columns = columnsOf(layout, at.zone, at.section)
  return columns?.[at.column]?.fields?.[at.index] || null
})

const load = async () => {
  error.value = ''
  palette.value = await workspace.printPalette(props.doctype)

  if (!props.name) {
    label.value = ''
    replace(emptyLayout(), { ...DEFAULT_SETUP })
    return
  }

  const found = await workspace.printFormat(props.name)
  label.value = found.name
  replace(adopt(found.layout), { ...DEFAULT_SETUP, ...found.setup })
}

const replace = (wanted, page) => {
  layout.sections = wanted.sections
  layout.header = wanted.header
  layout.footer = wanted.footer
  Object.assign(setup, page)
  selected.value = ''
  preview.value = false
}

watch(
  () => [showing.value, props.doctype, props.name],
  async ([open]) => {
    if (!open) return
    try {
      await load()
    } catch (raised) {
      error.value = errorText(raised)
    }
  },
  { immediate: true },
)

// --- moving things around ---------------------------------------------------

/** What a drag carries: a palette entry to add, or an address to move from. */
const carry = (event, payload) => {
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', JSON.stringify(payload))
}

/**
 * A drop on a column.
 *
 * Both cases end the same way — an element is spliced into a column at an
 * index — but a move has to come out of where it was first, and out of the
 * *same* list before the index it is going to is read, or dragging a thing
 * two places to its right lands it one place short.
 */
const place = ({ zone, section, column, index, raw }) => {
  const payload = parse(raw)
  if (!payload) return

  const columns = columnsOf(layout, zone, section)
  const target = columns[column]
  if (!target) return

  if (payload.add) {
    target.fields.splice(index, 0, dropped(payload.add))
    selected.value = address(zone, section, column, index)
    return
  }

  const from = payload.from
  if (!from) return
  const source = columnsOf(layout, from.zone, from.section)?.[from.column]
  if (!source) return

  const [moved] = source.fields.splice(from.index, 1)
  if (!moved) return

  const at = source === target && from.index < index ? index - 1 : index
  target.fields.splice(at, 0, moved)
  selected.value = address(zone, section, column, at)
}

/** Clicking a palette entry: onto the end of whichever column was last used. */
const add = (entry) => {
  const at = parse(selected.value) || { zone: 'sections', section: 0, column: 0 }
  const columns = columnsOf(layout, at.zone, at.section)
  const column = columns?.[at.column] || layout.sections[0].columns[0]
  column.fields.push(dropped(entry))
  selected.value = address(at.zone, at.section ?? 0, at.column ?? 0, column.fields.length - 1)
}

const pick = (at) => {
  selected.value = at
}

const drop = () => {
  const at = parse(selected.value)
  if (!at) return
  columnsOf(layout, at.zone, at.section)?.[at.column]?.fields?.splice(at.index, 1)
  selected.value = ''
}

const setOn = (key, value) => {
  if (chosen.value) chosen.value[key] = value
}

const setPage = (key, value) => {
  setup[key] = value
}

/** How a band distributes what is left over across its columns. */
const justify = (section, value) => {
  if (value) section.justify = value
  else delete section.justify
}

/** A zone's columns changed — one added, one removed, one made wider. */
const columnChange = (zone, section, columns) => {
  const held = columnsOf(layout, zone, section)
  held.splice(0, held.length, ...columns)
  selected.value = ''
}

// --- what it looks like -----------------------------------------------------

const look = async () => {
  if (preview.value) {
    preview.value = false
    return
  }
  preview.value = true
  rendering.value = true
  error.value = ''
  try {
    const found = await workspace.printFormatPreview(
      props.doctype,
      stripped(layout),
      { ...setup },
      { letterhead: letterhead.value },
    )
    if (found.empty) {
      error.value = 'There is no record of this kind yet to draw the preview over.'
      preview.value = false
      return
    }
    await draw(found.html)
  } catch (raised) {
    error.value = errorText(raised)
    preview.value = false
  } finally {
    rendering.value = false
  }
}

const draw = async (html) => {
  // The frame only exists once the preview pane is rendered.
  await new Promise((done) => setTimeout(done, 0))
  if (frame.value) frame.value.srcdoc = html
}

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    const found = await workspace.savePrintFormat(
      props.doctype,
      label.value.trim(),
      stripped(layout),
      { ...setup },
      props.name,
    )
    emit('saved', found)
    showing.value = false
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    saving.value = false
  }
}
</script>
