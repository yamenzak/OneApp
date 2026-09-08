<template>
  <!--
    How the page is set: how wide, in what face, how far apart the lines — and
    whether there are pages at all.

    A reader's choice about *this* document, stored on it rather than in a
    workspace setting — a contract wants a narrow measure and a rate schedule
    wants the full width, and the same person wants both on the same afternoon.

    Pageless is the default and stays the default. A document written to be
    read on a screen has no pages, and the moment it has to become paper is the
    moment somebody comes here and says so.
  -->
  <Dialog v-model="open" :title="__('Page setup')">
    <template #default>
      <div class="flex flex-col gap-4">
        <FormControl
          v-model="draft.width"
          type="select"
          :label="__('Width')"
          :options="options(WIDTHS)"
          :disabled="draft.paged"
          :description="draft.paged ? __('A paged document is as wide as its page.') : ''"
        />
        <FormControl
          v-model="draft.font"
          type="select"
          :label="__('Typeface')"
          :options="options(FONTS)"
        />
        <FormControl
          v-model="draft.spacing"
          type="select"
          :label="__('Line spacing')"
          :options="options(SPACINGS)"
        />

        <div class="border-t border-outline-gray-1 pt-4">
          <FormControl
            v-model="draft.paged"
            type="checkbox"
            :label="__('Break into pages')"
            :description="__('Off, the document is one continuous page that never ends.')"
          />
        </div>

        <div v-if="draft.paged" class="flex flex-col gap-4">
          <div class="grid grid-cols-2 gap-3">
            <FormControl
              v-model="draft.page_size"
              type="select"
              :label="__('Page size')"
              :options="options(PAGE_SIZES)"
            />
            <FormControl
              v-model="draft.orientation"
              type="select"
              :label="__('Orientation')"
              :options="options(ORIENTATIONS)"
            />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <FormControl
              v-model="marginChoice"
              type="select"
              :label="__('Margins')"
              :options="marginOptions"
            />
            <!-- A number, because somebody printing onto pre-printed
                 stationery has a measurement rather than a preference. -->
            <FormControl
              v-if="marginChoice === 'custom'"
              v-model.number="draft.margin"
              type="number"
              :label="__('Millimetres')"
              :min="MARGIN_MIN"
              :max="MARGIN_MAX"
            />
          </div>
          <!-- The workspace's letter heads, the same list the record printer
               offers. "None" first, because a workspace that has one still
               prints the odd thing that should not carry it. -->
          <FormControl
            v-model="draft.letter_head"
            type="select"
            :label="__('Letter head')"
            :options="letterheadOptions"
            :description="__('Shown at the top of every printed page.')"
          />
        </div>
      </div>
    </template>
    <template #actions>
      <Button variant="solid" :label="__('Apply')" class="w-full" @click="apply" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { Button, Dialog, FormControl } from '@/ui'
import { FONTS, SPACINGS, WIDTHS } from '@/modules/onedoc/components/toolbar'
import {
  MARGINS, MARGIN_MAX, MARGIN_MIN, ORIENTATIONS, PAGE_SIZES, marginMm,
} from '@/shared/lib/paper/setup'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const open = defineModel({ type: Boolean, default: false })
const settings = defineModel('settings', { type: Object, default: () => ({}) })

const emit = defineEmits(['change'])

const draft = ref({ ...settings.value })
const letterheads = ref([])

const options = (from) =>
  Object.entries(from).map(([value, one]) => ({ label: one.label, value }))

const marginOptions = computed(() => [
  ...Object.entries(MARGINS).map(([value, one]) => ({
    label: __('{0} ({1} mm)', [one.label, one.mm]),
    value,
  })),
  { label: __('Custom'), value: 'custom' },
])

/*
 * The preset, or the word "custom".
 *
 * `draft.margin` is what gets stored and is either a preset's name or a number
 * of millimetres — the same two shapes `paper.setup_of` reads. This is the
 * select over it: choosing a preset stores the name, choosing Custom turns
 * whatever is there now into the number it already meant, so the box opens on
 * the margin the document has rather than on nothing.
 */
const marginChoice = computed({
  get: () => (typeof draft.value.margin === 'number' ? 'custom' : draft.value.margin || 'normal'),
  set: (value) => {
    draft.value.margin = value === 'custom' ? marginMm(draft.value.margin) : value
  },
})

const letterheadOptions = computed(() => [
  { label: __('None'), value: '' },
  ...letterheads.value.map((one) => ({
    label: one.default ? __('{0} (default)', [one.name]) : one.name,
    value: one.name,
  })),
])

// Opened again after a change elsewhere — the lock, say — so the draft starts
// from what the document actually says rather than from the last look at it.
watch(open, (showing) => {
  if (!showing) return
  draft.value = { ...settings.value }
  if (letterheads.value.length) return
  workspace.letterHeads()
    .then((found) => { letterheads.value = found || [] })
    .catch(() => { letterheads.value = [] })
})

function apply() {
  settings.value = { ...settings.value, ...draft.value }
  open.value = false
  emit('change')
}
</script>
