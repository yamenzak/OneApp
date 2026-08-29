<template>
  <PageHeader>
    <PageHeaderTitle>Plan</PageHeaderTitle>
  </PageHeader>

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <div v-if="resource.loading && !data" class="grid place-items-center py-16">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else-if="data" class="flex flex-col gap-6 py-5">
      <p class="text-p-sm text-ink-gray-6">
        Every plan includes every app. They differ in how much you can store and
        how many people you can invite.
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
              <Badge v-if="plan.current" theme="green" label="Current" variant="subtle" />
            </div>
            <p v-if="plan.description" class="mt-1 text-p-sm text-ink-gray-6">
              {{ plan.description }}
            </p>
          </div>
          <div class="shrink-0 text-right">
            <p class="text-base-medium tabular-nums text-ink-gray-8">
              {{ money(plan.price_monthly, plan.currency) }}
            </p>
            <p class="text-p-sm text-ink-gray-5">per month</p>
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
          :title="`Your workspace is past this plan's ${plan.blocked_by.join(' and ')} limit`"
        >
          <template #description>
            Free some space or remove people first, and this plan becomes
            available.
          </template>
        </Alert>

        <Button
          v-else-if="!plan.current"
          class="mt-3"
          label="Change to this plan"
          @click="changePlan"
        />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  PageHeader, PageHeaderTitle, Alert, Badge, Button, LoadingIndicator,
} from '@/ui'
import { usePlans, customer } from '../../lib/customer'

const props = defineProps({ workspace: { type: String, required: true } })
const workspace = computed(() => props.workspace)

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

const limits = (plan) => {
  const out = []
  if (plan.storage_gb) out.push(`${plan.storage_gb} GB files`)
  if (plan.database_gb) out.push(`${plan.database_gb} GB database`)
  if (plan.max_users) out.push(`${plan.max_users} ${plan.max_users === 1 ? 'seat' : 'seats'}`)
  if (plan.monthly_credit_grant) out.push(`${plan.monthly_credit_grant} credits a month`)
  return out
}

// Changing plan is a Stripe change, so it happens where the card lives rather
// than through a button here that would have to duplicate proration, tax and
// payment-method rules Stripe already owns.
const changePlan = async () => {
  const result = await customer.billingPortal(workspace.value)
  if (result?.url) window.location.href = result.url
}
</script>
