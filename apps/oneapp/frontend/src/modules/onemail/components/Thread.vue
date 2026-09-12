<!--
  One conversation, in the shape a conversation actually has.

  Every message drawn open, oldest first, is right on a thread of two and a wall
  on a thread of fifteen. So, Frappe Mail's three rules over our own data:

  * A message already read starts as one row: who, the first line, when. The
    last one is always open.
  * A long run of read messages folds — four or more and the middle goes behind
    "N earlier messages", keeping the first and last of the run as context.
  * Where the unread starts is marked, once.

  Whether a message counts as read is decided by the *server*, when the thread
  is fetched, because opening it marks the whole thread read a moment later.

  Two things each message owns rather than the screen under it: **who else saw
  it**, behind the caret on the recipients line, and **answering this one** —
  the ⋯ menu. The strip at the bottom of the page answers the *newest* message,
  which is right nine times in ten and silently wrong the tenth: pressing
  Forward while reading something from three weeks ago forwarded today's mail
  instead, and nothing on the screen said so.
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
          :label="__('{0} earlier messages', [folded.size])"
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
          The header is the control: a read message opens by pressing it and
          closes the same way, because the whole row is a bigger target and a
          thread is read with a thumb as often as with a mouse.
        -->
        <div
          class="flex items-start justify-between gap-3"
          :class="collapsible(at) ? 'cursor-pointer' : ''"
          @click="collapsible(at) && toggle(one)"
        >
          <SenderChip
            card
            class="min-w-0 text-p-sm"
            :sender="one.sender"
            :who="one.who"
            name-class="font-medium text-ink-primary"
          />
          <div class="flex shrink-0 items-center gap-1">
            <span class="text-p-xs text-ink-muted">
              {{ when(one.communication_date) }}
            </span>
            <!--
              On a span that stops the click, for the same reason the list's
              tick is: the menu sits inside the header, and the header is the
              collapse toggle. Without this, opening the menu on a read message
              expands it underneath and opening it on the last one shuts the
              thread's only open message.
            -->
            <span class="flex items-center" @click.stop>
              <Dropdown :options="answering(one)" align="end">
                <Button
                  variant="ghost"
                  size="sm"
                  icon="lucide-more-horizontal"
                  :label="__('Answer this message')"
                  :tooltip="__('Answer this message')"
                  data-slot="mail-message-menu"
                />
              </Dropdown>
            </span>
          </div>
        </div>

        <!-- Closed: the first line of the body, which is what makes a collapsed
             row worth having rather than a list of names. -->
        <p
          v-if="!isOpen(one, at)"
          class="mt-0.5 truncate text-xs text-ink-muted"
          data-slot="mail-snippet"
        >
          {{ one.preview }}
        </p>

        <template v-else>
          <!--
            Who it went to, in one line, and the whole envelope behind the
            caret. The line stays because on most mail it is the entire answer;
            the caret is for the message where it is not — a Bcc, a second
            address of your own, the date this actually arrived rather than
            "3 days ago".
          -->
          <button
            type="button"
            class="mt-0.5 flex max-w-full items-start gap-1 text-start text-p-xs text-ink-muted hover:text-ink-secondary"
            data-slot="mail-details-toggle"
            :aria-expanded="detailed.has(one.name)"
            :aria-label="__('Details')"
            @click="detail(one)"
          >
            <span class="min-w-0 truncate">
              to {{ one.recipients }}
              <!-- Cc, which the server has always sent and the reader never
                   drew. Who else saw a message decides whether a reply goes to
                   one person or to six. -->
              <span v-if="one.cc" data-slot="mail-cc">· cc {{ one.cc }}</span>
            </span>
            <Icon
              :name="detailed.has(one.name) ? 'lucide-chevron-up' : 'lucide-chevron-down'"
              class="mt-px size-3 shrink-0"
            />
          </button>

          <dl
            v-if="detailed.has(one.name)"
            class="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 rounded-6 bg-surface-gray-1 p-3 text-p-xs"
            data-slot="mail-details"
          >
            <template v-for="row in envelope(one)" :key="row.label">
              <dt class="text-ink-muted">{{ row.label }}</dt>
              <dd class="break-words text-ink-primary">{{ row.value }}</dd>
            </template>
          </dl>

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
import { Button, Dropdown, Icon, dayjsLocal } from '@/ui'

import { firstUnread, foldedRead } from '@/modules/onemail/components/thread'
import SenderChip from '@/modules/onemail/components/SenderChip.vue'
import ThreadDivider from '@/modules/onemail/components/ThreadDivider.vue'
import AttachmentChip from '@/modules/onemail/components/AttachmentChip.vue'
import EmailContent from '@/modules/onemail/components/reader/EmailContent.vue'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  /** The whole conversation, oldest first, each with `seen` and `preview`. */
  messages: { type: Array, default: () => [] },
})

const emit = defineEmits(['preview', 'respond'])

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

/** The date in full, for the details panel — "3 days ago" is not a date. */
const exactly = (value) => (value ? dayjsLocal(value).format('D MMMM YYYY, HH:mm') : '')

/** Messages somebody has pressed since this thread was opened. */
const opened = ref(new Map())
const unfolded = ref(false)

/** Messages whose envelope is showing. */
const detailed = ref(new Set())

// A different conversation is a different set of decisions. Without this,
// opening thread B shows thread A's messages expanded by position.
watch(
  () => props.messages,
  () => {
    opened.value = new Map()
    detailed.value = new Set()
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

function detail(one) {
  // A new Set rather than a mutation: Vue tracks the ref, not the Set's
  // contents, so `add` on the same object redraws nothing.
  const showing = new Set(detailed.value)
  if (!showing.delete(one.name)) showing.add(one.name)
  detailed.value = showing
}

/**
 * The envelope, as rows. Empty fields are left out rather than drawn blank:
 * most mail has no Bcc, and a panel of four labels with nothing beside them is
 * a panel nobody opens twice.
 */
function envelope(one) {
  const from = one.who?.label && one.who.label !== one.sender
    ? `${one.who.label} <${one.sender}>`
    : one.sender
  return [
    { label: __('From'), value: from },
    { label: __('To'), value: one.recipients },
    { label: __('Cc'), value: one.cc },
    { label: __('Bcc'), value: one.bcc },
    { label: __('Date'), value: exactly(one.communication_date) },
  ].filter((row) => row.value)
}

/**
 * Answering *this* message rather than the newest one.
 *
 * The same three verbs as the strip under the conversation, and they are here
 * because the strip cannot mean both things at once: it answers the last
 * message, which is what somebody reading the last message wants and not what
 * somebody who has just opened a message from three weeks ago does.
 */
function answering(one) {
  return [
    {
      label: __('Reply'),
      icon: 'lucide-corner-up-left',
      onClick: () => emit('respond', { message: one, kind: 'reply' }),
    },
    {
      label: __('Reply to all'),
      icon: 'lucide-corner-up-left',
      onClick: () => emit('respond', { message: one, kind: 'reply_all' }),
    },
    {
      label: __('Forward'),
      icon: 'lucide-corner-up-right',
      onClick: () => emit('respond', { message: one, kind: 'forward' }),
    },
  ]
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
  unread.value.length === 1 ? __('1 new message') : __('{0} new messages', [unread.value.length]),
)
</script>
