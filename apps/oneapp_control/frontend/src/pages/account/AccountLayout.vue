<template>
  <div class="min-h-screen bg-surface-white">
    <div v-if="workspaces.loading" class="grid h-screen place-items-center">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!workspaces.list.length"
      icon="lucide-layout-grid"
      title="No workspaces yet"
      description="Create one to get started — it takes about a minute."
    >
      <template #action>
        <Button variant="solid" label="Create a workspace" @click="toSignup" />
      </template>
    </EmptyState>

    <template v-else>
      <PageHeader>
        <template #title>
          <div class="flex items-center gap-2">
            <Dropdown v-if="workspaces.list.length > 1" :options="switcher">
              <Button variant="ghost">
                <template #prefix>
                  <Avatar :label="current?.tenant_name || '?'" size="sm" shape="square" />
                </template>
                {{ current?.tenant_name }}
                <template #suffix>
                  <Icon name="lucide-chevron-down" class="size-4 text-ink-gray-5" />
                </template>
              </Button>
            </Dropdown>
            <span v-else class="text-base font-medium text-ink-gray-8">
              {{ current?.tenant_name || 'Account' }}
            </span>
          </div>
        </template>
        <template #actions>
          <Button
            v-if="current?.url"
            variant="solid"
            label="Open workspace"
            @click="openWorkspace"
          />
          <UserMenu />
        </template>
      </PageHeader>

      <div class="mx-auto max-w-3xl p-5">
        <Tabs v-model="tab">
          <TabList>
            <TabTrigger v-for="t in TABS" :key="t.value" :value="t.value">
              {{ t.label }}
            </TabTrigger>
          </TabList>

          <TabPanel value="overview"><AccountOverview :workspace="workspaceName" /></TabPanel>
          <TabPanel value="billing"><AccountBilling :workspace="workspaceName" /></TabPanel>
          <TabPanel value="domain"><AccountDomain :workspace="workspaceName" /></TabPanel>
        </Tabs>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  PageHeader,
  Button,
  Dropdown,
  Avatar,
  Icon,
  LoadingIndicator,
  Tabs,
  TabList,
  TabTrigger,
  TabPanel,
} from '@/ui'
import EmptyState from '@/components/EmptyState.vue'
import UserMenu from '@/components/UserMenu.vue'
import AccountOverview from './AccountOverview.vue'
import AccountBilling from './AccountBilling.vue'
import AccountDomain from './AccountDomain.vue'
import { workspaces } from '../../lib/customer'
import { notifyInfo, notifySuccess } from '../../lib/notify'

const TABS = [
  { value: 'overview', label: 'Overview' },
  { value: 'billing', label: 'Billing' },
  { value: 'domain', label: 'Domain' },
]

const props = defineProps({
  workspace: { type: String, default: '' },
})

const route = useRoute()
const router = useRouter()

const isTab = (value) => TABS.some((t) => t.value === value)
const tab = ref(isTab(route.query.tab) ? route.query.tab : 'overview')

const current = computed(() => workspaces.selected)
const workspaceName = computed(() => workspaces.current)

const switcher = computed(() =>
  workspaces.list.map((w) => ({
    label: w.tenant_name,
    onClick: () => select(w.name),
  })),
)

// The workspace lives in the URL, not just in memory: Stripe sends the customer
// back to a specific one, and someone with several workspaces open in tabs would
// otherwise find every tab showing whichever they touched last.
function select(name) {
  router.push({ name: 'AccountWorkspace', params: { workspace: name }, query: { tab: tab.value } })
}

watch(tab, (value) => {
  if (route.query.tab === value) return
  router.replace({ query: { ...route.query, tab: value } })
})

// Follows the URL rather than being set once, so back and forward work and the
// switcher's push above is what actually changes the selection.
watch(
  () => props.workspace,
  (name) => {
    if (name && workspaces.list.some((w) => w.name === name)) workspaces.current = name
  },
)

const openWorkspace = () => window.open(current.value.url, '_blank', 'noopener')
const toSignup = () => router.push({ name: 'Signup' })

function reportCheckout() {
  // Stripe's redirect is the only signal the customer gets that a purchase
  // landed; the webhook that actually applies it arrives separately.
  if (route.query.checkout === 'success') {
    notifySuccess('Payment received — your balance updates in a moment')
  } else if (route.query.checkout === 'cancelled') {
    notifyInfo('Checkout cancelled. Nothing was charged.')
  } else {
    return
  }
  const query = { ...route.query }
  delete query.checkout
  delete query.session
  router.replace({ query })
}

onMounted(async () => {
  await workspaces.load(props.workspace || null)
  // A deep link to a workspace that is not this account's resolves to the first
  // one they do own, so correct the URL rather than leaving it lying.
  if (workspaces.current && workspaces.current !== props.workspace) {
    router.replace({
      name: 'AccountWorkspace',
      params: { workspace: workspaces.current },
      query: route.query,
    })
  }
  reportCheckout()
})
</script>
