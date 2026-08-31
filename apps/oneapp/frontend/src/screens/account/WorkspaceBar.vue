<template>
  <!--
    Which workspace this screen is about.

    An account may own several — signing up for a company and later for
    something at home is ordinary — so every account screen says which one it
    is showing rather than leaving it to be inferred from the numbers.

    This is the piece that is only possible here. A tenant site can prove it is
    *itself* and nothing more: its HMAC secret is scoped to one tenant. The
    control plane is the one place that knows a person owns three of them, so
    the account area belongs here and this row is why.
  -->
  <div class="mb-5 flex items-center justify-between gap-3">
    <div class="min-w-0">
      <p class="truncate text-base-medium text-ink-gray-8">
        {{ selected?.workspace_name || selected?.name || 'Your account' }}
      </p>
      <p v-if="selected?.url" class="truncate text-p-sm text-ink-gray-5">
        {{ selected.url }}
      </p>
    </div>

    <!-- Only where there is a choice. A switcher over one workspace is a
         control that does nothing, and it is most people. -->
    <Dropdown v-if="list.length > 1" :options="options">
      <Button icon-right="lucide-chevron-down" label="Switch workspace" />
    </Dropdown>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Dropdown } from '@/ui'
import { workspaces } from './customer'

const list = computed(() => workspaces.list)
const selected = computed(() => workspaces.selected)

const options = computed(() =>
  workspaces.list.map((one) => ({
    label: one.workspace_name || one.name,
    onClick: () => {
      workspaces.current = one.name
    },
  })),
)
</script>
