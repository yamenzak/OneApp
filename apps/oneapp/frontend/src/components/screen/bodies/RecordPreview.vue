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
      at all — that is the consumer's, and the first version of this card forgot
      it, so the header sat against the corner and the rows ran into each other.
      `RecordCard` owns the padding now.
    -->
    <div class="w-72">
      <RecordCard
        :record="preview?.record || record"
        :fields="fields"
        :states="preview?.states || []"
        :loading="loading"
        shape="panel"
      />
    </div>
  </HoverCard>

  <RecordChip v-else :record="record" compact />
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { HoverCard } from '@/ui'
import RecordCard from './RecordCard.vue'
import RecordChip from '../record/RecordChip.vue'
import { workspace } from '../../../lib/workspace'

const props = defineProps({
  /** { value, label, id, image, description } — the shape the server returns. */
  record: { type: Object, required: true },
  fieldname: { type: String, required: true },
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  /** Which doctype this points at, for a Dynamic Link only — see LinkPicker. */
  target: { type: String, default: '' },
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
      props.target,
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
