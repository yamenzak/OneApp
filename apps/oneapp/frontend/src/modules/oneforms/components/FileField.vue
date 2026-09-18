<template>
  <!--
    An `Attach` field on a page a stranger opened.

    `docs/ONEFORMS.md` §14, stage 11. An application form that cannot take a CV
    is not an application form, and `Attach` was never in `NEVER` — so somebody
    could drag one onto a form and a stranger was handed a text box.

    **The file goes inline, and that is Frappe's design rather than a shortcut.**
    `accept` reads a value of the form `filename,data:…;base64,…`, writes the
    `File` itself and puts its url on the document. So there is no upload
    endpoint here, no guest upload permission, and nothing new to secure — the
    one thing a public page must not be given is a second way to write.

    The cost is the cap. Base64 is a third larger than the file, and it rides in
    one POST, so `max_attachment_size` is checked before the read rather than
    after: reading a 200MB file into a string to then refuse it is how a tab
    stops responding.
  -->
  <div class="flex flex-col gap-1" :data-slot="`field-${field.fieldname}`">
    <span class="text-p-sm text-ink-secondary">
      {{ field.label }}<span v-if="field.reqd" class="text-ink-red-3"> *</span>
    </span>

    <label
      class="flex cursor-pointer items-center gap-2 rounded-6 border border-dashed border-outline-gray-2 px-3 py-2"
    >
      <Icon name="lucide-paperclip" class="size-4 shrink-0 text-ink-muted" :aria-hidden="true" />
      <span class="min-w-0 flex-1 truncate text-sm" :class="chosen ? HAS : NONE">
        {{ chosen || __('Choose a file') }}
      </span>
      <!-- eslint-disable-next-line vue/no-restricted-html-elements -- @/ui has no file control: FormControl's types are text-like, and FileUploader posts to Frappe's upload endpoint, which is the second write path a public page must not have -->
      <input
        type="file"
        class="sr-only"
        :accept="field.fieldtype === 'Attach Image' ? 'image/*' : undefined"
        :required="Boolean(field.reqd) && !chosen"
        :aria-label="field.label"
        @change="take"
      />
    </label>

    <p v-if="field.description" class="text-p-xs text-ink-muted">{{ field.description }}</p>
    <ErrorMessage v-if="refused" :message="refused" />
  </div>
</template>

<script setup>
import { ref } from 'vue'

import { ErrorMessage, Icon } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

//: Hoisted, because a class compared inside a `:class` is a name Tailwind's
//: JIT never sees — `tests/token_audit.py` reads for exactly this.
const HAS = 'text-ink-primary'
const NONE = 'text-ink-muted'

//: What the site allows when the form names no cap of its own. Frappe's own
//: default, and the page says the number rather than discovering it in a 413.
const DEFAULT_MB = 10

const props = defineProps({
  field: { type: Object, required: true },
  /** `Web Form.max_attachment_size`, in MB. 0 means the site's own. */
  most: { type: Number, default: 0 },
})

const value = defineModel({ type: String, default: '' })

const chosen = ref('')
const refused = ref('')

/**
 * The file, as the string `accept` expects.
 *
 * Checked before the read: base64 is a third larger than the file and it rides
 * in one POST, so reading a 200MB file into a string in order to then refuse it
 * is how a tab stops responding.
 */
function take(event) {
  const file = event.target.files?.[0]
  refused.value = ''
  if (!file) {
    chosen.value = ''
    value.value = ''
    return
  }

  const cap = (props.most || DEFAULT_MB) * 1024 * 1024
  if (file.size > cap) {
    refused.value = __('That file is larger than {0}MB.', [props.most || DEFAULT_MB])
    event.target.value = ''
    chosen.value = ''
    value.value = ''
    return
  }

  const reader = new FileReader()
  reader.onload = () => {
    // `filename,dataurl` — the shape `accept` splits on its first comma.
    value.value = `${file.name},${reader.result}`
    chosen.value = file.name
  }
  reader.onerror = () => {
    refused.value = __('That file could not be read.')
  }
  reader.readAsDataURL(file)
}
</script>
