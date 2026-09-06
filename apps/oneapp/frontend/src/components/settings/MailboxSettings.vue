<template>
  <!--
    The mail settings that belong to a person rather than to the workspace.

    They were all in the admin's Email tab, which meant a colleague who answers
    `sales@` could not set their own signature, could not say they were away,
    and could not file their own mail — the three things somebody with a
    mailbox actually asks for. Nothing here is an admin's: every endpoint under
    it already checked that the address is one the caller holds, and the tab is
    offered on exactly that question. See `oneapp_core/tabs.py`.
  -->
  <SettingsHeader
    title="Mailbox"
    description="Your signature, your away message, and where your mail files itself."
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" text="Loading" />

    <div v-else class="flex flex-col gap-6 py-4">
      <EmptyState
        v-if="!held.length && !connected.length"
        icon="lucide-at-sign"
        title="No address yet"
        description="An admin gives you one, or connect the mailbox you already have below."
      />

      <!-- The signature is the address's, not the account's: `sales@` signs
           the same way whoever answers it, which is the reason `signatures.py`
           holds off the framework's own per-user rule. -->
      <div v-if="held.length" class="flex flex-col gap-2">
        <div
          v-for="row in held"
          :key="row.name"
          class="flex flex-col gap-3 rounded-6 border border-outline-gray-2 p-3"
          data-slot="mailbox-address"
        >
          <div class="flex items-center gap-2">
            <span class="truncate text-base font-medium text-ink-gray-8">
              {{ row.email_id }}
            </span>
            <Badge v-if="row.default_outgoing" theme="green" label="Sends notifications" />
          </div>

          <FormControl
            type="textarea"
            label="Signature"
            :rows="3"
            :model-value="row.signature"
            placeholder="Added to the bottom of mail sent from this address."
            @change="saveSignature(row, $event.target.value)"
          />
        </div>
      </div>

      <!--
        Rules and the out-of-office, for one address at a time. Both belong to a
        mailbox rather than to a workspace, so a picker rather than a single
        form. Frappe has the auto-reply already — what it does not have is a
        date, and one somebody forgot to switch off answers their mail for a
        month.
      -->
      <div v-if="held.length" class="flex flex-col gap-3 border-t border-outline-gray-1 pt-4">
        <div class="flex items-end gap-2">
          <span class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
            Rules and away message
          </span>
          <Select
            v-if="held.length > 1"
            v-model="chosen"
            class="ms-auto"
            :options="held.map((one) => ({ label: one.email_id, value: one.email_id }))"
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
          <!-- Named for what it saves, not "Save": this panel holds several
               independent forms. -->
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

        <!-- The two the rule could always do and the form never offered.
             `star` in particular was stored, listed and fetched from the day
             rules shipped and acted on nowhere. -->
        <div class="flex flex-wrap items-center gap-4">
          <Checkbox v-model="rule.mark_read" label="Mark it read" />
          <Checkbox v-model="rule.star" label="Star it" />
        </div>
        <ErrorMessage v-if="ruleError" :message="ruleError" />
      </div>

      <!--
        And for most people the half that matters: the address they have used
        for nine years. Never gated on a role — a mailbox somebody connects
        with their own password is theirs.
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
                 and nobody finding out. -->
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

          <!-- Hidden until asked for: four fields is a form somebody fills in,
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
import { session } from '@/lib/shell/session'

const loading = ref(true)

const addresses = ref([])
const connected = ref([])

const connecting = ref(false)
const connectError = ref('')
const advanced = ref(false)
const guess = ref({})
const mailbox = ref({ email_id: '', password: '', email_server: '', smtp_server: '' })

const user = computed(() => session.user?.name || '')

/**
 * The addresses this person holds.
 *
 * `addresses.listing` returns every address the workspace owns — deliberately,
 * so "why can Sam send as sales@ and I cannot" is answerable. This tab is the
 * other question, so it narrows to the ones with this person's name on them.
 */
const held = computed(() =>
  addresses.value.filter((one) => (one.granted_to || []).includes(user.value)),
)

// --- rules and the away message ---------------------------------------------
const chosen = ref('')
const rules = ref([])
const ruleError = ref('')
const awayState = reactive({ enabled: false, message: '', until: '' })
const rule = reactive({
  title: '', field: 'Sender', operator: 'Contains', matches: '', into: '',
  mark_read: false, star: false,
})

watch(chosen, async (address) => {
  if (!address) return
  rules.value = (await workspace.mailRules(address)) || []
  Object.assign(awayState, await workspace.mailAway(address))
})

async function addRule() {
  ruleError.value = ''
  try {
    await workspace.mailSaveRule({
      ...rule,
      address: chosen.value,
      enabled: 1,
      // The doctype's fields are Check, which is 0/1 and not a boolean.
      mark_read: rule.mark_read ? 1 : 0,
      star: rule.star ? 1 : 0,
    })
    Object.assign(rule, { title: '', matches: '', into: '', mark_read: false, star: false })
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
 * Saved on blur rather than on every keystroke, and without reloading the list:
 * a signature is a paragraph somebody types slowly, and a reload after each
 * character would move the cursor out from under them.
 */
async function saveSignature(row, value) {
  if (value === row.signature) return
  await workspace.mailUpdate(row.name, { signature: value, add_signature: 1 })
  row.signature = value
}

// Watched rather than hung off a `change` event, which fires on blur: somebody
// who types their address and goes straight for the password field would see
// the servers appear a moment late, or not at all.
watch(
  () => mailbox.value.email_id,
  () => describe(),
)

/**
 * Fill in what the address already told us. Somebody typing `you@gmail.com` has
 * said where their mail lives. The note comes back with it — for Gmail and
 * Outlook, "this needs an app password", which is the commonest reason a
 * connection fails, said before it fails rather than after.
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

async function load() {
  loading.value = true
  try {
    const [mail, boxes] = await Promise.all([
      workspace.mail(),
      workspace.mailConnected(),
    ])
    addresses.value = mail.addresses || []
    connected.value = boxes || []
    // The address whose rules are shown. First one held, because a picker that
    // opens on nothing makes somebody choose before they can look.
    chosen.value = held.value[0]?.email_id || ''
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
