<template>
  <!--
    Addresses: what this workspace sends from, and who may use each.

    One list, not three, because there is one kind of thing here. An address a
    person holds alone and one a team shares differ only in how many names are
    against them. See `onemail/addresses.py`.
  -->
  <SettingsHeader
    :title="__('Email')"
    :description="__('The addresses this workspace sends from, and who may use each.')"
    :class="PANEL_HEADER"
  />
  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" :text="__('Loading')" />

    <div v-else class="flex flex-col gap-6 py-4">
      <!-- What leaves the site today. Shown first and without being asked for,
           because "which address do my notifications come from" is the question
           this page exists to answer. -->
      <div class="flex flex-col gap-2 rounded-4 bg-surface-gray-1 p-3">
        <div class="flex items-center justify-between gap-3">
          <span class="text-p-sm text-ink-gray-7">{{ __('Notifications leave from') }}</span>
          <span class="text-p-sm font-medium text-ink-gray-8">
            {{ sendingFrom }}
          </span>
        </div>
        <!-- Each half says its own window. The row was labelled "Sent this
             hour" and then carried the day's count beside it, so half of what
             it showed was under a heading that did not cover it. -->
        <div class="flex items-center justify-between gap-3">
          <span class="text-p-xs text-ink-gray-5">{{ __('Sent') }}</span>
          <span class="text-p-xs tabular-nums text-ink-gray-6">
            {{ __('{0} of {1} this hour', [usage.sent_this_hour ?? 0, usage.hourly_limit ?? '—']) }}
            <span class="text-ink-gray-4">·</span>
            {{ __('{0} of {1} today', [usage.sent_today ?? 0, usage.daily_limit ?? '—']) }}
          </span>
        </div>
        <p v-if="usage.suspended" class="text-p-xs text-ink-red-4">
          {{ __('This workspace is suspended and is not sending email.') }}
        </p>
      </div>

      <EmptyState
        v-if="!addresses.length"
        icon="lucide-mail"
        :title="__('No addresses yet')"
        :description="__('Add one on {0} and mail to it arrives here.', [domain])"
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
                <!-- What this address *is*. Five rows all read the same
                     before this: nothing said which was the shared mailbox and
                     which was somebody's own. `addresses.kind_of` works it out
                     from the domain and the number of people on it. -->
                <Badge :theme="KINDS[row.kind]?.theme || 'gray'"
                       :label="KINDS[row.kind]?.label || row.kind" />
              </div>
              <span class="truncate text-p-xs text-ink-gray-5">
                {{ row.granted_to.length ? row.granted_to.join(', ') : __('Nobody yet') }}
              </span>
            </div>

            <div v-if="canManage" class="flex shrink-0 items-center gap-1">
              <Button
                v-if="!row.default_outgoing"
                variant="ghost"
                size="sm"
                icon="lucide-send"
                :label="__('Send notifications from this')"
                :tooltip="__('Send notifications from this')"
                @click="setDefault(row)"
              />
              <Button
                variant="ghost"
                size="sm"
                icon="lucide-users"
                :label="__('Who may use this')"
                :tooltip="__('Who may use this')"
                @click="opened = opened === row.name ? '' : row.name"
              />
              <Button
                variant="ghost"
                size="sm"
                icon="lucide-trash-2"
                :label="__('Remove this address')"
                :tooltip="__('Remove this address')"
                @click="remove(row)"
              />
            </div>
          </div>

          <!-- Editable here by an admin, who manages an address whether or not
               they answer it. Whoever holds it edits the same field under their
               own Mailbox tab, which is where it reads as theirs. -->
          <FormControl
            v-if="canManage"
            type="textarea"
            :label="__('Signature')"
            :rows="3"
            :model-value="row.signature"
            :placeholder="__('Added to the bottom of mail sent from this address.')"
            @change="saveSignature(row, $event.target.value)"
          />

          <div v-if="opened === row.name && canManage" class="flex flex-col gap-2">
            <span class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
              {{ __('Who may use this') }}
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

      <!--
        A domain the workspace owns. `email/verify.py` has answered these two
        questions since the day it shipped and nothing drew them, so a
        workspace could add `billing@theirs.com` and had nowhere to be told what
        DNS to publish — and no way to know sending was refused until it was.
      -->
      <section v-if="canManage" class="flex flex-col gap-3 border-t border-outline-gray-1 pt-5">
        <h3 class="text-base-medium text-ink-gray-8">{{ __('Your own domain') }}</h3>
        <p class="text-p-sm text-ink-gray-5">
          {{ __('Send as you@yourcompany.com rather than on ours. Mail to that domain still goes wherever its MX points — connect those mailboxes under your own Mailbox tab to read them here.') }}
        </p>

        <div class="flex items-end gap-2">
          <FormControl
            v-model="checking"
            class="flex-1"
            :label="__('Domain')"
            :placeholder="__('yourcompany.com')"
          />
          <Button :label="__('Check DNS')" :loading="checkingNow" @click="checkDomain" />
        </div>

        <div v-if="dns.records" class="flex flex-col gap-2">
          <Badge
            :theme="dns.verified ? 'green' : 'amber'"
            :label="dns.verified ? __('Verified') : __('Not verified yet')"
          />
          <div
            v-for="record in dns.records"
            :key="record.kind"
            class="flex flex-col gap-1 rounded-6 border border-outline-gray-2 p-3"
            data-slot="mail-dns-record"
          >
            <div class="flex items-center gap-2">
              <span class="text-base font-medium text-ink-gray-8">{{ record.kind }}</span>
              <span class="text-p-xs text-ink-gray-5">{{ record.type }}</span>
            </div>
            <span class="break-all text-p-xs text-ink-gray-6">{{ record.host }}</span>
            <span class="break-all font-mono text-p-xs text-ink-gray-7">
              {{ record.value || '—' }}
            </span>
            <span v-if="record.note" class="text-p-xs text-ink-gray-5">{{ record.note }}</span>
          </div>
          <Button
            v-if="!dns.verified"
            class="self-start"
            variant="solid"
            :label="__('I have published them')"
            :loading="confirming"
            @click="confirmDomain"
          />
        </div>
      </section>

      <!--
        Whether a member may bring their own mailbox. Most workspaces want yes
        — it is the half that matters to somebody with a nine-year-old address
        — and a regulated one wants no, because a connected mailbox brings
        private mail into a workspace their colleagues hold addresses in.
      -->
      <!--
        A mailbox the team shares. One set of credentials, several people
        reading it: `sales@thecompany.com` on their own server, granted the way
        an address on our domain is. Without this a workspace could grant
        sending as `sales@` to three people and reading it to one, which is not
        what anybody means by a shared mailbox.
      -->
      <section v-if="canManage" class="flex flex-col gap-3 border-t border-outline-gray-1 pt-5">
        <h3 class="text-base-medium text-ink-gray-8">{{ __('A mailbox the team shares') }}</h3>
        <p class="text-p-sm text-ink-gray-5">
          {{ __('Connect one the company already has, then grant it below like any other address. Everyone who holds it reads the same inbox — and the same sent mail.') }}
        </p>
        <!--
          The hint sits under the row rather than on the password field. On the
          field it is a description below one of three controls, and `items-end`
          then aligns the bottom of *that* — which lifts the password box a line
          above the address box beside it.
        -->
        <div class="flex flex-wrap items-end gap-2">
          <FormControl
            v-model="team.email_id"
            class="flex-1"
            :label="__('Mailbox address')"
            :placeholder="__('sales@yourcompany.com')"
          />
          <FormControl
            v-model="team.password"
            class="flex-1"
            type="password"
            :label="__('Password')"
          />
          <Button
            variant="solid"
            :label="__('Connect')"
            data-slot="mail-connect-shared"
            :loading="connecting"
            @click="connectShared"
          />
        </div>
        <p class="text-p-xs text-ink-gray-5">
          {{ __('An app password where the provider needs one.') }}
        </p>
        <ErrorMessage v-if="teamError" :message="teamError" />
      </section>

      <section v-if="canManage" class="flex flex-col gap-3 border-t border-outline-gray-1 pt-5">
        <h3 class="text-base-medium text-ink-gray-8">{{ __('Outside mailboxes') }}</h3>
        <p class="text-p-sm text-ink-gray-5">
          {{ __("Whether members may connect a mailbox they already have, such as Gmail or the company's own server.") }}
        </p>
        <div class="flex flex-wrap items-center gap-1">
          <Button
            v-for="mode in CONNECT_MODES"
            :key="mode.value"
            size="sm"
            :variant="policy.mode === mode.value ? 'solid' : 'subtle'"
            :label="mode.label"
            :data-slot="`mail-policy-${mode.value}`"
            @click="savePolicy(mode.value)"
          />
        </div>
        <FormControl
          v-if="policy.mode === 'domains'"
          :model-value="policy.domains.join(', ')"
          :label="__('Allowed domains')"
          :placeholder="__('yourcompany.com, gmail.com')"
          :description="__('Comma separated. A mailbox on anything else is refused.')"
          @change="savePolicy('domains', $event.target.value)"
        />
      </section>

      <div v-if="canManage" class="flex flex-col gap-2 border-t border-outline-gray-1 pt-5">
        <!-- The same heading the two sections above it use. It was the one in
             uppercase, which read as a different kind of thing. -->
        <h3 class="text-base-medium text-ink-gray-8">{{ __('Add an address') }}</h3>
        <div class="flex items-end gap-2">
          <FormControl
            v-model="draft"
            class="flex-1"
            :label="__('Address')"
            :placeholder="__('sales')"
            :description="__('Becomes {0}', [becomes])"
          />
          <Button variant="solid" :label="__('Add')" :loading="saving" @click="create" />
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
  ErrorMessage,
  FormControl,
  LoadingText,
  SettingsBody,
  SettingsHeader,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'
import { __ } from '@/lib/runtime/translate'
import { errorText } from '@/lib/runtime/errors'

/**
 * The five kinds an address can be, in the workspace's words.
 *
 * Derived on the server from the domain and how many people hold it — see
 * `addresses.kind_of`. Written out here rather than built from the key so the
 * label is a sentence somebody wrote and not a capitalised enum.
 */
const KINDS = {
  workspace: { label: __('Sends notifications'), theme: 'green' },
  shared: { label: __('Shared'), theme: 'blue' },
  person: { label: __('One person'), theme: 'gray' },
  domain: { label: __('Your domain'), theme: 'amber' },
  connected: { label: __('Connected mailbox'), theme: 'gray' },
}

/** Who may connect a mailbox of their own. See `addresses.connect_policy`. */
const CONNECT_MODES = [
  { value: 'any', label: __('Anybody') },
  { value: 'domains', label: __('Only some domains') },
  { value: 'none', label: __('Nobody') },
]

const loading = ref(true)
const saving = ref(false)
const policy = ref({ mode: 'any', domains: [] })

const team = ref({ email_id: '', password: '' })
const connecting = ref(false)
const teamError = ref('')

const checking = ref('')
const checkingNow = ref(false)
const confirming = ref(false)
const dns = ref({})
const error = ref('')
const draft = ref('')

// What the address will be, as it is typed. The literal word `name` stood here
// before, which made the one line on the page that answers "what am I about to
// create" the one line that never changed. Falls back to the placeholder rather
// than to a stand-in word, so the example and the answer are the same shape.
const becomes = computed(() => {
  const local = draft.value.trim().toLowerCase() || 'sales'
  return `${prefix.value ? prefix.value + '.' : ''}${local}@${domain.value}`
})
const opened = ref('')

const addresses = ref([])
const members = ref([])
const domain = ref('')
// Every address this workspace issues carries its label on the front — one
// domain serves the whole platform, see `onemail/addresses.py`.
const prefix = ref('')
const canManage = ref(false)
const usage = ref({})

/**
 * Which address the workspace's own mail actually leaves from: the one marked
 * default, and the platform's own sender otherwise — reported by the server
 * rather than assumed here, because "we did not set one so it must be the
 * platform's" is wrong on a site where the token is missing.
 */
const sendingFrom = computed(() => {
  const chosen = addresses.value.find((one) => one.default_outgoing)
  if (chosen) return chosen.email_id
  return usage.value.sender || __('the platform address')
})

async function connectShared() {
  teamError.value = ''
  connecting.value = true
  try {
    // Granted to the admin doing it, and then to whoever else through the
    // list above — the same grant an address on our own domain gets.
    await workspace.mailConnect({
      email_id: team.value.email_id.trim().toLowerCase(),
      password: team.value.password,
    })
    team.value = { email_id: '', password: '' }
    await load()
  } catch (e) {
    teamError.value = errorText(e)
  } finally {
    connecting.value = false
  }
}

async function checkDomain() {
  checkingNow.value = true
  try {
    dns.value = (await workspace.mailDomainStatus(checking.value.trim())) || {}
  } finally {
    checkingNow.value = false
  }
}

async function confirmDomain() {
  confirming.value = true
  try {
    await workspace.mailDomainConfirm(checking.value.trim())
    await checkDomain()
  } finally {
    confirming.value = false
  }
}

async function savePolicy(mode, domains) {
  policy.value = await workspace.mailSetConnectPolicy(
    mode,
    domains === undefined ? policy.value.domains.join(',') : domains,
  )
}

async function load() {
  loading.value = true
  try {
    const [mail, sending] = await Promise.all([
      workspace.mail(),
      workspace.mailUsage(),
    ])
    addresses.value = mail.addresses || []
    policy.value = mail.connect_policy || { mode: 'any', domains: [] }
    members.value = mail.members || []
    domain.value = mail.domain || ''
    prefix.value = mail.prefix || ''
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
    error.value = errorText(e)
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
 * Saved on blur rather than on every keystroke, and without reloading the list:
 * a signature is a paragraph somebody types slowly, and a reload after each
 * character would move the cursor out from under them.
 */
async function saveSignature(row, value) {
  if (value === row.signature) return
  await workspace.mailUpdate(row.name, { signature: value, add_signature: 1 })
  row.signature = value
}
</script>
