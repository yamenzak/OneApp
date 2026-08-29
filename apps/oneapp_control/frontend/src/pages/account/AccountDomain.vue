<template>
  <PageHeader>
    <PageHeaderTitle>Domain</PageHeaderTitle>
  </PageHeader>

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
  <div v-if="guide" class="flex flex-col gap-6 py-5">
    <section v-if="guide.current">
      <div class="flex items-center justify-between rounded-4 border border-outline-gray-2 p-4">
        <div>
          <p class="text-base-medium text-ink-gray-8">{{ guide.current }}</p>
          <p class="mt-0.5 text-p-sm text-ink-gray-6">Live and serving your workspace.</p>
        </div>
        <Badge theme="green" label="Active" variant="subtle" />
      </div>
    </section>

    <section v-if="guide.pending">
      <Alert theme="blue" title="Verifying your DNS">
        <template #description>
          We are checking the record and issuing a certificate. This usually takes a
          minute or two. If it does not complete, the cause is almost always a
          proxied record — see step two below.
        </template>
      </Alert>
    </section>

    <section>
      <h3 class="mb-1 text-base-medium text-ink-gray-8">
        {{ guide.current ? 'Use a different domain' : 'Use your own domain' }}
      </h3>
      <p class="mb-4 text-p-sm text-ink-gray-6">
        Your workspace already works at
        <span class="text-ink-gray-8">{{ guide.target }}</span>. A custom domain is
        optional.
      </p>

      <ol class="mb-5 flex flex-col gap-3">
        <li
          v-for="(step, i) in guide.steps"
          :key="step.title"
          class="flex gap-3 rounded-4 border border-outline-gray-2 p-3"
        >
          <span
            class="grid size-5 shrink-0 place-items-center rounded-full bg-surface-gray-3 text-xs tabular-nums text-ink-gray-7"
          >
            {{ i + 1 }}
          </span>
          <div class="min-w-0">
            <p class="text-p-base text-ink-gray-8">{{ step.title }}</p>
            <p class="mt-0.5 text-p-sm text-ink-gray-6">{{ step.detail }}</p>
          </div>
        </li>
      </ol>

      <div class="rounded-4 border border-outline-gray-2 p-4">
        <p class="mb-2 text-p-sm text-ink-gray-6">Your CNAME should point at:</p>
        <div class="flex items-center gap-2 rounded-4 bg-surface-gray-2 px-3 py-2">
          <code class="min-w-0 flex-1 truncate text-p-sm text-ink-gray-8">
            {{ guide.target }}
          </code>
          <Button label="Copy" @click="copyTarget" />
        </div>

        <div class="mt-4 flex items-end gap-2">
          <FormControl
            v-model="domain"
            label="Then add it here"
            placeholder="app.yourcompany.com"
            class="flex-1"
          />
          <Button
            variant="solid"
            label="Add domain"
            :loading="adding"
            :disabled="!domain"
            @click="submit"
          />
        </div>
      </div>
    </section>
  </div>

  <div v-else class="grid place-items-center py-16">
    <LoadingIndicator class="size-5 text-ink-gray-5" />
  </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { PageHeader, PageHeaderTitle, Alert, Badge, Button, FormControl, LoadingIndicator } from '@/ui'
import { customer } from '../../lib/customer'
import { notifySuccess } from '../../lib/notify'

const props = defineProps({ workspace: { type: String, default: null } })

const guide = ref(null)
const domain = ref('')
const adding = ref(false)

async function load() {
  if (!props.workspace) return
  guide.value = await customer.domainGuide(props.workspace)
}

function copyTarget() {
  navigator.clipboard?.writeText(guide.value.target)
  notifySuccess('Copied')
}

async function submit() {
  adding.value = true
  try {
    await customer.addDomain(props.workspace, domain.value)
    domain.value = ''
    await load()
  } finally {
    adding.value = false
  }
}

watch(() => props.workspace, load, { immediate: true })
</script>
