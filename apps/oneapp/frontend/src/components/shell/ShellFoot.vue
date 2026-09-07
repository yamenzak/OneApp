<template>
  <!--
    The foot of whichever column is showing: the same three rows under the
    space's screens, under Mail's folders, under the Drive's places.

    It is one component and not three copies because it was three copies for a
    while — the quota meter existed under the spaces and nowhere else, so the
    number that decides whether an upload is refused was invisible on the
    screen you upload from.

    Rows, in the order they are reached for: the surfaces that are not inside
    any space, then you and what is waiting for you, then the two controls that
    belong to the column itself.
  -->
  <div class="mt-auto shrink-0 p-2">
    <!-- A meter is a number and a bar, and neither survives 3rem of width. -->
    <QuotaMeter v-if="!collapsed" class="mb-2 px-1" />

    <div class="flex flex-col gap-1 border-t border-outline-gray-1 pt-2">
      <div class="flex flex-wrap items-center gap-0.5" :class="collapsed ? 'justify-center' : ''">
        <SurfaceLink v-for="one in quick" :key="one.key" :surface="one" />
      </div>

      <div class="flex items-center gap-1" :class="collapsed ? 'flex-col' : ''">
        <!-- Wrapped rather than given the class: UserMenu's own root is a
             Dropdown carrying `w-full`, so a `flex-1` on it fought that and
             the bell beside it was pushed out of a column that hides its own
             overflow. -->
        <div class="min-w-0 flex-1">
          <UserMenu
            :name="fullName"
            :email="email"
            :avatar="userImage"
            :extra="accountRows"
          />
        </div>
        <NotificationBell />
      </div>

      <div class="flex items-center gap-1" :class="collapsed ? 'flex-col' : ''">
        <SidebarCollapse class="min-w-0 flex-1" />
        <!--
          Settings is a dialog over whatever you are looking at rather than a
          place, so it is a button and not a `SidebarItem`. It sits beside the
          collapse because both are about the frame rather than about the work.
        -->
        <Button
          v-if="settings"
          variant="ghost"
          :icon="settings.icon"
          :label="settings.label"
          :tooltip="settings.label"
          :data-slot="`${settings.key}-link`"
          @click="settings.act?.()"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/ui'
import QuotaMeter from '../QuotaMeter.vue'
import SidebarCollapse from '../SidebarCollapse.vue'
import SurfaceLink from './SurfaceLink.vue'
import UserMenu from '../UserMenu.vue'
import NotificationBell from '../notifications/NotificationBell.vue'
import { useNav } from '@/lib/shell/nav'
import { useSidebar } from '@/lib/shell/sidebar'
import { fullName, email, userImage } from '@/lib/shell/user'
import { __ } from '@/lib/runtime/translate'

const router = useRouter()
const { collapsed } = useSidebar()
const { surfaces } = useNav()

// Two of the surfaces are not quick access and are not dropped: settings has
// its own place in the last row, and the marketplace is inside the switcher —
// adding a space is something you do to the workspace, so it belongs where the
// workspace's spaces are listed rather than beside the day's work.
const ELSEWHERE = ['settings', 'marketplace']

const quick = computed(() => surfaces.value.filter((one) => !ELSEWHERE.includes(one.key)))

const settings = computed(() => surfaces.value.find((one) => one.key === 'settings') || null)

// The one row UserMenu does not already carry. Appearance and signing out are
// its own; who you are is a page.
const accountRows = computed(() => [
  {
    label: __('Account'),
    icon: 'lucide-circle-user',
    onClick: () => router.push({ name: 'Account' }),
  },
])
</script>
