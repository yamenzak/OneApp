<template>
  <SettingsDialog v-model:open="showSettings" v-model:tab="activeSettingsTab" size="5xl">
    <SettingsBody>
      <SettingsSidebar>
        <SettingsNavGroup v-for="group in GROUPS" :key="group.label" :label="group.label">
          <SettingsNavItem
            v-for="item in group.items"
            :key="item.value"
            :value="item.value"
            :label="item.label"
          >
            <template #prefix>
              <Icon :name="item.icon" class="size-4 text-ink-gray-7" />
            </template>
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
      </SettingsContent>
    </SettingsBody>
  </SettingsDialog>
</template>

<script setup>
import {
  SettingsDialog, SettingsBody, SettingsSidebar, SettingsNavGroup,
  SettingsNavItem, SettingsContent, SettingsPanel, Icon,
} from '@/ui'
import ControlSettings from './ControlSettings.vue'
import CloudflareSettings from './CloudflareSettings.vue'
import BillingSettings from './BillingSettings.vue'
import PlansSettings from './PlansSettings.vue'
import RegionsSettings from './RegionsSettings.vue'
import BucketsSettings from './BucketsSettings.vue'
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
]
</script>
