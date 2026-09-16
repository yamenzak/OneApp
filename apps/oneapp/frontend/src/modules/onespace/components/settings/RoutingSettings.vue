<template>
  <!--
    Who a record lands with, decided by a rule rather than by whoever noticed.

    One sentence per rule, and the form is that sentence: when a **record**
    reaches **a state**, hand it to **these people**, **one after another**.

    Frappe's own Assignment Rule form offers three code boxes — assign,
    unassign and close — a day table and a priority. That is the right surface
    for somebody automating a helpdesk and the wrong one for a team who want
    review to land on a reviewer. The condition here is three controls the
    server compiles, for the same reason the alert's is: `assign_condition` is
    evaluated on every save of every record of that kind.
  -->
  <SettingsHeader
    :title="__('Handover rules')"
    :description="__('Hand a record to somebody when it reaches a state.')"
    :class="PANEL_HEADER"
  >
    <template #actions>
      <Button
        v-if="doctypes.length"
        icon-left="lucide-plus"
        :label="__('New rule')"
        @click="start()"
      />
    </template>
  </SettingsHeader>

  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" :text="__('Loading')" />

    <Alert v-else-if="error" theme="red" :title="__('Rules could not be loaded')">
      <template #description>{{ error }}</template>
    </Alert>

    <EmptyState
      v-else-if="!doctypes.length"
      icon="lucide-git-branch"
      :title="__('Nothing to hand over')"
      :description="__('This workspace has no records a rule could assign yet.')"
    />

    <EmptyState
      v-else-if="!rules.length"
      icon="lucide-git-branch"
      :title="__('No rules yet')"
      :description="__('A rule watches one kind of record and assigns it when it reaches a state.')"
    >
      <template #action>
        <Button icon-left="lucide-plus" :label="__('New rule')" @click="start()" />
      </template>
    </EmptyState>

    <div v-else class="flex flex-col gap-3 py-4">
      <article
        v-for="rule in rules"
        :key="rule.name"
        data-slot="routing-rule"
        class="flex items-start justify-between gap-3 rounded-6 border border-outline-gray-1 p-4"
      >
        <div class="min-w-0">
          <p class="truncate text-sm font-medium text-ink-primary">{{ rule.title }}</p>
          <p class="mt-1 text-p-xs text-ink-muted">{{ sentence(rule) }}</p>
          <Badge
            v-if="rule.orphaned"
            class="mt-2"
            theme="amber"
            :label="__('This record is no longer in the workspace')"
          />
        </div>

        <div class="flex shrink-0 items-center gap-2">
          <Switch
            :model-value="rule.enabled"
            :label="rule.enabled ? __('On') : __('Off')"
            @update:model-value="pause(rule, $event)"
          />
          <Button
            icon="lucide-pencil"
            variant="ghost"
            :label="__('Edit this rule')"
            :tooltip="__('Edit this rule')"
            @click="start(rule)"
          />
          <Button
            icon="lucide-trash-2"
            variant="ghost"
            theme="red"
            :label="__('Delete this rule for ever')"
            :tooltip="__('Delete this rule for ever')"
            :loading="removing === rule.name"
            @click="remove(rule)"
          />
        </div>
      </article>

      <ErrorMessage v-if="rowError" :message="rowError" />
    </div>
  </SettingsBody>

  <Dialog v-model="editing" :title="draft.name ? __('Edit rule') : __('New rule')">
    <template #default>
      <div class="flex flex-col gap-4">
        <FormControl
          v-model="draft.title"
          :label="__('Call it')"
          :description="__('What the list shows, and what somebody looks for when it misfires.')"
        />

        <Select
          v-model="draft.doctype"
          :label="__('When this record')"
          :options="doctypes.map((one) => ({ label: one.label, value: one.doctype }))"
          @update:model-value="onDoctype"
        />

        <!--
          Required, unlike an alert's. A rule with no test assigns *everything*
          of that kind to somebody for ever, which nobody means and nobody
          notices until a hundred tasks have landed on one person.
        -->
        <div class="flex items-end gap-2">
          <Select
            v-model="draft.condition.field"
            class="flex-1"
            :label="__('Reaches')"
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

        <Select v-model="draft.way" :label="__('Hand it over')" :options="WAYS" />

        <!-- The field that holds the person, for the rule that reads one off
             the record rather than choosing. The people below are still the
             set it is allowed to be — Frappe reads both. -->
        <Select
          v-if="draft.way === 'by field'"
          v-model="draft.field"
          :label="__('Named in')"
          :options="peopleOptions"
        />

        <div class="flex flex-col gap-2">
          <p class="text-p-sm text-ink-secondary">{{ __('To') }}</p>
          <!-- A checkbox each rather than a picker: a rule names a handful of
               colleagues, and the question "who is on this" is answered by
               looking rather than by opening a menu. -->
          <div class="flex max-h-56 flex-col gap-1 overflow-y-auto">
            <Checkbox
              v-for="one in users"
              :key="one.value"
              class="px-1 py-1"
              :model-value="draft.users.includes(one.value)"
              :label="one.label"
              @update:model-value="toggleUser(one.value, $event)"
            />
          </div>
        </div>

        <ErrorMessage :message="saveError" />
      </div>
    </template>
    <template #actions>
      <Button variant="solid" :label="__('Save')" :loading="saving" @click="save" />
    </template>
  </Dialog>
</template>

<script setup>
/**
 * The space this page belongs to, or empty for the workspace's own. Same prop
 * and same reason as `AlertSettings` — the narrowing is a filter on what the
 * server offers, not a second panel.
 */
const props = defineProps({
  space: { type: String, default: '' },
})

import { computed, onMounted, reactive, ref } from 'vue'
import {
  Alert,
  Badge,
  Button,
  Checkbox,
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

// The same six the alert builder offers, and the same server function compiles
// them — `onespace/alerts.OPERATORS`, which `routing` imports rather than
// restates.
const OPERATORS = [
  { label: __('is'), value: 'is' },
  { label: __('is not'), value: 'is not' },
  { label: __('is over'), value: 'over' },
  { label: __('is under'), value: 'under' },
  { label: __('is filled in'), value: 'is set' },
  { label: __('is empty'), value: 'is not set' },
]

// How a rule chooses between the people it was given. Frappe's three, in the
// words somebody would use — `onespace/routing.WAYS`.
const WAYS = [
  { label: __('one after another'), value: 'in turn' },
  { label: __('to whoever has least on'), value: 'by load' },
  { label: __('to whoever the record names'), value: 'by field' },
]

const rules = ref([])
const doctypes = ref([])
const users = ref([])
const loading = ref(false)
const error = ref('')
const saving = ref(false)
const saveError = ref('')
const removing = ref('')
const rowError = ref('')
const editing = ref(false)

const blank = () => ({
  name: '', title: '', doctype: '', way: 'in turn', field: '', users: [],
  condition: { field: '', operator: 'is', value: '' },
})
const draft = reactive(blank())

const chosen = computed(
  () => doctypes.value.find((one) => one.doctype === draft.doctype) || null,
)
const needsValue = computed(
  () => !['is set', 'is not set'].includes(draft.condition.operator),
)
const fields = (list) =>
  (list || []).map((one) => ({ label: one.label, value: one.fieldname }))
const watchOptions = computed(() => fields(chosen.value?.watchable))
const peopleOptions = computed(() => fields(chosen.value?.people))

/** The rule as the sentence it was written as, for the list. */
function sentence(rule) {
  const record = doctypes.value.find((one) => one.doctype === rule.doctype)
  const what = record?.label || rule.doctype
  const way = WAYS.find((one) => one.value === rule.way)?.label || rule.way
  const test = rule.condition
  const field = record?.watchable?.find((one) => one.fieldname === test?.field)
  const how = test
    ? __('{0} {1} {2}', [field?.label || test.field || '', test.operator || '',
                         test.value || ''])
    : __('it changes')
  // Who, and how many of them: "three people" is the fact somebody checks when
  // a rule stops behaving, and naming all twenty would be a paragraph.
  const who = rule.users.length === 1
    ? (users.value.find((one) => one.value === rule.users[0])?.label || rule.users[0])
    : __('{0} people', [String(rule.users.length)])
  return __('When {0} — {1} — hand it to {2}, {3}', [what, how.trim(), who, way])
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const found = await workspace.routing(props.space)
    rules.value = found?.rules || []
    doctypes.value = found?.doctypes || []
    users.value = found?.users || []
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    loading.value = false
  }
}

function start(rule = null) {
  Object.assign(draft, blank(), rule || {})
  if (!draft.doctype) draft.doctype = doctypes.value[0]?.doctype || ''
  draft.condition = rule?.condition || { field: '', operator: 'is', value: '' }
  draft.users = [...(rule?.users || [])]
  saveError.value = ''
  editing.value = true
}

// Changing what the rule is about invalidates every field picked off the last
// one. The people survive: colleagues are the workspace's, not the doctype's.
function onDoctype() {
  draft.field = ''
  draft.condition = { field: '', operator: 'is', value: '' }
}

function toggleUser(user, on) {
  draft.users = on
    ? [...draft.users, user]
    : draft.users.filter((one) => one !== user)
}

async function save() {
  saving.value = true
  saveError.value = ''
  try {
    await workspace.saveRoutingRule({
      ...draft,
      condition: draft.condition.field ? draft.condition : null,
    })
    editing.value = false
    await load()
  } catch (raised) {
    saveError.value = errorText(raised)
  } finally {
    saving.value = false
  }
}

// The switch moves first, and moves back when the write is refused — the same
// reason `AlertSettings` gives: a control left reading Off on a rule that is
// still on is worse than a slow one.
async function pause(rule, enabled) {
  const was = rule.enabled
  rule.enabled = enabled
  rowError.value = ''
  try {
    await workspace.setRoutingEnabled(rule.name, enabled)
  } catch (raised) {
    rule.enabled = was
    rowError.value = errorText(raised)
  }
}

async function remove(rule) {
  removing.value = rule.name
  rowError.value = ''
  try {
    await workspace.removeRoutingRule(rule.name)
    rules.value = rules.value.filter((one) => one.name !== rule.name)
  } catch (raised) {
    rowError.value = errorText(raised)
  } finally {
    removing.value = ''
  }
}

onMounted(() => load())
</script>
