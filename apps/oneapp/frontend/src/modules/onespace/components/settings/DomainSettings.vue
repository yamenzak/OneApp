<template>
  <!--
    What this workspace is called on the internet.

    One workspace has one domain, so this is a fact about the workspace and
    belongs beside Branding and Sign in rather than at another address. The
    record is still the control plane's — it is what issues the certificate —
    and `onespace/account.py` relays. See `docs/MARKETPLACE.md` §2.
  -->
  <SettingsHeader
    :title="__('Domain')"
    :description="__('The address people type to reach this workspace.')"
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <LoadingIndicator v-if="loading && !data" class="size-5 text-ink-muted" />

    <Alert v-else-if="unreachable" theme="amber" :title="__('Cannot reach your account')">
      <template #description>
        {{ __('Your domain is kept with your account, and it is not answering. The workspace is still reachable at the address it already has.') }}
      </template>
    </Alert>

    <div v-else-if="data" class="flex flex-col gap-5">
      <FormControl
        type="text"
        :label="__('Current address')"
        :model-value="data.current || data.target"
        disabled
      />

      <Alert
        v-if="data.pending"
        theme="blue"
        :title="__('{0} is being set up', [pendingDomain])"
      >
        <template #description>
          {{ data.pending.last_error
            || __('We are checking the record and issuing a certificate. Usually a minute or two.') }}
        </template>
      </Alert>

      <!--
        The four steps are the server's words, not this file's: two of the
        ways this fails — a proxied record and an apex domain — are invisible
        from our side and produce an error that points somewhere else.
      -->
      <section class="flex flex-col gap-3">
        <h3 class="text-base-medium text-ink-primary">{{ __('Using a domain of your own') }}</h3>
        <ol class="flex flex-col gap-2.5">
          <li
            v-for="(step, at) in data.steps"
            :key="step.title"
            data-slot="domain-step"
            class="flex gap-2.5"
          >
            <span
              class="mt-0.5 grid size-5 shrink-0 place-items-center rounded-full bg-surface-gray-3 text-p-xs tabular-nums text-ink-secondary"
            >{{ at + 1 }}</span>
            <span class="flex flex-col">
              <span class="text-p-sm text-ink-primary">{{ __(step.title) }}</span>
              <span class="text-p-xs text-ink-muted">{{ __(step.detail) }}</span>
            </span>
          </li>
        </ol>
      </section>

      <FormControl
        v-model="wanted"
        type="text"
        :label="__('Your domain')"
        :placeholder="__('app.yourcompany.com')"
        :disabled="!!data.pending"
      />

      <ErrorMessage v-if="error" :message="error" />
    </div>
  </SettingsBody>

  <div v-if="data && !unreachable" :class="PANEL_FOOTER">
    <Button
      variant="solid"
      :label="__('Add this domain')"
      :loading="saving"
      :disabled="!wanted.trim() || !!data.pending"
      @click="request"
    />
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Alert, Button, ErrorMessage, FormControl, LoadingIndicator,
  SettingsHeader, SettingsBody,
} from '@/ui'
import { PANEL_BODY, PANEL_FOOTER, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const data = ref(null)
const loading = ref(false)
const saving = ref(false)
const unreachable = ref(false)
const error = ref('')
const wanted = ref('')

// The job carries what was asked for, so a person who closed the tab and came
// back can see which domain is the one being set up.
const pendingDomain = computed(() => {
  try {
    return JSON.parse(data.value?.pending?.payload || '{}').domain || ''
  } catch {
    return ''
  }
})

const load = async () => {
  loading.value = true
  try {
    const answer = await workspace.domain()
    unreachable.value = !!answer.unreachable
    data.value = answer
  } catch (e) {
    error.value = errorText(e)
  } finally {
    loading.value = false
  }
}

const request = async () => {
  saving.value = true
  error.value = ''
  try {
    await workspace.requestDomain(wanted.value.trim())
    wanted.value = ''
    await load()
  } catch (e) {
    error.value = errorText(e)
  } finally {
    saving.value = false
  }
}

load()
</script>
