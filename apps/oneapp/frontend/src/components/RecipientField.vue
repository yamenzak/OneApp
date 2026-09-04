<template>
  <!--
    Who a message is going to, as people rather than a comma-separated string.

    A text box makes every recipient a typing exercise and every typo a bounce.
    Both halves of the completion are already on this site — `Contact` for
    people the workspace keeps, and everybody it has actually corresponded with
    — so there is no address book to build and nothing to sync.

    `filterable: false` because the search already happened on the server: a
    second literal substring pass here would drop matches found by company name
    or by a contact's surname.
  -->
  <!--
    The `data-slot` is on a wrapper because `MultiSelect` sets
    `inheritAttrs: false` and forwards only class and style — and the specs
    need to address To, Cc and Bcc separately. Derived from the label rather
    than passed in, so a fourth one cannot arrive without a handle.
  -->
  <div :data-slot="`mail-recipients-${label.toLowerCase()}`">
  <MultiSelect
    :model-value="chosen"
    :options="options"
    :label="label"
    :placeholder="placeholder"
    :loading="looking"
    :filterable="false"
    :query="query"
    @update:query="look"
    @update:model-value="pick"
  />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { MultiSelect } from '@/ui'
import { workspace } from '../lib/workspace'

const props = defineProps({
  /** The header as it will be sent: `a@x.test, b@y.test`. */
  modelValue: { type: String, default: '' },
  label: { type: String, default: 'To' },
  placeholder: { type: String, default: 'somebody@example.com' },
})
const emit = defineEmits(['update:modelValue'])

const query = ref('')
const looking = ref(false)
const found = ref([])

const chosen = computed(() =>
  (props.modelValue || '')
    .split(',')
    .map((one) => one.trim())
    .filter(Boolean),
)

// What is offered: whatever the search found, plus whatever is already picked
// — an option list that dropped the current value would render the chips blank.
const options = computed(() => {
  const by = new Map(found.value.map((one) => [one.email, one]))
  for (const one of chosen.value) {
    if (!by.has(one)) by.set(one, { email: one, label: one, company: '' })
  }
  return [...by.values()].map((one) => ({
    value: one.email,
    label: one.label === one.email ? one.email : `${one.label} · ${one.email}`,
    description: one.company || undefined,
  }))
})

// A typed address that matches nobody is still an address. Mail goes to people
// who are in no directory, which is most of the mail anybody sends.
function typed(text) {
  const one = (text || '').trim().replace(/[<>,;]/g, '')
  return one.includes('@') ? one : ''
}

let waiting = null
function look(text) {
  query.value = text
  clearTimeout(waiting)
  waiting = setTimeout(async () => {
    const term = (text || '').trim()
    if (term.length < 2) {
      found.value = []
      return
    }
    looking.value = true
    try {
      const rows = (await workspace.mailSuggest(term)) || []
      const free = typed(term)
      // The typed text first, so pressing enter on a complete address that
      // happens to also prefix-match a contact sends to what was typed.
      found.value = free && !rows.some((one) => one.email === free)
        ? [{ email: free, label: free, company: '' }, ...rows]
        : rows
    } finally {
      looking.value = false
    }
  }, 200)
}

function pick(values) {
  emit('update:modelValue', (values || []).join(', '))
}
</script>
