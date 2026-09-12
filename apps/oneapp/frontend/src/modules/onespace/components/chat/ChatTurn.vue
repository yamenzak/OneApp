<template>
  <!--
    One turn of a conversation, and what the assistant looked at to say it.

    The lookups are shown rather than hidden. An answer that says "four
    quotations are open" is worth nothing without knowing whether it counted or
    guessed, and this is the difference — a line saying it called count_records
    on the quotations screen turns an assertion into something checkable.

    A change it asked for is shown the same way and in the same place, and the
    ordering is the argument: the answer, then what it read, then what it wants
    to write. The button that writes is the last thing on the turn, under the
    working that led to it.
  -->
  <div
    :class="mine ? 'self-end max-w-[85%]' : 'flex w-full gap-2'"
    data-slot="chat-turn"
  >
    <!--
      Who is speaking, on the turns that are not yours — §E8. A transcript of
      unattributed bubbles is a chat window; a face beside the answer is the
      thing this workspace named and gave a picture to.
    -->
    <AiFace v-if="!mine" size="sm" class="mt-1" />

    <div :class="mine ? '' : 'min-w-0 flex-1'">
      <!--
        `v-text` and not an interpolation: the bubble is `whitespace-pre-wrap`, so
        a line break the template put between the tags and the text would be a
        line break the reader sees.
      -->
      <div
        class="rounded-6 px-3 py-2 text-p-base text-ink-primary whitespace-pre-wrap"
        :class="mine
          ? 'bg-surface-gray-3'
          : 'bg-surface-base border border-outline-gray-1'"
        v-text="turn.content || fallback"
      />

      <!-- Under the answer rather than above it: what was read is the working,
           and the working goes after the result. -->
      <ul v-if="turn.looked_at?.length" class="mt-1 space-y-0.5" data-slot="chat-looked-at">
        <li
          v-for="(one, at) in turn.looked_at"
          :key="at"
          class="flex items-start gap-1.5 text-p-xs text-ink-muted"
        >
          <Icon name="lucide-search" class="mt-0.5 size-3 shrink-0" :aria-hidden="true" />
          <span class="min-w-0 break-words">{{ said(one) }}</span>
        </li>
      </ul>

      <div v-if="turn.changes?.length" class="mt-2 flex flex-col gap-2">
        <SuggestionCard
          v-for="one in turn.changes"
          :key="one.name"
          :suggestion="one"
          @answered="emit('changed')"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Icon } from '@/ui'
import AiFace from '@/shared/components/AiFace.vue'
import SuggestionCard from '@/shared/components/SuggestionCard.vue'

const props = defineProps({
  turn: { type: Object, required: true },
})

// Answering a card changes a record, so the thread is re-read rather than
// patched here: the card's own state moves, and so may anything else the
// conversation has been shown about that record.
const emit = defineEmits(['changed'])

const mine = computed(() => props.turn.role === 'user')

/**
 * What to show when the assistant produced no text.
 *
 * Only two ways that happens and both are worth saying plainly, because the
 * alternative is an empty bubble that reads as a bug: it ran out of turns
 * mid-thought, or it reached the credits one question may spend.
 */
const fallback = computed(() => ({
  turns_spent: 'That took more steps than one question is allowed. Ask again, '
    + 'more narrowly.',
  budget_spent: 'That question reached what one question may spend. Ask again, '
    + 'more narrowly.',
}[props.turn.stopped] || ''))

/**
 * A tool call in words.
 *
 * `find_records` reads as "found records"; a space and a screen read as the
 * path somebody would have clicked; a filter reads as the sentence it is.
 * Raw JSON here — `filters: [["status","=","Open"]]` — is the machine's
 * spelling of something a reader has to be able to check at a glance, and the
 * whole point of showing the lookups is that they can be checked.
 */
const said = (one) => {
  const what = String(one.tool || '').replace(/_/g, ' ')
  const args = { ...(one.arguments || {}) }

  const where = [args.space, args.screen].filter(Boolean).join(' / ')
  delete args.space
  delete args.screen

  const narrowing = (Array.isArray(args.filters) ? args.filters : [])
    .map((one) => (Array.isArray(one) ? one.join(' ') : String(one)))
  delete args.filters

  const rest = Object.entries(args)
    .filter(([, value]) => value !== '' && value !== null && value !== undefined)
    .map(([key, value]) => `${key}: ${plain(value)}`)

  const parts = [where, ...narrowing, ...rest].filter(Boolean)
  return parts.length ? `${what} — ${parts.join(', ')}` : what
}

const plain = (value) =>
  typeof value === 'object' ? JSON.stringify(value) : String(value)

</script>
