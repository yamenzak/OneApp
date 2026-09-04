<template>
  <!--
    Mail, in the rail's footer beside the notification bell.

    Beside it and not inside it, because they are different things and the
    difference matters at a glance: a notification is the product telling you
    something happened, and mail is a person writing to you. Merging the two
    counts would mean a badge that could be either.

    Absent entirely for somebody who holds no address — most people, on most
    workspaces, until somebody sets one up. An icon that opens an empty page is
    worse than no icon.
  -->
  <RouterLink v-if="held" :to="{ name: 'Mail' }" class="relative">
    <Button
      variant="ghost"
      icon="lucide-mail"
      label="Mail"
      tooltip="Mail"
      data-slot="mail-bell"
    />
    <Badge
      v-if="count"
      theme="blue"
      :label="String(count > 99 ? '99+' : count)"
      class="pointer-events-none absolute -right-1 -top-1"
    />
  </RouterLink>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Badge, Button } from '@/ui'
import { workspace } from '../../lib/workspace'

const held = ref(false)
const count = ref(0)

// A minute, which is slow for a mail client and right for this. The page itself
// refreshes on open; this only decides whether a number in the rail is stale,
// and polling it faster would be a request a minute per open tab for a badge
// most people are not looking at.
const EVERY = 60_000
let timer = null

async function look() {
  try {
    const folders = await workspace.mailFolders()
    held.value = (folders?.addresses || []).length > 0
    count.value = held.value ? await workspace.mailUnread() : 0
  } catch {
    // A workspace with no mail set up answers with a refusal rather than a
    // zero, and a rail that toasted about it once a minute would be worse than
    // one that quietly shows nothing.
    held.value = false
  }
}

onMounted(() => {
  look()
  timer = setInterval(look, EVERY)
})

onUnmounted(() => clearInterval(timer))
</script>
