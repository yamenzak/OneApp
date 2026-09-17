<template>
  <!--
    One timeline over a record: everything that has happened to it.

    Two tabs before this — Comments and History — so answering "what happened on
    Tuesday" meant reading both and merging them by eye. Every entry says what
    kind of thing it is before it says anything else, through a glyph from a
    closed set: a column of identical avatars makes a comment and a field change
    look like the same event.

    Since `docs/ONECRM.md` stage 3 the mail and the attachments are in it too,
    which is what makes the question answerable in one scroll rather than in
    three tabs. The merge is the server's — `spaceview/surround.py`, where the
    sources are a registry — because every one of them is a read under this
    reader's own permissions and a browser cannot do that.
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

    <!-- The page is capped, and a list that silently stops reads as "that is
         all of them". Said once for the whole column rather than per kind:
         every source is capped and the merge is capped again, so which of them
         ran out is a detail nobody can act on. -->
    <p v-if="more" class="text-p-xs text-ink-muted">
      {{ __('Showing the most recent of what has happened here.') }}
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

          <!-- A message, said as the thing it is: which way it went, and what
               it was about. The subject and not the body — a timeline is a
               column of one-liners, and the Mail tab is where a message is
               read. -->
          <p v-else-if="entry.kind === 'mail'" class="text-p-sm text-ink-secondary">
            <span class="text-ink-primary">
              {{ entry.way === 'Sent' ? __('Sent') : __('Received') }}
            </span>
            <span>: {{ entry.subject || __('(no subject)') }}</span>
            <Icon
              v-if="entry.attached"
              name="lucide-paperclip"
              class="ms-1 inline size-3.5 text-ink-muted"
            />
          </p>

          <!-- An attachment, as a link to the thing rather than as a sentence
               about it: the one useful action on a file in a timeline is
               opening it. -->
          <p v-else-if="entry.kind === 'file'" class="text-p-sm text-ink-secondary">
            <span class="text-ink-primary">{{ __('Attached') }}</span>
            <span>: </span>
            <a
              :href="entry.url"
              target="_blank"
              rel="noopener"
              class="underline hover:text-ink-primary"
            >{{ entry.title }}</a>
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
  /** Everything that has happened to it, merged and sorted — `surround.py`. */
  entries: { type: Array, default: () => [] },
  /** Whether the column is a page of a longer history. */
  more: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['added'])

const draft = ref('')
const commenting = ref(false)
const kind = ref('all')

/**
 * What may be looked at on its own.
 *
 * Built from what is actually in the column rather than declared: a record
 * with no mail should not be offered a Mail filter that answers nothing, which
 * is `docs/UNIFICATION.md` F1 turned around — a surface renders what the
 * source has, and an empty door is worse than no door.
 *
 * `all` is always first and the creation never gets one of its own: there is
 * exactly one of it and filtering to it is a column of one line.
 */
const KINDS = [
  { value: 'comment', label: __('Comments') },
  { value: 'change', label: __('Changes') },
  { value: 'mail', label: __('Mail') },
  { value: 'file', label: __('Files') },
]

const filters = computed(() => {
  const here = new Set(entries.value.map((one) => one.kind))
  return [
    { label: __('All'), value: 'all' },
    ...KINDS.filter((one) => here.has(one.value)),
  ]
})

const when = (value) => (value ? ago(value) : '')

// One list, newest first, merged and sorted by the server — every entry in it
// is a read under this reader's own permissions, and only the server can do
// that. See `spaceview/surround.py`.
const entries = computed(() => props.entries || [])

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
  mail: {
    title: __('No mail'),
    description: __('Nothing has been written about this one yet.'),
  },
  file: {
    title: __('Nothing attached'),
    description: __('No files have been attached to this one.'),
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
