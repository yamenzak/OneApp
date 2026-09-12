<!--
  One question, a set to narrow, an answer.

  Five dialogs were this: a language, a folder, a template, a record, a file.
  Each had its own search box, its own scroller, its own "nothing matched"
  sentence and its own idea of what pressing a row does — and four of them
  could not be driven from the keyboard at all, so the fastest way to choose a
  language was to reach for the mouse after typing the name of it.

  What this owns is the interaction, not the content: the search, the
  debounce, the arrow keys, the active row, the empty state and the close. How
  a candidate *looks* is the caller's, through `#option`, because a folder
  shows its path and a language shows its extension and pretending those are
  one row would mean a slot per field anyway.

  Three things it deliberately does not do. It is not a menu — a menu is
  `Dropdown`, it has no search and it should not grow one. It is not a field —
  a Link field is an `Autocomplete` inside the form, and moving it into a
  dialog would put a modal in the middle of typing a record. And it does not
  multi-select: every one of the five picks exactly one thing and closes, and
  a `multiple` prop with one caller is how a component starts becoming two.

  `docs/UNIFICATION.md` §A2.
-->
<template>
  <Dialog v-model="open" :title="title" :size="size">
    <template #default>
      <div class="flex flex-col gap-3">
        <p v-if="said" class="text-p-sm text-ink-secondary">{{ said }}</p>

        <!--
          `aria-label` and not `label`: FormControl draws a label as visible
          text above the box, and a dialog titled "Move to a folder" with
          "Search folders" written above its only field says it twice.
        -->
        <FormControl
          v-if="searchable"
          v-model="query"
          type="text"
          :placeholder="placeholder || __('Search')"
          :aria-label="placeholder || __('Search')"
          data-slot="picker-search"
          @keydown="onKey"
        />

        <!-- Anything the caller wants above the candidates and outside the
             search — the Drive's "All files", which is a destination rather
             than a folder and so is in no list to be found in. -->
        <slot name="before" />

        <div v-if="busy" class="flex flex-col gap-2" data-slot="picker-loading">
          <Skeleton v-for="n in 5" :key="n" class="h-9 w-full" />
        </div>

        <!--
          A listbox, and the rows are options. Not decoration: this is the
          one thing the `Combobox` these replaced got right for free, and
          without it a screen reader announces a list of buttons with no
          sense that they are one choice — and every spec that finds a
          candidate by its role stops finding it.
        -->
        <div
          v-else-if="shown.length"
          ref="scroller"
          role="listbox"
          data-slot="picker-list"
          :class="['flex min-h-0 flex-col overflow-y-auto', tall ? 'max-h-overlay' : 'max-h-80']"
        >
          <Row
            v-for="(one, index) in shown"
            :key="keyOf(one, index)"
            role="option"
            :aria-selected="index === active"
            data-slot="picker-option"
            edge="rounded"
            pad="tight"
            :active="index === active"
            @click="take(one)"
          >
            <slot name="option" :one="one" :index="index">{{ labelOf(one) }}</slot>
          </Row>
        </div>

        <EmptyState
          v-else
          class="!py-6"
          :icon="emptyIcon"
          :title="emptyTitle || __('Nothing matched')"
          :description="emptyDescription"
        >
          <template v-if="$slots.empty" #action><slot name="empty" /></template>
        </EmptyState>

        <slot name="after" />
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'

import { Dialog, FormControl, Skeleton } from '@/ui'

import EmptyState from '@/shared/components/EmptyState.vue'
import Row from '@/shared/components/Row.vue'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  title: { type: String, required: true },
  /** One sentence saying what choosing will do, in the caller's words. */
  said: { type: String, default: '' },

  /**
   * What there is to choose from.
   *
   * An array is narrowed here, in the browser, which is right for a set that
   * is already whole and small — twenty-one languages, eight templates. A
   * function is asked the query instead and may answer with a promise, which
   * is right for a set the server owns; it is debounced and its own
   * in-flight state draws the skeleton, so a caller never wires a spinner.
   */
  source: { type: [Array, Function], required: true },

  /**
   * Whether a candidate matches what was typed. The default reads every
   * string the row has, which is what a person expects and what four of the
   * five did by hand; a caller overrides it to search fewer fields or more —
   * the languages match on extension as well as name.
   */
  match: { type: Function, default: null },

  /** What to show for a candidate when there is no `#option` slot. */
  label: { type: [String, Function], default: 'label' },
  /** What makes a candidate itself, for `:key` and for the active row. */
  identity: { type: [String, Function], default: 'name' },

  placeholder: { type: String, default: '' },
  //: A set of eight needs no search box; a set of two hundred is unusable
  //: without one. The caller knows which it has.
  searchable: { type: Boolean, default: true },
  //: A picker that is the whole point of the dialog gets the taller scroller.
  tall: { type: Boolean, default: false },
  size: { type: String, default: 'lg' },

  /** Nothing to choose from, or nothing left after narrowing. */
  emptyIcon: { type: String, default: '' },
  emptyTitle: { type: String, default: '' },
  emptyDescription: { type: String, default: '' },
})

const emit = defineEmits(['pick'])

const open = defineModel({ type: Boolean, default: false })

const query = ref('')
const active = ref(0)
const asked = ref([])
const looking = ref(false)
const scroller = ref(null)

const remote = computed(() => typeof props.source === 'function')

const read = (one, how, fallback) => {
  if (typeof how === 'function') return how(one)
  const value = one && typeof one === 'object' ? one[how] : one
  return value === undefined || value === null ? fallback(one) : value
}

const labelOf = (one) => String(read(one, props.label, (row) => row?.name ?? row ?? ''))
const keyOf = (one, index) => read(one, props.identity, () => index)

//: Every string the row carries, which is what somebody typing two letters
//: is hoping for. A row is sometimes a bare string, which is the whole of it.
function anyField(one, asking) {
  if (one === null || one === undefined) return false
  if (typeof one !== 'object') return String(one).toLowerCase().includes(asking)
  return Object.values(one).some(
    (value) => typeof value === 'string' && value.toLowerCase().includes(asking),
  )
}

const shown = computed(() => {
  if (remote.value) return asked.value
  const asking = query.value.trim().toLowerCase()
  const all = props.source || []
  if (!asking) return all
  return all.filter((one) => (props.match ? props.match(one, asking) : anyField(one, asking)))
})

//: Long enough that typing an id is one search rather than eleven, short
//: enough that the list has moved by the time the eye reaches it. The same
//: number `RecordPicker` chose alone, which is why it is here now.
const PAUSE = 250
let waiting = null

async function look() {
  if (!remote.value) return
  looking.value = true
  try {
    asked.value = (await props.source(query.value)) || []
  } catch {
    asked.value = []
  } finally {
    looking.value = false
  }
}

//: The skeleton belongs to the *first* look only. Redrawing it on every
//: keystroke makes the list flash rather than narrow, which reads as the
//: dialog reloading each time a letter is typed.
const busy = computed(() => looking.value && !asked.value.length)

watch(query, () => {
  active.value = 0
  if (!remote.value) return
  window.clearTimeout(waiting)
  waiting = window.setTimeout(look, PAUSE)
})

watch(open, (showing) => {
  if (!showing) {
    // Emptied on close rather than on open: a dialog that clears while it is
    // fading out shows the whole list flashing back for a frame.
    query.value = ''
    asked.value = []
    return
  }
  active.value = 0
  look()
})

function take(one) {
  emit('pick', one)
  open.value = false
}

/**
 * The arrow keys, which is the half of this that did not exist anywhere.
 *
 * Held on the search box rather than on the list, because that is where the
 * caret is the whole time somebody is choosing: a list that can only be
 * driven once it has focus is a list you have to tab into first, and nobody
 * does. Home and End because a set of two hundred has two ends worth
 * reaching.
 */
function onKey(event) {
  const last = shown.value.length - 1
  if (last < 0) return
  const moves = {
    ArrowDown: () => Math.min(active.value + 1, last),
    ArrowUp: () => Math.max(active.value - 1, 0),
    Home: () => 0,
    End: () => last,
  }
  if (moves[event.key]) {
    event.preventDefault()
    active.value = moves[event.key]()
    nextTick(reveal)
    return
  }
  if (event.key === 'Enter') {
    event.preventDefault()
    take(shown.value[active.value])
  }
}

//: Scrolling the active row into view, and only when it has gone out of it —
//: `block: 'nearest'` is what stops the list jumping a whole page each time
//: the arrow moves one row inside a scroller that is already showing it.
function reveal() {
  const rows = scroller.value?.querySelectorAll('[data-slot="picker-option"]')
  rows?.[active.value]?.scrollIntoView({ block: 'nearest' })
}
</script>
