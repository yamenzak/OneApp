<template>
  <!--
    The foot of whichever column is showing: the same three rows under the
    space's screens, under Mail's folders, under the Drive's places.

    It is one component and not three copies because it was three copies for a
    while — the quota meter existed under the spaces and nowhere else, so the
    number that decides whether an upload is refused was invisible on the
    screen you upload from.

    Two rows: the surfaces that are not inside any space, then you and what is
    waiting for you. Folding the column is in the bar and settings is in the
    account menu, because neither is a destination and this is a row of them.
  -->
  <div class="mt-auto shrink-0 p-2">
    <!-- A meter is a number and a bar, and neither survives 3rem of width. -->
    <QuotaMeter v-if="!collapsed" class="mb-2 px-1" />

    <div class="flex flex-col">
      <Divider class="mb-1" />

      <!--
        Spread rather than packed. Four icons bunched at the start of a 224px
        row leave a hole where the rest of the column has content, and the eye
        reads the hole as something missing; across the width they read as a
        set. Packed again when the column is 3rem wide, where there is no width
        to spread across.
      -->
      <div
        class="flex flex-wrap items-center px-1 py-0.5"
        :class="collapsed ? 'justify-center gap-0.5' : 'justify-between'"
      >
        <SurfaceLink v-for="one in quick" :key="one.key" :surface="one" />
      </div>

      <Divider class="my-1" />

      <div class="flex items-center gap-1" :class="collapsed ? 'flex-col' : ''">
        <!-- Wrapped rather than given the class: UserMenu's own root is a
             Dropdown carrying `w-full`, so a `flex-1` on it fought that and
             the bell beside it was pushed out of a column that hides its own
             overflow. -->
        <div class="min-w-0 flex-1">
          <UserMenu
            :compact="collapsed"
            :name="fullName"
            :email="email"
            :avatar="userImage"
            :extra="accountRows"
          />
        </div>
        <NotificationBell />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Divider } from '@/ui'
import QuotaMeter from '../QuotaMeter.vue'
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

// Two of the surfaces are not quick access and are not dropped: settings is in
// the account menu below, and the marketplace is inside the switcher — adding a
// space is something you do to the workspace, so it belongs where the
// workspace's spaces are listed rather than beside the day's work.
const ELSEWHERE = ['settings', 'marketplace']

const quick = computed(() => surfaces.value.filter((one) => !ELSEWHERE.includes(one.key)))

const settings = computed(() => surfaces.value.find((one) => one.key === 'settings') || null)

// The two rows UserMenu does not already carry — appearance and signing out are
// its own. Settings sits here rather than beside the surfaces because it is not
// a place: it opens a dialog over whatever you were looking at, which is the
// same thing every other row in this menu does.
const accountRows = computed(() => [
  {
    label: __('Account'),
    icon: 'lucide-circle-user',
    onClick: () => router.push({ name: 'Account' }),
  },
  ...(settings.value
    ? [{
      label: settings.value.label,
      icon: settings.value.icon,
      onClick: () => settings.value.act?.(),
    }]
    : []),
])
</script>
