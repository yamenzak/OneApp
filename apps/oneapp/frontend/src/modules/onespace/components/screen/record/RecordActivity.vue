<template>
  <!--
    One timeline over a record: what was said about it, what changed on it, and
    when it started.

    Two tabs before this — Comments and History — so answering "what happened on
    Tuesday" meant reading both and merging them by eye. Every entry says what
    kind of thing it is before it says anything else, through a glyph from a
    closed set: a column of identical avatars makes a comment and a field change
    look like the same event.
  -->
  <div class="flex flex-col gap-4 pt-4">
    <div class="flex items-start gap-2">
      <Textarea v-model="draft" :rows="2" :placeholder="__('Add a comment')" class="flex-1" />
      <Button
        :label="__('Comment')"
        :disabled="!draft.trim()"
        :loading="commenting"
        @click="addComment"
      />
    </div>

    <!-- Everything, or one kind of thing. A filter rather than tabs, because
         the answer to "what happened here" is the whole column. -->
    <TabButtons v-model="kind" :options="filters" />

    <LoadingText v-if="loading" :text="__('Loading activity')" />

    <EmptyState
      v-else-if="!shown.length"
      class="!py-8"
      :icon="activityIcon(kind === 'all' ? 'comment' : kind)"
      :title="empty.title"
      :description="empty.description"
    />

    <!-- The page is capped, and a list that silently stops at fifty reads as
         "that is all of them". -->
    <p v-if="more && kind !== 'change'" class="text-p-xs text-ink-muted">
      {{ __('Showing the {0} most recent comments of {1}.', [comments.length, count]) }}
    </p>

    <div v-if="shown.length" class="flex flex-col">
      <!--
        A rail down the gutter, drawn by each entry rather than by a line behind
        them: the last one stops at its own glyph instead of running past the
        end of the list.
      -->
      <div
        v-for="entry in shown"
        :key="entry.key"
        data-slot="activity"
        :data-activity="entry.kind"
        class="flex gap-3"
      >
        <div class="flex flex-col items-center">
          <span
            class="flex size-6 shrink-0 items-center justify-center rounded-full bg-surface-gray-2"
          >
            <Icon :name="activityIcon(entry.kind)" class="size-3.5 text-ink-secondary" />
          </span>
          <!-- A 1px rule drawn as a border, not a background: the theme's
               `outline-*` tokens are border colours and `bg-outline-gray-1`
               emits no CSS at all. -->
          <span
            v-if="entry !== shown[shown.length - 1]"
            class="w-0 flex-1 border-s border-outline-gray-2"
          />
        </div>

        <div class="min-w-0 flex-1 pb-5">
          <div class="flex items-baseline gap-2">
            <span class="truncate text-sm font-medium text-ink-primary">{{ entry.by }}</span>
            <span class="shrink-0 text-p-xs text-ink-muted">{{ when(entry.on) }}</span>
          </div>

          <!-- eslint-disable vue/multiline-html-element-content-newline --
               `whitespace-pre-wrap`, so a line break between the tags is a line
               break on screen. -->
          <p
            v-if="entry.kind === 'comment'"
            class="whitespace-pre-wrap text-p-sm text-ink-secondary"
          >{{ entry.content }}</p>
          <!-- eslint-enable vue/multiline-html-element-content-newline -->

          <!--
            One line per field, in the screen's own words. The values come back
            stripped of markup where the fieldtype is markup — a Text Editor's
            history is otherwise a line of `<p>` tags.
          -->
          <p
            v-for="(change, i) in entry.entries || []"
            :key="i"
            class="text-p-sm text-ink-secondary"
          >
            <span class="text-ink-primary">{{ change.label }}</span>
            <span class="text-ink-gray-4">: {{ change.from || '—' }} → </span>
            <span class="text-ink-primary">{{ change.to || '—' }}</span>
          </p>

          <p v-if="entry.kind === 'created'" class="text-p-sm text-ink-secondary">
            {{ __('Created this record.') }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Icon, LoadingText, TabButtons, Textarea } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { activityIcon } from '@/modules/onespace/lib/screen/fields'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { ago } from '@/shared/lib/runtime/format'

const props = defineProps({
  spaceCode: { type: String, required: true },
  screen: { type: String, required: true },
  name: { type: String, default: '' },
  comments: { type: Array, default: () => [] },
  changes: { type: Array, default: () => [] },
  /** The record itself, for the one entry nothing else records: its creation. */
  record: { type: Object, default: () => ({}) },
  /** How many comments there are, which is not how many came back. */
  count: { type: Number, default: 0 },
  more: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['added'])

const draft = ref('')
const commenting = ref(false)
const kind = ref('all')

const filters = [
  { label: __('All'), value: 'all' },
  { label: __('Comments'), value: 'comment' },
  { label: __('Changes'), value: 'change' },
]

const when = (value) => (value ? ago(value) : '')

// One list, newest first. Sorted here rather than asked for sorted: the two
// halves come back from two queries, and merging them on the server would mean
// paging them together.
const entries = computed(() => {
  const all = [
    ...props.comments.map((one) => ({
      key: `c:${one.name}`,
      kind: 'comment',
      by: one.comment_by || one.comment_email,
      on: one.creation,
      content: one.content,
    })),
    ...props.changes.map((one) => ({
      key: `v:${one.name}`,
      kind: 'change',
      by: one.by,
      on: one.on,
      entries: one.entries,
    })),
  ]

  // Where the record started. Last because it is oldest, and the one entry no
  // log holds: a Version records a change, and there was nothing before the
  // first one.
  if (props.record?.creation) {
    all.push({
      key: 'created',
      kind: 'created',
      by: props.record.owner,
      on: props.record.creation,
    })
  }

  return all.sort((a, b) => String(b.on).localeCompare(String(a.on)))
})

const shown = computed(() =>
  kind.value === 'all' ? entries.value : entries.value.filter((one) => one.kind === kind.value),
)

const EMPTY = {
  all: {
    title: __('Nothing yet'),
    description: __('Nothing has happened to this one yet.'),
  },
  comment: {
    title: __('No comments'),
    description: __('Nothing has been said about this one yet.'),
  },
  change: {
    title: __('No changes recorded'),
    description: __('Nothing on this record has changed since it was created.'),
  },
}

const empty = computed(() => EMPTY[kind.value] || EMPTY.all)

const addComment = async () => {
  commenting.value = true
  try {
    await workspace.comment(props.spaceCode, props.screen, props.name, draft.value)
    draft.value = ''
    emit('added')
  } finally {
    commenting.value = false
  }
}
</script>
