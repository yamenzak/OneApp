<template>
  <!--
    The folders this workspace reads on somebody else's server.

    It was a menu on the mount itself, in the Drive's rail, and that is
    `docs/UNIFICATION.md` §C2's other half: a thing you *use* belongs where you
    are using it, and a thing you *set up* belongs where everything else is set
    up. Browsing a mount is still the rail's. What host it points at, what
    credential it uses, and whether it is being read at all is this — beside
    Storage and Backups, which is the same subject from the other two sides.

    The form is still `ConnectFolder`, unchanged: the dialog that proves the
    connection before it writes the row is the whole feature, and moving where
    it opens from is not a reason to have a second one.
  -->
  <SettingsHeader
    :title="__('Connections')"
    :description="__('Folders on other servers, browsed here. Nothing is copied.')"
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <div class="flex flex-col gap-3">
      <div class="flex items-center justify-end">
        <Button
          variant="subtle"
          icon-left="lucide-plus"
          :label="__('Connect a folder')"
          data-slot="connect-folder"
          @click="connecting = true"
        />
      </div>

      <!-- The frame is `DataList` — §B1. No search: a workspace has a handful
           of these, and a box over four rows answers nothing. -->
      <DataList :source="source" :skeleton="2" skeleton-class="h-11 w-full">
        <template #row="{ row: mount }">
          <div
            data-slot="workspace-connection"
            class="flex items-center gap-3 border-b border-outline-gray-1 py-2.5"
          >
            <span class="flex min-w-0 flex-1 flex-col">
              <span class="truncate text-sm text-ink-primary">{{ mount.folder_name }}</span>
              <span class="truncate text-xs text-ink-muted">{{ where(mount) }}</span>
            </span>
            <!-- What it last said, where it said anything. A mount is proved
                 on the way in, so a row with a message on it is one that has
                 stopped working since — which is the only thing worth a
                 badge. -->
            <Badge
              v-if="mount.status === 'Paused'"
              theme="gray"
              variant="subtle"
              :label="__('Paused')"
            />
            <Tooltip v-else-if="mount.last_message" :text="mount.last_message">
              <Badge theme="red" variant="subtle" :label="__('Not answering')" />
            </Tooltip>
            <Button
              :icon="mount.status === 'Paused' ? 'lucide-play' : 'lucide-pause'"
              variant="ghost"
              :label="mount.status === 'Paused'
                ? __('Start reading {0} again', [mount.folder_name])
                : __('Pause {0}', [mount.folder_name])"
              :tooltip="mount.status === 'Paused'
                ? __('Start reading {0} again', [mount.folder_name])
                : __('Pause {0}', [mount.folder_name])"
              :loading="busy === mount.name"
              @click="pause(mount)"
            />
            <Button
              icon="lucide-settings-2"
              variant="ghost"
              :label="__('Settings for {0}', [mount.folder_name])"
              :tooltip="__('Settings for {0}', [mount.folder_name])"
              @click="edit(mount)"
            />
            <Button
              icon="lucide-unplug"
              variant="ghost"
              theme="red"
              :label="__('Disconnect {0}', [mount.folder_name])"
              :tooltip="__('Disconnect {0}', [mount.folder_name])"
              :loading="busy === mount.name"
              @click="disconnect(mount)"
            />
          </div>
        </template>
      </DataList>

      <ErrorMessage v-if="error" :message="error" />
    </div>
  </SettingsBody>

  <ConnectFolder v-model="connecting" @changed="load" />
  <!-- `:key` so it re-reads when you move from one mount's settings to
       another's without closing it in between. -->
  <ConnectFolder
    v-if="editing"
    :key="editing"
    v-model="editingOpen"
    :mount="editing"
    @changed="load"
  />
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Badge, Button, ErrorMessage, Tooltip, SettingsHeader, SettingsBody,
} from '@/ui'
import DataList from '@/shared/components/DataList.vue'
import ConnectFolder from '@/modules/onestorage/components/ConnectFolder.vue'
import { staticSource } from '@/shared/lib/list/source'
import { PANEL_BODY, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const rows = ref([])
const error = ref('')
const busy = ref('')
const connecting = ref(false)
const editing = ref('')
const editingOpen = ref(false)

const source = computed(() => staticSource({
  rows: rows.value,
  key: (mount) => mount.name,
  empty: {
    icon: 'lucide-server',
    title: __('No connected folders'),
    description: __('Point this at an FTP, SFTP, SMB or WebDAV server and its folders appear in Files.'),
  },
}))

/** Where it points, in one line — the protocol and the host, no credential. */
const where = (mount) => `${mount.protocol} · ${mount.host}`

const load = async () => {
  try {
    rows.value = (await workspace.driveMounts()) || []
  } catch (e) {
    error.value = errorText(e)
  }
}

const edit = (mount) => {
  editing.value = mount.name
  editingOpen.value = true
}

const pause = async (mount) => {
  busy.value = mount.name
  error.value = ''
  try {
    await workspace.drivePauseMount(mount.name, mount.status !== 'Paused')
    await load()
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = ''
  }
}

const disconnect = async (mount) => {
  busy.value = mount.name
  error.value = ''
  try {
    await workspace.driveDisconnect(mount.name)
    await load()
  } catch (e) {
    error.value = errorText(e)
  } finally {
    busy.value = ''
  }
}

load()
</script>
