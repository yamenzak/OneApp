<template>
  <SettingsHeader
    :title="__('AI')"
    :description="__('Which features use a model, which model they use, and anything you want it to keep in mind.')"
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <div v-if="loading" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!data?.features.length"
      class="!py-12"
      icon="lucide-sparkles"
      :title="__('Nothing uses AI yet')"
      :description="__('Features appear here as the apps in your workspace add them. There is nothing to set up in advance.')"
    />

    <div v-else class="flex flex-col gap-5 pt-6">
      <div class="flex items-start justify-between gap-4 rounded-6 border border-outline-gray-1 p-4">
        <div class="min-w-0">
          <p class="text-base-medium text-ink-gray-8">{{ __('Use AI in this workspace') }}</p>
          <p class="mt-0.5 text-p-sm text-ink-gray-5">
            {{ __('{0} credits left. Each feature is charged for what it actually uses.', [data.credit_balance]) }}
          </p>
        </div>
        <Switch v-model="form.ai_enabled" />
      </div>

      <!--
        Who the assistant is. Above the features because it is one answer for
        all of them: the same character answers in the chat panel and drafts a
        reply, and a name that changed between the two would read as two
        products. The picture and the name are what the app shows; the tone and
        the sentence are what the model is told.
      -->
      <div class="flex flex-col gap-4 rounded-6 border border-outline-gray-1 p-4">
        <div class="flex items-center gap-3">
          <Avatar
            size="2xl"
            :image="form.assistant.avatar"
            :label="form.assistant.name || __('Assistant')"
          />
          <div class="min-w-0">
            <p class="text-base-medium text-ink-gray-8">{{ __('The assistant') }}</p>
            <p class="mt-0.5 text-p-sm text-ink-gray-5">
              {{ __('Its name and picture are used wherever it appears.') }}
            </p>
          </div>
        </div>

        <div class="grid gap-3 sm:grid-cols-2">
          <FormControl
            v-model="form.assistant.name"
            :label="__('Name')"
            :placeholder="__('Assistant')"
          />
          <FormControl
            v-model="form.assistant.tone"
            type="select"
            :label="__('Tone')"
            :options="toneOptions"
          />
        </div>

        <SettingsAttach
          v-model="form.assistant.avatar"
          image
          :label="__('Picture')"
          :hint="__('A letter from its name is used where there is none.')"
        />

        <FormControl
          v-model="form.assistant.personality"
          type="textarea"
          :rows="3"
          :label="__('Who it is')"
          :placeholder="__('Knows the trade, answers short, never guesses a price.')"
          :description="__('Added to the instructions it already has. It changes how answers read, not what a feature does.')"
        />
      </div>

      <div
        v-for="feature in data.features"
        :key="feature.key"
        class="flex flex-col gap-3 rounded-6 border border-outline-gray-1 p-4"
        :class="dimmed(feature) && 'opacity-60'"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <p class="truncate text-base-medium text-ink-gray-8">{{ feature.label }}</p>
            <p v-if="feature.description" class="mt-0.5 text-p-sm text-ink-gray-5">
              {{ feature.description }}
            </p>
          </div>

          <!--
            A feature can be declared as one where AI *is* the process rather
            than an assistant beside it. Those show what they are instead of a
            switch that would break the workflow it belongs to.
          -->
          <Badge
            v-if="!feature.can_disable"
            theme="blue"
            :label="__('Always on')"
            variant="subtle"
          />
          <Switch
            v-else
            v-model="answers[feature.key].enabled"
            :disabled="!form.ai_enabled || feature.suspended"
          />
        </div>

        <Alert v-if="feature.suspended" theme="amber" :title="__('Paused')">
          <template #description>
            {{ __('This one is paused for everyone at the moment. Nothing you change here is lost.') }}
          </template>
        </Alert>

        <div v-if="!dimmed(feature)" class="flex flex-col gap-3">
          <FormControl
            v-if="!feature.pinned_model"
            v-model="answers[feature.key].model"
            type="select"
            :label="__('Model')"
            :options="modelOptions(feature)"
            :description="__('Only models that can do this job are listed.')"
          />

          <!--
            Added to our instructions, never instead of them. Said in the
            description because the difference matters to what someone writes
            here: a preference works, a rewrite of the task does not.
          -->
          <FormControl
            v-if="feature.allow_prompt_addendum"
            v-model="answers[feature.key].prompt_addendum"
            type="textarea"
            :rows="3"
            :label="__('Anything it should keep in mind')"
            :placeholder="__('Write in British English. Never quote a delivery date.')"
            :description="__('Added to the instructions this feature already has. Use it for your preferences, not for changing what the feature does.')"
          />
        </div>
      </div>

      <ErrorMessage v-if="error" :message="error" />
    </div>
  </SettingsBody>

  <div v-if="data?.features.length" :class="PANEL_FOOTER">
    <Button variant="solid" :label="__('Save')" :loading="saving" @click="save" />
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  Alert, Avatar, Badge, Button, ErrorMessage, FormControl, LoadingIndicator, Switch,
  SettingsHeader, SettingsBody,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import SettingsAttach from './SettingsAttach.vue'
import { PANEL_BODY, PANEL_FOOTER, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'
import { __ } from '@/lib/runtime/translate'
import { settings } from '@/lib/shell/settings'
import { errorText } from '@/lib/runtime/errors'

const data = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive({
  ai_enabled: true,
  assistant: { name: '', avatar: '', tone: '', personality: '' },
})

// From the server, which reads them off the Select's own options — restating
// them here would be a second list to keep in step.
const toneOptions = computed(() =>
  (data.value?.tones || []).map((one) => ({ label: __(one), value: one })),
)
const answers = reactive({})

// Greyed rather than hidden: a feature that has been switched off should still
// say what it is, or turning it back on is a hunt.
const dimmed = (feature) =>
  feature.suspended || (feature.can_disable && (!form.ai_enabled || !answers[feature.key]?.enabled))

const modelOptions = (feature) => [
  { label: __('Recommended'), value: '' },
  ...feature.models.map((m) => ({
    label: m.description ? `${m.label} — ${m.description}` : m.label,
    value: m.value,
  })),
]

const load = async () => {
  loading.value = true
  try {
    const spec = await workspace.ai()
    data.value = spec
    form.ai_enabled = !!spec.ai_enabled
    Object.assign(form.assistant, spec.assistant || {})
    for (const feature of spec.features) {
      answers[feature.key] = {
        enabled: feature.enabled,
        model: feature.model,
        prompt_addendum: feature.prompt_addendum,
      }
    }
  } finally {
    loading.value = false
  }
}

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    data.value = await workspace.saveAi({
      ai_enabled: form.ai_enabled ? 1 : 0,
      assistant: { ...form.assistant },
      features: answers,
    })
  } catch (e) {
    error.value = errorText(e)
  } finally {
    saving.value = false
  }
}

// Read when the tab is first opened: most sessions never look at it, and this
// reads the whole model catalogue.
watch(
  () => settings.tab,
  (tab) => {
    if (tab === 'ai' && !data.value) load()
  },
  { immediate: true },
)
</script>
