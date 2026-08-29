<template>
  <FrappeUIProvider>
    <DesktopShell>
      <template #sidebar>
        <Sidebar>
          <div class="px-3 py-4">
            <div class="flex items-center gap-2 px-2">
              <span
                class="grid h-7 w-7 place-items-center rounded bg-surface-gray-7 text-xs font-medium text-ink-white"
              >
                1
              </span>
              <span class="text-base font-medium">OneApp Admin</span>
            </div>

            <nav class="mt-6 flex flex-col gap-0.5">
              <router-link
                v-for="item in nav"
                :key="item.to"
                :to="item.to"
                class="rounded px-2 py-1.5 text-sm text-ink-gray-7 hover:bg-surface-gray-2"
                active-class="bg-surface-gray-3 font-medium text-ink-gray-9"
              >
                {{ item.label }}
              </router-link>
            </nav>
          </div>

          <template #footer>
            <div class="px-3 pb-3">
              <Badge
                v-if="!setup.canProvision"
                theme="orange"
                :label="`Setup: ${blockersLeft} left`"
              />
              <Badge v-else-if="!setup.canBill" theme="blue" label="Billing not configured" />
              <Badge v-else theme="green" label="Ready" />
            </div>
          </template>
        </Sidebar>
      </template>

      <router-view />
    </DesktopShell>
  </FrappeUIProvider>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { FrappeUIProvider, DesktopShell, Sidebar, Badge, usePageMeta } from '@/ui'
import { setup } from './lib/setup'

const nav = [
  { to: '/tenants', label: 'Tenants' },
  { to: '/shards', label: 'Shards' },
  { to: '/jobs', label: 'Provisioning' },
  { to: '/setup', label: 'Setup' },
]

const blockersLeft = computed(() => setup.blockers.length)

usePageMeta(() => ({ title: 'OneApp Admin', emoji: '⚙️' }))

onMounted(() => setup.load())
</script>
