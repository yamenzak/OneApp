<template>
  <!-- `side` + `align`, not `placement`: frappe-ui removed `placement` in 1.0
       and warns about it in dev, so the menu was never positioned. -->
  <Dropdown :options="options" side="right" align="end">
    <template #trigger>
      <Tooltip :text="fullName || 'Account'" side="right">
        <Avatar
          :label="fullName || '?'"
          :image="userImage"
          size="lg"
          class="size-7 cursor-pointer transition hover:opacity-90"
        />
      </Tooltip>
    </template>
  </Dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Avatar, Dropdown, Tooltip } from '@/ui'
import { useAppearance } from '../lib/appearance'
import { openSettings } from '../lib/settings'
import { session } from '../lib/session'
import { fullName, userImage } from '../lib/user'

// The rail's foot, matching where every frappe-ui shell puts the account. The
// trigger is an Avatar rather than a Button so it reads as a person, not an
// action — and it keeps the rail's 28px rhythm.
const router = useRouter()

// Appearance is here as well as in settings: it is the preference people change
// most often, and hunting for it behind a dialog is the slow path.
const { menuGroup } = useAppearance()

const options = computed(() => [
  {
    label: 'Account',
    icon: 'lucide-circle-user',
    onClick: () => router.push({ name: 'Account' }),
  },
  // Only an admin sees it: the settings behind it are the workspace's, and a
  // member who opens a dialog every field of which refuses them has been shown
  // a door that does not open.
  ...(session.isAdmin
    ? [{ label: 'Workspace settings', icon: 'lucide-settings', onClick: () => openSettings() }]
    : []),
  menuGroup.value,
  {
    label: 'Log out',
    icon: 'lucide-log-out',
    // Frappe's own logout clears the session cookie server-side; a client-side
    // redirect alone would leave the session valid.
    onClick: () => {
      window.location.href = '/api/method/logout'
    },
  },
])
</script>
