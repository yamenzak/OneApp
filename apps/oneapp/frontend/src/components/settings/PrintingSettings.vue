<template>
  <!--
    What is printed, as against what it is printed on.

    The paper — size, font, engine, margins — is a settings group and renders
    from `SettingsFields` like every other. This is the other half: the formats
    themselves and the letter heads they sit under. Both are documents rather
    than settings, which is why they are here rather than in a form, and both
    are the workspace's own decision rather than a person's, which is why they
    are behind the same admin door.
  -->
  <SettingsHeader
    title="Print formats"
    description="What a printed document looks like, and the letter head it sits under."
    :class="PANEL_HEADER"
  />
  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" text="Loading" />

    <div v-else class="flex flex-col gap-6 py-4">
      <EmptyState
        v-if="!doctypes.length"
        icon="lucide-printer"
        title="Nothing to print yet"
        description="A format is drawn over the records an app in this workspace shows."
      />

      <div v-else class="flex flex-col gap-3">
        <div class="flex flex-wrap items-end gap-2">
          <Select
            v-model="doctype"
            class="w-56"
            label="Records"
            :options="doctypes.map((one) => ({ label: one.label, value: one.doctype }))"
          />
          <span class="flex-1" />
          <Button
            variant="solid"
            icon-left="lucide-plus"
            label="New format"
            @click="draw('')"
          />
        </div>

        <ul class="flex flex-col border-t border-outline-gray-1">
          <li
            v-for="one in formats"
            :key="one.name"
            data-slot="print-format"
            class="flex items-center gap-3 border-b border-outline-gray-1 py-2"
          >
            <span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-8">{{ one.name }}</span>
            <Badge v-if="one.default" label="Default" theme="blue" variant="subtle" />
            <Badge v-if="one.standard" label="Ships with the app" theme="gray" variant="subtle" />
            <Button
              v-if="!one.default"
              label="Make default"
              :loading="working === one.name"
              @click="makeDefault(one)"
            />
            <Button
              v-if="one.built"
              icon="lucide-pencil"
              tooltip="Open in the builder"
              @click="draw(one.name)"
            />
            <Button
              v-if="one.built && !one.standard"
              icon="lucide-trash-2"
              tooltip="Delete this format"
              :loading="working === one.name"
              @click="remove(one)"
            />
          </li>
        </ul>

        <p class="text-p-xs text-ink-gray-5">
          Standard is Frappe's own fallback: every field of the record, in the
          order the form declares them. A format written as a template rather
          than drawn still prints, and opens wherever it was written.
        </p>
      </div>

      <div class="flex flex-col gap-3 border-t border-outline-gray-1 pt-5">
        <div class="flex items-center gap-2">
          <span class="text-p-sm font-medium text-ink-gray-8">Letter heads</span>
          <span class="flex-1" />
          <Button icon-left="lucide-plus" label="New letter head" @click="head('')" />
        </div>

        <ul v-if="letterHeads.length" class="flex flex-col border-t border-outline-gray-1">
          <li
            v-for="one in letterHeads"
            :key="one.name"
            data-slot="letter-head"
            class="flex items-center gap-3 border-b border-outline-gray-1 py-2"
          >
            <span class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-8">{{ one.name }}</span>
            <Badge v-if="one.default" label="Default" theme="blue" variant="subtle" />
            <Button icon="lucide-pencil" tooltip="Edit this letter head" @click="head(one.name)" />
            <Button
              icon="lucide-trash-2"
              tooltip="Delete this letter head"
              :loading="working === one.name"
              @click="removeHead(one)"
            />
          </li>
        </ul>

        <p v-else class="text-p-xs text-ink-gray-5">
          None yet. A letter head is the band above and below every printed
          page — a logo, an address, a footer — and one format can use another's.
        </p>
      </div>

      <ErrorMessage v-if="error" :message="error" />
    </div>
  </SettingsBody>

  <FormatBuilder
    v-if="doctype"
    v-model="building"
    :doctype="doctype"
    :name="editing"
    :letter-heads="letterHeads"
    @saved="load"
  />

  <LetterHeadDialog v-model="heading" :name="editingHead" @saved="load" />
</template>

<script setup>
import { ref, watch } from 'vue'
import {
  Badge,
  Button,
  ErrorMessage,
  LoadingText,
  Select,
  SettingsBody,
  SettingsHeader,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import FormatBuilder from './printing/FormatBuilder.vue'
import LetterHeadDialog from './printing/LetterHeadDialog.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'

const doctypes = ref([])
const doctype = ref('')
const formats = ref([])
const letterHeads = ref([])

const loading = ref(false)
const working = ref('')
const error = ref('')

const building = ref(false)
const editing = ref('')
const heading = ref(false)
const editingHead = ref('')

const load = async () => {
  loading.value = !doctypes.value.length
  error.value = ''
  try {
    const found = await workspace.printFormats(doctype.value)
    doctypes.value = found.doctypes || []
    doctype.value = found.doctype || ''
    formats.value = found.formats || []
    letterHeads.value = found.letter_heads || []
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    loading.value = false
  }
}

// The formats follow the doctype, and only after the first load has settled —
// which is what sets it in the first place.
watch(doctype, (wanted, was) => {
  if (was && wanted !== was) load()
})

const draw = (name) => {
  editing.value = name
  building.value = true
}

const head = (name) => {
  editingHead.value = name
  heading.value = true
}

const makeDefault = async (one) => {
  working.value = one.name
  error.value = ''
  try {
    formats.value = await workspace.setDefaultPrintFormat(doctype.value, one.name)
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    working.value = ''
  }
}

const remove = async (one) => {
  working.value = one.name
  error.value = ''
  try {
    const found = await workspace.deletePrintFormat(one.name)
    formats.value = found.formats || []
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    working.value = ''
  }
}

const removeHead = async (one) => {
  working.value = one.name
  error.value = ''
  try {
    letterHeads.value = await workspace.deleteLetterHead(one.name)
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    working.value = ''
  }
}

load()
</script>
