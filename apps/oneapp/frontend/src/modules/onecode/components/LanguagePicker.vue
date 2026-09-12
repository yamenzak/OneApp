<template>
  <!--
    Which language a new code file is.

    A dialog rather than a submenu under New. Twenty-one languages is a
    scrolling menu that covers the screen and buries the four kinds beside it,
    and the question is worth its own moment: the extension is the only thing
    that decides what a file is here, so picking it is picking the file.

    Searchable, because a person who knows they want Ruby should not read
    twenty rows to find it, and because the list is alphabetical by label —
    which puts `.rb` under R and nowhere near the top.
  -->
  <Picker
    v-model="open"
    :title="__('New code file')"
    :source="ALL"
    :match="matches"
    identity="key"
    :placeholder="__('Search languages')"
    :empty-title="__('No language here goes by that name.')"
    @pick="pick"
  >
    <template #option="{ one }">
      <span class="flex items-center justify-between gap-2 text-p-sm text-ink-primary">
        <span class="truncate">{{ one.label }}</span>
        <!-- The extension, because it is what the file will be called and
             because two languages can read alike and write differently. -->
        <span class="shrink-0 font-mono text-p-xs text-ink-gray-4">.{{ one.key }}</span>
      </span>
    </template>
  </Picker>
</template>

<script setup>
import Picker from '@/shared/components/Picker.vue'
import { languageOptions } from '@/modules/onestorage/lib/languages'
import { __ } from '@/shared/lib/runtime/translate'

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['pick'])

const ALL = languageOptions()

// The extension as well as the label, so `py` finds Python and `rb` finds Ruby
// — which is what somebody who writes code will actually type. Narrower than
// the default, which would also match the two other strings a row carries.
const matches = (one, asked) =>
  one.label.toLowerCase().includes(asked) || one.key.includes(asked)

const pick = (one) => emit('pick', one)
</script>
