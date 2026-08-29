<template>
  <PageHeader>
    <PageHeaderTitle>Billing</PageHeaderTitle>
  </PageHeader>

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
  <div v-if="data" class="flex flex-col gap-6 py-5">
    <section>
      <div class="flex items-start justify-between gap-4 rounded-4 border border-outline-gray-2 p-4">
        <div>
          <p class="text-base-medium text-ink-gray-8">{{ data.plan.name }}</p>
          <p class="mt-0.5 text-p-sm text-ink-gray-6">
            <template v-if="data.subscription">
              {{ data.subscription.interval }} · renews
              {{ formatDate(data.subscription.current_period_end) }}
            </template>
            <template v-else>No active subscription</template>
          </p>
          <Badge
            v-if="data.subscription?.cancel_at_period_end"
            class="mt-2"
            theme="amber"
            label="Cancels at period end"
            variant="subtle"
          />
        </div>
        <Button label="Manage billing" :loading="opening" @click="openPortal" />
      </div>
      <p class="mt-2 text-p-sm text-ink-gray-5">
        Cards, invoices and cancellation are handled by Stripe.
      </p>
    </section>

    <section>
      <h3 class="mb-1 text-base-medium text-ink-gray-8">Add-ons</h3>
      <p class="mb-3 text-p-sm text-ink-gray-6">
        Storage is bought outright and never expires. It is deliberately not paid
        for with AI credits — a large upload should not quietly drain the budget
        you were keeping for something else.
      </p>

      <div class="grid gap-3 sm:grid-cols-3">
        <PackCard
          v-for="pack in packs.storage"
          :key="pack.code"
          :title="`${pack.gb} GB`"
          :price="pack.amount"
          :busy="busy === pack.code"
          @buy="buy('storage', pack.code)"
        />
      </div>

      <div class="mt-4 grid gap-3 sm:grid-cols-3">
        <PackCard
          v-for="pack in packs.credits"
          :key="pack.code"
          :title="`${pack.credits.toLocaleString()} credits`"
          :price="pack.amount"
          :busy="busy === pack.code"
          @buy="buy('credits', pack.code)"
        />
      </div>
    </section>

    <section v-if="invoices.length">
      <h3 class="mb-3 text-base-medium text-ink-gray-8">Invoices</h3>
      <List :columns="['minmax(0,1fr)', '8rem', '7rem']" :row-height="52" class="list-row-px-3" divider="full">
        <ListRows :items="invoices" row-key="name" v-slot="{ item: inv, value }">
          <ListRow :value="value">
            <ListCell>
              <span class="text-p-sm text-ink-gray-8">{{ formatDate(inv.posting_date) }}</span>
            </ListCell>
            <ListCell>
              <span class="text-p-sm tabular-nums text-ink-gray-7">
                {{ inv.currency }} {{ inv.grand_total }}
              </span>
            </ListCell>
            <ListCell>
              <Badge :label="inv.status" variant="subtle" theme="gray" />
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>
  </div>

  <div v-else class="grid place-items-center py-16">
    <LoadingIndicator class="size-5 text-ink-gray-5" />
  </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, toRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { PageHeader, PageHeaderTitle, Alert, Badge, Button, LoadingIndicator, List, ListRows, ListRow, ListCell, dayjs } from '@/ui'
import PackCard from '../../components/PackCard.vue'
import { customer, useOverview } from '../../lib/customer'
import { notifyInfo, notifySuccess } from '../../lib/notify'

const props = defineProps({ workspace: { type: String, default: null } })
const resource = useOverview(toRef(props, 'workspace'))

const data = computed(() => resource.data)
const packs = ref({ credits: [], storage: [] })
const invoices = ref([])
const opening = ref(false)
const busy = ref(null)

const route = useRoute()
const router = useRouter()

// Stripe's redirect is the only signal the customer gets that a purchase landed;
// the webhook that actually applies it arrives separately, so this says
// "received" rather than claiming the balance is already updated. The flags are
// stripped afterwards so a refresh does not toast a second time.
onMounted(() => {
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
})

const formatDate = (value) => (value ? dayjs(value).format('D MMM YYYY') : '—')

async function openPortal() {
  opening.value = true
  try {
    const { url } = await customer.billingPortal(props.workspace)
    if (url) window.location.href = url
  } finally {
    opening.value = false
  }
}

async function buy(kind, pack) {
  busy.value = pack
  try {
    const fn = kind === 'storage' ? customer.buyStorage : customer.buyCredits
    const { url } = await fn(props.workspace, pack)
    if (url) window.location.href = url
  } finally {
    busy.value = null
  }
}

watch(
  () => props.workspace,
  async (workspace) => {
    if (!workspace) return
    packs.value = (await customer.packs()) || { credits: [], storage: [] }
    invoices.value = (await customer.invoices(workspace)) || []
  },
  { immediate: true },
)
</script>
