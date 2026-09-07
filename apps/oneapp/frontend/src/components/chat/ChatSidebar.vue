<template>
  <!--
    The conversations this person has had with the assistant.

    Theirs alone — the transcripts are stored per person, because two people
    asking the same question see different answers under their own roles, so a
    shared list would be a list of threads whose contents nobody else may read.

    The same `Sidebar` every other rail is. See `components/SpaceSidebar.vue`.
  -->
  <Sidebar
    v-model:collapsed="collapsed"
    :width="`${width}px`"
    class="border-e border-outline-gray-1"
  >
    <SidebarHeader :title="__('Assistant')" :subtitle="session.tenant?.name" :show-logo="false" />

    <div class="px-2 pb-2">
      <Button
        class="w-full"
        variant="subtle"
        icon-left="lucide-plus"
        :label="__('New chat')"
        data-slot="chat-rail-new"
        @click="$router.push({ name: 'Chat' })"
      />
    </div>

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pb-6">
      <nav class="space-y-0.5">
        <SidebarItem
          v-for="one in state.sessions"
          :key="one.name"
          :active="one.name === open"
          data-slot="chat-thread"
          icon="lucide-message-square"
          @click="$router.push({ name: 'Chat', query: { chat: one.name } })"
        >
          <span class="flex-1 truncate text-sm">{{ one.title }}</span>
        </SidebarItem>
      </nav>

      <p v-if="!state.sessions.length" class="px-2 py-3 text-p-sm text-ink-gray-5">
        {{ __('Nothing yet.') }}
      </p>
    </ScrollArea>

    <div class="mt-auto shrink-0">
      <div class="p-2">
        <SidebarCollapse />
      </div>
    </div>
  </Sidebar>

  <SidebarResizer />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Button, ScrollArea, Sidebar, SidebarHeader, SidebarItem,
} from '@/ui'
import SidebarCollapse from '../SidebarCollapse.vue'
import SidebarResizer from '../SidebarResizer.vue'
import { assistant as state, loadAssistant } from '@/lib/shell/assistant'
import { session } from '@/lib/shell/session'
import { useSidebar } from '@/lib/shell/sidebar'
import { __ } from '@/lib/runtime/translate'

const { collapsed, width } = useSidebar()
const route = useRoute()

const open = computed(() => route.query.chat || '')

loadAssistant()
</script>
