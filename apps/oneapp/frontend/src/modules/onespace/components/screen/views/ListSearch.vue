<template>
  <!--
    One box that asks every column at once.

    The quick boxes above ask a field a question and the panel asks a harder
    one; neither is what somebody does first, which is type part of a name and
    expect the list to shrink. This is that — the server ORs a `like` across
    the columns the screen shows, so it reaches exactly the fields a person
    could have filtered one at a time.

    Debounced rather than sent per keystroke. A search is a scan per column,
    and "Halloway" typed at speed is eight of them; the pause is what turns it
    into one.
  -->
  <div class="w-32 shrink-0 md:w-44" data-slot="list-search">
    <FormControl
      v-model="typed"
      type="text"
      :placeholder="__('Search')"
      @update:model-value="ask"
      @keydown.escape="clear"
    >
      <template #prefix>
        <Icon name="lucide-search" class="size-4 text-ink-gray-5" :aria-hidden="true" />
      </template>
    </FormControl>
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { FormControl, Icon } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

// Long enough that a fast typist sends one request, short enough that a
// deliberate one does not feel like a submit button.
const PAUSE = 300

const props = defineProps({
  /** What the screen is currently searched by, so a reset reaches the box. */
  modelValue: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'changed'])

const typed = ref(props.modelValue)
let waiting = null

// The box follows the screen, not only the other way round: clearing every
// filter clears this, and a box still holding the word would say the list is
// narrowed when it is not.
watch(() => props.modelValue, (value) => {
  if (value !== typed.value) {
    typed.value = value
    window.clearTimeout(waiting)
  }
})

const ask = (value) => {
  window.clearTimeout(waiting)
  waiting = window.setTimeout(() => {
    emit('update:modelValue', (value || '').trim())
    emit('changed')
  }, PAUSE)
}

const clear = () => {
  window.clearTimeout(waiting)
  typed.value = ''
  emit('update:modelValue', '')
  emit('changed')
}

onBeforeUnmount(() => window.clearTimeout(waiting))
</script>
