<template>
  <!--
    What you are told about, and whether any of it reaches your inbox.

    The controls are `components/notifications/NotificationSettings.vue`, which
    the Account page has drawn for a while; this is the same thing given a tab,
    so somebody looking for it in Settings finds it where they looked.
  -->
  <SettingsHeader
    :title="__('Notifications')"
    :description="__('What you are told about, and how.')"
    :class="PANEL_HEADER"
  />
  <SettingsBody :class="PANEL_BODY">
    <div class="pt-6"><NotificationSettings /></div>
  </SettingsBody>
</template>

<script setup>
import { SettingsBody, SettingsHeader } from '@/ui'
import NotificationSettings from '@/modules/onespace/components/notifications/NotificationSettings.vue'
import { __ } from '@/shared/lib/runtime/translate'
import { PANEL_BODY, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
</script>
