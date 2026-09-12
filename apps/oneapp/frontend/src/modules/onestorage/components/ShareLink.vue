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
  <Dialog v-model="open" :title="__('Share a link')" size="lg">
    <template #default>
      <div class="flex flex-col gap-4 py-2">
        <p class="text-p-sm text-ink-secondary">
          {{
            __('Anybody with the link can open {0} until it expires. They do not need an account here.', [
              file?.file_name,
            ])
          }}
        </p>

        <div class="flex items-end gap-2">
          <FormControl
            v-model="days"
            class="flex-1"
            type="select"
            :label="__('It stops working after')"
            :options="dayOptions"
          />
          <!--
            What the link hands over. Offered only where this person may
            write the file themselves — the server refuses either way, and a
            control that is drawn and a write that is allowed should read the
            same flag at the same moment.
          -->
          <FormControl
            v-if="canWrite"
            v-model="level"
            class="flex-1"
            type="select"
            :label="__('They can')"
            :options="levelOptions"
          />
          <Button variant="solid" :label="__('Make a link')" :loading="making" @click="make" />
        </div>

        <!-- Said before it is made rather than after. An editable link is a
             different thing from a read-only one and the difference is worth
             a sentence: whoever holds it changes the file everybody else is
             looking at, and there is no name on the change. -->
        <Alert
          v-if="level === 'write'"
          theme="amber"
          :title="__('Anybody with this link can edit')"
          :description="__('Changes go into the file, attributed to the link rather than a person.')"
        />

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
              <p class="truncate text-xs text-ink-secondary">{{ absolute(row) }}</p>
              <p class="text-p-xs text-ink-muted">
                {{ row.level === 'write' ? __('Can edit') : __('Read only') }}
                ·
                {{ row.revoked ? __('Revoked') : __('Until {0}', [until(row)]) }}
                ·
                {{
                  row.opened === 1
                    ? __('opened {0} time', [row.opened])
                    : __('opened {0} times', [row.opened])
                }}
              </p>
            </div>
            <!--
              `label` as well as `tooltip`. An icon-only Button takes its
              accessible name from the label, and a tooltip is not one: without
              this a screen reader announces both of these as "button", and the
              destructive one is indistinguishable from the harmless one.
            -->
            <Button
              v-if="!row.revoked"
              icon="lucide-copy"
              variant="ghost"
              :label="__('Copy the link')"
              :tooltip="__('Copy the link')"
              @click="copy(row)"
            />
            <Button
              v-if="!row.revoked"
              icon="lucide-x"
              variant="ghost"
              theme="red"
              :label="__('Stop this link working')"
              :tooltip="__('Stop this link working')"
              @click="revoke(row)"
            />
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Alert, Button, Dialog, Divider, ErrorMessage, FormControl, toast } from '@/ui'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

// The server's own bound is ninety days; these are the answers people give.
const dayOptions = computed(() => [
  { label: __('a day'), value: '1' },
  { label: __('a week'), value: '7' },
  { label: __('a month'), value: '30' },
  { label: __('three months'), value: '90' },
])

const props = defineProps({
  file: { type: Object, default: null },
})

const open = defineModel({ type: Boolean, default: false })

// What the link hands over. `read` first and by default: an editable link is
// the unusual one and should be chosen, not arrived at.
const levelOptions = computed(() => [
  { label: __('open it'), value: 'read' },
  { label: __('open and edit it'), value: 'write' },
])

// Only where this person may write the file. The server refuses either way —
// you cannot give away a right you do not have — and drawing the choice
// anyway would be offering something that fails on the press.
const canWrite = computed(() => props.file?.can_write !== false)

const days = ref('7')
const level = ref('read')
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
    error.value = errorText(e)
  }
}

async function make() {
  making.value = true
  error.value = ''
  try {
    const made = await workspace.driveMakeLink(props.file.name, Number(days.value), level.value)
    await copy(made)
    await load()
  } catch (e) {
    error.value = errorText(e)
  } finally {
    making.value = false
  }
}

async function copy(row) {
  try {
    await navigator.clipboard?.writeText(absolute(row))
    toast.success(__('Link copied'))
  } catch {
    // A browser that refuses the clipboard is not a failed share — the link is
    // on screen and can be selected.
    toast.success(__('Link made'))
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
