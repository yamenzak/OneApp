<template>
  <div class="min-h-screen bg-surface-gray-1 py-10">
    <div class="mx-auto max-w-lg px-5">
      <div class="mb-6 text-center">
        <Avatar :label="TENANT_APP" shape="square" size="2xl" class="mx-auto" />
        <h1 class="mt-3 text-xl-semibold text-ink-gray-9">{{ __('Create your workspace') }}</h1>
      </div>

      <div v-if="!open.checked" class="grid place-items-center py-16">
        <LoadingIndicator class="size-5 text-ink-gray-5" />
      </div>

      <Alert v-else-if="!open.open" theme="amber" :title="__('Signups are paused')">
        <template #description>
          {{ __('New workspaces are closed for now. Try again later.') }}
        </template>
      </Alert>

      <div v-else class="flex flex-col gap-4 rounded-6 border border-outline-gray-2 bg-surface-base p-5">
        <FormControl
          v-model="form.workspace_name"
          :label="__('Workspace name')"
          :placeholder="__('Acme Ltd')"
        />

        <div>
          <FormControl
            v-model="form.slug"
            :label="__('Address')"
            :placeholder="__('acme')"
            :description="slugHint"
          />
          <ErrorMessage v-if="slugError" class="mt-1" :message="slugError" />
        </div>

        <FormControl
          v-model="form.email"
          type="email"
          :label="__('Email')"
          :placeholder="__('you@acme.com')"
        />

        <FormControl
          v-model="form.plan"
          type="select"
          :label="__('Plan')"
          :options="planOptions"
        />

        <FormControl
          v-model="form.region"
          type="select"
          :label="__('Region')"
          :options="regionOptions"
          :description="__('Where your workspace runs. The price is the same everywhere.')"
        />

        <FormControl
          v-model="form.storage_jurisdiction"
          type="select"
          :label="__('File storage')"
          :options="jurisdictions"
          :description="__('Where your files are stored. This cannot be changed later.')"
        />

        <!--
          Optional, and last: a field somebody has no code for should read as
          "skip this" rather than as one more thing to fill in. Validated
          server-side on submit, so a wrong code is a message here rather than a
          Stripe page that refuses after everything else was typed.
        -->
        <FormControl
          v-model="form.code"
          :label="__('Promo code')"
          :placeholder="__('Optional')"
          :description="__('If you were given one.')"
        />

        <ErrorMessage v-if="error" :message="error" />

        <Button
          variant="solid"
          size="md"
          :label="submitLabel"
          :loading="submitting"
          :disabled="!valid"
          @click="submit"
        />

        <p class="text-center text-p-sm text-ink-gray-5">
          {{ __('Payment comes next. Your workspace is created once it clears.') }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { TENANT_APP } from '@/lib/runtime/brand'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Alert, Avatar, Button, ErrorMessage, FormControl, LoadingIndicator, debounce } from '@/ui'
import { callMethod } from '@/lib/runtime/resource'
import { __ } from '@/lib/runtime/translate'

const jurisdictions = computed(() => [
  { label: __('Global network'), value: 'Global' },
  { label: __('European Union only'), value: 'EU' },
])

const method = (name) => `oneapp_control.api.signup.${name}`

const form = reactive({
  workspace_name: '',
  slug: '',
  email: '',
  plan: '',
  region: '',
  storage_jurisdiction: 'Global',
  code: '',
})

const open = reactive({ checked: false, open: false })
const plans = ref([])
const regions = ref([])
const slugError = ref('')
const error = ref('')
const submitting = ref(false)

const planOptions = computed(() =>
  plans.value.map((p) => ({
    label: __('{0} — ${1}/mo', [p.plan_name, p.price_monthly]),
    value: p.code,
  })),
)
const regionOptions = computed(() =>
  regions.value.map((r) => ({ label: `${r.region_name}, ${r.country}`, value: r.code })),
)

const slugHint = computed(() =>
  form.slug ? `${form.slug}.4dl.app` : __('Your workspace address.'),
)

const selectedPlan = computed(() => plans.value.find((p) => p.code === form.plan))
const submitLabel = computed(() =>
  selectedPlan.value
    ? __('Continue — ${0}/mo', [selectedPlan.value.price_monthly])
    : __('Continue'),
)

const valid = computed(
  () =>
    form.workspace_name &&
    form.slug &&
    form.email &&
    form.plan &&
    form.region &&
    !slugError.value,
)

// Checked server-side: the slug rules are a security boundary, not formatting.
const checkSlug = debounce(async (slug) => {
  if (!slug) return (slugError.value = '')
  const { available } = await callMethod(method('check_slug'), { slug }, { silent: true })
  slugError.value = available ? '' : __('That address is taken or reserved.')
}, 400)

watch(() => form.slug, checkSlug)

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    const payload = { ...form, code: form.code.trim() || undefined }
    const { url } = await callMethod(method('start'), payload, { silent: true })
    if (url) window.location.href = url
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  const status = await callMethod(method('signup_open'), {}, { silent: true, method: 'GET' })
  Object.assign(open, { checked: true, open: status.open })
  if (!status.open) return

  plans.value = (await callMethod(method('plans'), {}, { silent: true, method: 'GET' })) || []
  regions.value = (await callMethod(method('regions'), {}, { silent: true, method: 'GET' })) || []
  form.plan = plans.value[0]?.code || ''
  form.region = regions.value[0]?.code || ''
})
</script>
