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
    :title="__('Print formats')"
    :description="__('What a printed document looks like, and the letter head it sits under.')"
    :class="PANEL_HEADER"
  />
  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" :text="__('Loading')" />

    <div v-else class="flex flex-col gap-6 py-4">
      <EmptyState
        v-if="!doctypes.length"
        icon="lucide-printer"
        :title="__('Nothing to print yet')"
        :description="__('A format is drawn over the records an app in this workspace shows.')"
      />

      <div v-else class="flex flex-col gap-3">
        <div class="flex flex-wrap items-end gap-2">
          <Select
            v-model="doctype"
            class="w-56"
            :label="__('Records')"
            :options="doctypes.map((one) => ({ label: one.label, value: one.doctype }))"
          />
          <span class="flex-1" />
          <Button
            variant="solid"
            icon-left="lucide-plus"
            :label="__('New format')"
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
            <span class="min-w-0 flex-1 truncate text-sm text-ink-primary">{{ one.name }}</span>
            <Badge v-if="one.default" :label="__('Default')" theme="blue" variant="subtle" />
            <Badge v-if="one.standard" :label="__('Ships with the app')" theme="gray" variant="subtle" />
            <Button
              v-if="!one.default"
              :label="__('Make default')"
              :loading="working === one.name"
              @click="makeDefault(one)"
            />
            <Button
              v-if="one.built"
              icon="lucide-pencil"
              :label="__('Open in the builder')"
              :tooltip="__('Open in the builder')"
              @click="draw(one.name)"
            />
            <Button
              v-if="one.built && !one.standard"
              icon="lucide-trash-2"
              :label="__('Delete this format')"
              :tooltip="__('Delete this format')"
              :loading="working === one.name"
              @click="remove(one)"
            />
          </li>
        </ul>

        <p class="text-p-xs text-ink-muted">
          {{ __('Standard is the fallback: every field, in the order the form declares them.') }}
        </p>
      </div>

      <div class="flex flex-col gap-3 border-t border-outline-gray-1 pt-5">
        <div class="flex items-center gap-2">
          <span class="text-p-sm font-medium text-ink-primary">{{ __('Letter heads') }}</span>
          <span class="flex-1" />
          <Button icon-left="lucide-plus" :label="__('New letter head')" @click="head('')" />
        </div>

        <ul v-if="letterHeads.length" class="flex flex-col border-t border-outline-gray-1">
          <li
            v-for="one in letterHeads"
            :key="one.name"
            data-slot="letter-head"
            class="flex items-center gap-3 border-b border-outline-gray-1 py-2"
          >
            <span class="min-w-0 flex-1 truncate text-sm text-ink-primary">{{ one.name }}</span>
            <Badge v-if="one.default" :label="__('Default')" theme="blue" variant="subtle" />
            <!-- The same one-click the formats list above offers. It was a
                 switch three clicks into the editor, on the half of this
                 feature that Printing's own "Print with the letter head"
                 depends on. -->
            <Button
              v-else
              :label="__('Make default')"
              :loading="working === one.name"
              @click="makeHeadDefault(one)"
            />
            <Button
              icon="lucide-pencil"
              :label="__('Edit this letter head')"
              :tooltip="__('Edit this letter head')"
              @click="head(one.name)"
            />
            <Button
              icon="lucide-trash-2"
              :label="__('Delete this letter head')"
              :tooltip="__('Delete this letter head')"
              :loading="working === one.name"
              @click="removeHead(one)"
            />
          </li>
        </ul>

        <!--
          The one way these two halves disagree, said out loud. `with_letterhead`
          is a switch on the Printing tab and the letter head it uses is the one
          flagged default here; ERPNext ships three and flags none, so a
          workspace can have the switch on, three letter heads, and a blank band
          at the top of every page.
        -->
        <p
          v-if="letterHeads.length && withLetterhead && !letterHeads.some((one) => one.default)"
          class="text-p-xs text-ink-amber-3"
          data-slot="no-default-letter-head"
        >
          {{ __('Letter heads are on, but none is the default — so nothing is added to the page.') }}
        </p>

        <p v-if="!letterHeads.length" class="text-p-xs text-ink-muted">
          {{ __("None yet. A letter head is the band above and below a printed page.'s.") }}
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
import EmptyState from '@/shared/components/EmptyState.vue'
import FormatBuilder from '@/modules/onespace/components/settings/printing/FormatBuilder.vue'
import LetterHeadDialog from '@/modules/onespace/components/settings/printing/LetterHeadDialog.vue'
import { PANEL_BODY, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
import { workspace } from '@/shared/lib/workspace'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'

const doctypes = ref([])
const doctype = ref('')
const formats = ref([])
const letterHeads = ref([])
const withLetterhead = ref(false)

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
    withLetterhead.value = Boolean(found.with_letterhead)
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

const makeHeadDefault = async (one) => {
  working.value = one.name
  error.value = ''
  try {
    letterHeads.value = await workspace.setDefaultLetterHead(one.name)
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
