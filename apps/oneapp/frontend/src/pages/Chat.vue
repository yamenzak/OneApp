<template>
  <!--
    The workspace assistant.

    One conversation at a time, its threads in the rail. What the assistant can
    reach is declared on the server — it runs as whoever is reading this page,
    so it can look at exactly what they could have clicked to and no further.

    Deliberately not a chat that types itself out. An answer here can be four
    provider calls deep, and a streamed reply would hold a worker open for the
    length of that loop; what arrives is the finished answer with the lookups it
    made listed under it, which is the part worth seeing anyway.
  -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center">
      <Breadcrumbs :items="crumbs" />
    </nav>

    <div class="flex items-center gap-2">
      <Button
        v-if="session"
        variant="ghost"
        icon-left="lucide-trash-2"
        label="Delete"
        data-slot="chat-forget"
        @click="forget"
      />
      <Button
        variant="subtle"
        icon-left="lucide-plus"
        label="New chat"
        data-slot="chat-new"
        @click="fresh"
      />
    </div>
  </PageHeader>

  <div class="flex min-h-0 flex-1 flex-col" data-slot="chat">
    <Alert v-if="!state.available && state.loaded" theme="amber"
           title="The assistant is not switched on here">
      <template #description>
        A workspace owner can turn it on under Settings, AI.
      </template>
    </Alert>

    <!-- The transcript owns the scroller; the composer below it does not move. -->
    <div ref="scroller" class="min-h-0 flex-1 overflow-auto px-4 py-6">
      <div class="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <p v-if="!turns.length && !asking" class="text-p-base text-ink-gray-5">
          Ask about anything in this workspace — the records on your screens, a
          file in the Drive, what a document says. Only what you can already
          open.
        </p>

        <ChatTurn v-for="turn in turns" :key="turn.name" :turn="turn" />

        <div v-if="asking" class="flex items-center gap-2 text-ink-gray-5"
             data-slot="chat-thinking">
          <Spinner class="size-4" />
          <span class="text-p-sm">Looking…</span>
        </div>
      </div>
    </div>

    <div class="border-t border-outline-gray-1 px-4 py-3">
      <div class="mx-auto flex w-full max-w-3xl items-end gap-2">
        <!--
          Enter sends and shift-Enter breaks the line, which is what every chat
          does and therefore what fingers expect. A Textarea rather than an
          input because a question about a quotation is often three lines.
        -->
        <Textarea
          v-model="typed"
          class="flex-1"
          :rows="1"
          placeholder="Ask about this workspace"
          data-slot="chat-input"
          :disabled="asking || (state.loaded && !state.available)"
          @keydown.enter.exact.prevent="ask"
        />
        <Button
          variant="solid"
          icon-left="lucide-send"
          label="Send"
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
import { computed, nextTick, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Alert, Breadcrumbs, Button, PageHeader, Spinner, Textarea } from '@/ui'
import ChatTurn from '../components/chat/ChatTurn.vue'
import { assistant as state, loadAssistant } from '@/lib/shell/assistant'
import { workspace } from '@/lib/workspace'

const route = useRoute()
const router = useRouter()

const typed = ref('')
const asking = ref(false)
const turns = ref([])
const scroller = ref(null)

// The thread is in the URL, so a conversation can be linked to, bookmarked and
// reloaded — the same reason a record is.
const session = computed(() => route.query.chat || '')

const crumbs = computed(() => [
  { label: 'Assistant', route: { name: 'Chat' } },
  ...(current.value?.title
    ? [{ label: current.value.title, route: route.fullPath }]
    : []),
])

const current = computed(() =>
  state.sessions.find((one) => one.name === session.value) || null,
)

loadAssistant()

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
    const answered = await workspace.askAssistant(question, session.value)
    turns.value = answered?.messages || turns.value
    if (answered?.session && answered.session !== session.value) {
      router.replace({ name: 'Chat', query: { chat: answered.session } })
    }
    await loadAssistant({ reload: true })
  } finally {
    asking.value = false
    toBottom()
  }
}

function fresh() {
  turns.value = []
  typed.value = ''
  router.push({ name: 'Chat' })
}

async function forget() {
  await workspace.forgetChat(session.value)
  await loadAssistant({ reload: true })
  fresh()
}

function toBottom() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}
</script>
