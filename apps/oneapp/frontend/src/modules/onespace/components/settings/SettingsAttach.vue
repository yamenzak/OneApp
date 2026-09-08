<template>
  <!--
    A file chosen for a setting: the logo, the favicon, the splash image.

    These were text boxes. `SettingsFields` mapped `Attach Image` to `'text'`,
    so setting a logo meant knowing the `/files/...` URL of something already
    uploaded, which nothing in this product tells anybody — the one screen every
    user sees before they are anyone was unbrandable in practice.

    `FilePicker` rather than an uploader of its own: it is the same dialog a
    record's Attach field opens, with the library, this device and the camera in
    it, so a logo is chosen the way everything else is and lands in the Drive
    like everything else.
  -->
  <div class="flex flex-col gap-1.5">
    <FormLabel :label="label" />

    <div class="flex items-center gap-3">
      <!-- What is actually set, shown rather than described. A logo you cannot
           see is a logo you cannot tell is wrong. -->
      <img
        v-if="image && modelValue"
        :src="modelValue"
        :alt="label"
        class="h-10 max-w-32 rounded-6 border border-outline-gray-2 object-contain"
      />
      <span
        v-else-if="modelValue"
        class="truncate text-p-sm text-ink-gray-6"
        :title="modelValue"
      >{{ modelValue }}</span>

      <Button
        :label="modelValue ? __('Replace') : __('Choose')"
        :data-slot="`attach-${label.toLowerCase().replace(/\s+/g, '-')}`"
        @click="picking = true"
      />
      <Button
        v-if="modelValue"
        variant="ghost"
        :label="__('Clear')"
        @click="modelValue = ''"
      />
    </div>

    <p v-if="hint" class="text-p-sm text-ink-gray-5">{{ hint }}</p>

    <!-- No `attached-to`: a workspace's logo belongs to the workspace, not to a
         record, so it is an ordinary file in the Drive. -->
    <FilePicker
      v-model="picking"
      :kind="image ? 'Image' : ''"
      :title="__('Choose {0}', [label.toLowerCase()])"
      @picked="(file) => { modelValue = file.file_url }"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Button, FormLabel } from '@/ui'
import FilePicker from '@/modules/onestorage/components/FilePicker.vue'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  label: { type: String, required: true },
  hint: { type: String, default: '' },
  /** An `Attach Image` shows what it is set to; an `Attach` shows its name. */
  image: { type: Boolean, default: false },
})

const modelValue = defineModel({ type: String, default: '' })
const picking = ref(false)
</script>
