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
    class="hidden w-96 shrink-0 flex-col border-s border-outline-gray-1 bg-surface-base sm:flex"
    :aria-label="assistantName"
    data-slot="assistant-panel"
  >
    <div
      class="flex shrink-0 items-center justify-between gap-2 border-b border-outline-gray-1 px-4 py-3"
    >
      <div class="min-w-0">
        <div class="flex min-w-0 items-center gap-2">
          <Avatar size="sm" :image="assistantAvatar" :label="assistantName" />
          <p class="truncate text-p-base font-medium text-ink-gray-8">{{ assistantName }}</p>
        </div>
        <!-- What it is scoped to, in the header rather than only in the empty
             state: the empty state is gone the moment anybody asks anything. -->
        <p v-if="state.on?.label" class="truncate text-p-xs text-ink-gray-5">
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
          :label="__('Close the assistant')"
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
import { Avatar, Button, Dropdown } from '@/ui'
import ChatPanel from './ChatPanel.vue'
import {
  assistant as state,
  assistantAvatar,
  assistantName,
  closeAssistant,
  loadAssistant,
} from '@/lib/shell/assistant'
import { workspace } from '@/lib/workspace'
import { __ } from '@/lib/runtime/translate'

const router = useRouter()

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
    icon: 'plus',
    onClick: () => { state.session = '' },
  },
  {
    label: __('Open as a page'),
    icon: 'maximize-2',
    onClick: () => {
      closeAssistant()
      router.push({
        name: 'Chat',
        ...(state.session ? { query: { chat: state.session } } : {}),
      })
    },
  },
  ...(state.session
    ? [{
      label: __('Delete this conversation'),
      icon: 'trash-2',
      onClick: async () => {
        await workspace.forgetChat(state.session)
        state.session = ''
        await loadAssistant({ reload: true })
      },
    }]
    : []),
])
</script>
