<template>
  <!--
    The theme. Yours, and this browser's.

    A panel of its own now rather than a block inside the shell, because every
    tab is a panel the server declared and this is the one that was written
    inline. Nothing here reaches the server: a theme is a per-person preference
    kept in this browser, and a round trip would only make the toggle slower.
  -->
  <SettingsHeader
    title="Appearance"
    description="How OneSpace looks, on this browser."
    :class="PANEL_HEADER"
  />
  <SettingsBody :class="PANEL_BODY">
    <div class="pt-6"><ThemeSetting /></div>
  </SettingsBody>
</template>

<script setup>
import { SettingsBody, SettingsHeader } from '@/ui'
import ThemeSetting from '../ThemeSetting.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
</script>
