<!--
  Ported from the portal SPA. The content and its reasoning are unchanged; what
  moved is the frame: a screen renders inside the shell's own header, so the
  PageHeader is gone and the workspace it is about is stated by WorkspaceBar
  rather than carried in the route.
-->
<template>
  <WorkspaceBar />

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <div v-if="resource.loading && !data" class="grid place-items-center py-16">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else-if="data" class="flex flex-col gap-6 py-5">
      <p class="text-p-sm text-ink-gray-6">
        {{ __('Every plan includes every app. They differ in how much you can store and how many people you can invite.') }}
      </p>

      <section
        v-for="plan in data.plans"
        :key="plan.code"
        class="rounded-6 border p-4"
        :class="plan.current ? 'border-outline-gray-3' : 'border-outline-gray-2'"
      >
        <div class="flex items-start justify-between gap-4">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <h3 class="text-base-medium text-ink-gray-8">{{ plan.name }}</h3>
              <Badge v-if="plan.current" theme="green" :label="__('Current')" variant="subtle" />
              <!-- The limits below are what this workspace was sold, which is
                   not always what the plan offers today. Saying so beats a card
                   that quietly disagrees with the price sheet. -->
              <Badge
                v-if="plan.grandfathered"
                theme="blue"
                :label="__('Your original terms')"
                variant="subtle"
              />
            </div>
            <p v-if="plan.description" class="mt-1 text-p-sm text-ink-gray-6">
              {{ plan.description }}
            </p>
          </div>
          <div class="shrink-0 text-end">
            <p class="text-base-medium tabular-nums text-ink-gray-8">
              {{ money(plan.price_monthly, plan.currency) }}
            </p>
            <p class="text-p-sm text-ink-gray-5">{{ __('per month') }}</p>
          </div>
        </div>

        <div class="mt-3 flex flex-wrap gap-x-6 gap-y-1">
          <span v-for="line in limits(plan)" :key="line" class="text-p-sm text-ink-gray-6">
            {{ line }}
          </span>
        </div>

        <!--
          Named, not just refused. "Storage" tells someone what to clear;
          a disabled button with no reason tells them to write in.
        -->
        <Alert
          v-if="plan.blocked_by.length"
          class="mt-3"
          theme="amber"
          :title="__('Your workspace is past the {0} limit on this plan', [limitNames(plan.blocked_by)])"
        >
          <template #description>
            {{ __('Free some space or remove people first, and this plan becomes available.') }}
          </template>
        </Alert>

        <Button
          v-else-if="!plan.current"
          class="mt-3"
          :loading="busy === plan.code"
          :disabled="Boolean(busy)"
          :label="__('Change to this plan')"
          @click="choose(plan)"
        />
      </section>
    </div>
  </div>

  <!--
    Confirmed, not one-tap. This charges or credits a card immediately, and the
    number involved is not on the button.
  -->
  <Dialog
    v-model="showConfirm"
    :title="__('Change to {0}?', [chosen?.name || ''])"
    :actions="[
      { label: __('Change plan'), variant: 'solid', loading: Boolean(busy), onClick: confirm },
    ]"
  >
    <div class="flex flex-col gap-3">
      <p class="text-p-base text-ink-gray-7">
        {{ chosen && chosen.price_monthly > (current?.price_monthly || 0)
          ? __('Your card is charged the difference for the rest of this billing period, and the new limits apply straight away.')
          : __('The difference is credited against your next invoice, and the new limits apply straight away.') }}
      </p>
      <p v-if="chosen" class="text-p-sm text-ink-gray-5">
        {{ __('{0} a month, from now on.', [money(chosen.price_monthly, chosen.currency)]) }}
      </p>
    </div>
  </Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Alert, Badge, Button, Dialog, LoadingIndicator,
} from '@/ui'
import WorkspaceBar from './WorkspaceBar.vue'
import { useWorkspace } from './workspace'
import { usePlans, customer } from './customer'
import { __ } from '@/lib/runtime/translate'

defineProps({
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

// Shared with every other account screen, so switching on the overview is
// still switched when you open this one.
const workspace = useWorkspace()

const resource = usePlans(workspace)
const data = computed(() => resource.data)

const money = (amount, currency) =>
  amount == null
    ? '—'
    : new Intl.NumberFormat(undefined, {
        style: 'currency',
        currency: currency || 'USD',
        maximumFractionDigits: 0,
      }).format(amount)

// A limit is one whole phrase per line, placeholder and all: "{0} GB files" is
// a sentence somebody can reorder, and `n + ' ' + noun` is not.
const limits = (plan) => {
  const out = []
  if (plan.storage_gb) out.push(__('{0} GB files', [plan.storage_gb]))
  if (plan.database_gb) out.push(__('{0} GB database', [plan.database_gb]))
  if (plan.max_users)
    out.push(
      plan.max_users === 1 ? __('One seat') : __('{0} seats', [plan.max_users]),
    )
  if (plan.monthly_credit_grant)
    out.push(__('{0} credits a month', [plan.monthly_credit_grant]))
  return out
}

// The server names a limit the way it stores it — `storage`, `users`. A reader
// owns files and people, so the alert says those.
const LIMIT_NAMES = () => ({
  storage: __('files'),
  database: __('database'),
  users: __('people'),
})
const limitNames = (keys) => (keys || []).map((key) => LIMIT_NAMES()[key] || key).join(', ')

// Changed here rather than in the payment provider's billing portal. It owns cards,
// invoices and cancellation, and it is better at all three — but it cannot know
// our quotas, so it would happily sell a downgrade to a workspace already
// holding more than the smaller plan allows. The server runs the same fit check
// this page renders.
const showConfirm = ref(false)
const chosen = ref(null)
const busy = ref('')

const current = computed(() => data.value?.plans?.find((p) => p.current) || null)

const choose = (plan) => {
  chosen.value = plan
  showConfirm.value = true
}

const confirm = async () => {
  const plan = chosen.value
  if (!plan) return
  busy.value = plan.code
  try {
    await customer.changePlan(workspace.value, plan.code)
    showConfirm.value = false
    await resource.reload()
  } finally {
    busy.value = ''
  }
}
</script>
