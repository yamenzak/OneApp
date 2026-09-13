<template>
  <!--
    The assistant beside whatever you are looking at.

    A **panel** in this product's vocabulary (`docs/ONESPACE.md` §12): a strip
    inside a page you toggle and that keeps its state. Not a popover, and the
    difference is the whole reason it is this: an answer here can be eight
    provider calls and forty seconds, and a popover dismisses on the outside
    click somebody makes to go and check the record they were asking about. A
    panel is the popover that survives being ignored.

    Mounted once, in the shell, so every page has it without every page knowing
    about it. `lib/shell/assistant.js` holds whether it is open and what it is
    looking at, because the thing that opens it is somewhere else every time.

    Not drawn on a phone: the page has one surface there, and the assistant is a
    page (`/one/chat`) like everything else.
  -->
  <aside
    v-if="state.showing && state.available"
    class="hidden w-96 shrink-0 flex-col border-s border-outline-gray-1 bg-surface-base md:flex"
    :aria-label="assistantName"
    data-slot="assistant-panel"
  >
    <div
      class="flex shrink-0 items-center justify-between gap-2 border-b border-outline-gray-1 px-4 py-3"
    >
      <div class="min-w-0">
        <div class="flex min-w-0 items-center gap-2">
          <AiFace size="sm" />
          <p class="truncate text-base font-medium text-ink-primary">{{ assistantName }}</p>
        </div>
        <!-- What it is scoped to, in the header rather than only in the empty
             state: the empty state is gone the moment anybody asks anything. -->
        <p v-if="state.on?.label" class="truncate text-xs text-ink-muted">
          {{ state.on.label }}
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-1">
        <Dropdown :options="menu">
          <Button variant="ghost" icon="lucide-ellipsis" :label="__('More')" :tooltip="__('More')" />
        </Dropdown>
        <Button
          variant="ghost"
          icon="lucide-x"
          :label="__('Close {0}', [assistantName])"
          :tooltip="__('Close')"
          data-slot="assistant-close"
          @click="closeAssistant"
        />
      </div>
    </div>

    <ChatPanel v-model="state.session" :on="state.on" />
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Button, Dropdown } from '@/ui'
import AiFace from '@/shared/components/AiFace.vue'
import ChatPanel from '@/modules/onespace/components/chat/ChatPanel.vue'
import {
  assistant as state,
  assistantName,
  closeAssistant,
  loadAssistant,
  openAssistant,
} from '@/modules/onespace/lib/shell/assistant'
import { useAddress } from '@/shared/composables/useAddress'
import { workspace } from '@/shared/lib/workspace'
import { KIND, writeAt } from '@/shared/lib/url/at'
import { __ } from '@/shared/lib/runtime/translate'

const router = useRouter()

/**
 * The assistant has an address — `?ask=`, §C4.
 *
 * Empty means open on a new conversation; a session name means open on that
 * one. It is a panel and stays one — an answer here can be forty seconds and
 * a popover dismisses on the click somebody makes to go and check the record
 * they asked about — but a panel with an address is one a colleague can be
 * sent to.
 *
 * Not drawn on a phone, where the assistant is a page; the address there is
 * `/one/chat`, which is a route and already had one.
 */
useAddress('ask', {
  read: () => {
    if (!state.showing) return ''
    // A blank value is still an answer: `?ask=` is the assistant open on
    // nothing, which is what pressing the rail entry gives you. Vue Router
    // drops an empty string, so a new conversation says so with a word.
    return state.session || 'new'
  },
  write: (value) => {
    if (!value) {
      closeAssistant()
      return
    }
    state.session = value === 'new' ? '' : value
    openAssistant(state.on)
  },
})

/**
 * The three things a conversation can be, beyond having it.
 *
 * "Open as a page" is the one that matters and it is why the page still exists:
 * a panel is 384px, and a long answer with four lookups under it wants a
 * column. The thread goes with it — the same conversation, wider.
 */
const menu = computed(() => [
  {
    label: __('New chat'),
    icon: 'lucide-plus',
    onClick: () => { state.session = '' },
  },
  {
    label: __('Open as a page'),
    icon: 'lucide-maximize-2',
    onClick: () => {
      closeAssistant()
      router.push({
        name: 'Chat',
        ...(state.session ? { query: { at: writeAt(KIND.CHAT, state.session) } } : {}),
      })
    },
  },
  ...(state.session
    ? [{
      label: __('Delete for ever'),
      icon: 'lucide-trash-2',
      onClick: async () => {
        await workspace.forgetChat(state.session)
        state.session = ''
        await loadAssistant({ reload: true })
      },
    }]
    : []),
])
</script>
