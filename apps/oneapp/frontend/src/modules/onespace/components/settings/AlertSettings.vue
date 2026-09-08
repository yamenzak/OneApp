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
    :title="__('Alerts')"
    :description="__('Tell somebody when something happens to a record.')"
    :class="PANEL_HEADER"
  >
    <template #actions>
      <Button
        v-if="doctypes.length"
        icon-left="lucide-plus"
        :label="__('New alert')"
        @click="start()"
      />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" :text="__('Loading')" />

    <Alert v-else-if="error" theme="red" :title="__('Alerts could not be loaded')">
      <template #description>{{ error }}</template>
    </Alert>

    <EmptyState
      v-else-if="!doctypes.length"
      icon="lucide-bell"
      :title="__('Nothing to alert on')"
      :description="__('This workspace has no records an alert could watch yet.')"
    />

    <EmptyState
      v-else-if="!rules.length"
      icon="lucide-bell"
      :title="__('No alerts yet')"
      :description="__('An alert watches one kind of record and tells somebody when it changes.')"
    >
      <template #action>
        <Button icon-left="lucide-plus" :label="__('New alert')" @click="start()" />
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
            :label="__('This record is no longer in the workspace')"
          />
        </div>

        <div class="flex shrink-0 items-center gap-2">
          <!-- Pausing is the control people reach for. A rule that is wrong at
               month end is one to stop, not one to rewrite from memory. -->
          <!-- The label is the state, not a static word: a switch that says
               "On" while it is off is a switch that reads as broken. -->
          <Switch
            :model-value="rule.enabled"
            :label="rule.enabled ? __('On') : __('Off')"
            @update:model-value="pause(rule, $event)"
          />
          <Button
            icon="lucide-pencil"
            variant="ghost"
            :label="__('Edit this alert')"
            :tooltip="__('Edit this alert')"
            @click="start(rule)"
          />
          <Button
            icon="lucide-trash-2"
            variant="ghost"
            theme="red"
            :label="__('Delete this alert')"
            :tooltip="__('Delete this alert')"
            :loading="removing === rule.name"
            @click="remove(rule)"
          />
        </div>
      </article>

      <ErrorMessage v-if="rowError" :message="rowError" />
    </div>
</SettingsBody>

  <!--
    Outside `SettingsBody`, because a Dialog is not part of the panel that
    scrolls — and because a Save nested in there is a Save the geometry guard
    reads as one that scrolls away on a phone.
  -->
  <Dialog v-model="editing" :title="draft.name ? __('Edit alert') : __('New alert')">
    <template #default>
      <div class="flex flex-col gap-4">
        <Select
          v-model="draft.doctype"
          :label="__('When this record')"
          :options="doctypes.map((one) => ({ label: one.label, value: one.doctype }))"
          @update:model-value="onDoctype"
        />

        <Select v-model="draft.when" :label="__('Is')" :options="whenOptions" />

        <!-- Only the two that count days need a date to count from, and the
             number only means anything beside it. -->
        <div v-if="dated" class="flex items-end gap-2">
          <Select
            v-model="draft.date_field"
            class="flex-1"
            :label="__('Counting from')"
            :options="dateOptions"
          />
          <FormControl v-model="draft.days" type="number" :label="__('Days')" class="w-24" />
        </div>

        <!-- Optional, and three controls rather than a box: the rules people
             write are "when the status is Overdue".

             Collapsed, this is the button and nothing else. The label used to
             sit beside it with nothing under it, which read as a heading for
             the row below — "Only when / Tell this role" is a sentence the
             form does not mean. -->
        <div class="flex flex-col gap-2">
          <div v-if="!condition">
            <Button
              icon-left="lucide-plus"
              variant="ghost"
              :label="__('Only when a field says something')"
              @click="toggleCondition"
            />
          </div>
          <div v-else class="flex items-center justify-between">
            <p class="text-p-sm text-ink-gray-7">{{ __('Only when') }}</p>
            <Button
              variant="ghost"
              :label="__('Remove the test')"
              @click="toggleCondition"
            />
          </div>
          <div v-if="condition" class="flex items-end gap-2">
            <Select
              v-model="draft.condition.field"
              class="flex-1"
              :label="__('Field')"
              :options="watchOptions"
            />
            <Select
              v-model="draft.condition.operator"
              class="w-36"
              :label="__('Test')"
              :options="OPERATORS"
            />
            <FormControl
              v-if="needsValue"
              v-model="draft.condition.value"
              class="flex-1"
              :label="__('Value')"
            />
          </div>
        </div>

        <div class="flex items-end gap-2">
          <Select
            v-model="draft.to_role"
            class="flex-1"
            :label="__('Tell this role')"
            :options="[{ label: __('Nobody by role'), value: '' }, ...roles]"
          />
          <Select
            v-model="draft.to_field"
            class="flex-1"
            :label="__('Or whoever is in')"
            :options="[{ label: __('No field'), value: '' }, ...addressOptions]"
          />
        </div>

        <Select v-model="draft.channel" :label="__('Send it')" :options="CHANNELS" />

        <FormControl v-model="draft.subject" :label="__('Subject')" />
        <FormControl
          v-model="draft.message"
          type="textarea"
          :rows="4"
          :label="__('Message')"
          :description="__('Leave it empty to send the subject on its own.')"
        />

        <ErrorMessage :message="saveError" />
      </div>
    </template>
    <template #actions>
      <Button variant="solid" :label="__('Save')" :loading="saving" @click="save" />
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
import EmptyState from '@/shared/components/EmptyState.vue'
import { PANEL_BODY, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
import { workspace } from '@/shared/lib/workspace'
import { errorText } from '@/shared/lib/runtime/errors'
import { __ } from '@/shared/lib/runtime/translate'

// The words a rule is written in. The server maps each onto Frappe's own
// `event`, so this is a vocabulary rather than a second event system.
const WHEN = [
  { label: __('made'), value: 'created' },
  { label: __('changed'), value: 'changed' },
  { label: __('submitted'), value: 'submitted' },
  { label: __('cancelled'), value: 'cancelled' },
  { label: __('coming up'), value: 'before' },
  { label: __('past due'), value: 'after' },
]

const OPERATORS = [
  { label: __('is'), value: 'is' },
  { label: __('is not'), value: 'is not' },
  { label: __('is over'), value: 'over' },
  { label: __('is under'), value: 'under' },
  { label: __('is filled in'), value: 'is set' },
  { label: __('is empty'), value: 'is not set' },
]

const CHANNELS = [
  { label: __('By email'), value: 'email' },
  { label: __('In the app'), value: 'app' },
  { label: __('Both'), value: 'both' },
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
// Kept apart from `error`, which renders *instead of* the list: a refused
// pause or delete that blanked every rule would hide the row it was about.
const rowError = ref('')
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
  const who = rule.to_role || rule.to_field || __('nobody')
  const what = record?.label || rule.doctype
  return DATED.includes(rule.when)
    ? __('When {0} is {1} by {2} days, tell {3}', [what, when, rule.days, who])
    : __('When {0} is {1}, tell {2}', [what, when, who])
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const found = await workspace.alerts()
    rules.value = found?.rules || []
    doctypes.value = found?.doctypes || []
    roles.value = found?.roles || []
  } catch (raised) {
    // `errorText` and not `e.message`: a `frappe.throw` travels in
    // `_server_messages`, which `.message` does not read — so every sentence
    // this module writes ("Say who the alert goes to.") arrived as
    // `/api/method/…save_alert ValidationError`.
    error.value = errorText(raised)
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
  } catch (raised) {
    saveError.value = errorText(raised)
  } finally {
    saving.value = false
  }
}

// The switch moves first because that is what makes it feel like a switch. So
// it has to move back when the write is refused: a control left reading Off on
// a rule that is still on is worse than a slow one.
async function pause(rule, enabled) {
  const was = rule.enabled
  rule.enabled = enabled
  rowError.value = ''
  try {
    await workspace.setAlertEnabled(rule.name, enabled)
  } catch (raised) {
    rule.enabled = was
    rowError.value = errorText(raised)
  }
}

async function remove(rule) {
  removing.value = rule.name
  rowError.value = ''
  try {
    await workspace.removeAlert(rule.name)
    rules.value = rules.value.filter((one) => one.name !== rule.name)
  } catch (raised) {
    rowError.value = errorText(raised)
  } finally {
    removing.value = ''
  }
}

onMounted(() => load())
</script>
