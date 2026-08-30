<template>
  <SettingsDialog v-model:open="settings.open" v-model:tab="settings.tab" size="5xl">
    <!-- The dialog is `bare`, so frappe-ui renders no close button and no
         chrome. Full-screen on a phone that leaves no backdrop to tap and no
         Escape key to press, so the way out is ours to add. -->
    <div
      data-oneapp="settings-dialog"
      class="flex shrink-0 items-center justify-between border-b border-outline-gray-1 px-4 py-3 sm:hidden"
    >
      <span class="text-lg font-semibold text-ink-gray-8">Settings</span>
      <Button
        variant="ghost"
        icon="lucide-x"
        label="Close settings"
        tooltip="Close settings"
        @click="settings.open = false"
      />
    </div>

    <SettingsSidebar :class="TAB_STRIP">
      <SettingsNavGroup label="Workspace" :class="TAB_GROUP">
        <SettingsNavItem
          v-for="group in groups"
          :key="group.key"
          :value="group.key"
          :class="TAB_ITEM"
        >
          <template #prefix>
            <Icon :name="group.icon" class="size-4 text-ink-gray-7" />
          </template>
          {{ group.label }}
        </SettingsNavItem>

        <SettingsNavItem value="books" :class="TAB_ITEM">
          <template #prefix>
            <Icon name="lucide-book-open" class="size-4 text-ink-gray-7" />
          </template>
          Books
        </SettingsNavItem>

        <SettingsNavItem value="ai" :class="TAB_ITEM">
          <template #prefix>
            <Icon name="lucide-sparkles" class="size-4 text-ink-gray-7" />
          </template>
          AI
        </SettingsNavItem>
      </SettingsNavGroup>

      <SettingsNavGroup label="You" :class="TAB_GROUP">
        <SettingsNavItem value="appearance" :class="TAB_ITEM">
          <template #prefix>
            <Icon name="lucide-sun-moon" class="size-4 text-ink-gray-7" />
          </template>
          Appearance
        </SettingsNavItem>
      </SettingsNavGroup>
    </SettingsSidebar>

    <SettingsContent :class="PANEL_CONTENT">
      <SettingsPanel v-for="group in groups" :key="group.key" :value="group.key">
        <SettingsFields :group="group" @saved="reload" />
      </SettingsPanel>

      <SettingsPanel value="books"><BooksSettings /></SettingsPanel>

      <SettingsPanel value="ai"><AiSettings /></SettingsPanel>

      <SettingsPanel value="appearance">
        <SettingsHeader title="Appearance" :class="PANEL_HEADER" />
        <SettingsBody :class="PANEL_BODY">
          <!-- Yours, not the workspace's: a theme is a per-person preference
               and lives in this browser, so it is not one of the settings the
               server spec above carries. -->
          <div class="pt-6"><ThemeSetting /></div>
        </SettingsBody>
      </SettingsPanel>
    </SettingsContent>
  </SettingsDialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  SettingsDialog,
  SettingsSidebar,
  SettingsNavGroup,
  SettingsNavItem,
  SettingsContent,
  SettingsPanel,
  SettingsHeader,
  SettingsBody,
  Button,
  Icon,
} from '@/ui'
import SettingsFields from './SettingsFields.vue'
import BooksSettings from './BooksSettings.vue'
import AiSettings from './AiSettings.vue'
import ThemeSetting from '../ThemeSetting.vue'
import { PANEL_BODY, PANEL_HEADER, TAB_GROUP, TAB_ITEM, TAB_STRIP, PANEL_CONTENT } from './geometry'
import { settings } from '../../lib/settings'
import { workspace } from '../../lib/workspace'

const data = ref(null)

// The groups come from the server, which also owns the allowlist they are
// checked against on save. See lib/workspace.js.
const groups = computed(() => data.value?.groups || [])

const reload = async () => {
  data.value = await workspace.settings()
}

// Fetched when the dialog first opens rather than at boot: most sessions never
// open settings, and this reads several singles.
watch(
  () => settings.open,
  (open) => {
    if (open && !data.value) reload()
  },
)
</script>
