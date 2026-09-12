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
    <!-- No header. The bar's corner names the workspace directly above this and
         the trail beside it names where you are, so a header here was a third
         telling of the same two words — and its own dropdown, which read as a
         second switcher. -->

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

      <p v-if="!state.sessions.length" class="px-2 py-3 text-p-sm text-ink-muted">
        {{ __('Nothing yet.') }}
      </p>
    </ScrollArea>

    <ShellFoot />
  </Sidebar>

  <SidebarResizer />
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Button, ScrollArea, Sidebar, SidebarItem,
} from '@/ui'
import ShellFoot from '@/modules/onespace/components/shell/ShellFoot.vue'
import SidebarResizer from '@/modules/onespace/components/SidebarResizer.vue'
import { assistant as state, loadAssistant } from '@/modules/onespace/lib/shell/assistant'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { __ } from '@/shared/lib/runtime/translate'

const { collapsed, width } = useSidebar()
const route = useRoute()

const open = computed(() => route.query.chat || '')

loadAssistant()
</script>
