<template>
  <SettingsDialog v-model:open="showSettings" v-model:tab="activeSettingsTab" size="5xl">
    <SettingsSidebar>
      <SettingsNavGroup v-for="group in GROUPS" :key="group.label" :label="group.label">
        <!-- The label is the default slot, not a prop: passing :label renders
             an item with an icon and no text. -->
        <SettingsNavItem v-for="item in group.items" :key="item.value" :value="item.value">
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
        <SettingsHeader title="Appearance" />
        <SettingsBody>
          <div class="pt-6"><ThemeSetting /></div>
        </SettingsBody>
      </SettingsPanel>
    </SettingsContent>
  </SettingsDialog>
</template>

<script setup>
import {
  SettingsDialog, SettingsSidebar, SettingsNavGroup, SettingsNavItem,
  SettingsContent, SettingsPanel, SettingsHeader, SettingsBody, Icon,
} from '@/ui'
import ControlSettings from './ControlSettings.vue'
import CloudflareSettings from './CloudflareSettings.vue'
import BillingSettings from './BillingSettings.vue'
import PlansSettings from './PlansSettings.vue'
import RegionsSettings from './RegionsSettings.vue'
import BucketsSettings from './BucketsSettings.vue'
import ThemeSetting from '../ThemeSetting.vue'
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
