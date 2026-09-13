<template>
  <!--
    One field, rendered by whatever frappe-ui component its type maps to.

    The map is generated from Frappe's own fieldtype list
    (`lib/screen/fields.js`), so a type nobody placed fails the build rather
    than quietly becoming a text box over a Currency column.
  -->
  <!--
    Read-only, and read-only is not disabled — §B5. The value as text, in the
    field's own place. Not for the four that have a real read-only form of
    their own: a document, a code file, a gallery and an upload are all things
    you still *look at*, and a line of text is not a smaller version of them.
  -->
  <ReadValue
    v-if="asText"
    :field="field"
    :model-value="modelValue"
    :doc="doc"
    :space-code="spaceCode"
    :screen="screen"
    :states="states"
    :ai="ai"
    :note="note"
  />

  <!-- A Link is a record, so it gets the record picker rather than a text box
       over a foreign key. -->
  <LinkPicker
    v-else-if="component === 'Combobox'"
    :model-value="modelValue"
    :fieldname="field.fieldname"
    :space-code="spaceCode"
    :screen="screen"
    :label="field.label"
    :description="note"
    :placeholder="field.placeholder"
    :disabled="off"
    :required="!!field.reqd"
    :field="field"
    :is-new="isNew"
    :target="target"
    allow-create
    allow-open
    @update:model-value="emit('update:modelValue', $event)"
  >
    <!--
      `v-if` on the slot, not inside it: frappe-ui renders its label element
      whenever the slot exists, whatever is in it, so a labelless control in a
      child grid still drew a row of bare type icons above the inputs.
    -->
    <template #label v-if="field.label">
      <FieldLabel
        :label="field.label"
        :icon="field.icon"
        :required="!!field.reqd"
        :ai="ai"
      />
    </template>
  </LinkPicker>

  <Switch
    v-else-if="component === 'Switch'"
    :model-value="!!modelValue"
    :label="field.label"
    :description="note"
    :disabled="off"
    @update:model-value="emit('update:modelValue', $event ? 1 : 0)"
  >
    <template #label v-if="field.label">
      <FieldLabel
        :label="field.label"
        :icon="field.icon"
        :required="!!field.reqd"
        :ai="ai"
      />
    </template>
  </Switch>

  <Rating
    v-else-if="component === 'Rating'"
    :model-value="Number(modelValue) || 0"
    :label="field.label"
    :disabled="off"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #label v-if="field.label">
      <FieldLabel
        :label="field.label"
        :icon="field.icon"
        :required="!!field.reqd"
        :ai="ai"
      />
    </template>
  </Rating>

  <Password
    v-else-if="component === 'Password'"
    :model-value="modelValue"
    :label="field.label"
    :disabled="off"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #label v-if="field.label">
      <FieldLabel
        :label="field.label"
        :icon="field.icon"
        :required="!!field.reqd"
        :ai="ai"
      />
    </template>
  </Password>

  <!-- frappe-ui's Duration has no day unit at all, so Frappe's `hide_days` is
       already how it behaves. -->
  <Duration
    v-else-if="component === 'Duration'"
    :model-value="Number(modelValue) || 0"
    :format="field.hide_seconds ? `h'h' m'm'` : 'short'"
    :label="field.label"
    :disabled="off"
    @update:model-value="emit('update:modelValue', $event)"
  />

  <!--
    A Table MultiSelect is a child table whose rows hold one Link each: the
    control shows the ids, `tagged` puts the rows back together.
  -->
  <MultiSelect
    v-else-if="component === 'MultiSelect'"
    :model-value="tags"
    :options="options"
    :label="field.label"
    :disabled="off"
    @update:model-value="emit('update:modelValue', tagged($event))"
  >
    <template #label v-if="field.label">
      <FieldLabel
        :label="field.label"
        :icon="field.icon"
        :required="!!field.reqd"
        :ai="ai"
      />
    </template>
  </MultiSelect>

  <!-- Attach and Attach Image. The picker hands back the File document, and
       what belongs in the field is its URL. -->
  <div v-else-if="component === 'FileUploader'" class="flex flex-col gap-1">
    <div class="flex items-center gap-1.5">
      <!-- These four draw their own label because the control below has none
           to give: FormLabel takes the text as a prop and has no slot. -->
      <Icon v-if="field.icon" :name="field.icon" class="size-3.5 shrink-0 text-ink-gray-4"
            :aria-hidden="true" />
      <FormLabel :label="field.label" :required="!!field.reqd" />
    </div>
    <div class="flex items-center gap-2">
      <Button
        :label="modelValue ? __('Replace') : __('Attach')"
        :disabled="off"
        @click="picking = true"
      />
      <span v-if="modelValue" class="truncate text-sm text-ink-secondary">
        {{ modelValue }}
      </span>
    </div>
    <!--
      One picker, not an uploader. `attached-to` is what makes the file *belong*
      to the record rather than only be named by it: without it the file lands
      loose in the Drive, missing from the record's own Files tab, and is
      orphaned the moment somebody clears the field.
    -->
    <FilePicker
      v-model="picking"
      :kind="field.fieldtype === 'Attach Image' ? 'Image' : ''"
      :attached-to="attachTarget"
      @picked="(file) => emit('update:modelValue', file.file_url)"
    />
  </div>

  <!-- A child table: rows of another doctype belonging to this record. The
       control writes the whole list, which is how Frappe stores one. -->
  <ChildTable
    v-else-if="field.fieldtype === 'Table' && field.child"
    :rows="Array.isArray(modelValue) ? modelValue : []"
    :field="field"
    :space-code="spaceCode"
    :screen="screen"
    :disabled="off"
    :doctype="doctype"
    :docname="docname"
    @update:rows="emit('update:modelValue', $event)"
    @reload="emit('reload')"
  />

  <!--
    A gallery of the record's own attachments. The field holds no value at all —
    Frappe lists it in `no_value_fields` — so the control writes through the
    File endpoints and never emits an update.
  -->
  <AttachmentGallery
    v-else-if="component === 'AttachmentGallery'"
    :field="field"
    :space-code="spaceCode"
    :screen="screen"
    :doctype="doctype"
    :docname="docname"
    :disabled="off"
    :note="note"
  />

  <!--
    Prose. One component for both of Frappe's prose fieldtypes; `format` is the
    only difference between them. A pasted image becomes an attachment on the
    record like any other.
  -->
  <div v-else-if="component === 'Editor'" class="flex flex-col gap-1">
    <div class="flex items-center gap-1.5">
      <Icon v-if="field.icon" :name="field.icon" class="size-3.5 shrink-0 text-ink-gray-4"
            :aria-hidden="true" />
      <FormLabel :label="field.label" :required="!!field.reqd" />
      <!-- Where a model wrote this. Beside the label like every other field's
           is, and said here rather than through `FieldLabel` because this row
           is built by hand: `FormLabel` renders its own `<label>` and the
           editor below is a `contenteditable` rather than an input, so the
           slot the other controls use does not exist here. -->
      <AiMark v-if="ai" :mark="ai" />
      <!--
        The room a document gets, for the field a doctype's author meant for
        long-form content. It writes back to the field: nothing here becomes a
        file, because this text is part of the record and part of what its
        print format renders.

        The label does not name the field, deliberately. The editor beside it
        is `aria-label`led with the field's own label, and a button called
        "Open Description in the editor" makes `getByLabel('Description')` — and
        anything else asking the accessible tree for that field — ambiguous.
        The tooltip is where the field's name belongs.
      -->
      <OpenIn
        brand="onedoc"
        slot-name="open-in-doc"
        :tooltip="__('Open {0} in OneDoc', [field.label])"
        @open="expanded = true"
      />
    </div>
    <Panel pad="bar" :class="off ? 'opacity-60' : ''">
      <!--
        `extensions` is the whole capability of the editor. RichTextKit is
        frappe-ui's article-grade bundle; the lighter CommentKit is the wrong
        choice for a field a doctype's author meant for long-form content.

        `Editor` is *renderless* — it owns the lifecycle, the v-model and the
        upload and draws nothing. Without this slot the field is an empty box,
        which a build and 944 unit tests had nothing to say about.
      -->
      <Editor
        :model-value="modelValue || ''"
        :extensions="EXTENSIONS"
        :format="editorFormat(field)"
        :editable="!off"
        :placeholder="field.placeholder"
        :upload-function="uploadInto"
        @update:model-value="emit('update:modelValue', $event)"
      >
        <template #default="{ editor }">
          <EditorFixedMenu v-if="!off" :editor="editor" :items="articleToolbar" class="mb-2" />
          <!-- The accessible name. EditorContent forwards attributes onto the
               element ProseMirror mounts on, which is what a person types
               into. -->
          <!-- `dir="auto"` here too: an Arabic body lays itself out from its
               own first word, beside an English one, with nothing declared. -->
          <EditorContent :editor="editor" :aria-label="field.label" dir="auto" />
        </template>
      </Editor>
    </Panel>
    <p v-if="note" class="text-p-xs text-ink-muted">{{ note }}</p>

    <LongTextDialog
      v-model="expanded"
      :value="modelValue || ''"
      :label="field.label"
      :format="editorFormat(field)"
      :disabled="off"
      :upload-function="uploadInto"
      @apply="emit('update:modelValue', $event)"
    />
  </div>

  <!--
    Source. Code, JSON, and Frappe's HTML Editor, which is markup somebody edits
    as markup rather than prose. CodePreview rather than a disabled CodeEditor
    where it cannot be written: a greyed-out editor still carries an editor's
    affordances.
  -->
  <div v-else-if="component === 'CodeEditor'" class="flex flex-col gap-1">
    <!-- CodePreview takes only what it reads, so the label and the note are
         drawn here rather than passed to it. -->
    <template v-if="off">
      <div class="flex items-center gap-1.5">
      <Icon v-if="field.icon" :name="field.icon" class="size-3.5 shrink-0 text-ink-gray-4"
            :aria-hidden="true" />
      <FormLabel :label="field.label" :required="!!field.reqd" />
    </div>
      <CodePreview :model-value="modelValue || ''" :language="language" />
      <p v-if="note" class="text-p-xs text-ink-muted">{{ note }}</p>
    </template>
    <template v-else>
      <!--
        The way into OneCode, on the same terms the long-text field opens
        OneDoc: the value stays the field's and nothing becomes a file. A
        400-line print format in a box eight lines tall is the case this is
        for, and it is the common case rather than the rare one.

        The label does not name the field, deliberately — the editor beside it
        is `aria-label`led with it, and a second control carrying the same name
        makes `getByLabel('Terms')` ambiguous. The tooltip is where the field's
        name belongs.
      -->
      <div class="flex items-center justify-between gap-2">
        <div class="flex items-center gap-1.5">
          <Icon v-if="field.icon" :name="field.icon" class="size-3.5 shrink-0 text-ink-gray-4"
                :aria-hidden="true" />
          <FormLabel :label="field.label" :required="!!field.reqd" />
        </div>
        <OpenIn
          brand="onecode"
          slot-name="open-in-code"
          :tooltip="__('Open {0} in OneCode', [field.label])"
          @open="coding = true"
        />
      </div>
      <CodeEditor
        :model-value="modelValue || ''"
        :language="language"
        :description="note"
        :placeholder="field.placeholder"
        :aria-label="field.label"
        @update:model-value="emit('update:modelValue', $event)"
      />
      <CodeDialog
        v-model="coding"
        :value="modelValue || ''"
        :label="field.label"
        :language="language"
        @apply="emit('update:modelValue', $event)"
      />
    </template>
  </div>

  <!--
    No frappe-ui counterpart: colour, signature, geolocation, barcode, icon.
    Shown, never offered — a text box writing a hex string into a Signature
    field is worse than a value someone can read.
  -->
  <div v-else-if="!controlType" class="flex flex-col gap-1">
    <div class="flex items-center gap-1.5">
      <Icon v-if="field.icon" :name="field.icon" class="size-3.5 shrink-0 text-ink-gray-4"
            :aria-hidden="true" />
      <FormLabel :label="field.label" :required="!!field.reqd" />
    </div>
    <div class="flex items-center gap-2 rounded-4 bg-surface-gray-1 px-3 py-2">
      <!-- A colour is a colour: the list cell has always drawn the swatch. -->
      <span
        v-if="field.fieldtype === 'Color' && modelValue"
        class="size-4 shrink-0 rounded-full border border-outline-gray-2"
        :style="{ backgroundColor: modelValue }"
      />
      <!-- Frappe stores a signature as a data-URI PNG, so the honest rendering
           is the picture. -->
      <img
        v-else-if="field.fieldtype === 'Signature' && modelValue"
        :src="modelValue"
        :alt="__('Signature')"
        class="h-12 max-w-full object-contain"
      />
      <!-- Geolocation is a GeoJSON blob with no honest small rendering. -->
      <span
        v-if="field.fieldtype === 'Geolocation'"
        class="truncate text-sm text-ink-secondary"
      >
        {{ modelValue ? __('Map') : '—' }}
      </span>
      <!-- Barcode stores the value; the bars are a rendering of it. The value
           is the useful half, in the typeface that separates an O from a 0. -->
      <span
        v-else-if="field.fieldtype === 'Barcode'"
        class="truncate font-mono text-sm text-ink-secondary"
      >
        {{ modelValue || '—' }}
      </span>
      <span
        v-else-if="field.fieldtype !== 'Signature'"
        class="truncate text-sm text-ink-secondary"
      >
        {{ modelValue || '—' }}
      </span>
    </div>
    <!--
      No apology. A value that cannot be edited here needs a reason only when
      there is somewhere else to edit it, and frappe-ui has no colour picker,
      signature pad or map.
    -->
    <p v-if="note" class="text-p-xs text-ink-muted">{{ note }}</p>
  </div>

  <!--
    The doctype's own bounds reach the control as attributes rather than as
    validation: they make a field pleasant to type into, and the server enforces
    all three on save regardless.
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
    :disabled="off"
    :rows="controlType === 'textarea' ? 3 : undefined"
    @update:model-value="emit('update:modelValue', $event)"
  >
    <template #label v-if="field.label">
      <FieldLabel
        :label="field.label"
        :icon="field.icon"
        :required="!!field.reqd"
        :ai="ai"
      />
    </template>
  </FormControl>
</template>

<script setup>
import { computed, ref } from 'vue'
import { STATE } from '@/shared/lib/fields/state'
import ReadValue from '@/modules/onespace/components/screen/fields/ReadValue.vue'
import {
  Icon,
  FormControl,
  FormLabel,
  Switch,
  Rating,
  Password,
  Duration,
  MultiSelect,
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
import FieldLabel from '@/modules/onespace/components/screen/fields/FieldLabel.vue'
import AiMark from '@/modules/onespace/components/AiMark.vue'
import FilePicker from '@/modules/onestorage/components/FilePicker.vue'
import LinkPicker from '@/modules/onespace/components/screen/fields/LinkPicker.vue'
import AttachmentGallery from '@/modules/onespace/components/screen/record/AttachmentGallery.vue'
import ChildTable from '@/modules/onespace/components/screen/record/ChildTable.vue'
import LongTextDialog from '@/modules/onedoc/components/LongTextDialog.vue'
import CodeDialog from '@/modules/onecode/components/CodeDialog.vue'
import OpenIn from '@/shared/components/brand/OpenIn.vue'
import { controlComponent, editorFormat, formControlType, valueIcon } from '@/modules/onespace/lib/screen/fields'
import { __ } from '@/shared/lib/runtime/translate'
import Panel from '@/shared/components/Panel.vue'

// Built once for the module: the kit is a static extension list, and a form
// with six rich-text fields should not assemble six identical ones.
const EXTENSIONS = [RichTextKit]

// Whether the long field is open in the document surface. One flag, because a
// control draws one field.
const expanded = ref(false)
const coding = ref(false)

/**
 * Where an image dropped into the editor goes: onto the record, as a File
 * attached to it, rather than into a second invisible store.
 *
 * Undefined on a new record — there is nothing to attach to until it has an id
 * — and the editor then offers no upload.
 */
/** Where a file attached through this field belongs. `undefined` until the
 *  record has an id; the picker then files it in the Drive and the field still
 *  gets its URL. */
const attachTarget = computed(() => {
  if (!props.doctype || !props.docname) return null
  return {
    doctype: props.doctype,
    docname: props.docname,
    fieldname: props.field.fieldname,
  }
})

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
      // means private.
      private: true,
    })
})

const props = defineProps({
  field: { type: Object, required: true },
  modelValue: { type: [String, Number, Boolean, Array, Object], default: null },
  /**
   * What this field *is* on this record — `lib/fields/state.js`, §B5. One of
   * `writable`, `readonly`, `hidden`; every surface resolves it the same way
   * and a caller that used to pass `disabled` for "the record is locked" now
   * passes this.
   */
  state: { type: String, default: STATE.WRITABLE },
  /**
   * Momentarily unavailable, which is what `disabled` actually means: a save
   * in flight, an upload running. Not "you may not edit this" — that is
   * `state`, and conflating the two is what made a locked record look broken.
   */
  disabled: { type: Boolean, default: false },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** A record being made rather than edited. Only the Link picker reads it,
      for `remember_last_selected_value`. */
  isNew: { type: Boolean, default: false },
  /** The doctype's Document States, so an option's glyph matches its badge. */
  states: { type: Array, default: () => [] },
  /** Where a model wrote this value: `{ feature, model, by, when }` off the
   *  record's `_ai`, or nothing. Drawn beside the label — see `AiMark.vue`. */
  ai: { type: Object, default: null },
  /** The record this field belongs to, where there is one. Only the rich-text
   *  editor reads them, to attach a pasted image. */
  doctype: { type: String, default: '' },
  docname: { type: String, default: '' },
  /**
   * The record as it stands, for the fields whose behaviour depends on another
   * of its values. Only a Dynamic Link reads it today, and it is the object
   * `FormSections` is already editing.
   */
  doc: { type: Object, default: () => ({}) },
})
// `reload` is for the controls that write through the server rather than
// through the record — filling a child table from a sheet is the one today.
const emit = defineEmits(['update:modelValue', 'reload'])

// Whether the attach picker is open. One per control, so two Attach fields on
// one form do not share a dialog.
const picking = ref(false)

const component = computed(() => controlComponent(props.field))

//: Not writable, for whatever reason. Every control below takes this where it
//: used to take `disabled`, because to a control the two are the same refusal
//: — the difference is only in what is drawn *instead*, which is the branch
//: at the top of the template.
const off = computed(() => props.disabled || props.state !== STATE.WRITABLE)

/**
 * Whether this one reads as text when it is locked.
 *
 * Four do not. A prose document, a code file, a gallery and an upload have a
 * read-only form of their own that is still the thing itself, and the
 * template already draws each of them — `CodePreview` rather than a greyed
 * editor is the oldest of these decisions. `cell` of `hidden` is the server
 * saying this value has no one-line reading at all, which a Password is.
 */
const NOT_TEXT = ['Editor', 'CodeEditor', 'AttachmentGallery', 'FileUploader']
const asText = computed(() =>
  props.state === STATE.READONLY
  && !props.disabled
  && !NOT_TEXT.includes(component.value)
  && props.field?.cell !== 'hidden')

// A Dynamic Link points wherever another field says. Empty until that field is
// filled in: a picker with no target has nothing to search.
const target = computed(() => {
  const field = props.field
  if (field.fieldtype !== 'Dynamic Link' || !field.depends_on_field) return ''
  return props.doc?.[field.depends_on_field] || ''
})
const controlType = computed(() => formControlType(props.field))

/**
 * Which language CodeMirror highlights. Frappe puts it in `options` on a Code
 * field and leaves it blank more often than not; JSON and HTML Editor answer
 * for themselves. An unknown key is plain text rather than an error.
 */
const LANGUAGE_BY_TYPE = { JSON: 'json', 'HTML Editor': 'html' }

const language = computed(() => {
  const field = props.field
  return LANGUAGE_BY_TYPE[field.fieldtype] || (field.options || '').trim().toLowerCase() || 'plain'
})

// A Select's own list. `sort_options` is the doctype asking for it
// alphabetically rather than in the order somebody typed it.
const selectOptions = computed(() => {
  const options = (props.field.options || '').split('\n').filter(Boolean)
  const ordered = props.field.sort_options
    ? [...options].sort((a, b) => a.localeCompare(b))
    : options

  // The same glyph the badge draws, so a value looks the same being chosen as
  // once chosen. Every option or none: a list where half the rows carry a glyph
  // reads as broken rather than as varied.
  return ordered.map((value) => ({
    label: value,
    value,
    icon: valueIcon(value, props.states),
  }))
})

/**
 * `min`, `max` and `maxlength`, where the doctype set them. An object because
 * each is absent far more often than present; 0 is a real bound and travels,
 * only null means unset.
 */
// Which control types hold words somebody types in a language. An array, and
// it is worth saying why: `('text', 'textarea', …)` in JavaScript is the comma
// operator, so that expression is the *last* string and nothing else — and
// `.includes` on a string then answers about substrings.
const WORDS = ['text', 'textarea', 'email', 'password', 'url']

const bounds = computed(() => {
  const field = props.field
  const found = {}
  /**
   * `dir="auto"`, on everything a person types words into.
   *
   * Direction belongs to the *value*, not to the schema: a company writes to a
   * municipality in Arabic and a consultant in English from the same field on
   * the same day. Never `rtl` — a field forced one way mangles what ends up in
   * it just as thoroughly as the other.
   */
  if (WORDS.includes(controlType.value)) found.dir = 'auto'
  if (controlType.value === 'number') {
    if (field.non_negative) found.min = 0
    if (field.min_value !== null && field.min_value !== undefined) found.min = field.min_value
    if (field.max_value !== null && field.max_value !== undefined) found.max = field.max_value
  } else if (field.length) {
    found.maxlength = field.length
  }
  // Frappe's own ceiling on a text control, in pixels. A style rather than a
  // prop because no frappe-ui control takes a height.
  if (field.max_height && controlType.value === 'textarea') {
    found.style = { maxHeight: `${parseInt(field.max_height, 10) || 0}px`, overflowY: 'auto' }
  }
  return found
})

/**
 * The line under the control, as one sentence rather than three stacked notes:
 * the doctype's `description`, where a `fetch_from` value comes from, and that
 * the value may not repeat. `show_description_on_click` moves the description
 * behind the label's info icon instead.
 */
const note = computed(() => {
  const field = props.field
  const parts = []

  if (field.description && !field.show_description_on_click) parts.push(field.description)

  if (field.fetch_from) {
    const from = String(field.fetch_from).split('.')[0].replace(/_/g, ' ')
    parts.push(
      field.fetch_if_empty
        ? __('From {0} if left blank', [from])
        : __('From {0}', [from]),
    )
  }

  if (field.unique) parts.push(__('Must be unique'))

  return parts.join(' · ') || undefined
})


// A Select and a Table MultiSelect choose from the field's own `options`; a
// Link does not — its list is records. A Table MultiSelect takes plain values
// rather than option objects, having no icon slot.
const options = computed(() => selectOptions.value.map((one) => one.value))

/**
 * The one field a Table MultiSelect's rows actually carry. The fieldname comes
 * from the child's own shape rather than being guessed at.
 */
const tagField = computed(() => {
  const fields = props.field.child?.fields || []
  const link = fields.find((one) => one.fieldtype === 'Link')
  return link?.fieldname || ''
})

const tags = computed(() => {
  const rows = Array.isArray(props.modelValue) ? props.modelValue : []
  const key = tagField.value
  // A list of plain strings is what this looked like before the rows arrived.
  return rows.map((row) => (typeof row === 'string' ? row : row?.[key])).filter(Boolean)
})

// Rows back out, keeping each one's identity: without `name` Frappe deletes and
// recreates every row on every save.
const tagged = (values) => {
  const key = tagField.value
  const rows = Array.isArray(props.modelValue) ? props.modelValue : []
  const known = new Map(
    rows.filter((row) => row && typeof row === 'object').map((row) => [row[key], row]),
  )
  return (values || []).map((value) => known.get(value) || { [key]: value })
}
</script>
