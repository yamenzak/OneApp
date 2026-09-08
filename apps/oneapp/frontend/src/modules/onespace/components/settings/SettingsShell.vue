<template>
  <SettingsDialog v-model:open="settings.open" v-model:tab="settings.tab" size="5xl">
    <!-- The dialog is `bare`, so frappe-ui renders no close button and no
         chrome. Full-screen on a phone that leaves no backdrop to tap and no
         Escape key to press, so the way out is ours to add. -->
    <div
      data-oneapp="settings-dialog"
      class="flex shrink-0 items-center justify-between border-b border-outline-gray-1 px-4 py-3 sm:hidden"
    >
      <span class="text-lg font-semibold text-ink-gray-8">{{ __('Settings') }}</span>
      <Button
        variant="ghost"
        icon="lucide-x"
        :label="__('Close settings')"
        :tooltip="__('Close settings')"
        @click="settings.open = false"
      />
    </div>

    <!--
      The tabs are the server's list, not this file's.

      They were written here by hand and drawn for everybody, with the actual
      gate inside each endpoint — so the dialog could only be offered to admins,
      because a member opening it would have found ten tabs and been refused by
      all of them. `onespace/tabs.py` declares every tab with the audience it
      is for and returns the ones this reader may open, which is what makes one
      dialog serve the owner and the member.
    -->
    <SettingsSidebar :class="TAB_STRIP">
      <SettingsNavGroup
        v-for="section in sections"
        :key="section.label"
        :label="section.label"
        :class="TAB_GROUP"
      >
        <SettingsNavItem
          v-for="tab in section.tabs"
          :key="tab.key"
          :value="tab.key"
          :class="TAB_ITEM"
          :data-slot="`settings-tab-${tab.key}`"
        >
          <template #prefix>
            <Icon :name="iconFor(tab)" class="size-4 text-ink-gray-7" />
          </template>
          {{ tab.label }}
        </SettingsNavItem>
      </SettingsNavGroup>
    </SettingsSidebar>

    <SettingsContent :class="PANEL_CONTENT">
      <SettingsPanel v-for="tab in tabs" :key="tab.key" :value="tab.key">
        <!-- A `fields` tab is a spec the server renders and checks writes
             against; a `panel` tab is one the SPA draws because it is not a
             list of fields. `PANELS` is the whole of the second contract, and
             `tests/test_settings_tabs.py` holds the two ends to it. -->
        <SettingsFields
          v-if="tab.kind === 'fields'"
          :group="groupFor(tab.key)"
          @saved="reload"
        />
        <component :is="PANELS[tab.key]" v-else-if="PANELS[tab.key]" />
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
  Button,
  Icon,
} from '@/ui'
import SettingsFields from '@/modules/onespace/components/settings/SettingsFields.vue'
import AppearanceSettings from '@/modules/onespace/components/settings/AppearanceSettings.vue'
import BooksSettings from '@/modules/onespace/components/settings/BooksSettings.vue'
import AiSettings from '@/modules/onespace/components/settings/AiSettings.vue'
import AlertSettings from '@/modules/onespace/components/settings/AlertSettings.vue'
import TemplateSettings from '@/modules/onespace/components/settings/TemplateSettings.vue'
import DomainSettings from '@/modules/onespace/components/settings/DomainSettings.vue'
import PeopleSettings from '@/modules/onespace/components/settings/PeopleSettings.vue'
import RoleSettings from '@/modules/onespace/components/settings/RoleSettings.vue'
import StorageSettings from '@/modules/onespace/components/settings/StorageSettings.vue'
import NamingSettings from '@/modules/onespace/components/settings/NamingSettings.vue'
import LegalSettings from '@/modules/onespace/components/settings/LegalSettings.vue'
import PrintingSettings from '@/modules/onespace/components/settings/PrintingSettings.vue'
import MailSettings from '@/modules/onespace/components/settings/MailSettings.vue'
import MailboxSettings from '@/modules/onespace/components/settings/MailboxSettings.vue'
import ProfileSettings from '@/modules/onespace/components/settings/ProfileSettings.vue'
import SecuritySettings from '@/modules/onespace/components/settings/SecuritySettings.vue'
import NotificationSettingsPanel from '@/modules/onespace/components/settings/NotificationSettingsPanel.vue'
import { TAB_GROUP, TAB_ITEM, TAB_STRIP, PANEL_CONTENT } from '@/modules/onespace/components/settings/geometry'
// Imported for the literals rather than for the value: Tailwind emits a
// `lucide-*` class only where it can read it as a string, and a tab's icon is
// named in Python. See `./icons.js`.
import { TAB_ICONS } from '@/modules/onespace/components/settings/icons'
import { settings } from '@/modules/onespace/lib/shell/settings'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'

/**
 * Which component draws each `panel` tab.
 *
 * The other half of the contract in `onespace/tabs.py`: the server says a
 * tab exists and who may open it, and this says what it looks like. A key on
 * one side with nothing on the other is a tab that renders as an empty panel —
 * silently, the way Vue does — so a test reads both lists and fails on either
 * gap.
 */
const PANELS = {
  profile: ProfileSettings,
  security: SecuritySettings,
  notifications: NotificationSettingsPanel,
  appearance: AppearanceSettings,
  mailbox: MailboxSettings,
  books: BooksSettings,
  'print-formats': PrintingSettings,
  legal: LegalSettings,
  naming: NamingSettings,
  mail: MailSettings,
  templates: TemplateSettings,
  alerts: AlertSettings,
  ai: AiSettings,
  domain: DomainSettings,
  people: PeopleSettings,
  roles: RoleSettings,
  storage: StorageSettings,
}

const data = ref(null)

/** An icon the build never saw is a blank space, so fall back to one it did. */
const iconFor = (tab) => (TAB_ICONS.includes(tab.icon) ? tab.icon : 'lucide-settings')

const tabs = computed(() => data.value?.tabs || [])
const groups = computed(() => data.value?.groups || [])

const groupFor = (key) => groups.value.find((one) => one.key === key) || null

/**
 * The tabs grouped under their headings, in the order the server sent them.
 *
 * Built from the tabs rather than from a list of section names, so a section
 * with nothing in it does not draw a heading over an empty column — which is
 * what a member would have seen under "Workspace".
 */
const sections = computed(() => {
  const found = []
  for (const tab of tabs.value) {
    const section = found.find((one) => one.label === tab.section)
    if (section) section.tabs.push(tab)
    else found.push({ label: tab.section, tabs: [tab] })
  }
  return found
})

const reload = async () => {
  data.value = await workspace.settings()

  // The remembered tab can be one this person cannot open — the dialog keeps
  // whatever it was last asked for, and an admin's deep link is a member's
  // blank panel. Fall back to the first they do have.
  const open = tabs.value.some((one) => one.key === settings.tab)
  if (!open && tabs.value.length) settings.tab = tabs.value[0].key
}

// Fetched when the dialog is open and has nothing rather than at boot: most
// sessions never open settings, and this reads several singles.
//
// On the *state* and not on the open transition. This component is mounted
// under `session.loaded`, and reloading the session — which saving a profile
// does, so the rail's name follows — unmounts and remounts it with `data` back
// to null. Watching the transition, that remount happened while `settings.open`
// was already true, so nothing fired and the dialog stayed a spinner until it
// was closed and opened again.
watch(
  () => settings.open && !data.value,
  (wanted) => wanted && reload(),
  { immediate: true },
)
</script>
