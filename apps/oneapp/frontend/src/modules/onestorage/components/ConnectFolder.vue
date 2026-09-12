<template>
  <!--
    Connect a folder on somebody else's server.

    Six fields and a button, and the button does not close the dialog until the
    host has answered. That is the whole point of the screen: a credential form
    that saves whatever you typed is the form every FTP integration has, and it
    is why "is the feed running" is a question nobody can answer until a Monday
    morning. `connect_folder` opens the connection, lists the base path, and
    deletes the row again if either fails — so a mount in the rail is a mount
    that worked at least once.
  -->
  <Dialog v-model="open" :title="editing ? __('Connection settings') : __('Connect a folder')">
    <template #default>
      <div class="flex flex-col gap-4">
        <p v-if="!editing" class="text-p-sm text-ink-secondary">
          {{ __('A folder on another server, browsed here. Nothing is copied — the files stay on the host and do not count against your storage.') }}
        </p>

        <!-- The name is the mount's id and the first part of every path under
             it, so changing one would change every link anybody saved. Shown
             and not editable rather than hidden: it is what you came here to
             recognise the connection by. -->
        <FormControl
          v-if="!editing"
          v-model="form.folder_name"
          :label="__('Name')"
          :description="__('What it is called in the rail.')"
        />

        <div class="grid grid-cols-3 gap-3">
          <FormControl
            v-model="form.protocol"
            type="select"
            :label="__('Protocol')"
            :options="PROTOCOLS"
          />
          <FormControl
            v-model="form.host"
            class="col-span-2"
            :label="__('Host')"
            :description="form.protocol === 'WebDAV'
              ? __('https is assumed. Write http:// for a box with no certificate.')
              : ''"
          />
        </div>

        <div class="grid grid-cols-3 gap-3">
          <FormControl
            v-model="form.port"
            type="number"
            :label="__('Port')"
            :placeholder="defaultPort"
          />
          <FormControl
            v-model="form.base_path"
            class="col-span-2"
            :label="__('Folder on the host')"
            :description="form.protocol === 'SMB'
              ? __('The share first: /drawings, or /drawings/2026 for a folder in it.')
              : __('Nothing above this is reachable.')"
          />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <FormControl v-model="form.username" :label="__('Username')" />
          <!-- Blank means unchanged. A password is never sent back to the
               browser, so a field showing dots would be showing dots it made
               up — and clearing one has to be a deliberate act rather than
               the accident of opening the form and saving it. -->
          <FormControl
            v-model="form.secret"
            type="password"
            :label="key ? __('Key passphrase') : __('Password')"
            :placeholder="editing && held.has_secret ? __('Unchanged') : ''"
          />
        </div>

        <!-- Behind a toggle, because a key is the less common half and six
             lines of PEM in an always-open textarea makes the password case
             look like the odd one. -->
        <div v-if="form.protocol === 'SFTP'">
          <Button
            variant="ghost"
            size="sm"
            :icon-left="key ? 'lucide-chevron-down' : 'lucide-chevron-right'"
            :label="__('Use a private key instead')"
            @click="key = !key"
          />
          <FormControl
            v-if="key"
            v-model="form.private_key"
            type="textarea"
            :rows="5"
            class="mt-2 font-mono"
            :label="__('Private key')"
            :placeholder="editing && held.has_private_key
              ? __('Unchanged')
              : '-----BEGIN OPENSSH PRIVATE KEY-----'"
          />
        </div>

        <!-- What the host said last, where somebody about to change a
             setting is looking. The commonest edit is the one that follows a
             failure, and making them close this to read the reason is making
             them remember it. -->
        <Alert
          v-if="editing && held.last_message && !failed"
          theme="gray"
          :title="__('Last time it was tried')"
        >
          <template #description>{{ held.last_message }}</template>
        </Alert>

        <Alert v-if="failed" theme="red" :title="__('That did not connect')">
          <template #description>{{ failed }}</template>
        </Alert>
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        :label="editing ? __('Save and try it') : __('Connect')"
        :loading="busy"
        @click="submit"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Alert, Button, Dialog, FormControl } from '@/ui'
import { workspace } from '@/shared/lib/workspace'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'

const open = defineModel({ type: Boolean, default: false })
// The mount being edited, or empty to make a new one. One dialog for both
// because they ask the same eight questions and differ only in what the
// button does — two would be two forms to keep in step, and the second one
// is always the one that goes stale.
const props = defineProps({
  mount: { type: String, default: '' },
})
const emit = defineEmits(['connected', 'changed'])

const editing = computed(() => !!props.mount)

// The server's own list, in its order: SFTP first because it is the one to
// pick, and plain FTP last because it sends the password in the clear. Kept
// in step with `remote.PROTOCOLS` by a test — a value here the server does
// not know is a mount that cannot be created, and one the server knows and
// this omits is a protocol nobody can choose.
const PROTOCOLS = ['SFTP', 'FTPS', 'FTP', 'SMB', 'WebDAV']

const router = useRouter()
const busy = ref(false)
const failed = ref('')
const key = ref(false)

const blank = () => ({
  folder_name: '',
  protocol: 'SFTP',
  host: '',
  port: '',
  base_path: '/',
  username: '',
  secret: '',
  private_key: '',
})
const form = ref(blank())
// What the server already holds, for the two placeholders that say
// "unchanged" and for the last message. Never a credential — see
// `remote.folder_settings`.
const held = ref({})

//: What the server uses when the port is left blank. Shown as the
//: placeholder so an empty field reads as a default rather than as a gap.
const PORTS = { SFTP: '22', FTPS: '21', FTP: '21', SMB: '445', WebDAV: '443' }
const defaultPort = computed(() => PORTS[form.value.protocol] || '')

// Cleared on open rather than on close: a dialog that empties itself while it
// is fading out is a dialog you watch forget what you typed.
// `immediate`, and this is the whole reason it is not a plain watcher: the
// host draws this behind `v-if` on the mount being edited, so the component is
// created with `open` already true and a transition-only watcher never fires.
// The symptom is a settings dialog with every field blank, which reads as a
// mount that has no settings rather than as a form that failed to load.
watch(open, async (now) => {
  if (!now) return
  form.value = blank()
  held.value = {}
  failed.value = ''
  key.value = false
  if (!props.mount) return

  const was = await workspace.driveFolderSettings(props.mount).catch(() => null)
  if (!was) return
  held.value = was
  form.value = {
    ...form.value,
    folder_name: was.folder_name,
    protocol: was.protocol,
    host: was.host,
    port: was.port || '',
    base_path: was.base_path,
    username: was.username || '',
  }
  // Opened straight onto the key field where there is a key, because the
  // person editing a mount that authenticates with one is usually here to
  // replace it.
  key.value = !!was.has_private_key
}, { immediate: true })

async function submit() {
  failed.value = ''
  busy.value = true
  try {
    const sending = { ...form.value, port: Number(form.value.port) || 0 }
    if (editing.value) {
      // The server proves the new settings and puts the old ones back if they
      // do not work, so a failure here has changed nothing — which is why the
      // dialog stays open on one rather than warning about a half-applied
      // edit it cannot describe.
      await workspace.driveUpdateFolder(props.mount, sending)
      open.value = false
      emit('changed')
      return
    }

    const made = await workspace.driveConnectFolder(sending)
    open.value = false
    emit('connected', made)
    // Straight into it. Connecting a folder is something somebody does in
    // order to look at it, and leaving them on the page they started from is
    // one more click to find out whether it worked.
    router.push({ name: 'Drive', query: { place: 'home', folder: made.folder } })
  } catch (error) {
    failed.value = errorText(error)
  } finally {
    busy.value = false
  }
}
</script>
