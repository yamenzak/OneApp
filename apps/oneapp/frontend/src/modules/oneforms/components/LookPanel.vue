<template>
  <!--
    What most people mean by "make it ours".

    `docs/ONEFORMS.md` §14, stage 13. The Style button beside this opens
    OneCode over the raw stylesheet, which is the right door for the one person
    in the building who writes CSS and no door at all for the person who wants
    their logo at the top. Both are real and both write the same field:
    `oneforms/theming.py` compiles these six into a block between two markers
    and leaves everything a person wrote around it alone.

    Every value is checked on the server and the refusal names the setting. The
    fonts are system stacks and only system stacks, which is not a limitation
    worked around but one worth keeping: `check_css` refuses `@import` and
    refuses `url()` to another site, so a form a stranger opens fetches nothing
    from anywhere.
  -->
  <Dialog v-model="open" :title="__('Look')" size="xl">
    <template #default>
      <div class="flex flex-col gap-4" data-slot="look-panel">
        <div class="grid gap-3 md:grid-cols-2">
          <ColourField v-model="draft.accent" :label="__('Buttons')" name="accent" />
          <ColourField v-model="draft.page" :label="__('Behind the form')" name="page" />
          <ColourField v-model="draft.paper" :label="__('The form itself')" name="paper" />
          <ColourField v-model="draft.ink" :label="__('Writing')" name="ink" />
        </div>

        <FormControl
          v-model="draft.font"
          type="select"
          :label="__('Lettering')"
          :options="FONTS"
          data-slot="look-font"
        />

        <div class="grid gap-3 md:grid-cols-2">
          <FormControl
            v-model="draft.corner"
            type="number"
            :label="__('Corner rounding')"
            :description="__('0 to 32')"
            data-slot="look-corner"
          />
          <FormControl
            v-model="draft.width"
            type="number"
            :label="__('How wide')"
            :description="__('360 to 960')"
            data-slot="look-width"
          />
        </div>

        <!-- A file on this site, and the refusal says so rather than letting
             the stylesheet door say it: an absolute URL would be a form
             fetching a picture from somewhere else on a page a stranger
             opened. -->
        <FormControl
          v-model="draft.mark"
          type="text"
          :label="__('Your mark')"
          :placeholder="__('/files/logo.png')"
          :description="__('A picture uploaded here, above the heading.')"
          data-slot="look-mark"
        />
      </div>
    </template>

    <template #actions>
      <Button variant="solid" :label="__('Save')" :loading="saving" @click="save" />
      <Button :label="__('Clear it')" @click="clear" />
    </template>
  </Dialog>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'

import { Button, Dialog, FormControl } from '@/ui'
import ColourField from '@/modules/oneforms/components/ColourField.vue'
import { notifyError, notifySuccess } from '@/shared/lib/runtime/notify'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

//: The keys `theming.FONTS` knows, said the way somebody choosing one would.
const FONTS = [
  { label: __('The default'), value: '' },
  { label: __('Plain'), value: 'sans' },
  { label: __('Serif'), value: 'serif' },
  { label: __('Typewriter'), value: 'mono' },
  { label: __('Rounded'), value: 'rounded' },
]

const open = defineModel({ type: Boolean, default: false })

const props = defineProps({
  name: { type: String, required: true },
  theme: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['saved'])

const draft = reactive({})
const saving = ref(false)

// Reopened on what is stored rather than on the last look at it, like
// `CodeDialog`: somebody else may have saved in between.
watch(open, (showing) => {
  if (!showing) return
  for (const key of Object.keys(draft)) delete draft[key]
  Object.assign(draft, props.theme || {})
})

async function save() {
  saving.value = true
  try {
    const answer = await workspace.formLook(props.name, { ...draft })
    emit('saved', answer)
    notifySuccess(__('Saved'))
    open.value = false
  } catch (error) {
    notifyError(error)
  } finally {
    saving.value = false
  }
}

/**
 * Back to nothing, which takes the block out and keeps the rest.
 *
 * Its own button rather than emptying six fields: "undo the theme" is one
 * decision, and `theming.into` with nothing set removes the block and leaves
 * whatever was written by hand around it.
 */
async function clear() {
  const answer = await workspace.formLook(props.name, {})
  emit('saved', answer)
  open.value = false
}
</script>
