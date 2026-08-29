<template>
  <FrappeUIProvider>
    <AppShell
      v-if="session.loaded && session.isLoggedIn"
      :apps="railApps"
      :active-app="activeAppCode"
      :nav-items="nav"
      :user="identity"
    >
      <template #sidebar>
        <AppSidebar />
      </template>

      <template #rail-footer>
        <RailAccount />
      </template>

      <router-view :key="$route.fullPath" />
    </AppShell>

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
  </FrappeUIProvider>
</template>

<script setup>
import { TENANT_APP } from './lib/brand'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { FrappeUIProvider, Button, LoadingIndicator, usePageMeta } from '@/ui'
import AppShell from './components/AppShell.vue'
import AppSidebar from './components/AppSidebar.vue'
import RailAccount from './components/RailAccount.vue'
import { useNav } from './lib/nav'
import { session, sessionResource } from './lib/session'
import { fullName, email, userImage } from './lib/user'

const route = useRoute()

// The rail is the workspace's apps. This is the one place they are enumerated
// for navigation; the sidebar then belongs to whichever is active.
const railApps = computed(() =>
  session.apps.map((app) => ({
    key: app.app_code,
    label: app.app_label,
    description: app.description,
    to: { name: 'App', params: { appCode: app.app_code } },
  })),
)

const activeAppCode = computed(() => route.params.appCode || '')

// One list, rendered twice: the sidebar on a desktop, the bottom bar and its
// More sheet on a phone. Declared in lib/nav.js so the two cannot drift — and
// an app that declares more sections than the bar has slots keeps the rest
// reachable in the sheet rather than losing them.
const { nav } = useNav()

const identity = computed(() => ({
  name: fullName.value,
  email: email.value,
  avatar: userImage.value,
  subtitle: session.tenant?.name || '',
}))

usePageMeta(() => ({ title: session.tenant?.name || TENANT_APP }))
</script>
