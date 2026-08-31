<template>
  <!--
    One record, as a card. The hover card over a link and the card on a board
    are the same thing: an identity, then the few fields worth reading without
    opening the record.

    Which few is not ours to choose — `in_preview` is a flag a doctype sets on
    its own fields, once, and every surface pointing at that doctype gets the
    same answer. That is what makes a board card good for free: a doctype whose
    author marked three fields worth previewing already described its card.

    Two shapes rather than two components, because the difference is only how
    much room there is:

      * `panel` — a hover card. Labels in a narrow column of their own, because
        five stacked label/value pairs read as ten unrelated lines and the same
        five in two columns read as a record.
      * `tile` — a board card. No labels at all: a column of values under the
        title, because a card 18rem wide has no room for a label column and the
        field is usually recognisable from its own value.
  -->
  <div :class="frame">
    <div :class="inset">
      <RecordChip :record="record">
        <template v-if="$slots.badge" #badge><slot name="badge" /></template>
      </RecordChip>
    </div>

    <Divider v-if="isPanel && (loading || fields.length)" />

    <div :class="inset">
      <LoadingText v-if="loading" text="Loading" />

      <!-- A hover card: labels beside values. -->
      <dl
        v-else-if="isPanel && fields.length"
        class="grid grid-cols-[7rem_1fr] items-baseline gap-x-3 gap-y-2"
      >
        <template v-for="field in fields" :key="field.fieldname">
          <dt class="truncate text-p-sm text-ink-gray-5">{{ field.label }}</dt>
          <dd class="flex min-w-0 items-center">
            <FieldCell
              :column="field"
              :value="field.value"
              :states="states"
              :links="links"
            />
          </dd>
        </template>
      </dl>

      <!-- A board card: values only, wrapped, so a card stays short. -->
      <div v-else-if="!isPanel && fields.length" class="flex flex-wrap items-center gap-2">
        <FieldCell
          v-for="field in fields"
          :key="field.fieldname"
          :column="field"
          :value="field.value"
          :states="states"
          :links="links"
          class="min-w-0"
        />
      </div>

      <span
        v-else-if="isPanel"
        class="text-p-sm text-ink-gray-5"
      >Nothing else to show.</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Divider, LoadingText } from '@/ui'
import FieldCell from './FieldCell.vue'
import RecordChip from './RecordChip.vue'

const props = defineProps({
  /** { value, label, id, image, description } — the shape the server returns. */
  record: { type: Object, required: true },
  /** `[{ fieldname, label, fieldtype, value, … }]`, already resolved. */
  fields: { type: Array, default: () => [] },
  /** The target doctype's Document States, so a status reads in its colour. */
  states: { type: Array, default: () => [] },
  /**
   * The row's resolved links, keyed by fieldname. A board card draws fields
   * straight off a list row, where a Link is an id and the label for it came
   * back beside it; a hover card's fields arrive already resolved and pass
   * nothing here.
   */
  links: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  shape: { type: String, default: 'panel' },
})

// Computed rather than a ternary in the binding. `test_every_class_emits_css`
// reads the string literals out of a `:class` and checks each is a real
// utility, so `shape === 'panel' ? 'p-3' : ''` offered it `panel` and `tile` as
// class names and it rightly said neither emits any CSS.
const isPanel = computed(() => props.shape === 'panel')
const frame = computed(() => (isPanel.value ? '' : 'flex flex-col gap-2 p-3'))
const inset = computed(() => (isPanel.value ? 'p-3' : ''))
</script>
