<!--
  Ported from the portal SPA. The content and its reasoning are unchanged; what
  moved is the frame: a screen renders inside the shell's own header, so the
  PageHeader is gone and the workspace it is about is stated by WorkspaceBar
  rather than carried in the route.
-->
<template>
  <WorkspaceBar />

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
  <div v-if="data" class="flex flex-col gap-6 py-5">
    <section>
      <div class="flex items-start justify-between gap-4 rounded-6 border border-outline-gray-2 p-4">
        <div>
          <p class="text-base-medium text-ink-gray-8">{{ data.plan.name }}</p>
          <p class="mt-0.5 text-p-sm text-ink-gray-6">
            <template v-if="data.subscription">
              {{ __('{0} · renews {1}', [
                data.subscription.interval,
                formatDate(data.subscription.current_period_end),
              ]) }}
            </template>
            <template v-else>{{ __('No plan running yet') }}</template>
          </p>
          <Badge
            v-if="data.subscription?.cancel_at_period_end"
            class="mt-2"
            theme="amber"
            :label="__('Cancels at the end of this period')"
            variant="subtle"
          />
        </div>
        <Button :label="__('Manage billing')" :loading="opening" @click="openPortal" />
      </div>
      <p class="mt-2 text-p-sm text-ink-gray-5">
        {{ __('Change your card, download an invoice or cancel from there.') }}
      </p>
    </section>

    <section>
      <h3 class="mb-1 text-base-medium text-ink-gray-8">{{ __('Add-ons') }}</h3>
      <p class="mb-3 text-p-sm text-ink-gray-6">
        {{ __('Extra room, billed with your plan and charged from the day you add it. It is not paid for with AI credits.') }}
      </p>

      <Alert v-if="!addons.can_buy" theme="amber" :title="__('No plan yet')">
        <template #description>
          {{ __('An add-on goes on the same invoice as your plan, so there has to be a plan first.') }}
        </template>
      </Alert>

      <div v-else class="flex flex-col gap-2">
        <AddonRow
          v-for="addon in addons.addons"
          :key="addon.code"
          :addon="addon"
          :interval="addons.interval"
          :busy="busy === addon.code"
          @set="(quantity) => setAddon(addon, quantity)"
        />
        <EmptyState
          v-if="!addons.addons.length"
          class="!py-8"
          icon="lucide-package"
          :title="__('Nothing on offer yet')"
          :description="__('Extra storage appears here when it is available.')"
        />
      </div>
    </section>

    <section>
      <div class="mb-1 flex items-baseline justify-between gap-3">
        <h3 class="text-base-medium text-ink-gray-8">{{ __('AI credits') }}</h3>
        <span class="text-p-sm tabular-nums text-ink-gray-6">
          {{ __('{0} available', [Math.round(data.credits.available).toLocaleString()]) }}
        </span>
      </div>
      <p class="mb-3 text-p-sm text-ink-gray-6">
        {{ __('Your plan adds credits every month and they expire at the end of it. Credits you buy roll over and are spent last.') }}
      </p>

      <div class="grid gap-3 md:grid-cols-3">
        <PackCard
          v-for="pack in packs.credits"
          :key="pack.code"
          :title="__('{0} credits', [Number(pack.credits).toLocaleString()])"
          :price="pack.amount"
          :currency="pack.currency"
          :description="pack.description"
          :busy="busy === pack.code"
          @buy="buy(pack.code)"
        />
      </div>

      <!-- Where the balance went. A number with no history behind it is one
           nobody can question, and "why am I out of credits" is the question
           this section exists to answer. -->
      <List
        v-if="history.length"
        :columns="historyColumns"
        :row-height="48"
        class="px-3 mt-4"
        divider="full"
      >
        <ListRows :items="history" row-key="creation" v-slot="{ item: row, value }">
          <ListRow :value="value">
            <ListCell>
              <div class="min-w-0">
                <p class="truncate text-p-sm text-ink-gray-8">{{ row.entry_type }}</p>
                <p v-if="row.remarks" class="truncate text-xs text-ink-gray-5">
                  {{ row.remarks }}
                </p>
              </div>
            </ListCell>
            <ListCell v-if="historyShows('when')">
              <span class="text-p-sm text-ink-gray-5">{{ formatDate(row.creation) }}</span>
            </ListCell>
            <ListCell>
              <span
                class="text-p-sm tabular-nums"
                :class="row.credits < 0 ? 'text-ink-red-3' : 'text-ink-gray-8'"
              >
                {{ row.credits > 0 ? '+' : '' }}{{ Math.round(row.credits).toLocaleString() }}
              </span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>

    <section v-if="invoices.length">
      <h3 class="mb-3 text-base-medium text-ink-gray-8">{{ __('Invoices') }}</h3>
      <!-- Narrowed rather than dropped: three short cells all fit a phone once
           the two fixed tracks stop being sized for a desktop. -->
      <List :columns="invoiceColumns" :row-height="52" class="px-3" divider="full">
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
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Alert, Badge, Button, LoadingIndicator, List, ListRows, ListRow, ListCell, dayjsLocal } from '@/ui'
import WorkspaceBar from '@/modules/onespace/screens/account/WorkspaceBar.vue'
import { useWorkspace } from '@/modules/onespace/screens/account/workspace'
import PackCard from '@/modules/onespace/screens/account/PackCard.vue'
import AddonRow from '@/modules/onespace/screens/account/AddonRow.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useListColumns } from '@/modules/onespace/lib/screen/list'
import { customer, useOverview } from '@/modules/onespace/screens/account/customer'
import { notifyInfo, notifySuccess } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'

const { columns: invoiceColumns } = useListColumns([
  { key: 'date', header: __('Date'), track: 'minmax(0,1fr)' },
  { key: 'amount', header: __('Amount'), track: '8rem', mobile: '6rem' },
  { key: 'status', header: __('Status'), track: '7rem', mobile: '5rem' },
])

const { columns: historyColumns, shows: historyShows } = useListColumns([
  { key: 'entry', header: __('Entry'), track: 'minmax(0,1fr)' },
  { key: 'when', header: __('When'), track: '10rem', mobile: false },
  { key: 'credits', header: __('Credits'), track: '7rem', mobile: '5rem' },
])

defineProps({ spaceCode: { type: String, default: '' }, screen: { type: String, default: '' } })
const workspace = useWorkspace()
const resource = useOverview(workspace)

const data = computed(() => resource.data)
const packs = ref({ credits: [] })
const addons = ref({ interval: 'Monthly', addons: [], can_buy: false })
const history = ref([])
const invoices = ref([])
const opening = ref(false)
const busy = ref(null)

const route = useRoute()
const router = useRouter()

// The redirect back from checkout is the only signal the customer gets that a
// purchase landed; what actually applies it arrives separately, so this says
// "received" rather than claiming the balance is already updated. The flags are
// stripped afterwards so a refresh does not toast a second time.
onMounted(() => {
  if (route.query.checkout === 'success') {
    notifySuccess(__('Payment received — your balance updates in a moment'))
  } else if (route.query.checkout === 'cancelled') {
    notifyInfo(__('Cancelled. Nothing was charged.'))
  } else {
    return
  }
  const query = { ...route.query }
  delete query.checkout
  delete query.session
  router.replace({ query })
})

// dayjsLocal, not dayjs: the value is stored in the site's timezone, and
// reading it as local puts an invoice on the wrong day for anyone far
// enough east or west of the server.
const formatDate = (value) => (value ? dayjsLocal(value).format('D MMM YYYY') : '—')

async function openPortal() {
  opening.value = true
  try {
    const { url } = await customer.billingPortal(workspace.value)
    if (url) window.location.href = url
  } finally {
    opening.value = false
  }
}

async function buy(pack) {
  busy.value = pack
  try {
    const { url } = await customer.buyCredits(workspace.value, pack)
    if (url) window.location.href = url
  } finally {
    busy.value = null
  }
}

// No redirect: there is a card on file and a cycle running, so this is a change
// to the subscription rather than a checkout. The money arrives on the next
// invoice, prorated from now.
async function setAddon(addon, quantity) {
  busy.value = addon.code
  try {
    await customer.setAddon(workspace.value, addon.code, quantity)
    await loadAddons()
    resource.reload()
  } finally {
    busy.value = null
  }
}

const loadAddons = async () => {
  addons.value = (await customer.addons(workspace.value)) || {
    interval: 'Monthly',
    addons: [],
    can_buy: false,
  }
}

watch(
  () => workspace.value,
  async (chosen) => {
    if (!chosen) return
    // In parallel: four independent reads, and doing them in turn makes the
    // page as slow as their sum for no reason.
    const [catalogue, ledger, bills] = await Promise.all([
      customer.packs(),
      customer.creditHistory(chosen),
      customer.invoices(chosen),
      loadAddons(),
    ])
    packs.value = catalogue || { credits: [] }
    history.value = ledger || []
    invoices.value = bills || []
  },
  { immediate: true },
)
</script>
