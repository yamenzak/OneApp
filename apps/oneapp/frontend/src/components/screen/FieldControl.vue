<template>
  <!--
    One field, rendered by whatever frappe-ui component its type maps to.

    The map is generated from Frappe's own fieldtype list (src/lib/fields.js), so
    a type nobody placed fails the build rather than quietly becoming a text box
    over a Currency column.
  -->
  <!--
    A Link is a record, so it gets the record picker rather than a text box
    over a foreign key — searchable, showing a face and a name, and able to
    create one where the doctype and this person's permissions allow it.
  -->
  <LinkPicker
    v-if="component === 'Combobox'"
    :model-value="modelValue"
    :fieldname="field.fieldname"
    :space-code="spaceCode"
    :screen="screen"
    :label="field.label"
    :description="note"
    :placeholder="field.placeholder"
    :disabled="disabled"
    :required="!!field.reqd"
    :field="field"
    :is-new="isNew"
    :target="target"
    allow-create
    @update:model-value="emit('update:modelValue', $event)"
  />

  <Switch
    v-else-if="component === 'Switch'"
    :model-value="!!modelValue"
    :label="field.label"
    :description="note"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event ? 1 : 0)"
  />

  <Rating
    v-else-if="component === 'Rating'"
    :model-value="Number(modelValue) || 0"
    :label="field.label"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <Password
    v-else-if="component === 'Password'"
    :model-value="modelValue"
    :label="field.label"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <!--
    frappe-ui's Duration has no day unit at all — hours accumulate — so Frappe's
    `hide_days` is already how it behaves and only `hide_seconds` has anything
    to change here.
  -->
  <Duration
    v-else-if="component === 'Duration'"
    :model-value="Number(modelValue) || 0"
    :format="field.hide_seconds ? `h'h' m'm'` : 'short'"
    :label="field.label"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <!--
    A Table MultiSelect is a child table whose rows hold one Link each, so what
    a person edits is a list of ids and what Frappe stores is a list of rows.
    The control shows the ids; `tagged` puts the rows back together.

    It was mapped to this component and unreachable for as long as it has
    existed: `_offerable` excluded child tables outright and `_placed`
    intersects the manifest with what is offered, so a screen naming one got
    nothing at all.
  -->
  <MultiSelect
    v-else-if="component === 'MultiSelect'"
    :model-value="tags"
    :options="options"
    :label="field.label"
    :disabled="disabled"
    @update:model-value="emit('update:modelValue', tagged($event))"
  />

  <!--
    Attach and Attach Image. FileUploader takes a callback rather than a
    v-model — it hands back the File document, and what belongs in the field is
    its URL.
  -->
  <div v-else-if="component === 'FileUploader'" class="flex flex-col gap-1">
    <FormLabel :label="field.label" />
    <FileUploader
      :file-types="field.fieldtype === 'Attach Image' ? 'image/*' : undefined"
      @success="(file) => emit('update:modelValue', file.file_url)"
    >
      <template #default="{ openFileSelector }">
        <div class="flex items-center gap-2">
          <Button
            :label="modelValue ? 'Replace' : 'Upload'"
            :disabled="disabled"
            @click="openFileSelector"
          />
          <span v-if="modelValue" class="truncate text-p-sm text-ink-gray-6">
            {{ modelValue }}
          </span>
        </div>
      </template>
    </FileUploader>
  </div>

  <!--
    A child table: rows of another doctype belonging to this record. The
    control writes the whole list, which is how Frappe stores one.
  -->
  <ChildTable
    v-else-if="field.fieldtype === 'Table' && field.child"
    :rows="Array.isArray(modelValue) ? modelValue : []"
    :field="field"
    :space-code="spaceCode"
    :screen="screen"
    :disabled="disabled"
    @update:rows="emit('update:modelValue', $event)"
  />

  <!--
    A gallery of the record's own attachments. The field holds no value at all
    — Frappe lists this in `no_value_fields` — so the control writes through
    the File endpoints rather than through the record, and never emits an
    update.
  -->
  <AttachmentGallery
    v-else-if="component === 'AttachmentGallery'"
    :field="field"
    :space-code="spaceCode"
    :screen="screen"
    :doctype="doctype"
    :docname="docname"
    :disabled="disabled"
    :note="note"
  />

  <!--
    Prose. One component for both of Frappe's prose fieldtypes — a Text Editor
    stores HTML and a Markdown Editor stores markdown, and `format` is the only
    difference between them. An image pasted in becomes an attachment on the
    record like any other, through the same File endpoints the sidebar lists.
  -->
  <div v-else-if="component === 'Editor'" class="flex flex-col gap-1">
    <FormLabel :label="field.label" />
    <div
      class="rounded-6 border border-outline-gray-2 bg-surface-base px-3 py-2"
      :class="disabled ? 'opacity-60' : ''"
    >
      <!--
        `extensions` is required and is the whole capability of the editor —
        which extensions load decides what the toolbar can do and what the
        document may contain. RichTextKit is frappe-ui's article-grade bundle:
        tables, task lists, headings, alignment. A lighter one exists
        (CommentKit) and is the wrong choice here, because a Text Editor field
        is where a doctype's author put the long-form content.

        `Editor` is *renderless*: it owns the lifecycle, the v-model, the upload
        and the placeholder, and renders no UI at all. Without this slot the
        field is an empty box — which is exactly what it was, and what a build
        and 944 unit tests had nothing to say about. The consumer owns the
        chrome, which is why the menu is a deliberate choice here rather than
        something that arrived by default.
      -->
      <Editor
        :model-value="modelValue || ''"
        :extensions="EXTENSIONS"
        :format="editorFormat(field)"
        :editable="!disabled"
        :placeholder="field.placeholder"
        :upload-function="uploadInto"
        @update:model-value="emit('update:modelValue', $event)"
      >
        <template #default="{ editor }">
          <EditorFixedMenu v-if="!disabled" :editor="editor" :items="articleToolbar" class="mb-2" />
          <!--
            The accessible name. EditorContent forwards attributes onto the
            element ProseMirror mounts on, which is the thing a person actually
            types into — so this is what gives the field a name for a screen
            reader, and the only way to reach it by its label.
          -->
          <EditorContent :editor="editor" :aria-label="field.label" />
        </template>
      </Editor>
    </div>
    <p v-if="note" class="text-p-xs text-ink-gray-5">{{ note }}</p>
  </div>

  <!--
    Source. Code, JSON, and Frappe's HTML Editor, which is markup somebody
    edits as markup rather than prose — getting that and Text Editor the right
    way round is the whole point of separating them.

    CodePreview rather than a disabled CodeEditor when it cannot be written:
    frappe-ui ships the reader as its own component, and a greyed-out editor
    still carries an editor's affordances.
  -->
  <div v-else-if="component === 'CodeEditor'" class="flex flex-col gap-1">
    <!-- CodePreview is the reader and takes only what it reads, so the label
         and the note are drawn here rather than passed to it. -->
    <template v-if="disabled">
      <FormLabel :label="field.label" />
      <CodePreview :model-value="modelValue || ''" :language="language" />
      <p v-if="note" class="text-p-xs text-ink-gray-5">{{ note }}</p>
    </template>
    <CodeEditor
      v-else
      :model-value="modelValue || ''"
      :language="language"
      :label="field.label"
      :description="note"
      :placeholder="field.placeholder"
      :required="!!field.reqd"
      @update:model-value="emit('update:modelValue', $event)"
    />
  </div>

  <!--
    No frappe-ui counterpart: colour, signature, geolocation, barcode, icon.
    Shown, never offered — a text box that writes a hex string into a Signature
    field is worse than a value someone can read.
  -->
  <div v-else-if="!controlType" class="flex flex-col gap-1">
    <FormLabel :label="field.label" />
    <div class="flex items-center gap-2 rounded-4 bg-surface-gray-1 px-3 py-2">
      <!-- A colour is a colour. The list cell has always drawn the swatch;
           there is no reason the record should show the hex and not it. -->
      <span
        v-if="field.fieldtype === 'Color' && modelValue"
        class="size-4 shrink-0 rounded-full border border-outline-gray-2"
        :style="{ backgroundColor: modelValue }"
      />
      <!-- Frappe stores a signature as a data-URI PNG, so the honest rendering
           is the picture. Reading a wall of base64 tells nobody whether the
           thing was signed. -->
      <img
        v-else-if="field.fieldtype === 'Signature' && modelValue"
        :src="modelValue"
        alt="Signature"
        class="h-12 max-w-full object-contain"
      />
      <!-- Geolocation is a GeoJSON blob with no honest small rendering, and
           printing the JSON is worse than saying what it is. -->
      <span
        v-if="field.fieldtype === 'Geolocation'"
        class="truncate text-p-sm text-ink-gray-7"
      >
        {{ modelValue ? 'Map' : '—' }}
      </span>
      <!-- Barcode stores the value; the bars are a rendering of it, and one
           nobody can scan off a screen usefully yet. The value is the useful
           half, in the typeface that makes an O and a 0 different. -->
      <span
        v-else-if="field.fieldtype === 'Barcode'"
        class="truncate font-mono text-p-sm text-ink-gray-7"
      >
        {{ modelValue || '—' }}
      </span>
      <span
        v-else-if="field.fieldtype !== 'Signature'"
        class="truncate text-p-sm text-ink-gray-7"
      >
        {{ modelValue || '—' }}
      </span>
    </div>
    <!--
      No apology. A value that cannot be edited here needs a reason only when
      there is somewhere else to edit it, and for these there is not: frappe-ui
      has no colour picker, signature pad or map, so the field is read-only
      until it does. `description` still shows if the doctype wrote one.
    -->
    <p v-if="note" class="text-p-xs text-ink-gray-5">{{ note }}</p>
  </div>

  <!--
    The doctype's own bounds reach the control as attributes rather than as
    validation: `min`, `max` and `maxlength` are what make a field pleasant to
    type into, and the server enforces all three on save regardless. A browser
    makes typing pleasant; a database decides what is true.
  -->
  <FormControl
    v-else
    v-bind="bounds"
    :model-value="modelValue"
    :type="controlType"
    :label="field.label"
    :description="note"
    :placeholder="field.placeholder"
    :options="controlType === 'select' ? selectOptions : undefined"
    :required="!!field.reqd"
    :disabled="disabled"
    :rows="controlType === 'textarea' ? 3 : undefined"
    @update:model-value="emit('update:modelValue', $event)"
  />
</template>

<script setup>
import { computed } from 'vue'
import {
  FormControl,
  FormLabel,
  Switch,
  Rating,
  Password,
  Duration,
  MultiSelect,
  FileUploader,
  Button,
  Editor,
  EditorContent,
  EditorFixedMenu,
  articleToolbar,
  CodeEditor,
  CodePreview,
  RichTextKit,
  upload,
} from '@/ui'
import LinkPicker from './LinkPicker.vue'
import AttachmentGallery from './AttachmentGallery.vue'
import ChildTable from './ChildTable.vue'
import { controlComponent, editorFormat, formControlType } from '../../lib/fields'

// Built once for the module rather than per field: the kit is a static
// extension list, and a form with six rich-text fields should not assemble six
// identical ones.
const EXTENSIONS = [RichTextKit]

/**
 * Where an image dropped into the editor goes.
 *
 * Onto the record, as a File attached to it — the same rows the sidebar lists
 * and an Attach field points at, so a picture pasted into a description is an
 * attachment like any other rather than a second, invisible store.
 *
 * Undefined on a new record, which is the honest answer: there is nothing to
 * attach to until it has an id, and Frappe's own form says the same thing.
 * The editor then simply offers no upload.
 */
const uploadInto = computed(() => {
  const doctype = props.doctype
  const docname = props.docname
  if (!doctype || !docname) return undefined
  return (file) =>
    upload(file, {
      doctype,
      docname,
      fieldname: props.field.fieldname,
      // Attachments follow the record's own visibility, which on a tenant site
      // means private: a customer's file should not become a public URL
      // because it was pasted rather than uploaded.
      private: true,
    })
})

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: null },
  disabled: { type: Boolean, default: false },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** A record being made rather than edited. Only the Link picker reads it,
      for `remember_last_selected_value`. */
  isNew: { type: Boolean, default: false },
  /**
   * The record this field belongs to, where there is one. Only the rich-text
   * editor reads them, to attach a pasted image to it — so both are absent on
   * a create form, and the editor correctly offers no upload there.
   */
  doctype: { type: String, default: '' },
  docname: { type: String, default: '' },
  /**
   * The record as it stands, for the fields whose behaviour depends on another
   * of its values. Only a Dynamic Link reads it today — its target doctype is
   * in the field `depends_on_field` names — and it is the same object
   * `FormSections` is already editing, so nothing is copied to provide it.
   */
  doc: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue'])

const component = computed(() => controlComponent(props.field))

// A Dynamic Link points wherever another field on this record says. Empty
// until that field is filled in, which is exactly right: a picker with no
// target has nothing to search, and the server refuses an unnamed one.
const target = computed(() => {
  const field = props.field
  if (field.fieldtype !== 'Dynamic Link' || !field.depends_on_field) return ''
  return props.doc?.[field.depends_on_field] || ''
})
const controlType = computed(() => formControlType(props.field))

/**
 * Which language CodeMirror highlights.
 *
 * Frappe puts it in `options` on a Code field — the same slot a Link uses for
 * its doctype and a Select for its choices — and leaves it blank more often
 * than not. JSON and HTML Editor answer for themselves, since the fieldtype
 * *is* the language.
 *
 * An unknown key is plain text rather than an error: frappe-ui's `loadLanguage`
 * returns null for one, and a code box with no highlighting is still a code box.
 */
const LANGUAGE_BY_TYPE = { JSON: 'json', 'HTML Editor': 'html' }

const language = computed(() => {
  const field = props.field
  return LANGUAGE_BY_TYPE[field.fieldtype] || (field.options || '').trim().toLowerCase() || 'plain'
})

// A Select's own list. `sort_options` is the doctype asking for it
// alphabetically rather than in the order somebody typed it in, which is what
// the desk does and the only thing that flag means.
const selectOptions = computed(() => {
  const options = (props.field.options || '').split('\n').filter(Boolean)
  return props.field.sort_options ? [...options].sort((a, b) => a.localeCompare(b)) : options
})

/**
 * `min`, `max` and `maxlength`, where the doctype set them.
 *
 * Bound as an object because each is absent far more often than it is present,
 * and `:max="undefined"` on every number field is three attributes of noise for
 * the one doctype that uses them. `min_value`/`max_value` of 0 are real bounds
 * and travel as 0 — only null means unset.
 */
const bounds = computed(() => {
  const field = props.field
  const found = {}
  if (controlType.value === 'number') {
    if (field.non_negative) found.min = 0
    if (field.min_value !== null && field.min_value !== undefined) found.min = field.min_value
    if (field.max_value !== null && field.max_value !== undefined) found.max = field.max_value
  } else if (field.length) {
    found.maxlength = field.length
  }
  // Frappe's own ceiling on a text control, in pixels. Bound as a style rather
  // than a prop because no frappe-ui control takes a height: the textarea
  // still grows to it and then scrolls, which is what the flag asks for.
  if (field.max_height && controlType.value === 'textarea') {
    found.style = { maxHeight: `${parseInt(field.max_height, 10) || 0}px`, overflowY: 'auto' }
  }
  return found
})

/**
 * The line under the control.
 *
 * Three things can want to be there, and a field that says all three should
 * read as one sentence rather than three stacked notes:
 *
 *  - the doctype's own `description`
 *  - where a `fetch_from` value comes from, because a box that fills itself
 *    with no explanation is a box people retype. Frappe writes the source as
 *    `customer.customer_name`; the field it comes from is the half worth
 *    saying, and `fetch_if_empty` is the difference between "filled in once"
 *    and "replaced on every save"
 *  - that the value may not repeat, which is otherwise something you find out
 *    from a database error
 *
 * `show_description_on_click` moves the description behind the label's info
 * icon instead, which is the doctype saying it is long.
 */
const note = computed(() => {
  const field = props.field
  const parts = []

  if (field.description && !field.show_description_on_click) parts.push(field.description)

  if (field.fetch_from) {
    const from = String(field.fetch_from).split('.')[0].replace(/_/g, ' ')
    parts.push(field.fetch_if_empty ? `From ${from} if left blank` : `From ${from}`)
  }

  if (field.unique) parts.push('Must be unique')

  return parts.join(' · ') || undefined
})


// A Select and a Table MultiSelect both choose from the field's own `options`
// list. A Link does not — its list is records, which the picker fetches from
// the server behind the screen's own bounds.
const options = computed(() => selectOptions.value)

/**
 * The one field a Table MultiSelect's rows actually carry.
 *
 * Frappe stores these as a child table whose child doctype has a single Link,
 * so the value on the record is `[{link_field: 'ACME'}, …]` and what a person
 * means is `['ACME', …]`. The fieldname comes from the child's own shape
 * rather than being guessed at, so a doctype that named its column something
 * other than the usual still works.
 */
const tagField = computed(() => {
  const fields = props.field.child?.fields || []
  const link = fields.find((one) => one.fieldtype === 'Link')
  return link?.fieldname || ''
})

const tags = computed(() => {
  const rows = Array.isArray(props.modelValue) ? props.modelValue : []
  const key = tagField.value
  // A list of plain strings is what this looked like before the rows arrived,
  // and a draft that has not been saved yet may still be one.
  return rows.map((row) => (typeof row === 'string' ? row : row?.[key])).filter(Boolean)
})

// Rows back out, keeping each one's identity where it had one: without `name`
// Frappe deletes and recreates every row on every save.
const tagged = (values) => {
  const key = tagField.value
  const rows = Array.isArray(props.modelValue) ? props.modelValue : []
  const known = new Map(
    rows.filter((row) => row && typeof row === 'object').map((row) => [row[key], row]),
  )
  return (values || []).map((value) => known.get(value) || { [key]: value })
}
</script>
