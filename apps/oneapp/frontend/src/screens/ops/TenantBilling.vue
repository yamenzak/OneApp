<template>
  <div v-if="loading && !data" class="grid place-items-center py-12">
    <LoadingIndicator class="size-5 text-ink-gray-5" />
  </div>

  <div v-else-if="data" class="flex flex-col gap-6">
    <!--
      The one question an operator has that the customer's own plan page cannot
      answer: are the limits this workspace holds still the ones its plan
      offers? Quotas are captured when a subscription is sold, so a plan edited
      afterwards leaves the two disagreeing on purpose.
    -->
    <Alert v-if="data.grandfathered.length" theme="blue" title="On its original terms">
      <template #description>
        {{ data.grandfathered.join(', ') }} differ from the plan as it stands
        now. Captured when the subscription was sold, and unchanged by later
        edits to the plan.
      </template>
      <template #actions>
        <Button label="Move to current terms" :loading="adopting" @click="adopt" />
      </template>
    </Alert>

    <section>
      <h3 class="mb-3 text-base-medium text-ink-gray-8">Subscription</h3>
      <List :columns="fieldTracks" divider="full">
        <ListRows :items="subscriptionRows" row-key="label" v-slot="{ item: row, value }">
          <ListRow :value="value" class="py-3">
            <ListCell>
              <span class="text-p-sm text-ink-gray-6">{{ row.label }}</span>
            </ListCell>
            <ListCell>
              <Badge v-if="row.badge" :theme="row.theme" :label="row.value" variant="subtle" />
              <span v-else class="truncate text-p-sm text-ink-gray-8">{{ row.value }}</span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>

    <section>
      <div class="mb-3 flex items-baseline justify-between gap-3">
        <h3 class="text-base-medium text-ink-gray-8">Limits in force</h3>
        <Button label="Change plan" variant="subtle" @click="showChange = true" />
      </div>
      <List :columns="fieldTracks" divider="full">
        <ListRows :items="termRows" row-key="label" v-slot="{ item: row, value }">
          <ListRow :value="value" class="py-3">
            <ListCell>
              <span class="text-p-sm text-ink-gray-6">{{ row.label }}</span>
            </ListCell>
            <ListCell>
              <span class="truncate text-p-sm text-ink-gray-8">
                {{ row.value }}
                <span v-if="row.plan !== undefined" class="text-ink-gray-4">
                  · plan now offers {{ row.plan }}
                </span>
              </span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>

    <section>
      <div class="mb-1 flex items-baseline justify-between gap-3">
        <h3 class="text-base-medium text-ink-gray-8">Credits</h3>
        <Button label="Add credits" variant="subtle" @click="showGrant = true" />
      </div>
      <p class="mb-3 text-p-sm text-ink-gray-5">
        {{ data.credits.available }} available of {{ data.credits.balance }} —
        the difference is reserved by calls in flight.
      </p>

      <EmptyState
        v-if="!data.credits.history.length"
        class="!py-8"
        title="No credit movement"
        description="Grants land on each paid invoice; spend appears as it happens."
      />
      <List v-else :columns="creditTracks" :row-height="48" class="px-3" divider="full">
        <ListRows :items="data.credits.history" row-key="creation" v-slot="{ item: row, value }">
          <ListRow :value="value">
            <ListCell>
              <div class="min-w-0">
                <p class="truncate text-p-sm text-ink-gray-8">{{ row.entry_type }}</p>
                <p v-if="row.remarks" class="truncate text-xs text-ink-gray-5">{{ row.remarks }}</p>
              </div>
            </ListCell>
            <ListCell v-if="creditShows('when')">
              <span class="text-p-sm text-ink-gray-5">{{ when(row.creation) }}</span>
            </ListCell>
            <ListCell>
              <span
                class="text-p-sm tabular-nums"
                :class="row.credits < 0 ? 'text-ink-red-3' : 'text-ink-gray-8'"
              >
                {{ row.credits > 0 ? '+' : '' }}{{ row.credits }}
              </span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>

    <section>
      <div class="mb-1 flex items-center justify-between gap-2">
        <h3 class="text-base-medium text-ink-gray-8">AI usage</h3>
        <Button
          icon="lucide-refresh-cw"
          variant="ghost"
          label="Compare against the gateway log"
          tooltip="Compare against the gateway log"
          :loading="reconciling"
          @click="reconcile"
        />
      </div>
      <!--
        Two numbers per row, deliberately. We charge what the model reported it
        used; the gateway keeps its own figure and bills the account on it. Where
        they differ an adjustment has already been posted to the ledger above,
        and this is where an operator sees why.
      -->
      <p class="mb-3 text-p-sm text-ink-gray-5">
        Charged from what each model reported it used. The gateway column is
        Cloudflare's own figure, filled in once its log catches up.
      </p>

      <EmptyState
        v-if="!usage.length"
        class="!py-8"
        title="No AI calls"
        description="Nothing in this workspace has called a model yet."
      />
      <List v-else :columns="usageTracks" :row-height="48" class="px-3" divider="full">
        <ListRows :items="usage" row-key="name" v-slot="{ item: row, value }">
          <ListRow :value="value">
            <ListCell>
              <div class="min-w-0">
                <p class="truncate text-p-sm text-ink-gray-8">{{ row.feature || 'AI call' }}</p>
                <p class="truncate text-xs text-ink-gray-5">{{ row.model }}</p>
              </div>
            </ListCell>
            <ListCell v-if="usageShows('when')">
              <span class="text-p-sm text-ink-gray-5">{{ when(row.creation) }}</span>
            </ListCell>
            <ListCell v-if="usageShows('gateway')">
              <span class="text-p-sm tabular-nums text-ink-gray-5">
                {{ row.reconciled_on ? `$${row.gateway_cost_usd}` : '—' }}
              </span>
            </ListCell>
            <ListCell>
              <span class="text-p-sm tabular-nums text-ink-gray-8">
                {{ row.credits_charged }}
              </span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>
    </section>
  </div>

  <!--
    The one way credits arrive that is not Stripe. Goodwill, a migration
    allowance, a demo top-up — none of which had a path before, so they meant
    opening the desk, which this product does not do.
  -->
  <Dialog v-model="showGrant" title="Add credits">
    <div v-focus class="flex flex-col gap-4">
      <FormControl
        v-model="grantAmount"
        type="number"
        label="Credits"
        description="Negative takes some away. Nothing here expires."
      />
      <FormControl
        v-model="grantReason"
        type="textarea"
        label="Why"
        placeholder="Goodwill after the outage on the 12th"
        description="Goes on the ledger. Somebody will read it in six months."
      />
      <ErrorMessage v-if="grantError" :message="grantError" />
    </div>
    <template #actions>
      <Button
        variant="solid"
        label="Add credits"
        :loading="granting"
        :disabled="!Number(grantAmount) || !grantReason.trim()"
        @click="grant"
      />
    </template>
  </Dialog>

  <Dialog v-model="showChange" title="Change plan" size="lg">
    <div class="flex flex-col gap-4">
      <p class="text-p-base text-ink-gray-7">
        The same switch the customer's own page runs, so the fit check, the
        proration and the Frappe Cloud site plan behave identically. A plan
        smaller than what this workspace already holds is refused.
      </p>
      <FormControl
        v-model="chosen"
        type="select"
        label="Plan"
        :options="planOptions"
      />
      <ErrorMessage v-if="error" :message="error" />
    </div>
    <template #actions>
      <Button
        variant="solid"
        label="Change plan"
        :loading="changing"
        :disabled="!chosen || chosen === data?.plan"
        @click="change"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import {
  Alert, Badge, Button, Dialog, ErrorMessage, FormControl, LoadingIndicator, vFocus,
  List, ListRows, ListRow, ListCell, dayjsLocal,
} from '@/ui'
import EmptyState from '../../components/EmptyState.vue'
import { useListColumns } from '../../lib/list'
import { useDocList } from '../../lib/resource'
import { admin } from './admin'

const props = defineProps({ tenant: { type: String, required: true } })

const data = ref(null)
const loading = ref(false)
const adopting = ref(false)
const changing = ref(false)
const showChange = ref(false)
const showGrant = ref(false)
const granting = ref(false)
const grantAmount = ref('')
const grantReason = ref('')
const grantError = ref('')
const chosen = ref('')
const error = ref('')

const { columns: fieldTracks } = useListColumns([
  { key: 'label', header: '', track: '12rem', mobile: '8rem' },
  { key: 'value', header: '', track: 'minmax(0,1fr)' },
])

const usage = ref([])
const reconciling = ref(false)

const { columns: usageTracks, shows: usageShows } = useListColumns([
  { key: 'call', header: 'Call', track: 'minmax(0,1fr)' },
  { key: 'when', header: 'When', track: '9rem', mobile: false },
  { key: 'gateway', header: 'Gateway', track: '7rem', mobile: false },
  { key: 'credits', header: 'Credits', track: '7rem', mobile: '5rem' },
])

const { columns: creditTracks, shows: creditShows } = useListColumns([
  { key: 'entry', header: 'Entry', track: 'minmax(0,1fr)' },
  { key: 'when', header: 'When', track: '10rem', mobile: false },
  { key: 'credits', header: 'Credits', track: '7rem', mobile: '5rem' },
])

const plans = useDocList('Plan', {
  fields: ['name', 'plan_name', 'price_monthly'],
  filters: { is_active: 1 },
  orderBy: 'sort_order asc',
})

const planOptions = computed(() =>
  (plans.data || []).map((p) => ({
    label: `${p.plan_name} — $${p.price_monthly}/mo`,
    value: p.name,
  })),
)

// Units belong beside the number: "File storage 10" is ambiguous in a table
// whose next row is a count of seats.
const TERMS = [
  { field: 'storage_gb', label: 'File storage', unit: 'GB' },
  { field: 'database_gb', label: 'Database', unit: 'GB' },
  { field: 'max_users', label: 'Seats' },
  { field: 'monthly_credit_grant', label: 'Monthly credits', unit: 'a month' },
  { field: 'background_workers', label: 'Background workers' },
  { field: 'press_site_plan', label: 'Frappe Cloud site plan' },
]

const amount = (value, unit) => {
  if (value === null || value === undefined || value === '') return '—'
  return unit ? `${value} ${unit}` : String(value)
}

const subscriptionRows = computed(() => {
  const sub = data.value?.subscription
  if (!sub) {
    return [{ label: 'Subscription', value: 'None — this workspace was not sold through checkout' }]
  }
  return [
    { label: 'Plan', value: data.value.plan || '—' },
    {
      label: 'Status',
      value: sub.status,
      badge: true,
      theme: { Active: 'green', Trialing: 'blue', 'Past Due': 'amber', Canceled: 'red' }[sub.status] || 'gray',
    },
    { label: 'Interval', value: sub.interval },
    { label: 'Period ends', value: when(sub.current_period_end) },
    { label: 'Cancels at period end', value: sub.cancel_at_period_end ? 'Yes' : 'No' },
    { label: 'Stripe subscription', value: sub.stripe_subscription_id || '—' },
  ]
})

const termRows = computed(() => {
  const terms = data.value?.terms || {}
  const planTerms = data.value?.plan_terms || {}
  return TERMS.map(({ field, label, unit }) => ({
    label,
    value: amount(terms[field], unit),
    plan: data.value?.grandfathered.includes(field)
      ? amount(planTerms[field], unit)
      : undefined,
  }))
})

const when = (value) => (value ? dayjsLocal(value).format('D MMM YYYY, HH:mm') : '—')

const load = async () => {
  loading.value = true
  try {
    const [billing, calls] = await Promise.all([
      admin.tenantBilling(props.tenant),
      admin.aiUsage({ tenant: props.tenant, limit: 25 }),
    ])
    data.value = billing
    usage.value = calls || []
    chosen.value = data.value?.plan || ''
  } finally {
    loading.value = false
  }
}

async function reconcile() {
  reconciling.value = true
  try {
    await admin.reconcileAiUsage()
    usage.value = (await admin.aiUsage({ tenant: props.tenant, limit: 25 })) || []
  } finally {
    reconciling.value = false
  }
}

onMounted(load)
watch(() => props.tenant, load)

watch(showGrant, (open) => {
  if (!open) return
  grantAmount.value = ''
  grantReason.value = ''
  grantError.value = ''
})

async function grant() {
  granting.value = true
  grantError.value = ''
  try {
    await admin.grantCredits(props.tenant, Number(grantAmount.value), grantReason.value)
    showGrant.value = false
    await load()
  } catch (e) {
    grantError.value = e.message || String(e)
  } finally {
    granting.value = false
  }
}

async function adopt() {
  adopting.value = true
  try {
    await admin.adoptPlanTerms(props.tenant)
    await load()
  } finally {
    adopting.value = false
  }
}

async function change() {
  changing.value = true
  error.value = ''
  try {
    await admin.setTenantPlan(props.tenant, chosen.value)
    showChange.value = false
    await load()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    changing.value = false
  }
}
</script>
