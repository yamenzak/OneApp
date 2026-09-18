<template>
  <FrappeUIProvider>
    <!--
      A page somebody reached with a link and no account.

      Ahead of everything, and outside the shell, because the shell is the
      workspace: a rail of spaces, a sidebar, a settings dialog, an assistant
      and a notification feed, every one of which needs a session this reader
      does not have. What they get instead is the file and nothing around it,
      which is also all they were given.

      `meta.public` is the only route flag that reaches this far up; the
      router's guard reads the same one to let the navigation happen at all.
    -->
    <router-view v-if="$route.meta.public" />

    <template v-else>
    <AppShell
      v-if="session.loaded && session.isLoggedIn"
      :scroll="false"
      :chrome="!$route.meta.focused"
      :framed="!$route.meta.bare"
      :entries="railSpaces"
      :active-entry="activeSpaceCode"
      :entries-to="WORKSPACE"
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
          :folder="$route.query.folder || ''"
        />
        <!-- And the diary's, which is the list of calendars it merges. -->
        <DiarySidebar v-else-if="$route.name === 'Calendar'" />
        <!-- And the assistant's, which is this person's own conversations. -->
        <ChatSidebar v-else-if="$route.name === 'Chat'" />
        <SpaceSidebar v-else />
      </template>

      <!-- The apps, and you, along the bottom. A slot of the shell's rather
           than a fixed row of its own, so the page above it is laid out with
           the dock's height taken off rather than sliding under it. -->
      <template #dock>
        <Dock />
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
          data-slot="page-body"
        >
          <!--
            Keyed on the path, not the full path. A screen, a view type, a saved
            view and an open record are all query parameters, and keying on the
            query tore the page down and rebuilt it to open a dialog.
          -->
          <router-view :key="$route.path" />
        </div>
      </div>
    </AppShell>

    <!-- Fixed to the viewport rather than a column in the row above: it is
         about wherever you happen to be, so it is the one surface with no
         claim on the layout. See the component. -->
    <AssistantWidget />

    <!-- One box over every space, on Ctrl+K. Mounted here rather than in the
         shell because the shell is generated and shared with the control
         plane, and this knows what a space is. Always mounted, hidden until
         it is opened: the shortcut is its own listener and has to be bound
         whatever page is showing. -->
    <Finder v-if="session.isLoggedIn" />

    <!-- The list you came from, while you read one of its rows. Always
         mounted, hidden until it is opened: a `<Teleport>` resolves its target
         when it patches, and a target that appears in the same tick as the
         teleport wanting it is one Vue warns about and then ignores. -->
    <PipWindow v-if="session.isLoggedIn" />

    <!-- OneCloud, on the desk. Here for the same reason the tray is: mounted
         once for the session, outside the layout, so a folder opened beside a
         project survives the page changing under it. -->
    <!-- OneCloud and the three editors, which are the same window over four
         different `where`s — `onestorage/lib/window.js`. -->
    <template v-if="session.isLoggedIn">
      <DriveWindow v-for="one in DRIVE_APPS" :key="one.id" :id="one.id" />
      <!-- And every document or sheet somebody has open, each in its own —
           `onestorage/lib/editing.js`. -->
      <FileWindows />
      <!-- And the mail, which is the one people keep open beside everything
           else: a reply is almost always about what is on the page behind it.
           The diary is the other: the week is a thing you check *against* what
           you are doing. -->
      <MailWindow />
      <DiaryWindow />
      <!-- And OneTask, which is neither: a place to put a thought down and a
           list to tick, over the same ERPNext tasks OneProject's board draws.
           `docs/WORK.md` §12. -->
      <TaskWindow />
      <!-- And OneForms, which is the same shape again: a list of doors you
           glance at while writing the thing that needs one. -->
      <FormsWindow />
    </template>

    <!--
      What is going up, wherever it was started from — §D3.

      It was rendered in one place, the Drive, so the queue that survives a
      navigation existed only if you happened to have started there. Attaching
      a 200 MB video to a record worked and you watched it inside a dialog you
      could not close.

      Here rather than inside `AppShell` because the shell is generated into
      both SPAs and the control plane has no files; and outside it so an upload
      survives the layout swapping under it.
    -->
    <UploadTray v-if="session.isLoggedIn" />


    <div v-else-if="sessionResource.error" class="grid h-screen place-items-center p-6">
      <div class="max-w-sm text-center">
        <p class="text-base-medium text-ink-primary">
          {{ __('Your workspace did not load') }}
        </p>
        <p class="mt-1.5 text-p-base text-ink-secondary">
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
        <LoadingIndicator class="size-5 text-ink-muted" />
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
    </template>
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
import ChatSidebar from '@/modules/oneai/components/chat/ChatSidebar.vue'
import AssistantWidget from '@/modules/oneai/components/chat/AssistantWidget.vue'
import Dock from '@/modules/onespace/components/desk/Dock.vue'
import Finder from '@/modules/onespace/components/shell/Finder.vue'
import PipWindow from '@/modules/onespace/components/desk/PipWindow.vue'
import DriveWindow from '@/modules/onestorage/components/DriveWindow.vue'
import MailWindow from '@/modules/onemail/components/MailWindow.vue'
import DiaryWindow from '@/modules/onecalendar/components/DiaryWindow.vue'
import TaskWindow from '@/modules/onetask/components/TaskWindow.vue'
import FormsWindow from '@/modules/oneforms/components/FormsWindow.vue'
import FileWindows from '@/modules/onestorage/components/FileWindows.vue'
import { APPS as DRIVE_APPS } from '@/modules/onestorage/lib/window'
import DriveSidebar from '@/modules/onestorage/components/DriveSidebar.vue'
import UploadTray from '@/modules/onestorage/components/UploadTray.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceSwitcher from '@/modules/onespace/components/shell/SpaceSwitcher.vue'
import NotificationList from '@/modules/onespace/components/notifications/NotificationList.vue'
import LegalGate from '@/modules/onelegal/components/LegalGate.vue'
import { useNav } from '@/modules/onespace/lib/shell/nav'
import { WORKSPACE } from '@/shared/composables/useCrumbs'
import { followNotifications, notifications } from '@/modules/onespace/lib/shell/notifications'
import { session, sessionResource } from '@/modules/onespace/lib/shell/session'
import { fullName, email, userImage } from '@/modules/onespace/lib/shell/user'
import { followMail } from '@/modules/onespace/lib/shell/mail'
import { loadAssistant } from '@/modules/oneai/lib/assistant'

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
const { nav, services } = useNav()

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
  // The marketplace is not among them: it is a tile on the switcher's board,
  // on a phone as on a desktop, and a sheet that offered it in both places
  // would offer it twice. The catalogue leaves it out of this list.
  ...services.value.map((one) => ({
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
