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
  <Dialog v-model="open" :title="__('Connect a folder')">
    <template #default>
      <div class="flex flex-col gap-4">
        <p class="text-p-sm text-ink-gray-6">
          {{ __('A folder on an FTP or SFTP server, browsed here. Nothing is copied — the files stay on the host and do not count against your storage.') }}
        </p>

        <FormControl
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
          <FormControl v-model="form.host" class="col-span-2" :label="__('Host')" />
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
            :description="__('Nothing above this is reachable.')"
          />
        </div>

        <div class="grid grid-cols-2 gap-3">
          <FormControl v-model="form.username" :label="__('Username')" />
          <FormControl
            v-model="form.secret"
            type="password"
            :label="key ? __('Key passphrase') : __('Password')"
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
            :placeholder="'-----BEGIN OPENSSH PRIVATE KEY-----'"
          />
        </div>

        <Alert v-if="failed" theme="red" :title="__('That did not connect')">
          <template #description>{{ failed }}</template>
        </Alert>
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        :label="__('Connect')"
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
const emit = defineEmits(['connected'])

// The server's own list, in its order: SFTP first because it is the one to
// pick, and plain FTP last because it sends the password in the clear.
const PROTOCOLS = ['SFTP', 'FTPS', 'FTP']

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

const defaultPort = computed(() => (form.value.protocol === 'SFTP' ? '22' : '21'))

// Cleared on open rather than on close: a dialog that empties itself while it
// is fading out is a dialog you watch forget what you typed.
watch(open, (now) => {
  if (now) {
    form.value = blank()
    failed.value = ''
    key.value = false
  }
})

async function submit() {
  failed.value = ''
  busy.value = true
  try {
    const made = await workspace.driveConnectFolder({
      ...form.value,
      port: Number(form.value.port) || 0,
    })
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
