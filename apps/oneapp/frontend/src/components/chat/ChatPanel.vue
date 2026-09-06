<template>
  <!--
    A conversation: what has been said, and the box to say the next thing in.

    Mounted twice — in the panel beside whatever you are looking at, and on the
    page at /one/chat. One component because they are the same conversation
    seen at two widths, and two would be two places for "what happens when the
    answer comes back" to drift apart.

    Deliberately not a chat that types itself out. An answer here can be eight
    provider calls deep, and streaming it would hold a worker open for the whole
    loop; what arrives is the finished answer with the lookups it made under it.
  -->
  <div class="flex min-h-0 flex-1 flex-col" data-slot="chat">
    <Alert
      v-if="!state.available && state.loaded"
      theme="amber"
      :title="__('The assistant is not switched on here')"
    >
      <template #description>
        {{ __('A workspace owner can turn it on under Settings, AI.') }}
      </template>
    </Alert>

    <!-- The transcript owns the scroller; the composer below it does not move. -->
    <div ref="scroller" class="min-h-0 flex-1 overflow-auto px-4 py-6">
      <div class="mx-auto flex w-full flex-col gap-6" :class="wide ? 'max-w-3xl' : ''">
        <div v-if="!turns.length && !asking" class="flex flex-col gap-2">
          <p class="text-p-base text-ink-gray-5">
            {{ __('Ask about anything in this workspace — the records on your screens, your files, what a document says. Only what you can already open.') }}
          </p>
          <!-- What it is scoped to, said before the first question rather than
               discovered from an answer that turned out to be narrower than
               expected. -->
          <p v-if="on?.label" class="text-p-sm text-ink-gray-5">
            {{ __('Looking at {0}.', [on.label]) }}
          </p>
        </div>

        <ChatTurn v-for="turn in turns" :key="turn.name" :turn="turn" />

        <div
          v-if="asking"
          class="flex items-center gap-2 text-ink-gray-5"
          data-slot="chat-thinking"
        >
          <Spinner class="size-4" />
          <span class="text-p-sm">{{ __('Looking…') }}</span>
        </div>
      </div>
    </div>

    <div class="border-t border-outline-gray-1 px-4 py-3">
      <div class="mx-auto flex w-full items-end gap-2" :class="wide ? 'max-w-3xl' : ''">
        <!--
          Enter sends and shift-Enter breaks the line, which is what every chat
          does and therefore what fingers expect. A Textarea rather than an
          input because a question about a quotation is often three lines.
        -->
        <Textarea
          v-model="typed"
          class="flex-1"
          :rows="1"
          :placeholder="
            on?.label ? __('Ask about {0}', [on.label]) : __('Ask about this workspace')
          "
          data-slot="chat-input"
          :disabled="asking || (state.loaded && !state.available)"
          @keydown.enter.exact.prevent="ask"
        />
        <Button
          variant="solid"
          icon-left="lucide-send"
          :label="wide ? __('Send') : ''"
          :tooltip="__('Send')"
          data-slot="chat-send"
          :loading="asking"
          :disabled="!typed.trim()"
          @click="ask"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import { Alert, Button, Spinner, Textarea } from '@/ui'
import ChatTurn from './ChatTurn.vue'
import { assistant as state, loadAssistant } from '@/lib/shell/assistant'
import { workspace } from '@/lib/workspace'
import { __ } from '@/lib/runtime/translate'

const props = defineProps({
  /**
   * What the reader has open, or null. `{space, screen, docname, label}` — the
   * label is for this component and the rest is for the server, which checks
   * every part of it against what this person may actually reach.
   */
  on: { type: Object, default: null },
  /** The page has room for a column of text; the panel does not. */
  wide: { type: Boolean, default: false },
})

/** The open thread. Empty until the first question opens one. */
const session = defineModel({ type: String, default: '' })

const typed = ref('')
const asking = ref(false)
const turns = ref([])
const scroller = ref(null)

watch(session, async (name) => {
  turns.value = name ? (await workspace.assistantMessages(name))?.messages || [] : []
  toBottom()
}, { immediate: true })

async function ask() {
  const question = typed.value.trim()
  if (!question || asking.value) return

  // Shown before the round trip, because the round trip can be a minute. The
  // server writes its own row; this one is replaced by it when the answer
  // lands, which is why its key is not an id from the server.
  turns.value = [...turns.value, { name: 'asking', role: 'user', content: question }]
  typed.value = ''
  asking.value = true
  toBottom()

  try {
    const answered = await workspace.askAssistant(question, session.value, props.on)
    turns.value = answered?.messages || turns.value
    if (answered?.session) session.value = answered.session
    await loadAssistant({ reload: true })
  } finally {
    asking.value = false
    toBottom()
  }
}

function toBottom() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}
</script>
