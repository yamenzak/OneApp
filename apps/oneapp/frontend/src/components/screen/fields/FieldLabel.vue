<template>
  <!--
    A field's label, with its type's icon in front of it.

    Inside frappe-ui's own `<label for=…>`: every control this is used through
    exposes a `label` **slot** that renders within that element, so the label
    still points at its input and `getByLabel` keeps resolving. That was the
    thing to get right; an icon is not worth breaking the accessible name over.

    `inline-flex` because a `<label>` is `display: block`.
  -->
  <span class="inline-flex min-w-0 items-center gap-1.5">
    <Icon v-if="icon" :name="icon" class="size-3.5 shrink-0 text-ink-gray-4" aria-hidden="true" />
    <span class="truncate">{{ label }}</span>
    <!--
      The asterisk, copied from frappe-ui's `RequiredIndicator` because that
      component is not exported — only `FormLabel` is, and it renders a whole
      `<label>` of its own, which is the element this is already inside.
    -->
    <template v-if="required">
      <span class="select-none text-ink-red-5" aria-hidden="true">*</span>
      <span class="sr-only">(required)</span>
    </template>
    <!-- Where a model wrote this value. Last, after the asterisk, because the
         prose editor builds its label by hand out of frappe-ui's `FormLabel`,
         which draws its own asterisk and gives nothing to put a mark before.
         One order across every fieldtype is worth more than the argument for
         the other one. See `components/AiMark.vue`. -->
    <AiMark v-if="ai" :mark="ai" />
  </span>
</template>

<script setup>
import { Icon } from '@/ui'
import AiMark from '../../AiMark.vue'

defineProps({
  label: { type: String, default: '' },
  /** `{ feature, model, by, when }` where a model wrote this value, else null. */
  ai: { type: Object, default: null },
  /** A lucide name from the fieldtype table. Absent for a type with no icon. */
  icon: { type: String, default: '' },
  required: { type: Boolean, default: false },
})
</script>
