<template>
  <FrappeUIProvider>
    <AppShell
      v-if="session.loaded && session.isLoggedIn"
      :scroll="!$route.meta.pane"
      :entries="railSpaces"
      :active-entry="activeSpaceCode"
      :entries-to="{ name: 'Launcher' }"
      :nav-items="nav"
      :menu-items="menuItems"
      :user="identity"
    >
      <template #sidebar>
        <SpaceSidebar />
      </template>

      <template #rail-footer>
        <NotificationBell />
        <RailAccount />
      </template>

      <!--
        Keyed on the path, not the full path. A screen, a view type, a saved
        view and an open record are all query parameters, and the page watches
        every one of them — keying on the query as well tore the page down and
        rebuilt it to open a dialog, which reloaded the list underneath it.
        The path still changes between spaces, which is what the key is for.
      -->
      <router-view :key="$route.path" />
    </AppShell>

    <!-- Outside the shell so it survives a layout swap, and a dialog rather
         than a route because settings overlay whatever you were doing —
         closing should put you back, not navigate you away. -->
    <SettingsShell v-if="session.loaded && session.isLoggedIn" />


    <div v-else-if="sessionResource.error" class="grid h-screen place-items-center p-6">
      <div class="max-w-sm text-center">
        <p class="text-base-medium text-ink-gray-8">
          We couldn't load your workspace
        </p>
        <p class="mt-1.5 text-p-base text-ink-gray-6">This is usually temporary.</p>
        <Button class="mt-4" variant="solid" label="Try again" @click="session.reload()" />
      </div>
    </div>

    <div v-else class="grid h-screen place-items-center">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <!--
      The same feed, for a phone — and after the chain above rather than inside
      it, because a `v-else-if` has to be the immediately next sibling of its
      `v-if` and anything dropped between them breaks the whole ladder.

      A phone has no rail, so the bell has nowhere to be, and the rule this
      shell already follows is that everything in the rail's foot is reachable
      from the More sheet. A dialog rather than a second bell somewhere: the
      sheet is already the phone's answer to "where is the rest of it".
    -->
    <Dialog v-if="session.isLoggedIn" v-model="showNotifications">
      <NotificationList @opened="showNotifications = false" />
    </Dialog>
  </FrappeUIProvider>
</template>

<script setup>
import { TENANT_APP } from './lib/brand'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider, Button, Dialog, LoadingIndicator, usePageMeta } from '@/ui'
import AppShell from './components/AppShell.vue'
import SpaceSidebar from './components/SpaceSidebar.vue'
import RailAccount from './components/RailAccount.vue'
import NotificationBell from './components/NotificationBell.vue'
import NotificationList from './components/NotificationList.vue'
import SettingsShell from './components/settings/SettingsShell.vue'
import { useNav } from './lib/nav'
import { followNotifications, notifications } from './lib/notifications'
import { openSettings } from './lib/settings'
import { session, sessionResource } from './lib/session'
import { fullName, email, userImage } from './lib/user'

const route = useRoute()

// The rail is the workspace's spaces. This is the one place they are
// enumerated for navigation; the sidebar then belongs to whichever is active.
const railSpaces = computed(() =>
  session.spaces.map((space) => ({
    key: space.space_code,
    label: space.space_label,
    // The manifest's own logo where there is one, so a space reads as itself
    // on the rail rather than as a letter.
    image: space.logo || null,
    description: space.description,
    to: { name: 'Screen', params: { spaceCode: space.space_code } },
  })),
)

const activeSpaceCode = computed(() => route.params.spaceCode || '')

// One list, rendered twice: the sidebar on a desktop, the bottom bar and its
// More sheet on a phone. Declared in lib/nav.js so the two cannot drift — and
// a space that declares more screens than the bar has slots keeps the rest
// reachable in the sheet rather than losing them.
const { nav } = useNav()

// A phone has no rail, so the account menu's entries have to reach the More
// sheet instead — the same gap the console hit with its own settings.
const showNotifications = ref(false)

const menuItems = computed(() => [
  ...(session.isAdmin
    ? [{ label: 'Workspace settings', icon: 'lucide-settings', onClick: () => openSettings() }]
    : []),
  {
    // Named with its count for the same reason the bell's tooltip is: this row
    // is the only thing a phone has to tell somebody there is anything here.
    label: notifications.unread
      ? `Notifications (${notifications.unread})`
      : 'Notifications',
    icon: 'lucide-bell',
    onClick: () => {
      showNotifications.value = true
    },
  },
])

// One subscription for the app, started as soon as there is a session to start
// it for. The server pokes; the store decides whether to refetch the rows or
// only the count. See `lib/notifications.js`.
watch(
  () => session.isLoggedIn,
  (yes) => yes && followNotifications(),
  { immediate: true },
)

const identity = computed(() => ({
  name: fullName.value,
  email: email.value,
  avatar: userImage.value,
  subtitle: session.tenant?.name || '',
}))

usePageMeta(() => ({ title: session.tenant?.name || TENANT_APP }))
</script>
