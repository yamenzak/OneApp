<template>
  <!--
    Tell somebody when something happens to a record.

    One sentence per rule, and the form is that sentence: when a **record**
    is **created / changed / three days past a date**, tell **a role or a
    person**, and say **this**.

    Frappe's own Notification form offers eight events, a Jinja condition box,
    a filters JSON, four channels and a Slack webhook. That is the right
    surface for somebody automating a factory and the wrong one for somebody
    who wants to know about an overdue invoice — and the condition especially,
    because Frappe evaluates it as code. Here the condition is three controls
    the server compiles.
  -->
  <SettingsHeader
    title="Alerts"
    description="Tell somebody when something happens to a record."
    :class="PANEL_HEADER"
  >
    <template #actions>
      <Button
        v-if="doctypes.length"
        icon-left="lucide-plus"
        label="New alert"
        @click="start()"
      />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" text="Loading" />

    <Alert v-else-if="error" theme="red" title="Alerts could not be loaded">
      <template #description>{{ error }}</template>
    </Alert>

    <EmptyState
      v-else-if="!doctypes.length"
      icon="lucide-bell"
      title="Nothing to alert on"
      description="This workspace has no records an alert could watch yet."
    />

    <EmptyState
      v-else-if="!rules.length"
      icon="lucide-bell"
      title="No alerts yet"
      description="An alert watches one kind of record and tells somebody when it changes."
    >
      <template #action>
        <Button icon-left="lucide-plus" label="New alert" @click="start()" />
      </template>
    </EmptyState>

    <div v-else class="flex flex-col gap-3 py-4">
      <article
        v-for="rule in rules"
        :key="rule.name"
        data-slot="alert-rule"
        class="flex items-start justify-between gap-3 rounded-6 border border-outline-gray-1 p-4"
      >
        <div class="min-w-0">
          <p class="truncate text-p-sm font-medium text-ink-gray-8">{{ rule.title }}</p>
          <p class="mt-1 text-p-xs text-ink-gray-5">{{ sentence(rule) }}</p>
          <!-- A rule on a record the workspace no longer has. Shown rather
               than hidden, because a rule nobody can find is a rule nobody can
               delete. -->
          <Badge
            v-if="rule.orphaned"
            class="mt-2"
            theme="amber"
            label="This record is no longer in the workspace"
          />
        </div>

        <div class="flex shrink-0 items-center gap-2">
          <!-- Pausing is the control people reach for. A rule that is wrong at
               month end is one to stop, not one to rewrite from memory. -->
          <!-- The label is the state, not a static word: a switch that says
               "On" while it is off is a switch that reads as broken. -->
          <Switch
            :model-value="rule.enabled"
            :label="rule.enabled ? 'On' : 'Off'"
            @update:model-value="pause(rule, $event)"
          />
          <Button
            icon="lucide-pencil"
            variant="ghost"
            label="Edit this alert"
            tooltip="Edit this alert"
            @click="start(rule)"
          />
          <Button
            icon="lucide-trash-2"
            variant="ghost"
            theme="red"
            label="Delete this alert"
            tooltip="Delete this alert"
            :loading="removing === rule.name"
            @click="remove(rule)"
          />
        </div>
      </article>
    </div>
</SettingsBody>

  <!--
    Outside `SettingsBody`, because a Dialog is not part of the panel that
    scrolls — and because a Save nested in there is a Save the geometry guard
    reads as one that scrolls away on a phone.
  -->
  <Dialog v-model="editing" :title="draft.name ? 'Edit alert' : 'New alert'">
    <template #default>
      <div class="flex flex-col gap-4">
        <Select
          v-model="draft.doctype"
          label="When this record"
          :options="doctypes.map((one) => ({ label: one.label, value: one.doctype }))"
          @update:model-value="onDoctype"
        />

        <Select v-model="draft.when" label="Is" :options="whenOptions" />

        <!-- Only the two that count days need a date to count from, and the
             number only means anything beside it. -->
        <div v-if="dated" class="flex items-end gap-2">
          <Select
            v-model="draft.date_field"
            class="flex-1"
            label="Counting from"
            :options="dateOptions"
          />
          <FormControl v-model="draft.days" type="number" label="Days" class="w-24" />
        </div>

        <!-- Optional, and three controls rather than a box: the rules people
             write are "when the status is Overdue". -->
        <div class="flex flex-col gap-2">
          <div class="flex items-center justify-between">
            <p class="text-p-sm text-ink-gray-7">Only when</p>
            <Button
              :label="condition ? 'Remove the test' : 'Add a test'"
              variant="ghost"
              @click="toggleCondition"
            />
          </div>
          <div v-if="condition" class="flex items-end gap-2">
            <Select
              v-model="draft.condition.field"
              class="flex-1"
              label="Field"
              :options="watchOptions"
            />
            <Select
              v-model="draft.condition.operator"
              class="w-36"
              label="Test"
              :options="OPERATORS"
            />
            <FormControl
              v-if="needsValue"
              v-model="draft.condition.value"
              class="flex-1"
              label="Value"
            />
          </div>
        </div>

        <div class="flex items-end gap-2">
          <Select
            v-model="draft.to_role"
            class="flex-1"
            label="Tell this role"
            :options="[{ label: 'Nobody by role', value: '' }, ...roles]"
          />
          <Select
            v-model="draft.to_field"
            class="flex-1"
            label="Or whoever is in"
            :options="[{ label: 'No field', value: '' }, ...addressOptions]"
          />
        </div>

        <Select v-model="draft.channel" label="Send it" :options="CHANNELS" />

        <FormControl v-model="draft.subject" label="Subject" />
        <FormControl
          v-model="draft.message"
          type="textarea"
          :rows="4"
          label="Message"
          description="Leave it empty to send the subject on its own."
        />

        <ErrorMessage :message="saveError" />
      </div>
    </template>
    <template #actions>
      <Button variant="solid" label="Save" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  Alert,
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  LoadingText,
  Select,
  SettingsBody,
  SettingsHeader,
  Switch,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'

// The words a rule is written in. The server maps each onto Frappe's own
// `event`, so this is a vocabulary rather than a second event system.
const WHEN = [
  { label: 'made', value: 'created' },
  { label: 'changed', value: 'changed' },
  { label: 'submitted', value: 'submitted' },
  { label: 'cancelled', value: 'cancelled' },
  { label: 'coming up', value: 'before' },
  { label: 'past due', value: 'after' },
]

const OPERATORS = [
  { label: 'is', value: 'is' },
  { label: 'is not', value: 'is not' },
  { label: 'is over', value: 'over' },
  { label: 'is under', value: 'under' },
  { label: 'is filled in', value: 'is set' },
  { label: 'is empty', value: 'is not set' },
]

const CHANNELS = [
  { label: 'By email', value: 'email' },
  { label: 'In the app', value: 'app' },
  { label: 'Both', value: 'both' },
]

const DATED = ['before', 'after']

const rules = ref([])
const doctypes = ref([])
const roles = ref([])
const loading = ref(false)
const error = ref('')
const saving = ref(false)
const saveError = ref('')
const removing = ref('')
const editing = ref(false)
const condition = ref(false)

const blank = () => ({
  name: '', doctype: '', when: 'created', date_field: '', days: 3,
  to_role: '', to_field: '', channel: 'email', subject: '', message: '',
  condition: { field: '', operator: 'is', value: '' },
})
const draft = reactive(blank())

const chosen = computed(
  () => doctypes.value.find((one) => one.doctype === draft.doctype) || null,
)
const dated = computed(() => DATED.includes(draft.when))
const needsValue = computed(
  () => !['is set', 'is not set'].includes(draft.condition.operator),
)

// A doctype that is not submittable has no submitted or cancelled to wait for,
// and offering them would be offering a rule that can never fire.
const whenOptions = computed(() =>
  WHEN.filter(
    (one) =>
      !['submitted', 'cancelled'].includes(one.value) || chosen.value?.submittable,
  ),
)
const dateOptions = computed(() => fields(chosen.value?.dates))
const watchOptions = computed(() => fields(chosen.value?.watchable))
const addressOptions = computed(() => fields(chosen.value?.addresses))

const fields = (list) =>
  (list || []).map((one) => ({ label: one.label, value: one.fieldname }))

/** The rule as the sentence it was written as, for the list. */
function sentence(rule) {
  const record = doctypes.value.find((one) => one.doctype === rule.doctype)
  const when = WHEN.find((one) => one.value === rule.when)?.label || rule.when
  const who = rule.to_role || rule.to_field || 'nobody'
  const days = DATED.includes(rule.when) ? ` by ${rule.days} days` : ''
  return `When ${record?.label || rule.doctype} is ${when}${days}, tell ${who}`
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const found = await workspace.alerts()
    rules.value = found?.rules || []
    doctypes.value = found?.doctypes || []
    roles.value = found?.roles || []
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

function start(rule = null) {
  Object.assign(draft, blank(), rule || {})
  if (!draft.doctype) draft.doctype = doctypes.value[0]?.doctype || ''
  draft.condition = rule?.condition || { field: '', operator: 'is', value: '' }
  condition.value = !!rule?.condition
  saveError.value = ''
  editing.value = true
}

// Changing what the rule is about invalidates every field picked off the last
// one, so they are cleared rather than left pointing at a doctype that is gone.
function onDoctype() {
  draft.date_field = ''
  draft.to_field = ''
  draft.condition = { field: '', operator: 'is', value: '' }
  condition.value = false
  if (!whenOptions.value.some((one) => one.value === draft.when)) draft.when = 'created'
}

function toggleCondition() {
  condition.value = !condition.value
  if (!condition.value) draft.condition = { field: '', operator: 'is', value: '' }
}

async function save() {
  saving.value = true
  saveError.value = ''
  try {
    await workspace.saveAlert({
      ...draft,
      condition: condition.value && draft.condition.field ? draft.condition : null,
    })
    editing.value = false
    await load()
  } catch (e) {
    saveError.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

async function pause(rule, enabled) {
  rule.enabled = enabled
  await workspace.setAlertEnabled(rule.name, enabled)
}

async function remove(rule) {
  removing.value = rule.name
  try {
    await workspace.removeAlert(rule.name)
    rules.value = rules.value.filter((one) => one.name !== rule.name)
  } finally {
    removing.value = ''
  }
}

onMounted(() => load())
</script>
