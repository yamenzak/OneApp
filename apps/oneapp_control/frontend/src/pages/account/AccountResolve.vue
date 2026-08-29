<template>
  <div class="grid h-full place-items-center">
    <LoadingIndicator v-if="workspaces.loading" class="size-5 text-ink-gray-5" />

    <EmptyState
      v-else
      icon="lucide-layout-grid"
      title="No workspaces yet"
      description="Create one to get started — it takes about a minute."
    >
      <template #action>
        <Button variant="solid" label="Create a workspace" @click="toSignup" />
      </template>
    </EmptyState>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Button, LoadingIndicator } from '@/ui'
import EmptyState from '@/components/EmptyState.vue'
import { workspaces } from '../../lib/customer'

// /portal/account has no workspace in it. Rather than pick one implicitly and
// leave the URL lying about which workspace is on screen, this resolves to a
// real one and redirects — so every account URL below names its workspace.
const router = useRouter()
const toSignup = () => router.push({ name: 'Signup' })

onMounted(async () => {
  await workspaces.load()
  if (workspaces.current) {
    router.replace({
      name: 'AccountOverview',
      params: { workspace: workspaces.current },
    })
  }
})
</script>
