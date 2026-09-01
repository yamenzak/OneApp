<template>
  <!--
    One timeline over a record: what was said about it, what changed on it, and
    when it started.

    Two tabs before this — Comments and History — which meant "who changed this"
    and "what did they say about it" were two places, and answering "what
    happened on Tuesday" meant reading both and merging them by eye. The desk
    puts them in one column and so does Frappe CRM; the only thing that made
    them separate here was that they came back as two lists.

    Every entry says what kind of thing it is before it says anything else,
    through a glyph from a closed set. A column of identical avatars makes a
    comment and a field change look like the same event.
  -->
  <div class="flex flex-col gap-4 pt-4">
    <div class="flex items-start gap-2">
      <Textarea v-model="draft" :rows="2" placeholder="Add a comment" class="flex-1" />
      <Button
        label="Comment"
        :disabled="!draft.trim()"
        :loading="commenting"
        @click="addComment"
      />
    </div>

    <!-- Everything, or one kind of thing. A filter rather than tabs, because
         the answer to "what happened here" is the whole column and the
         narrowing is the exception. -->
    <TabButtons v-model="kind" :options="filters" />

    <LoadingText v-if="loading" text="Loading activity" />

    <EmptyState
      v-else-if="!shown.length"
      class="!py-8"
      :icon="activityIcon(kind === 'all' ? 'comment' : kind)"
      :title="empty.title"
      :description="empty.description"
    />

    <!-- The page is capped, and a list that silently stops at fifty reads as
         "that is all of them". -->
    <p v-if="more && kind !== 'change'" class="text-p-xs text-ink-gray-5">
      Showing the {{ comments.length }} most recent comments of {{ count }}.
    </p>

    <div v-if="shown.length" class="flex flex-col">
      <!--
        A rail down the gutter, drawn by each entry rather than by a line
        behind them: the last one stops at its own glyph instead of running on
        past the end of the list, which is the thing that makes a timeline read
        as finished rather than as cut off.
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
            <Icon :name="activityIcon(entry.kind)" class="size-3.5 text-ink-gray-6" />
          </span>
          <!-- A 1px rule drawn as a border, not a background: the theme's
               `outline-*` tokens are border colours and `bg-outline-gray-1`
               emits no CSS at all — which is a timeline with no line. -->
          <span
            v-if="entry !== shown[shown.length - 1]"
            class="w-0 flex-1 border-l border-outline-gray-2"
          />
        </div>

        <div class="min-w-0 flex-1 pb-5">
          <div class="flex items-baseline gap-2">
            <span class="truncate text-p-sm font-medium text-ink-gray-8">{{ entry.by }}</span>
            <span class="shrink-0 text-p-xs text-ink-gray-5">{{ when(entry.on) }}</span>
          </div>

          <!-- eslint-disable vue/multiline-html-element-content-newline --
               `whitespace-pre-wrap`, so a line break between the tags is a
               line break on screen: the comment would render indented by
               however far this file happens to be nested. -->
          <p
            v-if="entry.kind === 'comment'"
            class="whitespace-pre-wrap text-p-sm text-ink-gray-7"
          >{{ entry.content }}</p>
          <!-- eslint-enable vue/multiline-html-element-content-newline -->

          <!--
            One line per field, in the screen's own words. The values come back
            stripped of markup where the fieldtype is markup — a Text Editor's
            history is otherwise a line of `<p>` tags — and the label is a
            sentence's worth of space away from them rather than run into the
            first one.
          -->
          <p
            v-for="(change, i) in entry.entries || []"
            :key="i"
            class="text-p-sm text-ink-gray-6"
          >
            <span class="text-ink-gray-8">{{ change.label }}</span>
            <span class="text-ink-gray-4">: {{ change.from || '—' }} → </span>
            <span class="text-ink-gray-8">{{ change.to || '—' }}</span>
          </p>

          <p v-if="entry.kind === 'created'" class="text-p-sm text-ink-gray-6">
            Created this record.
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Icon, LoadingText, TabButtons, Textarea, dayjsLocal } from '@/ui'
import EmptyState from '../EmptyState.vue'
import { activityIcon } from '../../lib/fields'
import { workspace } from '../../lib/workspace'

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
  { label: 'All', value: 'all' },
  { label: 'Comments', value: 'comment' },
  { label: 'Changes', value: 'change' },
]

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

// One list, newest first. Sorted here rather than asked for sorted: the two
// halves come back from two queries and merging them on the server would mean
// paging them together, which is a different and much larger change than
// putting them in one column.
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

  // Where the record started. Last in the list because it is oldest, and it is
  // the one entry no log holds: a Version records a change and there was
  // nothing before the first one.
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
  all: { title: 'Nothing yet', description: 'Nothing has happened to this one yet.' },
  comment: {
    title: 'No comments',
    description: 'Nothing has been said about this one yet.',
  },
  change: {
    title: 'No changes recorded',
    description: 'Nothing on this record has changed since it was created.',
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
