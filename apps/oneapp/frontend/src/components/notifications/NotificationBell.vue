<template>
  <!--
    The bell, in the rail's foot beside the account. Shell chrome rather than a
    screen's: a notification is about something you were not looking at.
  -->
  <Popover v-model:open="open">
    <template #trigger>
      <!--
        A Button, so the count has an accessible name that says what it counts —
        `aria-label` on a bare glyph leaves a screen reader saying "bell, 3".
        And the Button's own `tooltip` rather than a `<Tooltip>` around it,
        which `test_an_icon_only_control_says_what_it_does` looks for on the
        control.

        No `@click` of its own: Popover toggles on a click in its trigger, so a
        handler here opens and shuts the panel inside one press.
      -->
      <span class="relative inline-flex">
        <Button
          variant="ghost"
          icon="lucide-bell"
          :label="label"
          :tooltip="label"
        />
        <!--
          A dot, not a number: the rail is 28px wide, and the count is in the
          panel's own header one press away.

          The gap around it is a padded background rather than a ring:
          `ring-*` takes a colour and the theme's are background, text and
          outline, so `ring-surface-base` emits no CSS at all.
        -->
        <span
          v-if="notifications.unread"
          class="pointer-events-none absolute -right-0 -top-0 rounded-full bg-surface-base p-0.5"
        >
          <span class="block size-2 rounded-full bg-surface-blue-3" />
        </span>
      </span>
    </template>

    <template #default>
      <div class="w-[min(24rem,90vw)]">
        <NotificationList @opened="open = false" />
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Popover } from '@/ui'

import NotificationList from './NotificationList.vue'
import { loadNotifications, notifications } from '@/lib/shell/notifications'

const open = ref(false)

// Named for what it is *and* what is in it, because this is the accessible
// name: "Notifications" alone says nothing about whether it is worth opening.
const label = computed(() =>
  notifications.unread
    ? `Notifications, ${notifications.unread} unread`
    : 'Notifications',
)

// Fetched when it is opened rather than on load. The bell only needs the count,
// which `followNotifications` keeps current.
watch(open, (showing) => {
  if (showing) loadNotifications()
})
</script>
