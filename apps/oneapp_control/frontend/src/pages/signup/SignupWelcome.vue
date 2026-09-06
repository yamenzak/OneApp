<template>
  <div class="grid min-h-screen place-items-center bg-surface-gray-1 p-5">
    <div class="w-full max-w-md text-center">
      <template v-if="status?.ready">
        <Avatar label="✓" shape="square" size="2xl" class="mx-auto" />
        <h1 class="mt-4 text-xl-semibold text-ink-gray-9">
          {{ __('{0} is ready', [status.workspace_name]) }}
        </h1>
        <p class="mt-2 text-p-base text-ink-gray-6">
          {{ __('Check your email for a link to set your password.') }}
        </p>
        <Button
          class="mt-5"
          variant="solid"
          size="md"
          :label="__('Open your workspace')"
          @click="go"
        />
      </template>

      <template v-else-if="status?.status === 'Failed'">
        <h1 class="text-xl-semibold text-ink-gray-9">{{ __('Setup did not finish') }}</h1>
        <p class="mt-2 text-p-base text-ink-gray-6">
          {{ __('Your payment went through and you will not be charged again. Support has been told, and there is nothing for you to do.') }}
        </p>
      </template>

      <template v-else>
        <LoadingIndicator class="mx-auto size-6 text-ink-gray-5" />
        <h1 class="mt-4 text-xl-semibold text-ink-gray-9">
          {{ __('Setting up your workspace') }}
        </h1>
        <p class="mt-2 text-p-base text-ink-gray-6">
          {{ __('This usually takes under a minute. If it takes longer, the link arrives by email — you can close this tab.') }}
        </p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Avatar, Button, LoadingIndicator } from '@/ui'
import { callMethod } from '@/lib/runtime/resource'
import { __ } from '@/lib/runtime/translate'

const route = useRoute()
const status = ref(null)
let timer = null

const go = () => (window.location.href = status.value.site_url)

async function poll() {
  const request = route.query.request
  if (!request) return

  // Not socket-driven: the visitor has no session yet, so there is no
  // authenticated channel to subscribe on.
  status.value = await callMethod(
    'oneapp_control.api.signup.status',
    { request },
    { silent: true, method: 'GET' },
  )

  if (status.value?.ready || status.value?.status === 'Failed') {
    clearInterval(timer)
  }
}

onMounted(() => {
  poll()
  timer = setInterval(poll, 4000)
})
onUnmounted(() => clearInterval(timer))
</script>
