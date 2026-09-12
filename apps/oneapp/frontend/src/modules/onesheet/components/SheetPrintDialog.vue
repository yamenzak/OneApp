<template>
  <!--
    Print a sheet.

    Google's shape, because it is the one everybody who has printed a
    spreadsheet already knows: what goes on the page is a set of decisions you
    make first and then look at. Which tabs, what paper, which way round, how
    much of it fits, whether the lines show, whether the top row comes back.

    The preview is an iframe and has to be — the printed page carries its own
    `@page` rule and its own stylesheet, and letting either into this document
    would restyle the app around it. It is also the thing that prints, so what
    the person is looking at is literally what comes out.
  -->
  <Dialog v-model="showing" size="5xl">
    <template #title>
      <EditorTitle brand="onesheet" :name="__('Print')" />
    </template>

    <template #default>
      <div class="flex flex-col gap-3 md:flex-row">
        <div class="flex w-full shrink-0 flex-col gap-3 md:w-64">
          <FormControl
            v-model="options.which"
            type="select"
            :label="__('Print')"
            :options="whichOptions"
          />
          <div class="grid grid-cols-2 gap-3">
            <FormControl
              v-model="setup.page_size"
              type="select"
              :label="__('Paper size')"
              :options="sizeOptions"
            />
            <FormControl
              v-model="setup.orientation"
              type="select"
              :label="__('Orientation')"
              :options="orientationOptions"
            />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <FormControl
              v-model="marginChoice"
              type="select"
              :label="__('Margins')"
              :options="marginOptions"
            />
            <FormControl
              v-if="marginChoice === 'custom'"
              v-model.number="setup.margin"
              type="number"
              :label="__('Millimetres')"
              :min="MARGIN_MIN"
              :max="MARGIN_MAX"
            />
            <FormControl
              v-model="options.scale"
              type="select"
              :label="__('Scale')"
              :options="scaleOptions"
            />
          </div>
          <FormControl
            v-model="setup.letter_head"
            type="select"
            :label="__('Letter head')"
            :options="letterheadOptions"
          />
          <FormControl
            v-model="options.gridlines"
            type="checkbox"
            :label="__('Show gridlines')"
          />
          <FormControl
            v-model="options.repeat_head"
            type="checkbox"
            :label="__('Repeat the first row on every page')"
          />
          <FormControl
            v-if="options.which === 'all'"
            v-model="options.tab_titles"
            type="checkbox"
            :label="__('Name each tab above it')"
          />
        </div>

        <div class="min-w-0 flex-1">
          <ErrorMessage v-if="error" :message="error" class="mb-2" />
          <!--
            The sandbox grants two things and refuses the one that matters. No
            `allow-scripts`, because a letter head is workspace-authored HTML.
            `allow-same-origin`, because without it a `srcdoc` frame gets an
            opaque origin and `contentWindow` is unreachable — safe precisely
            because scripts are still refused. `allow-modals`, because the
            browser's print dialog is a modal.
          -->
          <div class="h-overlay overflow-hidden rounded-6 border border-outline-gray-2 bg-white">
            <LoadingText v-if="loading" class="p-6" :text="__('Rendering')" />
            <iframe
              v-show="!loading"
              ref="frame"
              :title="__('Print preview')"
              sandbox="allow-same-origin allow-modals"
              class="h-full w-full"
            />
          </div>
        </div>
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        icon-left="lucide-printer"
        :label="__('Print')"
        :disabled="!ready"
        @click="send"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'

import { Button, Dialog, ErrorMessage, FormControl, LoadingText } from '@/ui'
import EditorTitle from '@/shared/components/brand/EditorTitle.vue'
import {
  MARGINS, MARGIN_MAX, MARGIN_MIN, ORIENTATIONS, PAGE_SIZES, marginMm,
} from '@/shared/lib/paper/setup'
import { workspace } from '@/shared/lib/workspace'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  name: { type: String, required: true },
  tab: { type: String, default: '' },
})

const showing = defineModel({ type: Boolean, default: false })

const loading = ref(false)
const error = ref('')
const ready = ref(false)
const frame = ref(null)
const letterheads = ref([])

// The same defaults `sheets/printing.options_of` fills in, so the dialog and
// the server agree before anybody has touched a control.
const options = reactive({
  which: 'current',
  scale: 100,
  gridlines: true,
  repeat_head: false,
  tab_titles: true,
})

const setup = reactive({
  page_size: 'A4',
  // Landscape, because a sheet is wider than it is tall far more often than a
  // document is — the one default here that is not the server's.
  orientation: 'landscape',
  margin: 'normal',
  letter_head: '',
})

const whichOptions = computed(() => [
  { label: __('This tab'), value: 'current' },
  { label: __('Every tab'), value: 'all' },
])

const sizeOptions = computed(() =>
  Object.entries(PAGE_SIZES).map(([value, one]) => ({ label: one.label, value })),
)

const orientationOptions = computed(() =>
  Object.entries(ORIENTATIONS).map(([value, one]) => ({ label: one.label, value })),
)

const marginOptions = computed(() => [
  ...Object.entries(MARGINS).map(([value, one]) => ({
    label: __('{0} ({1} mm)', [one.label, one.mm]),
    value,
  })),
  { label: __('Custom'), value: 'custom' },
])

/** The preset, or the word "custom" — `DocSettings.vue` says the rest. */
const marginChoice = computed({
  get: () => (typeof setup.margin === 'number' ? 'custom' : setup.margin || 'normal'),
  set: (value) => {
    setup.margin = value === 'custom' ? marginMm(setup.margin) : value
  },
})

const scaleOptions = computed(() =>
  [100, 90, 75, 50].map((one) => ({ label: `${one}%`, value: one })),
)

const letterheadOptions = computed(() => [
  { label: __('None'), value: '' },
  ...letterheads.value.map((one) => ({
    label: one.default ? __('{0} (default)', [one.name]) : one.name,
    value: one.name,
  })),
])

async function render() {
  if (!showing.value || !props.name) return
  loading.value = true
  error.value = ''
  try {
    const found = await workspace.sheetPrintable(
      props.name,
      { ...options, scale: Number(options.scale), tab: props.tab },
      setup,
    )
    if (frame.value) frame.value.srcdoc = found?.html || ''
    ready.value = !!found?.html
  } catch (raised) {
    error.value = errorText(raised)
    ready.value = false
  } finally {
    loading.value = false
  }
}

/** The frame's own print, so what is printed is the page rather than the app. */
function send() {
  const view = frame.value?.contentWindow
  if (!view) return
  view.focus()
  view.print()
}

watch(showing, async (open) => {
  if (!open) return
  if (!letterheads.value.length) {
    try {
      letterheads.value = (await workspace.letterHeads()) || []
    } catch {
      letterheads.value = []
    }
  }
  await render()
})

watch([options, setup], () => showing.value && render(), { deep: true })
</script>
