<template>
  <SettingsDialog v-model:open="showSettings" v-model:tab="activeSettingsTab" size="5xl">
    <!--
      A pinned header, phone only.

      SettingsDialog is `bare`, so frappe-ui renders no close button and no
      chrome of its own; on a desktop the backdrop is the way out. Full-screen
      on a phone there is no backdrop left to tap and no Escape key to press,
      so without this the dialog is a trap. It is the first row of the dialog's
      flex column below `sm` and vanishes above it, where the column becomes a
      row and the backdrop comes back.
    -->
    <div
      data-oneapp="settings-dialog"
      class="flex shrink-0 items-center justify-between border-b border-outline-gray-1 px-4 py-3 sm:hidden"
    >
      <span class="text-lg font-semibold text-ink-gray-8">Settings</span>
      <Button
        variant="ghost"
        icon="lucide-x"
        label="Close settings"
        @click="showSettings = false"
      />
    </div>

    <!-- On a phone the nav is a strip of tabs that scrolls sideways, not a
         column that eats a third of the screen. See geometry.js. -->
    <SettingsSidebar :class="TAB_STRIP">
      <SettingsNavGroup
        v-for="group in GROUPS"
        :key="group.label"
        :label="group.label"
        :class="TAB_GROUP"
      >
        <!-- The label is the default slot, not a prop: passing :label renders
             an item with an icon and no text. -->
        <SettingsNavItem
          v-for="item in group.items"
          :key="item.value"
          :value="item.value"
          :class="TAB_ITEM"
        >
          <template #prefix>
            <Icon :name="item.icon" class="size-4 text-ink-gray-7" />
          </template>
          {{ item.label }}
        </SettingsNavItem>
      </SettingsNavGroup>
    </SettingsSidebar>

    <SettingsContent>
      <SettingsPanel value="control"><ControlSettings /></SettingsPanel>
      <SettingsPanel value="cloudflare"><CloudflareSettings /></SettingsPanel>
      <SettingsPanel value="billing"><BillingSettings /></SettingsPanel>
      <SettingsPanel value="plans"><PlansSettings /></SettingsPanel>
      <SettingsPanel value="regions"><RegionsSettings /></SettingsPanel>
      <SettingsPanel value="buckets"><BucketsSettings /></SettingsPanel>
      <SettingsPanel value="appearance">
        <SettingsHeader title="Appearance" :class="PANEL_HEADER" />
        <SettingsBody :class="PANEL_BODY">
          <div class="pt-6"><ThemeSetting /></div>
        </SettingsBody>
      </SettingsPanel>
    </SettingsContent>
  </SettingsDialog>
</template>

<script setup>
import {
  SettingsDialog, SettingsSidebar, SettingsNavGroup, SettingsNavItem,
  SettingsContent, SettingsPanel, SettingsHeader, SettingsBody, Button, Icon,
} from '@/ui'
import ControlSettings from './ControlSettings.vue'
import CloudflareSettings from './CloudflareSettings.vue'
import BillingSettings from './BillingSettings.vue'
import PlansSettings from './PlansSettings.vue'
import RegionsSettings from './RegionsSettings.vue'
import BucketsSettings from './BucketsSettings.vue'
import ThemeSetting from '../ThemeSetting.vue'
import { PANEL_BODY, PANEL_HEADER, TAB_GROUP, TAB_ITEM, TAB_STRIP } from './geometry'
import { showSettings, activeSettingsTab } from '../../lib/settings'

// Everything an operator needs, so the desk is never required. Grouped by what
// the setting affects rather than by which doctype holds it.
const GROUPS = [
  {
    label: 'Platform',
    items: [
      { value: 'control', label: 'Frappe Cloud', icon: 'lucide-cloud' },
      { value: 'cloudflare', label: 'Cloudflare', icon: 'lucide-globe' },
      { value: 'billing', label: 'Billing', icon: 'lucide-credit-card' },
    ],
  },
  {
    label: 'Catalogue',
    items: [
      { value: 'plans', label: 'Plans', icon: 'lucide-layers' },
      { value: 'regions', label: 'Regions', icon: 'lucide-map-pin' },
      { value: 'buckets', label: 'Storage buckets', icon: 'lucide-database' },
    ],
  },
  {
    label: 'Preferences',
    items: [
      { value: 'appearance', label: 'Appearance', icon: 'lucide-sun-moon' },
    ],
  },
]
</script>
