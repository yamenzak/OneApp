<template>
  <!--
    A field's label, with its type's icon in front of it.

    The icon used to sit in a gutter to the left of the whole row — its own
    column, aligned to the control rather than to the label, which pushed every
    label and every input in the form 22px right of where the section heading
    started and left a ragged empty channel down the side of the form.

    It goes here instead, and "here" is inside frappe-ui's own `<label for=…>`:
    every control this is used through exposes a `label` **slot** that renders
    within that element, so the label still points at its input and
    `getByLabel` — which most of the browser suite is written in terms of —
    keeps resolving. That was the thing to get right; an icon is not worth
    breaking the accessible name over.

    `inline-flex` because a `<label>` is `display: block`: without it the icon
    and the text stack.
  -->
  <span class="inline-flex min-w-0 items-center gap-1.5">
    <Icon v-if="icon" :name="icon" class="size-3.5 shrink-0 text-ink-gray-4" aria-hidden="true" />
    <span class="truncate">{{ label }}</span>
    <!--
      The asterisk, copied from frappe-ui's `RequiredIndicator` because that
      component is not exported from the package — only `FormLabel` is, and
      FormLabel renders a whole `<label>` of its own, which is the element this
      is already inside. Same markup, same token, same screen-reader text, so a
      required field is marked the way every other required field in both apps
      is marked.
    -->
    <template v-if="required">
      <span class="select-none text-ink-red-5" aria-hidden="true">*</span>
      <span class="sr-only">(required)</span>
    </template>
  </span>
</template>

<script setup>
import { Icon } from '@/ui'

defineProps({
  label: { type: String, default: '' },
  /** A lucide name from the fieldtype table. Absent for a type with no icon. */
  icon: { type: String, default: '' },
  required: { type: Boolean, default: false },
})
</script>
