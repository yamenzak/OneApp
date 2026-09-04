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

      <!--
        Rules and the out-of-office, for one address at a time.

        Both belong to a mailbox rather than to a workspace: `sales@` and `ap@`
        sort differently and go away separately, so a picker rather than a
        single form. Frappe has the auto-reply already — what it does not have
        is a date, and one somebody forgot to switch off answers their mail for
        a month.
      -->
      <div v-if="addresses.length" class="flex flex-col gap-3 border-t border-outline-gray-1 pt-4">
        <div class="flex items-end gap-2">
          <span class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
            Rules and away message
          </span>
          <Select
            v-if="addresses.length > 1"
            v-model="chosen"
            class="ms-auto"
            :options="addresses.map((one) => ({ label: one.email_id, value: one.email_id }))"
          />
        </div>

        <div class="flex flex-col gap-2 rounded-6 border border-outline-gray-2 p-3">
          <Checkbox
            v-model="awayState.enabled"
            label="Reply automatically while I am away"
            data-slot="mail-away"
          />
          <template v-if="awayState.enabled">
            <FormControl
              v-model="awayState.message"
              type="textarea"
              label="What it says"
              :rows="3"
            />
            <FormControl
              v-model="awayState.until"
              type="date"
              label="Until"
              description="It switches itself off the day after this."
            />
          </template>
          <!-- Named for what it saves, not "Save". This panel holds four
               independent forms — a signature, a mailbox, rules, this — and a
               bare Save in the middle of them says nothing about which. -->
          <Button
            class="self-start"
            variant="subtle"
            label="Save away message"
            data-slot="mail-save-away"
            @click="saveAway"
          />
        </div>

        <div
          v-for="one in rules"
          :key="one.name"
          class="flex items-center gap-2 rounded-6 border border-outline-gray-2 p-3"
          data-slot="mail-rule"
        >
          <div class="flex min-w-0 flex-1 flex-col">
            <span class="truncate text-base font-medium text-ink-gray-8">{{ one.title }}</span>
            <span class="truncate text-p-xs text-ink-gray-5">
              {{ one.field }} {{ one.operator.toLowerCase() }} “{{ one.matches }}”
              <template v-if="one.into">→ {{ one.into }}</template>
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon="lucide-trash-2"
            :label="`Remove ${one.title}`"
            :tooltip="`Remove ${one.title}`"
            @click="dropRule(one)"
          />
        </div>

        <div class="flex flex-wrap items-end gap-2">
          <FormControl v-model="rule.title" class="flex-1" label="Rule" placeholder="Applicants" />
          <Select
            v-model="rule.field"
            label="Look at"
            :options="['Sender', 'Subject', 'Recipient', 'Body']"
          />
          <Select
            v-model="rule.operator"
            label="That"
            :options="['Contains', 'Is', 'Starts with', 'Ends with']"
          />
          <FormControl v-model="rule.matches" class="flex-1" label="This" />
          <FormControl v-model="rule.into" class="flex-1" label="File into" />
          <Button variant="solid" label="Add rule" @click="addRule" />
        </div>
        <ErrorMessage v-if="ruleError" :message="ruleError" />
      </div>

      <!--
        The other half, and for most people the half that matters: the address
        they have used for nine years, which they are not giving up because a
        new product would prefer it. Not gated on `canManage` — a mailbox
        somebody connects with their own password is theirs, and an owner has no
        more business connecting it than a colleague does.
      -->
      <div class="flex flex-col gap-2 border-t border-outline-gray-1 pt-4">
        <span class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
          Your own mailboxes
        </span>

        <div
          v-for="box in connected"
          :key="box.name"
          class="flex items-center justify-between gap-3 rounded-6 border border-outline-gray-2 p-3"
          data-slot="mail-connected"
        >
          <div class="flex min-w-0 flex-col">
            <span class="truncate text-base font-medium text-ink-gray-8">
              {{ box.email_id }}
            </span>
            <span class="truncate text-p-xs text-ink-gray-5">{{ box.server }}</span>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <!-- Frappe's own consecutive-failure count. Surfaced because the
                 alternative is a mailbox that quietly stopped three weeks ago
                 and nobody finding out until they wonder why it is silent. -->
            <Badge
              v-if="box.awaiting_password || box.failures"
              theme="red"
              label="Not connecting"
            />
            <Button
              variant="ghost"
              size="sm"
              icon="lucide-unplug"
              label="Disconnect this mailbox"
              tooltip="Disconnect this mailbox"
              @click="disconnect(box)"
            />
          </div>
        </div>

        <div class="flex flex-col gap-2">
          <div class="flex items-end gap-2">
            <FormControl
              v-model="mailbox.email_id"
              class="flex-1"
              label="Mailbox address"
              placeholder="you@gmail.com"
            />
            <FormControl
              v-model="mailbox.password"
              class="flex-1"
              type="password"
              label="Password"
              :description="guess.note"
            />
          </div>

          <!-- Hidden until asked for. Four fields is a form somebody fills in;
               six with two hostnames in them is a form they abandon. -->
          <div v-if="advanced" class="flex items-end gap-2">
            <FormControl v-model="mailbox.email_server" class="flex-1" label="Incoming (IMAP)" />
            <FormControl v-model="mailbox.smtp_server" class="flex-1" label="Outgoing (SMTP)" />
          </div>

          <div class="flex items-center justify-between gap-2">
            <Button
              variant="ghost"
              size="sm"
              :label="advanced ? 'Hide servers' : 'Change the servers'"
              @click="advanced = !advanced"
            />
            <Button
              variant="solid"
              label="Connect"
              :loading="connecting"
              @click="connect"
            />
          </div>
          <ErrorMessage v-if="connectError" :message="connectError" />
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  Badge,
  Button,
  Checkbox,
  ErrorMessage,
  FormControl,
  LoadingText,
  Select,
  SettingsBody,
  SettingsHeader,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
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

const connected = ref([])
const connecting = ref(false)
const connectError = ref('')
const advanced = ref(false)
const guess = ref({})
const mailbox = ref({ email_id: '', password: '', email_server: '', smtp_server: '' })

const user = computed(() => session.user?.name || '')

// --- rules and the away message ---------------------------------------------
const chosen = ref('')
const rules = ref([])
const ruleError = ref('')
const awayState = reactive({ enabled: false, message: '', until: '' })
const rule = reactive({
  title: '', field: 'Sender', operator: 'Contains', matches: '', into: '',
})

watch(chosen, async (address) => {
  if (!address) return
  rules.value = (await workspace.mailRules(address)) || []
  Object.assign(awayState, await workspace.mailAway(address))
})

async function addRule() {
  ruleError.value = ''
  try {
    await workspace.mailSaveRule({ ...rule, address: chosen.value, enabled: 1 })
    Object.assign(rule, { title: '', matches: '', into: '' })
    rules.value = (await workspace.mailRules(chosen.value)) || []
  } catch (e) {
    ruleError.value = e.message || String(e)
  }
}

async function dropRule(one) {
  await workspace.mailDropRule(one.name)
  rules.value = (await workspace.mailRules(chosen.value)) || []
}

async function saveAway() {
  await workspace.mailSetAway({
    address: chosen.value,
    enabled: awayState.enabled ? 1 : 0,
    message: awayState.message,
    until: awayState.until,
  })
}

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
    const [mail, sending, boxes] = await Promise.all([
      workspace.mail(),
      workspace.mailUsage(),
      workspace.mailConnected(),
    ])
    addresses.value = mail.addresses || []
    members.value = mail.members || []
    domain.value = mail.domain || ''
    canManage.value = !!mail.can_manage
    usage.value = sending || {}
    connected.value = boxes || []
    // The address whose rules are shown. First one held, because a picker that
    // opens on nothing makes somebody choose before they can look.
    chosen.value = addresses.value[0]?.email_id || ''
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

// Watched rather than hung off a `change` event: `change` fires on blur, so
// somebody who types their address and goes straight for the password field
// sees the servers appear under their cursor a moment late — or not at all, if
// they never leave the field.
watch(
  () => mailbox.value.email_id,
  () => describe(),
)

/**
 * Fill in what the address already told us.
 *
 * Somebody typing `you@gmail.com` has said where their mail lives, and asking
 * them for `imap.gmail.com` afterwards is asking them to look up something we
 * know. The note comes back with it — for Gmail and Outlook that note is "this
 * needs an app password", which is the single commonest reason a connection
 * fails, said before it fails rather than after.
 */
async function describe() {
  const address = (mailbox.value.email_id || '').trim().toLowerCase()
  if (!address.includes('@')) return
  guess.value = (await workspace.mailSuggestion(address)) || {}
  mailbox.value.email_server = guess.value.email_server || ''
  mailbox.value.smtp_server = guess.value.smtp_server || ''
}

async function connect() {
  connectError.value = ''
  connecting.value = true
  try {
    await workspace.mailConnect({
      email_id: (mailbox.value.email_id || '').trim().toLowerCase(),
      password: mailbox.value.password,
      email_server: mailbox.value.email_server,
      smtp_server: mailbox.value.smtp_server,
    })
    mailbox.value = { email_id: '', password: '', email_server: '', smtp_server: '' }
    guess.value = {}
    advanced.value = false
    await load()
  } catch (e) {
    connectError.value = e.message || String(e)
  } finally {
    connecting.value = false
  }
}

async function disconnect(box) {
  await workspace.mailDisconnect(box.name)
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
