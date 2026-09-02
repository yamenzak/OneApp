<template>
  <!--
    The account menu at the foot of the rail.

    The trigger goes in the **default** slot. frappe-ui's Dropdown has no
    `trigger` slot — it renders whatever its default slot holds and attaches the
    menu to that — so a `<template #trigger>` renders nothing, attaches to
    nothing, and the menu never opens. It looked right the whole time, because
    the avatar is drawn by the slot's fallback: settings, appearance and sign
    out were simply unreachable from here.

    `side` + `align`, not `placement`: frappe-ui removed `placement` in 1.0 and
    warns about it in dev, so the menu was never positioned either.
  -->
  <Dropdown :options="options" side="right" align="end">
    <!--
      An Avatar renders a div, so without these the one control that reaches
      settings had no name and no way in from a keyboard. `role` and `tabindex`
      are what a div acting as a control needs; the label is what a screen
      reader reads and what names it on hover.
    -->
    <Avatar
      :label="fullName || '?'"
      :image="userImage"
      size="lg"
      role="button"
      tabindex="0"
      :aria-label="fullName || 'Account'"
      class="size-7 cursor-pointer transition hover:opacity-90"
    />
  </Dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { Avatar, Dropdown } from '@/ui'
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
