<template>
  <Dropdown :options="options" placement="right-end">
    <template #trigger>
      <Tooltip :text="fullName || 'Account'" placement="right">
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
import { fullName, userImage } from '../lib/user'

// The rail's foot, matching where every frappe-ui shell puts the account. The
// trigger is an Avatar rather than a Button so it reads as a person, not an
// action — and it keeps the rail's 28px rhythm.
const router = useRouter()

const options = computed(() => [
  {
    label: 'Account',
    icon: 'lucide-circle-user',
    onClick: () => router.push({ name: 'Account' }),
  },
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
