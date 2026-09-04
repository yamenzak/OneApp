<!--
  A link to one file that works without an account, and stops working on a date.

  The gap `DocShare` cannot cover. Sharing a file inside the workspace is a
  `DocShare` row and needs the other person to have a login here; a consultant,
  an auditor or a customer has neither, and today the answer is that somebody
  emails the file as an attachment and it lives in that inbox for ever.

  So the dialog is built around the two things that make a link different from
  a copy: it ends, and it can be taken back.
-->
<template>
  <Dialog v-model="open" title="Share a link" size="lg">
    <template #default>
      <div class="flex flex-col gap-4 py-2">
        <p class="text-p-sm text-ink-gray-6">
          Anybody with the link can open
          <span class="text-ink-gray-8">{{ file?.file_name }}</span>
          until it expires. They do not need an account here.
        </p>

        <div class="flex items-end gap-2">
          <FormControl
            v-model="days"
            class="flex-1"
            type="select"
            label="It stops working after"
            :options="DAYS"
          />
          <Button variant="solid" label="Make a link" :loading="making" @click="make" />
        </div>

        <ErrorMessage :message="error" />

        <Divider v-if="rows.length" />

        <div v-if="rows.length" class="flex flex-col gap-2">
          <div
            v-for="row in rows"
            :key="row.name"
            data-slot="file-link"
            class="flex items-center gap-2 rounded-6 border border-outline-gray-1 px-3 py-2"
          >
            <div class="min-w-0 flex-1">
              <p class="truncate text-p-xs text-ink-gray-7">{{ absolute(row) }}</p>
              <p class="text-p-xs text-ink-gray-5">
                <template v-if="row.revoked">Revoked</template>
                <template v-else>Until {{ until(row) }}</template>
                · opened {{ row.opened }}
                {{ row.opened === 1 ? 'time' : 'times' }}
              </p>
            </div>
            <Button
              v-if="!row.revoked"
              icon="lucide-copy"
              variant="ghost"
              tooltip="Copy the link"
              @click="copy(row)"
            />
            <Button
              v-if="!row.revoked"
              icon="lucide-x"
              variant="ghost"
              theme="red"
              tooltip="Stop this link working"
              @click="revoke(row)"
            />
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Button, Dialog, Divider, ErrorMessage, FormControl, toast } from '@/ui'
import { workspace } from '../../lib/workspace'

// The server's own bound is ninety days; these are the answers people give.
const DAYS = [
  { label: 'a day', value: '1' },
  { label: 'a week', value: '7' },
  { label: 'a month', value: '30' },
  { label: 'three months', value: '90' },
]

const props = defineProps({
  file: { type: Object, default: null },
})

const open = defineModel({ type: Boolean, default: false })

const days = ref('7')
const rows = ref([])
const making = ref(false)
const error = ref('')

// The server returns a path, because the server does not know what host the
// person is looking at. The link has to survive being pasted into an email, so
// it is made absolute here — where the browser knows.
const absolute = (row) => new URL(row.url, window.location.origin).toString()

const until = (row) => (row.expires_on || '').slice(0, 10)

async function load() {
  error.value = ''
  try {
    rows.value = (await workspace.driveLinks(props.file.name)) || []
  } catch (e) {
    error.value = e.message || String(e)
  }
}

async function make() {
  making.value = true
  error.value = ''
  try {
    const made = await workspace.driveMakeLink(props.file.name, Number(days.value))
    await copy(made)
    await load()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    making.value = false
  }
}

async function copy(row) {
  try {
    await navigator.clipboard?.writeText(absolute(row))
    toast.success('Link copied')
  } catch {
    // A browser that refuses the clipboard is not a failed share — the link is
    // on screen and can be selected.
    toast.success('Link made')
  }
}

async function revoke(row) {
  await workspace.driveRevokeLink(row.name)
  await load()
}

watch(open, (showing) => {
  if (showing && props.file?.name) {
    days.value = '7'
    load()
  }
})
</script>
