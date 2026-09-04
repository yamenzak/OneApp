<template>
  <!--
    Addresses: what this workspace sends from, and who may use each.

    One list, not three, because there is one kind of thing here. An address a
    person holds alone and an address a team shares differ only in how many
    names are against them, and building two screens for that would mean two
    sets of rules to keep in step. See `oneapp_core/email/addresses.py`.
  -->
  <SettingsHeader
    title="Email"
    description="The addresses this workspace sends from, and who may use each."
    :class="PANEL_HEADER"
  />
  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" text="Loading" />

    <div v-else class="flex flex-col gap-6 py-4">
      <!--
        What leaves the site today. Shown first and without being asked for,
        because "which address do my notifications come from" is the question
        this page exists to answer and everything else is a way of changing it.
      -->
      <div class="flex flex-col gap-2 rounded-4 bg-surface-gray-1 p-3">
        <div class="flex items-center justify-between gap-3">
          <span class="text-p-sm text-ink-gray-7">Notifications leave from</span>
          <span class="text-p-sm font-medium text-ink-gray-8">
            {{ sendingFrom }}
          </span>
        </div>
        <div class="flex items-center justify-between gap-3">
          <span class="text-p-xs text-ink-gray-5">Sent this hour</span>
          <span class="text-p-xs tabular-nums text-ink-gray-6">
            {{ usage.sent_this_hour ?? 0 }} of {{ usage.hourly_limit ?? '—' }}
            <span class="text-ink-gray-4">·</span>
            {{ usage.sent_today ?? 0 }} of {{ usage.daily_limit ?? '—' }} today
          </span>
        </div>
        <p v-if="usage.suspended" class="text-p-xs text-ink-red-4">
          This workspace is suspended and is not sending email.
        </p>
      </div>

      <EmptyState
        v-if="!addresses.length"
        icon="lucide-mail"
        title="No addresses yet"
        :description="`Add one on ${domain} and mail to it arrives here.`"
      />

      <div v-else class="flex flex-col gap-2">
        <div
          v-for="row in addresses"
          :key="row.name"
          class="flex flex-col gap-3 rounded-6 border border-outline-gray-2 p-3"
          data-slot="mail-address"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="flex min-w-0 flex-col">
              <div class="flex items-center gap-2">
                <span class="truncate text-base font-medium text-ink-gray-8">
                  {{ row.email_id }}
                </span>
                <Badge v-if="row.default_outgoing" theme="green" label="Sends notifications" />
                <Badge v-if="!row.ours" theme="amber" label="Your domain" />
              </div>
              <span class="truncate text-p-xs text-ink-gray-5">
                {{ row.granted_to.length ? row.granted_to.join(', ') : 'Nobody yet' }}
              </span>
            </div>

            <div v-if="canManage" class="flex shrink-0 items-center gap-1">
              <Button
                v-if="!row.default_outgoing"
                variant="ghost"
                size="sm"
                icon="lucide-send"
                label="Send notifications from this"
                tooltip="Send notifications from this"
                @click="setDefault(row)"
              />
              <Button
                variant="ghost"
                size="sm"
                icon="lucide-users"
                label="Who may use this"
                tooltip="Who may use this"
                @click="opened = opened === row.name ? '' : row.name"
              />
              <Button
                variant="ghost"
                size="sm"
                icon="lucide-trash-2"
                label="Remove this address"
                tooltip="Remove this address"
                @click="remove(row)"
              />
            </div>
          </div>

          <!-- The signature, editable by anybody who holds the address: it is
               their name at the bottom of their own mail. -->
          <FormControl
            v-if="row.granted_to.includes(user) || canManage"
            type="textarea"
            label="Signature"
            :rows="3"
            :model-value="row.signature"
            placeholder="Added to the bottom of mail sent from this address."
            @change="saveSignature(row, $event.target.value)"
          />

          <div v-if="opened === row.name && canManage" class="flex flex-col gap-2">
            <span class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
              Who may use this
            </span>
            <label
              v-for="person in members"
              :key="person.name"
              class="flex items-center gap-2 text-p-sm text-ink-gray-7"
            >
              <Checkbox
                :model-value="row.granted_to.includes(person.name)"
                :label="person.full_name || person.name"
                @update:model-value="toggle(row, person.name, $event)"
              />
            </label>
          </div>
        </div>
      </div>

      <div v-if="canManage" class="flex flex-col gap-2 border-t border-outline-gray-1 pt-4">
        <span class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
          Add an address
        </span>
        <div class="flex items-end gap-2">
          <FormControl
            v-model="draft"
            class="flex-1"
            label="Address"
            :placeholder="`sales`"
            :description="`Becomes name@${domain}`"
          />
          <Button variant="solid" label="Add" :loading="saving" @click="create" />
        </div>
        <ErrorMessage v-if="error" :message="error" />
      </div>
    </div>
  </SettingsBody>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  Badge,
  Button,
  Checkbox,
  EmptyState,
  ErrorMessage,
  FormControl,
  LoadingText,
  SettingsBody,
  SettingsHeader,
} from '@/ui'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'
import { session } from '../../lib/session'

const loading = ref(true)
const saving = ref(false)
const error = ref('')
const draft = ref('')
const opened = ref('')

const addresses = ref([])
const members = ref([])
const domain = ref('')
const canManage = ref(false)
const usage = ref({})

const user = computed(() => session.user?.name || '')

/**
 * Which address the workspace's own mail actually leaves from.
 *
 * The one marked default where there is one, and the platform's own sender
 * otherwise — reported by the server rather than assumed here, because "we did
 * not set one so it must be the platform's" is exactly the assumption that is
 * wrong on a site where the token is missing and nothing sends at all.
 */
const sendingFrom = computed(() => {
  const chosen = addresses.value.find((one) => one.default_outgoing)
  if (chosen) return chosen.email_id
  return usage.value.sender || 'the platform address'
})

async function load() {
  loading.value = true
  try {
    const [mail, sending] = await Promise.all([workspace.mail(), workspace.mailUsage()])
    addresses.value = mail.addresses || []
    members.value = mail.members || []
    domain.value = mail.domain || ''
    canManage.value = !!mail.can_manage
    usage.value = sending || {}
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function create() {
  error.value = ''
  saving.value = true
  try {
    await workspace.mailCreate(draft.value.trim().toLowerCase(), '', [])
    draft.value = ''
    await load()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  await workspace.mailRemove(row.name)
  await load()
}

async function setDefault(row) {
  await workspace.mailSetDefault(row.name)
  await load()
}

async function toggle(row, person, wanted) {
  if (wanted) await workspace.mailGrant(row.name, person)
  else await workspace.mailRevoke(row.name, person)
  await load()
}

/**
 * Saved on blur rather than on every keystroke, and without reloading the list.
 *
 * A signature is a paragraph somebody types slowly; a request per character
 * would be a request per character, and a reload after each one would move the
 * cursor out from under them.
 */
async function saveSignature(row, value) {
  if (value === row.signature) return
  await workspace.mailUpdate(row.name, { signature: value, add_signature: 1 })
  row.signature = value
}
</script>
