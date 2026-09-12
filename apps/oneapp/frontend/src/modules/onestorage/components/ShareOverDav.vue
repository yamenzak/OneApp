<template>
  <!--
    Serve a folder over WebDAV, so it mounts as a drive somewhere else.

    The mirror of Connect a folder, and deliberately the same shape: a short
    form, and a list of what already exists underneath it. What is different
    is the one-time secret — a key is shown once, here, and never again, so
    the copy button and the sentence under it are the whole design.
  -->
  <Dialog v-model="open" :title="__('Share over WebDAV')">
    <template #default>
      <div class="flex flex-col gap-4">
        <!-- The made key, if one was just made. Above the form rather than
             replacing it, because the next thing somebody does after making a
             key for the surveyor is make one for the engineer. -->
        <Panel ground="sunken" pad="tight" v-if="made" data-slot="dav-made" class="flex flex-col gap-2">
          <p class="text-p-sm font-medium text-ink-primary">
            {{ __('Copy this now — the password is not shown again.') }}
          </p>
          <!-- Three lines and a copy button each, which is `ShareLink`'s
               own pattern for a generated secret. Not a read-only
               `FormControl`: it has no `readonly`, and `disabled` is the
               one thing a value somebody has to copy must not be. -->
          <div
            v-for="one in copyable"
            :key="one.label"
            class="flex items-center gap-2"
          >
            <div class="min-w-0 flex-1">
              <p class="text-p-xs text-ink-muted">{{ one.label }}</p>
              <p class="truncate font-mono text-sm text-ink-primary">{{ one.value }}</p>
            </div>
            <Button
              icon="lucide-copy"
              variant="ghost"
              :label="__('Copy {0}', [one.label])"
              :tooltip="__('Copy')"
              @click="copy(one.value)"
            />
          </div>
          <p class="text-p-xs text-ink-muted">
            {{ __('On a Mac: Finder, Go, Connect to Server. On Windows: This PC, Map network drive.') }}
          </p>
        </Panel>

        <FormControl v-model="form.label" :label="__('What is it for')" />

        <div class="grid grid-cols-2 gap-3">
          <FormControl
            v-model="form.read_only"
            type="select"
            :label="__('Access')"
            :options="[
              { label: __('Read only'), value: '1' },
              { label: __('Read and write'), value: '0' },
            ]"
          />
          <FormControl
            v-model="form.days"
            type="number"
            :label="__('Expires after (days)')"
            :placeholder="__('Never')"
          />
        </div>

        <p class="text-p-xs text-ink-muted">
          {{ scopeSays }}
        </p>

        <Alert v-if="failed" theme="red" :title="__('That key was not made')">
          <template #description>{{ failed }}</template>
        </Alert>

        <!-- What already exists. A key nobody can see is a key nobody
             revokes, and the reason to keep a revoked one is `last_used`. -->
        <div v-if="keys.length" class="flex flex-col gap-1 border-t border-outline-gray-1 pt-3">
          <p class="text-p-xs font-medium uppercase tracking-wide text-ink-muted">
            {{ __('Keys you have made') }}
          </p>
          <div
            v-for="one in keys"
            :key="one.name"
            data-slot="dav-key"
            class="flex items-center gap-2 py-1"
          >
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm text-ink-primary">{{ one.label }}</p>
              <p class="truncate text-xs text-ink-muted">{{ says(one) }}</p>
            </div>
            <Button
              v-if="one.enabled"
              variant="ghost"
              size="sm"
              :label="__('Revoke')"
              :loading="busy"
              @click="revoke(one)"
            />
            <Badge v-else theme="gray" :label="__('Revoked')" />
          </div>
        </div>
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        :label="__('Make a key')"
        :loading="busy"
        @click="submit"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Alert, Badge, Button, Dialog, FormControl } from '@/ui'
import { workspace } from '@/shared/lib/workspace'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'
import Panel from '@/shared/components/Panel.vue'
import { date } from '@/shared/lib/runtime/format'

const open = defineModel({ type: Boolean, default: false })
const props = defineProps({
  // The folder to serve, or empty for the whole Drive.
  folder: { type: String, default: '' },
  folderLabel: { type: String, default: '' },
})

// The three lines somebody copies into a file manager. A list rather than
// three blocks, because they are one idea and differ only in their label.
const copyable = computed(() => made.value ? [
  { label: __('Address'), value: made.value.url },
  { label: __('Username'), value: made.value.access_user },
  { label: __('Password'), value: made.value.secret },
] : [])

async function copy(value) {
  try {
    await navigator.clipboard?.writeText(value)
  } catch {
    // A browser that refuses the clipboard has not lost the key — it is on
    // screen, and selecting it by hand still works.
  }
}

const busy = ref(false)
const failed = ref('')
const made = ref(null)
const keys = ref([])
const form = ref({ label: '', read_only: '1', days: '' })

const scopeSays = computed(() =>
  props.folder
    ? __('This key reaches {0} and everything in it, and nothing else.', [props.folderLabel])
    : __('This key reaches every file you can see. Pick a folder first to narrow it.'),
)

const says = (one) => {
  const how = one.read_only ? __('Read only') : __('Read and write')
  const when = one.last_used
    ? __('last used {0}', [date(one.last_used)])
    : __('never used')
  return `${one.access_user} · ${how} · ${when}`
}

watch(open, async (now) => {
  if (!now) return
  made.value = null
  failed.value = ''
  form.value = { label: props.folderLabel || '', read_only: '1', days: '' }
  keys.value = (await workspace.driveShares().catch(() => null)) || []
}, { immediate: true })

async function submit() {
  failed.value = ''
  busy.value = true
  try {
    made.value = await workspace.driveShareFolder({
      label: form.value.label,
      folder: props.folder,
      read_only: form.value.read_only === '1' ? 1 : 0,
      days: Number(form.value.days) || 0,
    })
    keys.value = (await workspace.driveShares().catch(() => null)) || []
  } catch (error) {
    failed.value = errorText(error)
  } finally {
    busy.value = false
  }
}

async function revoke(one) {
  busy.value = true
  try {
    await workspace.driveRevokeShare(one.name)
    keys.value = (await workspace.driveShares().catch(() => null)) || []
  } finally {
    busy.value = false
  }
}
</script>
