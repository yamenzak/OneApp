<template>
  <!--
    Print this record.

    Frappe renders it and Frappe makes the PDF — this is a picker and a
    preview. The three questions a person actually has are which format, which
    letter head and which language; everything else about printing is a
    workspace-wide decision and lives in settings, once, for everybody.

    The preview is an iframe and has to be. A print format's CSS is written to
    win against a blank page — `body { font-size: 8pt }`, table resets, page
    rules — so dropping the returned HTML into this document would restyle the
    app around it. An iframe is a second document, which is exactly what a
    printed page is.
  -->
  <Dialog v-model="showing" title="Print" size="4xl">
    <div class="flex flex-col gap-3">
      <div class="flex flex-wrap items-end gap-2">
        <Select
          v-model="format"
          class="w-48"
          label="Format"
          :options="formatOptions"
        />
        <Select
          v-model="letterhead"
          class="w-48"
          label="Letter head"
          :options="letterheadOptions"
        />
        <span class="flex-1" />
        <Button
          icon-left="lucide-download"
          label="Download PDF"
          :loading="downloading"
          @click="download"
        />
        <Button
          variant="solid"
          icon-left="lucide-printer"
          label="Print"
          :disabled="!html"
          @click="send"
        />
      </div>

      <ErrorMessage v-if="error" :message="error" />

      <!--
        A fixed height rather than one that follows the content: the frame is a
        page and a page has a shape.

        The sandbox grants two things and refuses the one that matters. No
        `allow-scripts`, because a print format may carry a Jinja-rendered
        script and a preview is not a place to run one. `allow-same-origin`,
        because without it a `srcdoc` frame gets an opaque origin and
        `frame.contentWindow` is unreachable — which is what Print needs, and
        it is safe precisely because scripts are still refused. `allow-modals`,
        because the browser's print dialog is a modal and a sandboxed frame may
        not open one without it.
      -->
      <div class="h-[70vh] overflow-hidden rounded-6 border border-outline-gray-2 bg-white">
        <LoadingText v-if="loading" class="p-6" text="Rendering" />
        <iframe
          v-show="!loading"
          ref="frame"
          title="Print preview"
          sandbox="allow-same-origin allow-modals"
          class="h-full w-full"
        />
      </div>
    </div>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dialog, ErrorMessage, LoadingText, Select } from '@/ui'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'
import { notifyError } from '../../lib/notify'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, required: true },
})

const showing = defineModel({ type: Boolean, default: false })

const loading = ref(false)
const downloading = ref(false)
const error = ref('')
const html = ref('')
const frame = ref(null)

const formats = ref([])
const letterheads = ref([])
const format = ref('')
const letterhead = ref('')

const formatOptions = computed(() =>
  formats.value.map((one) => ({
    label: one.default ? `${one.name} (default)` : one.name,
    value: one.name,
  })),
)

// "None" is a real answer and has to be first: a workspace with a letter head
// still prints the odd thing that should not carry one.
const letterheadOptions = computed(() => [
  { label: 'None', value: '' },
  ...letterheads.value.map((one) => ({
    label: one.default ? `${one.name} (default)` : one.name,
    value: one.name,
  })),
])

const look = async () => {
  const found = await workspace.printOptions(props.spaceCode, props.screen, props.name)
  formats.value = found?.formats || []
  letterheads.value = found?.letter_heads || []
  format.value = (formats.value.find((one) => one.default) || formats.value[0])?.name || ''
  // The workspace's own answer to "with a letter head", which is a setting
  // rather than a habit — so an unticked one starts with none.
  if (found?.settings?.with_letterhead) {
    letterhead.value = (letterheads.value.find((one) => one.default) || {}).name || ''
  }
}

const render = async () => {
  if (!showing.value || !props.name) return
  loading.value = true
  error.value = ''
  try {
    const found = await workspace.printPreview(props.spaceCode, props.screen, props.name, {
      format: format.value,
      letterhead: letterhead.value,
    })
    html.value = found?.html || ''
    // The stylesheet and the markup written together into the frame's own
    // document. `srcdoc` rather than `document.write`: it survives the frame
    // being re-created by a re-render, and it is what `sandbox` applies to.
    if (frame.value) {
      frame.value.srcdoc = `<style>${found?.style || ''}</style>${html.value}`
    }
  } catch (raised) {
    error.value = errorText(raised)
    html.value = ''
  } finally {
    loading.value = false
  }
}

const download = async () => {
  downloading.value = true
  try {
    // A window rather than fetch-and-blob: the PDF comes back as a real
    // download response with a filename on it, and asking the browser to
    // rebuild a file it was handed is asking it to lose the name.
    window.open(
      workspace.printPdfUrl(props.spaceCode, props.screen, props.name, {
        format: format.value,
        letterhead: letterhead.value,
      }),
      '_blank',
      'noopener',
    )
  } catch (raised) {
    notifyError(raised.message || String(raised))
  } finally {
    downloading.value = false
  }
}

/** The frame's own print, so what is printed is the page rather than the app. */
const send = () => {
  const view = frame.value?.contentWindow
  if (!view) return
  view.focus()
  view.print()
}

watch(showing, async (open) => {
  if (!open) return
  error.value = ''
  if (!formats.value.length) await look()
  await render()
})

watch([format, letterhead], () => showing.value && render())
</script>
