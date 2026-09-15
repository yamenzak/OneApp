<template>
  <!--
    The foot of whichever column is showing: the quota meter, you, and what is
    waiting for you.

    It is one component and not three copies because it was three copies for a
    while — the quota meter existed under the spaces and nowhere else, so the
    number that decides whether an upload is refused was invisible on the
    screen you upload from.

    What left is the row of app shortcuts, which is the dock now
    (`components/desk/Dock.vue`): four glyphs inside a column of navigation,
    folding to 3rem with it. You and the bell stayed, because they are not
    places you go — they are who you are and what is waiting, which is what the
    bottom of a column has said in every version of this product.
  -->
  <div class="mt-auto shrink-0 p-2">
    <!-- A meter is a number and a bar, and neither survives 3rem of width. -->
    <QuotaMeter v-if="!collapsed" class="mb-2 px-1" />

    <div class="flex flex-col">
      <Divider class="mb-1" />

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
import QuotaMeter from '@/modules/onespace/components/QuotaMeter.vue'
import UserMenu from '@/modules/onespace/components/UserMenu.vue'
import NotificationBell from '@/modules/onespace/components/notifications/NotificationBell.vue'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { fullName, email, userImage } from '@/modules/onespace/lib/shell/user'
import { openSettings } from '@/modules/onespace/lib/shell/settings'
import { __ } from '@/shared/lib/runtime/translate'

const router = useRouter()
const { collapsed } = useSidebar()

// The two rows UserMenu does not already carry — appearance and signing out are
// its own. Settings sits here rather than in the dock because it is not a
// place: it opens a dialog over whatever you were looking at, which is the same
// thing every other row in this menu does.
const accountRows = computed(() => [
  {
    label: __('Account'),
    icon: 'lucide-circle-user',
    onClick: () => router.push({ name: 'Account' }),
  },
  {
    label: __('Settings'),
    icon: 'lucide-settings',
    onClick: () => openSettings(),
  },
])
</script>
