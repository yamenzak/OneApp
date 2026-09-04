<template>
  <!--
    The mail rail *is* the sidebar, not a third column beside it.

    Mail is not inside a space — the addresses somebody holds do not change
    when they switch space — so on this route the shell's sidebar has nothing
    space-shaped to show, and drawing the workspace's own list beside a
    mailbox list gave the page two navigation columns arguing about which one
    you were in. Same component slot, same width, same collapse: what changes
    is what is in it.
  -->
  <Sidebar
    v-model:collapsed="collapsed"
    :width="`${width}px`"
    class="border-r border-outline-gray-1"
  >
    <SidebarHeader title="Mail" :subtitle="session.tenant?.name" :show-logo="false" />

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pb-6">
      <nav class="space-y-0.5">
        <!--
          An address, and under it that mailbox's own folders — the Applicants
          and Suppliers somebody spent years sorting into. Read off the server
          itself; see `oneapp_core/email/folders.py`.
        -->
        <template v-for="one in shown" :key="one.key">
          <SidebarItem
            :icon="one.icon"
            :to="{ name: 'Mail', query: { folder: one.key } }"
            :active="folder === one.key"
            :class="one.depth ? 'ms-3 border-s border-outline-gray-1 ps-1' : ''"
            data-slot="mail-folder"
          >
            <span class="flex-1 truncate text-sm" :class="one.depth ? SUB : ''">
              {{ one.label }}
            </span>
            <template v-if="one.unread" #suffix>
              <Badge theme="blue" :label="String(one.unread)" />
            </template>
          </SidebarItem>
        </template>

        <!-- Deleted mail, spam and drafts. Mirrored, because a mirror that
             silently omits folders is one nobody can trust, and behind a
             click, because a rail that opens on somebody's junk is a rail
             nobody wants. -->
        <SidebarItem
          v-if="quiet.length && !collapsed"
          :icon="showQuiet ? 'lucide-chevron-down' : 'lucide-chevron-right'"
          :active="false"
          data-slot="mail-more-folders"
          @click="showQuiet = !showQuiet"
        >
          <span class="flex-1 truncate text-sm text-ink-gray-6">
            {{ showQuiet ? 'Fewer folders' : 'More folders' }}
          </span>
        </SidebarItem>
      </nav>
    </ScrollArea>

    <div class="mt-auto shrink-0">
      <div class="flex flex-col gap-1 p-2">
        <!--
          Where mailboxes are added. The rail lists what somebody has; adding
          one is a form with a password in it, which belongs in Settings beside
          the addresses the workspace itself owns — one screen for "which
          addresses exist and who may use them", not two.
        -->
        <SidebarItem
          v-if="!collapsed"
          icon="lucide-plus"
          :active="false"
          data-slot="mail-add-mailbox"
          @click="openSettings('mail')"
        >
          <span class="flex-1 truncate text-sm text-ink-gray-6">Add a mailbox</span>
        </SidebarItem>
        <SidebarItem
          v-if="mail.mailboxes.length && !collapsed"
          icon="lucide-refresh-cw"
          :active="false"
          data-slot="mail-refresh-folders"
          @click="refreshMail()"
        >
          <span class="flex-1 truncate text-sm text-ink-gray-6">
            {{ mail.refreshing ? 'Refreshing…' : 'Refresh folders' }}
          </span>
        </SidebarItem>
        <SidebarCollapseToggle />
      </div>
    </div>
  </Sidebar>

  <Resizer
    v-if="!collapsed"
    v-model="width"
    :min="MIN"
    :default-size="DEFAULT"
    :max="MAX"
    side="right"
    label="the sidebar"
    remember="onespace.sidebar"
    slot-name="sidebar-resizer"
  />
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  Badge,
  ScrollArea,
  Sidebar,
  SidebarCollapseToggle,
  SidebarHeader,
  SidebarItem,
} from '@/ui'
import Resizer from './screen/Resizer.vue'
import { loadMail, mail, refreshMail } from '../lib/mail'
import { session } from '../lib/session'
import { openSettings, settings } from '../lib/settings'

const SUB = 'text-ink-gray-6'

const route = useRoute()
const folder = computed(() => String(route.query.folder || 'all'))

const showQuiet = ref(false)

// The quiet folders stay folded unless asked for — or unless one of them is
// the folder currently open, because collapsing the row somebody is standing
// on is how a rail loses them.
const shown = computed(() =>
  mail.folders.filter((one) => !one.quiet || showQuiet.value || folder.value === one.key),
)
const quiet = computed(() => mail.folders.filter((one) => one.quiet))

onMounted(() => loadMail())
// Reloaded when the settings dialog closes: connecting or disconnecting a
// mailbox is the one thing that changes this list without the page moving, and
// it happens in there. Watching the dialog rather than publishing an event
// keeps the settings panel from having to know a rail exists.
watch(
  () => settings.open,
  (isOpen, was) => {
    if (was && !isOpen) loadMail({ reload: true })
  },
)

// The same width, collapse state and storage key as the space sidebar: it is
// the same column, and a rail that changed width when you opened mail would
// read as the page jumping.
const MIN = 180
const DEFAULT = 224
const MAX = 360
const REMEMBERED = 'onespace.sidebar-collapsed'
const width = ref(DEFAULT)
const collapsed = ref(localStorage.getItem(REMEMBERED) === '1')
watch(collapsed, (shut) => localStorage.setItem(REMEMBERED, shut ? '1' : '0'))
</script>
