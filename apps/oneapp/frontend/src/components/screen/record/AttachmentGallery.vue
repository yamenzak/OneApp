<template>
  <div class="flex flex-col gap-2">
    <FormLabel :label="field.label" />

    <!--
      Frappe's own control says "Save the document to attach files." on an
      unsaved record, and it is right: the gallery is a window onto the
      record's File rows, and there is no record yet to file anything against.
      Inventing a staging area would be a lot of machinery for the create
      dialog, and a place for a file to be orphaned if the dialog is closed.
    -->
    <p v-if="!docname" class="text-p-sm text-ink-gray-5">
      Save this first, and you can attach files to it.
    </p>

    <template v-else>
      <LoadingText v-if="loading" text="Loading files" />

      <!--
        Pictures across, files below. frappe-ui ships no carousel, so this is a
        snap scroller with two chevrons — which is what a carousel is once you
        do not need autoplay, and it keeps the browser's own touch scrolling on
        a phone rather than replacing it with a drag handler.
      -->
      <div v-else-if="pictures.length" class="relative">
        <div
          ref="strip"
          class="flex snap-x snap-mandatory gap-2 overflow-x-auto scroll-smooth"
        >
          <a
            v-for="file in pictures"
            :key="file.name"
            :href="file.file_url"
            target="_blank"
            rel="noopener"
            class="w-40 shrink-0 snap-start"
          >
            <img
              :src="file.file_url"
              :alt="file.file_name || 'Attachment'"
              class="h-28 w-40 rounded-6 border border-outline-gray-1 object-cover"
              loading="lazy"
            />
            <span class="mt-1 block truncate text-p-xs text-ink-gray-6">
              {{ file.file_name || file.file_url }}
            </span>
          </a>
        </div>

        <!-- Only where they can do anything. Two arrows over three pictures
             that already fit is chrome pretending there is more. -->
        <template v-if="pictures.length > 2">
          <Button
            class="absolute left-1 top-10"
            icon="lucide-chevron-left"
            variant="solid"
            label="Previous"
            :tooltip="'Previous'"
            @click="nudge(-1)"
          />
          <Button
            class="absolute right-1 top-10"
            icon="lucide-chevron-right"
            variant="solid"
            label="Next"
            :tooltip="'Next'"
            @click="nudge(1)"
          />
        </template>
      </div>

      <!-- Everything that is not a picture. A gallery of PDFs is a list, and
           drawing a grey rectangle where a thumbnail would go says less than
           the file's own name does. -->
      <ul v-if="others.length" class="flex flex-col gap-1">
        <li
          v-for="file in others"
          :key="file.name"
          class="flex items-center gap-2 rounded-4 px-2 py-1.5 hover:bg-surface-gray-2"
        >
          <Icon :name="iconFor(file)" class="size-4 shrink-0 text-ink-gray-5" />
          <a
            :href="file.file_url"
            target="_blank"
            rel="noopener"
            class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-8 hover:underline"
          >
            {{ file.file_name || file.file_url }}
          </a>
          <span class="shrink-0 text-p-xs tabular-nums text-ink-gray-5">
            {{ humanSize(file) }}
          </span>
          <Button
            v-if="!disabled"
            icon="lucide-trash-2"
            variant="ghost"
            theme="red"
            :label="`Remove ${file.file_name || 'this file'}`"
            :tooltip="`Remove ${file.file_name || 'this file'}`"
            @click="remove(file)"
          />
        </li>
      </ul>

      <p v-if="!loading && !files.length" class="text-p-sm text-ink-gray-5">
        Nothing here yet.
      </p>

      <!--
        The upload carries the fieldname, so a doctype with two galleries can
        tell its own files apart through `link_filters` — which is how Frappe
        narrows them, and the only thing that makes two galleries on one record
        mean anything.
      -->
      <Button
        v-if="!disabled"
        class="w-full"
        icon-left="lucide-plus"
        label="Add a file"
        @click="picking = true"
      />
      <FilePicker
        v-model="picking"
        multiple
        :attached-to="{ doctype, docname, fieldname: field.fieldname }"
        @picked="reload"
      />
    </template>

    <p v-if="note" class="text-p-xs text-ink-gray-5">{{ note }}</p>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, FormLabel, Icon, LoadingText } from '@/ui'
import FilePicker from '../../drive/FilePicker.vue'
import { workspace } from '../../../lib/workspace'
import { humanSize, iconFor, isImage } from '../../../lib/files'

const props = defineProps({
  /** The docfield. Read for its label, its name and its description. */
  field: { type: Object, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** The record these are filed against. Empty on one not yet saved. */
  doctype: { type: String, default: '' },
  docname: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
  note: { type: String, default: '' },
})

const files = ref([])
const loading = ref(false)
const strip = ref(null)

const pictures = computed(() => files.value.filter(isImage))
const others = computed(() => files.value.filter((file) => !isImage(file)))

// One screen's width at a time, which is what a chevron means. Reading the
// element rather than a fixed number so it stays right in a pane somebody
// dragged narrower.
const nudge = (direction) => {
  const el = strip.value
  if (el) el.scrollBy({ left: direction * el.clientWidth, behavior: 'smooth' })
}

const reload = async () => {
  if (!props.docname) {
    files.value = []
    return
  }
  loading.value = true
  try {
    const found = await workspace.attachments(
      props.spaceCode,
      props.screen,
      props.docname,
      props.field.fieldname,
    )
    files.value = found?.files || []
  } finally {
    loading.value = false
  }
}

// Whether the picker is open. One per gallery, so two galleries on one
// record do not share a dialog.
const picking = ref(false)

const remove = async (file) => {
  await workspace.removeAttachment(props.spaceCode, props.screen, props.docname, file.name)
  await reload()
}

watch(() => props.docname, reload, { immediate: true })
</script>
