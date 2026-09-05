<!--
  One conversation, in the shape a conversation actually has.

  Every message was drawn open, all of it, oldest first. On a thread of two
  that is right and on a thread of fifteen it is a wall: the reply somebody
  came for is at the bottom, past nine copies of the quoted history above it,
  and there is nothing to say which part is new.

  So, Frappe Mail's three rules — the same three every mail client converged on
  — over our own data:

  * A message already read starts as one row: who, the first line, when. The
    last one is always open, because a thread nobody has anything new in is
    still a thread you opened to read something.
  * A long run of read messages folds. Four or more and the middle goes behind
    "N earlier messages", keeping the first and the last of the run as context.
  * Where the unread starts is marked, once, in the colour the notification
    feed already uses for new.

  Whether a message counts as read is decided by the *server*, when the thread
  is fetched, because opening it marks the whole thread read a moment later.
  Ask again and every one of these distinctions is gone.
-->
<template>
  <div class="flex flex-col gap-4">
    <template v-for="(one, at) in messages" :key="one.name">
      <ThreadDivider
        v-if="one.name === unreadFrom"
        tone="unread"
        :label="unreadLabel"
        data-slot="mail-unread-mark"
      />

      <ThreadDivider v-if="one.name === foldAnchor" data-slot="mail-fold">
        <Button
          variant="outline"
          size="sm"
          :label="`${folded.size} earlier messages`"
          @click="unfolded = true"
        />
      </ThreadDivider>

      <article
        v-if="!folded.has(one.name)"
        class="rounded-6 border border-outline-gray-2 p-4"
        data-slot="mail-message"
        :data-open="isOpen(one, at) ? 'yes' : 'no'"
      >
        <!--
          The header is the control. A read message opens by pressing it and
          closes the same way — there is no separate chevron, because the whole
          row is a bigger target and a thread is read with a thumb as often as
          with a mouse.
        -->
        <div
          class="flex items-start justify-between gap-3"
          :class="collapsible(at) ? 'cursor-pointer' : ''"
          @click="collapsible(at) && toggle(one)"
        >
          <SenderChip
            card
            class="text-p-sm"
            :sender="one.sender"
            :who="one.who"
            name-class="font-medium text-ink-gray-8"
          />
          <span class="shrink-0 text-p-xs text-ink-gray-5">
            {{ when(one.communication_date) }}
          </span>
        </div>

        <!-- Closed: the first line of the body, which is what makes a
             collapsed row worth having rather than a list of names. -->
        <p
          v-if="!isOpen(one, at)"
          class="mt-0.5 truncate text-p-xs text-ink-gray-5"
          data-slot="mail-snippet"
        >
          {{ one.preview }}
        </p>

        <template v-else>
          <span class="mt-0.5 block text-p-xs text-ink-gray-5">to {{ one.recipients }}</span>

          <!--
            The body, in a document of its own — Frappe's reader, vendored:
            DOMPurify, a pass that blanks remote images, then a `srcdoc` iframe
            that grows to its own height. See `mail/reader/VENDORED.md`.
          -->
          <div class="mt-3" data-slot="mail-body">
            <EmailContent :content="one.content" block-images />
          </div>

          <div v-if="one.attachments?.length" class="mt-3 flex flex-wrap gap-2">
            <AttachmentChip
              v-for="file in one.attachments"
              :key="file.name"
              :file="file"
              @open="emit('preview', file)"
            />
          </div>
        </template>
      </article>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, dayjsLocal } from '@/ui'

import { firstUnread, foldedRead } from './thread'
import SenderChip from './SenderChip.vue'
import ThreadDivider from './ThreadDivider.vue'
import AttachmentChip from './AttachmentChip.vue'
import EmailContent from './reader/EmailContent.vue'

const props = defineProps({
  /** The whole conversation, oldest first, each with `seen` and `preview`. */
  messages: { type: Array, default: () => [] },
})

const emit = defineEmits(['preview'])

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

/** Messages somebody has pressed since this thread was opened. */
const opened = ref(new Map())
const unfolded = ref(false)

// A different conversation is a different set of decisions. Without this,
// opening thread B shows thread A's messages expanded by position.
watch(
  () => props.messages,
  () => {
    opened.value = new Map()
    unfolded.value = false
  },
)

/** Anything but the last message can be shut; the last one is the point. */
const collapsible = (at) => at !== props.messages.length - 1

function isOpen(one, at) {
  if (opened.value.has(one.name)) return opened.value.get(one.name)
  return !one.seen || !collapsible(at)
}

const toggle = (one) => {
  const at = props.messages.indexOf(one)
  opened.value.set(one.name, !isOpen(one, at))
}

// Both rules live in `thread.js`, tested there: folding needs a thread of six
// with four of them read, and the fixture a browser pass runs against is two.
const folded = computed(() => (unfolded.value ? new Set() : foldedRead(props.messages)))

/** Where the fold's own line goes: in place of the first message it hides. */
const foldAnchor = computed(() => {
  const first = props.messages.find((one) => folded.value.has(one.name))
  return first?.name || null
})

const unread = computed(() => props.messages.filter((one) => !one.seen))
const unreadFrom = computed(() => firstUnread(props.messages))

const unreadLabel = computed(() =>
  unread.value.length === 1 ? '1 new message' : `${unread.value.length} new messages`,
)
</script>
