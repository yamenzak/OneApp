<template>
  <!--
    The bell, in the rail's foot beside the account.

    Shell chrome rather than a screen's: a notification is about something you
    were not looking at, so it cannot live inside the thing you are looking at.
    Above the avatar, because the account menu is the last thing in the rail
    everywhere in this product and moving it would be a different shell.
  -->
  <Popover v-model:open="open">
    <template #trigger>
      <!--
        A Button, so the count has an accessible name that says what it counts —
        `aria-label` on a bare glyph leaves a screen reader saying "bell, 3".
        And the Button's own `tooltip` rather than a `<Tooltip>` around it:
        wrapping is what `test_an_icon_only_control_says_what_it_does` looks for
        and does not find, because the wrapper is not on the control.

        No `@click` of its own: Popover toggles on a click in its trigger, so a
        handler here toggles it a second time and the panel opens and shuts
        inside one press. It looked exactly like a control that does nothing.
      -->
      <span class="relative inline-flex">
        <Button
          variant="ghost"
          icon="lucide-bell"
          :label="label"
          :tooltip="label"
        />
        <!--
          A dot, not a number. The rail is 28px wide and a two-digit badge on a
          28px control is a badge with a control behind it; the count is in the
          panel's own header, one press away.

          The gap around it is drawn as a padded background rather than a ring:
          `ring-*` takes a colour, and the theme's colours are background, text
          and outline — `ring-surface-base` is not a token and emits no CSS at
          all, which is a dot welded to whatever it sits on. Same lesson as the
          avatar stack.
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
import { loadNotifications, notifications } from '../../lib/notifications'

const open = ref(false)

// Named for what it is *and* what is in it, because this is the accessible
// name: "Notifications" alone tells somebody who cannot see the dot nothing
// about whether it is worth opening.
const label = computed(() =>
  notifications.unread
    ? `Notifications, ${notifications.unread} unread`
    : 'Notifications',
)

// Fetched when it is opened rather than on load. The bell only needs the
// count, which `followNotifications` keeps current; a page of rows nobody has
// asked to see is a request per session for nothing.
watch(open, (showing) => {
  if (showing) loadNotifications()
})
</script>
