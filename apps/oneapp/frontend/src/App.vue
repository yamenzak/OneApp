<template>
  <FrappeUIProvider>
    <AppShell
      v-if="session.loaded && session.isLoggedIn"
      :scroll="false"
      :chrome="!$route.meta.focused"
      :framed="!$route.meta.bare"
      :entries="railSpaces"
      :active-entry="activeSpaceCode"
      :entries-to="{ name: 'Launcher' }"
      :entry-extra="entryExtra"
      :nav-items="nav"
      :menu-items="menuItems"
      :user="identity"
    >
      <!-- The corner. Its own component because it knows what a space is and
           the shell does not. -->
      <template #corner>
        <SpaceSwitcher />
      </template>

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

    <!--
      Last, and over everything: the agreements. It draws nothing at all unless
      something is outstanding, and when it does it cannot be dismissed —
      `oneapp/onelegal/gate.py` says why the workspace's half and the person's
      half are asked separately.
    -->
    <LegalGate v-if="session.isLoggedIn" />
  </FrappeUIProvider>
</template>

<script setup>
import { TENANT_APP } from '@/shared/lib/runtime/brand'
import { brand } from '@/shared/lib/runtime/boot'
import { __ } from '@/shared/lib/runtime/translate'
import { computed, h, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { FrappeUIProvider, Button, Dialog, LoadingIndicator, usePageMeta } from '@/ui'
import AppShell from '@/modules/onespace/components/AppShell.vue'
import SpaceSidebar from '@/modules/onespace/components/SpaceSidebar.vue'
import MailSidebar from '@/modules/onemail/components/MailSidebar.vue'
import DiarySidebar from '@/modules/onecalendar/components/DiarySidebar.vue'
import ChatSidebar from '@/modules/onespace/components/chat/ChatSidebar.vue'
import AssistantPanel from '@/modules/onespace/components/chat/AssistantPanel.vue'
import DriveSidebar from '@/modules/onestorage/components/DriveSidebar.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceSwitcher from '@/modules/onespace/components/shell/SpaceSwitcher.vue'
import NotificationList from '@/modules/onespace/components/notifications/NotificationList.vue'
import SettingsShell from '@/modules/onespace/components/settings/SettingsShell.vue'
import LegalGate from '@/modules/onelegal/components/LegalGate.vue'
import { useNav } from '@/modules/onespace/lib/shell/nav'
import { followNotifications, notifications } from '@/modules/onespace/lib/shell/notifications'
import { session, sessionResource } from '@/modules/onespace/lib/shell/session'
import { fullName, email, userImage } from '@/modules/onespace/lib/shell/user'
import { followMail } from '@/modules/onespace/lib/shell/mail'
import { loadAssistant } from '@/modules/onespace/lib/shell/assistant'

const route = useRoute()
const router = useRouter()

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
  // The marketplace is not among them: it is a row inside the switcher, on a
  // phone as on a desktop, and a sheet that offers it in both places offers it
  // twice.
  ...surfaces.value.filter((one) => one.key !== 'marketplace').map((one) => ({
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

// The one row under the spaces: where a workspace gets another one. Its own
// mark rather than a lucide shop — the marketplace is one of ours, and every
// other place a space is offered already draws it that way. Absent for
// somebody who may not add one: `require_workspace_admin` on the control plane
// admits the owner and an Admin member, and a row leading to a page of
// refusals is worse than no row.
const entryExtra = computed(() =>
  session.isAdmin
    ? [{
      label: __('Add a space'),
      icon: () => h(BrandMark, { name: 'onemarket' }),
      onClick: () => router.push({ name: 'Marketplace' }),
    }]
    : [],
)

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
