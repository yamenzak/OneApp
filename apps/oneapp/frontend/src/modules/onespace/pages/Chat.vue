<template>
  <!--
    The assistant, given a page.

    The panel is where it is usually used — beside the record you are asking
    about, which is the whole point of it. This is where it goes when the
    conversation is the work rather than a check: a column of text instead of a
    384px strip, the thread list in the rail, and an address you can send
    somebody.

    Same transcript, same composer. `ChatPanel` is both.
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
        :label="__('Delete')"
        data-slot="chat-forget"
        @click="forget"
      />
      <Button
        variant="subtle"
        icon-left="lucide-plus"
        :label="__('New chat')"
        data-slot="chat-new"
        @click="fresh"
      />
    </div>
  </PageHeader>

  <!--
    No context here, unlike the panel. A page is not beside anything, so
    "this one" has nothing to mean and the tools stay open to the whole
    workspace.
  -->
  <ChatPanel v-model="session" wide />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Breadcrumbs, Button, PageHeader } from '@/ui'
import ChatPanel from '@/modules/onespace/components/chat/ChatPanel.vue'
import { assistant as state, assistantName, loadAssistant } from '@/modules/onespace/lib/shell/assistant'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

const route = useRoute()
const router = useRouter()

// The thread is in the URL, so a conversation can be linked to, bookmarked and
// reloaded — the same reason a record is. Writing to it navigates, which is how
// the first question of a new thread gives itself an address.
const session = computed({
  get: () => route.query.chat || '',
  set: (name) => {
    if (name === (route.query.chat || '')) return
    router.replace({ name: 'Chat', ...(name ? { query: { chat: name } } : {}) })
  },
})

const current = computed(() =>
  state.sessions.find((one) => one.name === session.value) || null,
)

const crumbs = computed(() => [
  { label: assistantName.value, route: { name: 'Chat' } },
  ...(current.value?.title
    ? [{ label: current.value.title, route: route.fullPath }]
    : []),
])

loadAssistant()

function fresh() {
  router.push({ name: 'Chat' })
}

async function forget() {
  await workspace.forgetChat(session.value)
  await loadAssistant({ reload: true })
  fresh()
}
</script>
