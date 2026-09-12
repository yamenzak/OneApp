<template>
  <!--
    The mail settings that belong to a person rather than to the workspace.

    They were all in the admin's Email tab, which meant a colleague who answers
    `sales@` could not set their own signature, could not say they were away,
    and could not file their own mail — the three things somebody with a
    mailbox actually asks for. Nothing here is an admin's: every endpoint under
    it already checked that the address is one the caller holds, and the tab is
    offered on exactly that question. See `onespace/tabs.py`.
  -->
  <SettingsHeader
    :title="__('Mailbox')"
    :description="__('Your signature, your away message, and where your mail files itself.')"
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" :text="__('Loading')" />

    <div v-else class="flex flex-col gap-6 py-4">
      <!--
        The address every member should already have. Nothing minted one: a
        person joined, opened Mail, and had nowhere to send from until an admin
        thought of it — a bottleneck on the one thing that has to work on the
        first morning. One each, suggested from the account they signed in with.
      -->
      <div
        v-if="ours.suggested"
        class="flex flex-wrap items-center justify-between gap-3 rounded-6 border border-outline-gray-2 bg-surface-gray-1 p-3"
        data-slot="mailbox-claim"
      >
        <div class="min-w-0">
          <p class="text-base font-medium text-ink-primary">{{ __('Take your address') }}</p>
          <p class="truncate text-sm text-ink-muted">
            {{ __("{0} — yours, on this workspace's domain.", [ours.suggested]) }}
          </p>
        </div>
        <Button
          variant="solid"
          :label="__('Claim it')"
          data-slot="mailbox-claim-go"
          :loading="claiming"
          @click="claim"
        />
      </div>

      <EmptyState
        v-else-if="!held.length && !connected.length"
        icon="lucide-at-sign"
        :title="__('No address yet')"
        :description="__('An admin gives you one, or connect the mailbox you already have below.')"
      />

      <!--
        Which of them a new message goes out as when nothing about the message
        decides it. The four rules are `mailbox.sending.default_sender`, and
        this is the third of them — a reply and a record answer for themselves.
      -->
      <div v-if="held.length > 1" class="flex flex-wrap items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="text-base text-ink-primary">{{ __('Write from') }}</p>
          <p class="text-p-sm text-ink-muted">
            {{ __('Unless you are replying, or writing on a record that already has correspondence.') }}
          </p>
        </div>
        <Select
          class="w-64"
          :model-value="defaultSender"
          :options="held.map((one) => ({ label: one.email_id, value: one.email_id }))"
          data-slot="mailbox-default-sender"
          @update:model-value="setDefault"
        />
      </div>

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
            <span class="truncate text-base font-medium text-ink-primary">
              {{ row.email_id }}
            </span>
            <Badge v-if="row.default_outgoing" theme="green" :label="__('Sends notifications')" />
          </div>

          <FormControl
            type="textarea"
            :label="__('Signature')"
            :rows="3"
            :model-value="row.signature"
            :placeholder="__('Added to the bottom of mail sent from this address.')"
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
      <section v-if="held.length" class="flex flex-col gap-3 border-t border-outline-gray-1 pt-5">
        <div class="flex items-center gap-2">
          <h3 class="text-base-medium text-ink-primary">{{ __('While you are away') }}</h3>
          <!-- Which address these two sections are about. Only when there is
               more than one to be about. -->
          <Select
            v-if="held.length > 1"
            v-model="chosen"
            class="ms-auto"
            :options="held.map((one) => ({ label: one.email_id, value: one.email_id }))"
          />
        </div>

        <div class="flex flex-col gap-2">
          <Checkbox
            v-model="awayState.enabled"
            :label="__('Reply automatically while I am away')"
            data-slot="mail-away"
          />
          <template v-if="awayState.enabled">
            <FormControl
              v-model="awayState.message"
              type="textarea"
              :label="__('What it says')"
              :rows="3"
            />
            <FormControl
              v-model="awayState.until"
              type="date"
              :label="__('Until')"
              :description="__('It switches itself off the day after this.')"
            />
          </template>
          <!-- Named for what it saves, not "Save": this panel holds several
               independent forms. -->
          <Button
            class="self-start"
            variant="subtle"
            :label="__('Save away message')"
            data-slot="mail-save-away"
            @click="saveAway"
          />
        </div>

        <h3 class="mt-2 text-base-medium text-ink-primary">{{ __('Rules') }}</h3>
        <p class="-mt-2 text-p-sm text-ink-muted">
          {{ __('Where mail that matches goes, before you see it.') }}
        </p>

        <div
          v-for="one in rules"
          :key="one.name"
          class="flex items-center gap-2 rounded-6 border border-outline-gray-2 p-3"
          data-slot="mail-rule"
        >
          <div class="flex min-w-0 flex-1 flex-col">
            <span class="truncate text-base font-medium text-ink-primary">{{ one.title }}</span>
            <span class="truncate text-xs text-ink-muted">
              {{ one.field }} {{ one.operator.toLowerCase() }} “{{ one.matches }}”
              <template v-if="one.into">→ {{ one.into }}</template>
            </span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            icon="lucide-trash-2"
            :label="__('Remove {0}', [one.title])"
            :tooltip="__('Remove {0}', [one.title])"
            @click="dropRule(one)"
          />
        </div>

        <div class="flex flex-wrap items-end gap-2">
          <FormControl v-model="rule.title" class="flex-1" :label="__('Rule')" :placeholder="__('Applicants')" />
          <Select
            v-model="rule.field"
            :label="__('Look at')"
            :options="['Sender', 'Subject', 'Recipient', 'Body']"
          />
          <Select
            v-model="rule.operator"
            :label="__('That')"
            :options="['Contains', 'Is', 'Starts with', 'Ends with']"
          />
          <FormControl v-model="rule.matches" class="flex-1" :label="__('This')" />
          <FormControl v-model="rule.into" class="flex-1" :label="__('File into')" />
          <Button variant="solid" :label="__('Add rule')" @click="addRule" />
        </div>

        <!-- The two the rule could always do and the form never offered.
             `star` in particular was stored, listed and fetched from the day
             rules shipped and acted on nowhere. -->
        <div class="flex flex-wrap items-center gap-4">
          <Checkbox v-model="rule.mark_read" :label="__('Mark it read')" />
          <Checkbox v-model="rule.star" :label="__('Star it')" />
        </div>
        <ErrorMessage v-if="ruleError" :message="ruleError" />
      </section>

      <!--
        And for most people the half that matters: the address they have used
        for nine years. Never gated on a role — a mailbox somebody connects
        with their own password is theirs.
      -->
      <section class="flex flex-col gap-2 border-t border-outline-gray-1 pt-5">
        <h3 class="text-base-medium text-ink-primary">{{ __('Your own mailboxes') }}</h3>
        <p class="text-p-sm text-ink-muted">
          {{ __('The address you already had. Read and answer it here.') }}
        </p>
        <!-- Said, not silently missing. A workspace can turn this off or hold
             it to a list of domains, and somebody refused is owed the reason
             rather than a form that fails on submit. -->
        <p v-if="!mayConnect" class="text-p-sm text-ink-secondary">
          {{ whyNot }}
        </p>

        <div
          v-for="box in connected"
          :key="box.name"
          class="flex items-center justify-between gap-3 rounded-6 border border-outline-gray-2 p-3"
          data-slot="mail-connected"
        >
          <div class="flex min-w-0 flex-col">
            <span class="truncate text-base font-medium text-ink-primary">
              {{ box.email_id }}
            </span>
            <span class="truncate text-xs text-ink-muted">{{ box.server }}</span>
          </div>
          <div class="flex shrink-0 items-center gap-2">
            <!-- Frappe's own consecutive-failure count. Surfaced because the
                 alternative is a mailbox that quietly stopped three weeks ago
                 and nobody finding out. -->
            <Badge
              v-if="box.awaiting_password || box.failures"
              theme="red"
              :label="__('Not connecting')"
            />
            <Button
              variant="ghost"
              size="sm"
              icon="lucide-unplug"
              :label="__('Disconnect this mailbox')"
              :tooltip="__('Disconnect this mailbox')"
              @click="disconnect(box)"
            />
          </div>
        </div>

        <div v-if="mayConnect" class="flex flex-col gap-2">
          <div class="flex items-end gap-2">
            <FormControl
              v-model="mailbox.email_id"
              class="flex-1"
              :label="__('Mailbox address')"
              :placeholder="__('you@gmail.com')"
            />
            <FormControl
              v-model="mailbox.password"
              class="flex-1"
              type="password"
              :label="__('Password')"
              :description="guess.note"
            />
          </div>

          <!-- Hidden until asked for: four fields is a form somebody fills in,
               eight with two hostnames and two ports in them is a form they
               abandon. Open, it is a whole mail client's Server Settings, which
               is what somebody on a host we have never heard of came here for.

               The port carries the encryption with it — 993 is IMAP over TLS,
               143 is STARTTLS, 465 and 587 the same two outgoing — so there is
               no third row of checkboxes. `connect.INCOMING_TLS` is the map. -->
          <template v-if="advanced">
            <div class="flex items-end gap-2">
              <FormControl v-model="mailbox.email_server" class="flex-1" :label="__('Incoming (IMAP)')" />
              <FormControl
                v-model="mailbox.incoming_port"
                type="number"
                class="w-24"
                :label="__('Port')"
                :min="1"
                :max="65535"
              />
            </div>
            <div class="flex items-end gap-2">
              <FormControl v-model="mailbox.smtp_server" class="flex-1" :label="__('Outgoing (SMTP)')" />
              <FormControl
                v-model="mailbox.smtp_port"
                type="number"
                class="w-24"
                :label="__('Port')"
                :min="1"
                :max="65535"
              />
            </div>
          </template>

          <div class="flex items-center justify-between gap-2">
            <Button
              variant="ghost"
              size="sm"
              :label="advanced ? __('Hide servers') : __('Change the servers and ports')"
              @click="advanced = !advanced"
            />
            <Button
              variant="solid"
              :label="__('Connect')"
              :loading="connecting"
              @click="connect"
            />
          </div>
          <ErrorMessage v-if="connectError" :message="connectError" />
        </div>
      </section>
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
import EmptyState from '@/shared/components/EmptyState.vue'
import { PANEL_BODY, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
import { workspace } from '@/shared/lib/workspace'
import { session } from '@/modules/onespace/lib/shell/session'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const loading = ref(true)

const addresses = ref([])
const connected = ref([])

/** Whether this person holds an address of the workspace's own, and what one
 *  would be called if they claimed it. See `addresses.mine`. */
const ours = ref({})
const claiming = ref(false)

/** Which address a new message goes out as. `mailbox.sending.default_sender`. */
const defaultSender = ref('')

/** The workspace's answer on outside mailboxes. `addresses.connect_policy`. */
const policy = ref({ mode: 'any', domains: [] })

const connecting = ref(false)
const connectError = ref('')
const advanced = ref(false)
const guess = ref({})
const BLANK = {
  email_id: '', password: '', email_server: '', smtp_server: '',
  incoming_port: '', smtp_port: '',
}

const mailbox = ref({ ...BLANK })

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
    ruleError.value = errorText(e)
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
  // The ports the server would use anyway, shown rather than implied: a person
  // who opens this block to change one of them should see what the other is.
  mailbox.value.incoming_port = String(guess.value.incoming_port || '')
  mailbox.value.smtp_port = String(guess.value.smtp_port || '')
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
      incoming_port: mailbox.value.incoming_port,
      smtp_port: mailbox.value.smtp_port,
    })
    mailbox.value = { ...BLANK }
    guess.value = {}
    advanced.value = false
    await load()
  } catch (e) {
    connectError.value = errorText(e)
  } finally {
    connecting.value = false
  }
}

async function disconnect(box) {
  await workspace.mailDisconnect(box.name)
  await load()
}

const mayConnect = computed(() => policy.value.mode !== 'none')

const whyNot = computed(() =>
  policy.value.mode === 'none'
    ? __('This workspace does not allow connecting outside mailboxes.')
    : '',
)

async function claim() {
  claiming.value = true
  try {
    await workspace.mailClaim()
    await load()
  } finally {
    claiming.value = false
  }
}

async function setDefault(address) {
  defaultSender.value = address
  await workspace.mailSetDefaultSender(address)
}

async function load() {
  loading.value = true
  try {
    const [mail, boxes, own, sending] = await Promise.all([
      workspace.mail(),
      workspace.mailConnected(),
      workspace.mailMine(),
      workspace.mailSendingFrom(),
    ])
    addresses.value = mail.addresses || []
    policy.value = mail.connect_policy || { mode: 'any', domains: [] }
    connected.value = boxes || []
    ours.value = own || {}
    // What the server would pick today, so the control opens on the truth
    // rather than on empty: this person may never have chosen one.
    defaultSender.value = sending?.default || sending?.sender || ''
    // The address whose rules are shown. First one held, because a picker that
    // opens on nothing makes somebody choose before they can look.
    chosen.value = held.value[0]?.email_id || ''
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
