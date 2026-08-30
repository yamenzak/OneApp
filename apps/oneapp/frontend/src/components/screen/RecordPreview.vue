<template>
  <!--
    A link, with a card on hover saying a few things about the record it points
    at without leaving the list.

    Which few is not ours to choose: `in_preview` is a flag a doctype sets on
    its own fields, once, and every screen pointing at that doctype gets the
    same card. A doctype that marks none has nothing to preview, and this
    renders the plain chip rather than an empty card — a card with nothing in
    it reads as one that failed to load.

    Nothing is fetched until somebody hovers. A list of a hundred rows is a
    hundred records nobody asked about.
  -->
  <HoverCard v-if="!barren" v-model:open="open" :hover-delay="0.4">
    <template #trigger>
      <span class="inline-flex min-w-0">
        <RecordChip :record="record" compact />
      </span>
    </template>

    <!--
      The panel shell brings a radius, a background and a shadow and no padding
      at all — that is the consumer's, and the first version of this card
      forgot it, so the header sat against the corner and the rows ran into
      each other.

      A header, a rule, and then a label/value grid: the labels are a narrow
      column of their own rather than a line above each value, because five
      stacked pairs read as ten unrelated lines and the same five in two
      columns read as a record.
    -->
    <div class="w-72">
      <div class="p-3">
        <RecordChip :record="preview?.record || record" />
      </div>

      <Divider />

      <div class="p-3">
        <LoadingText v-if="loading" text="Loading" />

        <dl
          v-else-if="fields.length"
          class="grid grid-cols-[7rem_1fr] items-baseline gap-x-3 gap-y-2"
        >
          <template v-for="field in fields" :key="field.fieldname">
            <dt class="truncate text-p-sm text-ink-gray-5">{{ field.label }}</dt>
            <dd class="flex min-w-0 items-center">
              <FieldCell :column="field" :value="field.value" :states="preview?.states || []" />
            </dd>
          </template>
        </dl>

        <span v-else class="text-p-sm text-ink-gray-5">Nothing else to show.</span>
      </div>
    </div>
  </HoverCard>

  <RecordChip v-else :record="record" compact />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Divider, HoverCard, LoadingText } from '@/ui'
import RecordChip from './RecordChip.vue'
import FieldCell from './FieldCell.vue'
import { workspace } from '../../lib/workspace'

const props = defineProps({
  /** { value, label, id, image, description } — the shape the server returns. */
  record: { type: Object, required: true },
  fieldname: { type: String, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
})

const open = ref(false)
const loading = ref(false)
const preview = ref(null)
// The target doctype marked nothing `in_preview`, so there is no card to show
// and this cell goes back to being a plain chip. Found by asking, once, on the
// first hover — the alternative is putting the whole target doctype's metadata
// in every list spec against the chance that somebody hovers.
const barren = ref(false)

const fields = computed(() => preview.value?.fields || [])

const load = async () => {
  if (preview.value || loading.value) return
  loading.value = true
  try {
    const found = await workspace.linkPreview(
      props.spaceCode,
      props.screen,
      props.fieldname,
      props.record.value,
    )
    if (!found?.fields?.length) {
      barren.value = true
      open.value = false
      return
    }
    preview.value = found
  } finally {
    loading.value = false
  }
}

watch(open, (isOpen) => isOpen && load())
watch(
  () => props.record?.value,
  () => {
    preview.value = null
  },
)
</script>
