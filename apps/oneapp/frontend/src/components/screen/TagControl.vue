<template>
  <!--
    The record's tags, and the way to change them.

    A tag is the workspace's own word for something — "urgent", "renewal",
    "chase in May" — and it is deliberately not a field: no doctype declares
    it, every doctype has it, and what it means is decided by the people using
    it rather than by whoever wrote the app.

    So the picker offers the whole workspace's vocabulary rather than this
    doctype's. Offering only tags already used here is how one word becomes
    three spellings of it.
  -->
  <MultiSelect
    :model-value="tags"
    v-model:query="query"
    :options="options"
    :loading="loading"
    :filterable="false"
    :disabled="disabled"
    placeholder="Tag this"
    empty-text="Type to make a tag"
    align="end"
    @update:model-value="write"
    @update:open="opened"
  >
    <template #trigger>
      <!--
        The badges are the control, the way the faces are in AssignControl. The
        accessible name is the button's rather than MultiSelect's `label`,
        which renders a visible label above the whole thing.
      -->
      <Button
        variant="ghost"
        data-slot="tags"
        :disabled="disabled"
        :aria-label="tags.length ? `Tags: ${tags.join(', ')}` : 'Add a tag'"
      >
        <span class="flex min-w-0 items-center gap-1">
          <Badge
            v-for="tag in shown"
            :key="tag"
            :label="tag"
            theme="gray"
            variant="subtle"
          />
          <span v-if="more" class="text-p-xs text-ink-gray-5">+{{ more }}</span>
          <Icon
            v-if="!tags.length"
            name="lucide-plus"
            class="size-4 text-ink-gray-5"
          />
        </span>
      </Button>
    </template>

    <template #item-prefix>
      <Icon name="lucide-tag" class="size-3.5 text-ink-gray-5" />
    </template>

    <!-- No Select All: "put every tag in the workspace on this record" is not
         a thing anybody means to press. -->
    <template #footer><span /></template>
  </MultiSelect>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, Icon, MultiSelect } from '@/ui'
import { workspace } from '../../lib/workspace'
import { notifyError } from '../../lib/notify'

// How many fit beside a label before the rest become a count. The row is one
// line high and the label owns the left of it.
const SHOWN = 2

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, required: true },
  tags: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['tagged'])

const query = ref('')
const loading = ref(false)
// The workspace's other tags. Fetched on the first open rather than with the
// record: most records are read without anybody touching this.
const offered = ref([])

const shown = computed(() => props.tags.slice(0, SHOWN))
const more = computed(() => Math.max(props.tags.length - SHOWN, 0))

/**
 * What the picker offers.
 *
 * The tags already on the record come first and always, so a search that does
 * not match one of them cannot drop it out of the list — which would read as
 * having taken it off. Then whatever was typed, as a tag of its own: a
 * vocabulary has to be able to grow, and the way it grows is somebody typing a
 * word that is not in it yet.
 */
const options = computed(() => {
  const held = props.tags.map((tag) => ({ label: tag, value: tag }))
  const known = new Set(props.tags.map((one) => one.toLowerCase()))

  const rest = offered.value
    .filter((tag) => !known.has(tag.toLowerCase()))
    .map((tag) => ({ label: tag, value: tag }))

  const typed = query.value.trim()
  const isNew =
    typed &&
    !known.has(typed.toLowerCase()) &&
    !offered.value.some((one) => one.toLowerCase() === typed.toLowerCase())

  return [
    ...held,
    ...(isNew ? [{ label: `Make the tag “${typed}”`, value: typed }] : []),
    ...rest,
  ]
})

const opened = async (open) => {
  if (!open) {
    query.value = ''
    return
  }
  await look()
}

const look = async () => {
  loading.value = true
  try {
    offered.value =
      (await workspace.tagOptions(props.spaceCode, props.screen, props.name, query.value)) || []
  } finally {
    loading.value = false
  }
}

/**
 * One tag on or off per press.
 *
 * The control hands back the whole set, so the difference is worked out here
 * and sent as the single change it was — which is what the server takes, and
 * what keeps a failed write from looking like the other five tags came off
 * too.
 */
const write = async (wanted) => {
  const held = props.tags
  const added = (wanted || []).find((one) => !held.includes(one))
  const gone = held.find((one) => !(wanted || []).includes(one))
  const tag = added || gone
  if (!tag) return

  try {
    const result = await workspace.setTag(
      props.spaceCode,
      props.screen,
      props.name,
      tag,
      !!added,
    )
    emit('tagged', result?.tags || [])
    query.value = ''
  } catch (raised) {
    notifyError(raised.message || String(raised))
  }
}
</script>
