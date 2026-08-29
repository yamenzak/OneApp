<template>
  <Sidebar class="border-r border-outline-gray-1">
    <SidebarHeader>
      <div class="flex items-center gap-2 px-1 py-0.5">
        <Avatar :label="session.tenant?.name || 'OneApp'" shape="square" size="lg" />
        <div class="min-w-0">
          <p class="truncate text-base font-medium text-ink-gray-8">
            {{ session.tenant?.name || 'OneApp' }}
          </p>
          <p
            v-if="session.tenant?.status && session.tenant.status !== 'Active'"
            class="truncate text-xs text-ink-amber-3"
          >
            {{ session.tenant.status }}
          </p>
          <p v-else class="truncate text-xs text-ink-gray-5">{{ session.plan || '' }}</p>
        </div>
      </div>
    </SidebarHeader>

    <SidebarSection>
      <SidebarLabel label="Apps" />
      <SidebarItem
        v-for="app in session.apps"
        :key="app.app_code"
        :label="app.app_label"
        :to="`/app/${app.app_code}`"
        :active="$route.params.appCode === app.app_code"
      >
        <template #prefix>
          <Icon :name="app.icon || 'lucide-square'" class="size-4 text-ink-gray-7" />
        </template>
      </SidebarItem>
    </SidebarSection>

    <template #footer>
      <div class="p-2">
        <QuotaMeter class="mb-2" />
        <UserMenu
          :name="session.user?.full_name"
          :email="session.user?.name"
          :subtitle="session.tenant?.plan"
          :extra="extraMenuItems"
        />
      </div>
    </template>
  </Sidebar>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sidebar, SidebarHeader, SidebarSection, SidebarLabel, SidebarItem,
  Avatar, Icon,
} from '@/ui'
import QuotaMeter from './QuotaMeter.vue'
import UserMenu from './UserMenu.vue'
import { session } from '../lib/session'

const router = useRouter()

// Dark mode and logout come from UserMenu, which every surface shares. There is
// deliberately no link to the desk: it exposes the whole schema behind a UI that
// was never designed to be a boundary, so it is not part of the product for
// anyone, ourselves included.
const extraMenuItems = computed(() => [
  {
    label: 'Account',
    icon: 'lucide-circle-user',
    onClick: () => router.push({ name: 'Account' }),
  },
])
</script>
