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

    `/` focuses it, which was Mail's idea and the best of the three boxes
    this replaced: it is what every mail client and every code host does, and
    it was the one thing that made a keyboard reader faster than a mouse on
    that screen. It is here now, so every surface with a search box has it.
    Escape clears — the other half of the same pair, and two of 215 files had
    it.
  -->
  <div ref="box" :class="width" data-slot="list-search">
    <FormControl
      v-model="typed"
      type="text"
      :placeholder="placeholder || __('Search')"
      :aria-label="placeholder || __('Search')"
      @update:model-value="ask"
      @keyup.enter="now"
      @keydown.escape="clear"
    >
      <template #prefix>
        <Icon name="lucide-search" class="size-4 text-ink-muted" :aria-hidden="true" />
      </template>
    </FormControl>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, useAttrs, watch } from 'vue'
import { FormControl, Icon } from '@/ui'
import { useShortcuts } from '@/modules/onespace/lib/shell/shortcuts'
import { __ } from '@/shared/lib/runtime/translate'

// Long enough that a fast typist sends one request, short enough that a
// deliberate one does not feel like a submit button.
const PAUSE = 300

const props = defineProps({
  /** What the screen is currently searched by, so a reset reaches the box. */
  modelValue: { type: String, default: '' },
  //: What this list is, where "Search" alone would not say — a mailbox and a
  //: drive both have one and they are not searching the same thing.
  placeholder: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'changed'])

// The width, and why it is worked out rather than always applied.
//
// Most lists want the same box and should not respell it; Mail's fills the
// column beside Write and Drive's used to be its own third size. A default
// class *and* a caller's class both land on the root, and which of
// `w-32` and `flex-1` wins is then whichever Tailwind emitted later — so the
// default stands down when a caller has an opinion, and the result is one
// box everywhere it is not deliberately another shape.
const attrs = useAttrs()
const width = computed(() => (attrs.class ? '' : 'w-32 shrink-0 md:w-44'))

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

const send = (value) => {
  emit('update:modelValue', (value || '').trim())
  emit('changed')
}

const ask = (value) => {
  window.clearTimeout(waiting)
  waiting = window.setTimeout(() => send(value), PAUSE)
}

const now = () => {
  window.clearTimeout(waiting)
  send(typed.value)
}

const clear = () => {
  window.clearTimeout(waiting)
  typed.value = ''
  emit('update:modelValue', '')
  emit('changed')
}

onBeforeUnmount(() => window.clearTimeout(waiting))

// The input is found through the wrapper rather than held in a ref of its
// own: `FormControl` renders whichever control it was told to, so a ref on it
// is the wrapper component rather than the thing that takes focus.
const box = ref(null)
useShortcuts({ '/': () => box.value?.querySelector('input')?.focus() })
</script>
