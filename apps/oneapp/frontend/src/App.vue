<template>
  <FrappeUIProvider>
    <AppShell
      v-if="session.loaded && session.isLoggedIn"
      :scroll="false"
      :chrome="!$route.meta.focused"
      :entries="railSpaces"
      :active-entry="activeSpaceCode"
      :entries-to="{ name: 'Launcher' }"
      :workspace="workspace"
      :nav-items="nav"
      :menu-items="menuItems"
      :user="identity"
    >
      <template #sidebar>
        <!-- Mail is not inside a space — the addresses somebody holds do not
             change when they switch space — so on that route the mailboxes go
             in the sidebar. -->
        <MailSidebar v-if="$route.name === 'Mail'" />
        <!-- Files are not inside a space either: an attachment on a project
             and a drawing nobody has filed are the same row in the same
             table. -->
        <DriveSidebar
          v-else-if="$route.name === 'Drive'"
          :place="$route.query.place || 'home'"
        />
        <!-- And the diary's, which is the list of calendars it merges. -->
        <DiarySidebar v-else-if="$route.name === 'Calendar'" />
        <!-- And the assistant's, which is this person's own conversations. -->
        <ChatSidebar v-else-if="$route.name === 'Chat'" />
        <SpaceSidebar v-else />
      </template>

      <!-- The surfaces that are not spaces: quick access from the bar,
           beside the switcher rather than under it. Everything here has a row
           in the More sheet below, because a phone draws no bar. -->
      <template #topbar>
        <RailSurface v-for="one in surfaces" :key="one.key" :surface="one" />
      </template>

      <!-- What is about you rather than about the workspace, at the far end. -->
      <template #topbar-end>
        <NotificationBell />
        <RailAccount />
      </template>

      <!--
        The page, and the assistant beside it.

        The shell's own scroll region is switched off (`:scroll="false"`) and
        this column owns it instead, because a panel inside a scrolling region
        scrolls away with the page. One path rather than two: a pane route's
        inner panes own their scrollers and this column simply does not
        overflow, which is what the shell was doing for them anyway.
      -->
      <div class="flex h-full min-h-0">
        <div
          class="flex min-h-0 min-w-0 flex-1 flex-col"
          :class="$route.meta.pane ? '' : 'overflow-auto'"
        >
          <!--
            Keyed on the path, not the full path. A screen, a view type, a saved
            view and an open record are all query parameters, and keying on the
            query tore the page down and rebuilt it to open a dialog.
          -->
          <router-view :key="$route.path" />
        </div>

        <AssistantPanel />
      </div>
    </AppShell>

    <!-- Outside the shell so it survives a layout swap, and a dialog rather
         than a route because settings overlay whatever you were doing. -->
    <SettingsShell v-if="session.loaded && session.isLoggedIn" />


    <div v-else-if="sessionResource.error" class="grid h-screen place-items-center p-6">
      <div class="max-w-sm text-center">
        <p class="text-base-medium text-ink-gray-8">
          {{ __('Your workspace did not load') }}
        </p>
        <p class="mt-1.5 text-p-base text-ink-gray-6">
          {{ __('Check your connection, then try again.') }}
        </p>
        <Button class="mt-4" variant="solid" :label="__('Try again')" @click="session.reload()" />
      </div>
    </div>

    <!-- The wait before there is anything to show. A workspace that set a
         splash image gets its own mark here rather than our spinner alone —
         which is the whole of what `Website Settings.splash_image` was for, and
         until now nothing read it. -->
    <div v-else class="grid h-screen place-items-center">
      <div class="flex flex-col items-center gap-5">
        <img
          v-if="brand.splash"
          :src="brand.splash"
          :alt="session.tenant?.name || TENANT_APP"
          class="max-h-24 max-w-64 object-contain"
        />
        <LoadingIndicator class="size-5 text-ink-gray-5" />
      </div>
    </div>

    <!--
      The same feed, for a phone — and after the chain above rather than inside
      it, because a `v-else-if` has to be the immediately next sibling of its
      `v-if`. A phone has no rail, so the bell has nowhere to be, and the sheet
      is already the phone's answer to "where is the rest of it".
    -->
    <Dialog v-if="session.isLoggedIn" v-model="showNotifications">
      <NotificationList @opened="showNotifications = false" />
    </Dialog>
  </FrappeUIProvider>
</template>

<script setup>
import { TENANT_APP } from '@/lib/runtime/brand'
import { brand } from '@/lib/runtime/boot'
import { __ } from '@/lib/runtime/translate'
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider, Button, Dialog, LoadingIndicator, usePageMeta } from '@/ui'
import AppShell from './components/AppShell.vue'
import SpaceSidebar from './components/SpaceSidebar.vue'
import MailSidebar from './components/mail/MailSidebar.vue'
import DiarySidebar from './components/diary/DiarySidebar.vue'
import ChatSidebar from './components/chat/ChatSidebar.vue'
import AssistantPanel from './components/chat/AssistantPanel.vue'
import DriveSidebar from './components/drive/DriveSidebar.vue'
import RailAccount from './components/RailAccount.vue'
import NotificationBell from './components/notifications/NotificationBell.vue'
import RailSurface from './components/RailSurface.vue'
import NotificationList from './components/notifications/NotificationList.vue'
import SettingsShell from './components/settings/SettingsShell.vue'
import { useNav } from '@/lib/shell/nav'
import { followNotifications, notifications } from '@/lib/shell/notifications'
import { session, sessionResource } from '@/lib/shell/session'
import { fullName, email, userImage } from '@/lib/shell/user'
import { followMail } from '@/lib/shell/mail'
import { loadAssistant } from '@/lib/shell/assistant'

const route = useRoute()

// The rail is the workspace's spaces. This is the one place they are enumerated
// for navigation; the sidebar belongs to whichever is active.
const railSpaces = computed(() =>
  session.spaces.map((space) => ({
    key: space.space_code,
    label: space.space_label,
    // The manifest's own logo where there is one, so a space reads as itself
    // rather than as a letter. `brand` travels beside it because a mark beats
    // both — see `components/brand/SpaceFace.vue`.
    image: space.logo || null,
    brand: space.brand || '',
    description: space.description,
    to: { name: 'Screen', params: { spaceCode: space.space_code } },
  })),
)

const activeSpaceCode = computed(() => route.params.spaceCode || '')

// One list, rendered twice: the sidebar on a desktop, the bottom bar and its
// More sheet on a phone. Declared in `lib/shell/nav.js` so the two cannot
// drift.
const { nav, surfaces } = useNav()

// A phone has no rail, so the account menu's entries have to reach the More
// sheet instead.
const showNotifications = ref(false)

/**
 * The More sheet: everything the rail's footer offers, for a phone that has no
 * rail. Mail sat in the rail's foot and nowhere else, so on a phone the only
 * way to it was typing the URL.
 */
const menuItems = computed(() => [
  // The rail footer's own destinations, from the one place navigation is
  // declared — settings among them now, rather than an admin-only row written
  // here as well. Named with their count: on a phone this row is the only
  // thing that says there is anything here.
  //
  // `act` becomes `onClick` because a surface that opens something over the
  // page has no route to push, and `settings: true` marks the one row the
  // drawer gives its own place to (see AppShell's `settingsItem`).
  ...surfaces.value.map((one) => ({
    ...one,
    label: one.count ? `${one.label} (${one.count})` : one.label,
    ...(one.act ? { onClick: one.act } : {}),
    ...(one.key === 'settings' ? { settings: true } : {}),
  })),
  {
    // Named with its count, for the reason above.
    label: notifications.unread
      ? __('Notifications ({0})', [notifications.unread])
      : __('Notifications'),
    icon: 'lucide-bell',
    onClick: () => {
      showNotifications.value = true
    },
  },
])

// One subscription for the app, started as soon as there is a session. The
// server pokes; the store decides whether to refetch the rows or only the
// count.
watch(
  () => session.isLoggedIn,
  (yes) => yes && followNotifications(),
  { immediate: true },
)

// The same shape, for the same reason: what the shell offers cannot be decided
// by a part of the shell that a phone never draws.
watch(
  () => session.isLoggedIn,
  (yes) => yes && followMail(),
  { immediate: true },
)

// And once, for the same reason: whether the rail offers an assistant is not
// the assistant page's to decide, and a phone never draws that page's rail.
watch(
  () => session.isLoggedIn,
  (yes) => yes && loadAssistant(),
  { immediate: true },
)

// The corner's own face: the workspace, drawn from what it chose for its tab.
// A workspace that set no image gets its initial, which is what SpaceFace does
// with a space that named no mark.
const workspace = computed(() => ({
  label: session.tenant?.name || TENANT_APP,
  logo: brand.favicon || null,
}))

const identity = computed(() => ({
  name: fullName.value,
  email: email.value,
  avatar: userImage.value,
  subtitle: session.tenant?.name || '',
}))

// The tab: what this workspace is called, and its own icon. The favicon was a
// literal in `index.html` — ours — so a workspace that had chosen one saw it on
// the sign-in page and then ours on every page after it. `icon` is frappe-ui's
// own hook for exactly this; undefined leaves the built-in in place.
usePageMeta(() => ({
  title: session.tenant?.name || TENANT_APP,
  icon: brand.favicon || undefined,
}))
</script>
