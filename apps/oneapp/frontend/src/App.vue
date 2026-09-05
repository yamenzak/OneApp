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
        <!--
          Mail is not inside a space — the addresses somebody holds do not
          change when they switch space — so on that route the sidebar has
          nothing space-shaped to show, and the mailboxes go here rather than
          into a third column beside a workspace list nobody asked for.
        -->
        <MailSidebar v-if="$route.name === 'Mail'" />
        <!-- Files are not inside a space either: an attachment on a project
             and a drawing nobody has filed are the same row in the same
             table. -->
        <DriveSidebar
          v-else-if="$route.name === 'Drive'"
          :place="$route.query.place || 'home'"
        />
        <SpaceSidebar v-else />
      </template>

      <!--
        The surfaces that are not spaces, then the alert, then you. Everything
        here has a row in the More sheet below, because a phone draws no rail
        and the sheet is its only way to any of them.
      -->
      <template #rail-footer>
        <RailSurface v-for="one in surfaces" :key="one.key" :surface="one" />
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
import MailSidebar from './components/mail/MailSidebar.vue'
import DriveSidebar from './components/drive/DriveSidebar.vue'
import RailAccount from './components/RailAccount.vue'
import NotificationBell from './components/notifications/NotificationBell.vue'
import RailSurface from './components/RailSurface.vue'
import NotificationList from './components/notifications/NotificationList.vue'
import SettingsShell from './components/settings/SettingsShell.vue'
import { useNav } from './lib/nav'
import { followNotifications, notifications } from './lib/notifications'
import { openSettings } from './lib/settings'
import { session, sessionResource } from './lib/session'
import { fullName, email, userImage } from './lib/user'
import { followMail } from './lib/mail'

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
const { nav, surfaces } = useNav()

// A phone has no rail, so the account menu's entries have to reach the More
// sheet instead — the same gap the console hit with its own settings.
const showNotifications = ref(false)

/**
 * The More sheet: everything the rail's footer offers, for a phone that has no
 * rail. That was already the rule this shell claimed to follow and was not —
 * Mail sat in the rail's foot and nowhere else, so on a phone the only way to
 * it was typing the URL. Files arrived the same way.
 */
const menuItems = computed(() => [
  ...(session.isAdmin
    ? [
        {
          label: 'Workspace settings',
          icon: 'lucide-settings',
          // Which row of the drawer this is, said rather than inferred from
          // being first — see AppShell's `settingsItem`.
          settings: true,
          onClick: () => openSettings(),
        },
      ]
    : []),
  // The rail footer's own destinations, from the one place navigation is
  // declared. Named with their count for the same reason Notifications is: on
  // a phone this row is the only thing that says there is anything here.
  ...surfaces.value.map((one) => ({
    ...one,
    label: one.count ? `${one.label} (${one.count})` : one.label,
  })),
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

// The same shape, for the same reason: what the shell offers cannot be decided
// by a part of the shell that a phone never draws. See `lib/mail`.
watch(
  () => session.isLoggedIn,
  (yes) => yes && followMail(),
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
