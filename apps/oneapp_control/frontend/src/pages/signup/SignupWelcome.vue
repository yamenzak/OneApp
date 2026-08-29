<template>
  <div class="grid min-h-screen place-items-center bg-surface-gray-1 p-5">
    <div class="w-full max-w-md text-center">
      <template v-if="status?.ready">
        <Avatar label="✓" shape="square" size="2xl" class="mx-auto" />
        <h1 class="mt-4 text-xl-semibold text-ink-gray-9">
          {{ status.workspace_name }} is ready
        </h1>
        <p class="mt-2 text-p-base text-ink-gray-6">
          We have emailed you a link to set your password.
        </p>
        <Button
          class="mt-5"
          variant="solid"
          size="md"
          label="Open your workspace"
          @click="go"
        />
      </template>

      <template v-else-if="status?.status === 'Failed'">
        <h1 class="text-xl-semibold text-ink-gray-9">Something went wrong</h1>
        <p class="mt-2 text-p-base text-ink-gray-6">
          Your payment went through but we could not finish setting up. We have
          been alerted and are looking at it — you do not need to do anything,
          and you will not be charged again.
        </p>
      </template>

      <template v-else>
        <LoadingIndicator class="mx-auto size-6 text-ink-gray-5" />
        <h1 class="mt-4 text-xl-semibold text-ink-gray-9">
          Setting up your workspace
        </h1>
        <p class="mt-2 text-p-base text-ink-gray-6">
          This usually takes under a minute. If it takes longer we will email you
          the link — you can safely close this tab.
        </p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { Avatar, Button, LoadingIndicator } from '@/ui'
import { callMethod } from '../../lib/resource'

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
