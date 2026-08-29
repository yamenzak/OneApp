<template>
  <CatalogueList
    title="Plans"
    description="Plans differ only in quotas — every feature is available on every plan, which is why no feature flags exist anywhere in the codebase. Saving a plan creates its Stripe product and prices; changing a price mints a new one and leaves existing subscriptions on the old."
    doctype="Plan"
    :fields="FIELDS"
    order-by="sort_order asc"
    :columns="['minmax(0,1fr)', '7rem', '6rem', '9rem', '7rem', '8rem']"
    :headers="['Plan', 'Audience', 'Price', 'Storage / DB', 'Seats', 'Stripe']"
    :cells="cells"
    :form="FORM"
    empty-title="No plans"
    empty-hint="Signup stays closed until at least one active plan has a Stripe price."
  />
</template>

<script setup>
import CatalogueList from './CatalogueList.vue'

const FIELDS = [
  'name', 'plan_code', 'plan_name', 'audience', 'is_active', 'sort_order',
  'currency', 'price_monthly', 'price_yearly',
  'storage_gb', 'database_gb', 'max_users', 'monthly_credit_grant',
  'background_workers', 'press_site_plan', 'description',
  'stripe_price_id_monthly', 'sync_error',
]

// Editable here because the desk is not part of this product: without a form,
// a control plane could show its price sheet and never write one.
//
// The Stripe ids are deliberately absent — they are minted by saving, and a
// field an operator can type into is the dual entry this replaced.
const FORM = [
  {
    name: 'plan_code',
    label: 'Code',
    required: true,
    createOnly: true,
    hint: 'Stable id, e.g. personal-starter. The plan is named after it, so it cannot change later.',
  },
  { name: 'plan_name', label: 'Name', required: true },
  {
    name: 'audience',
    label: 'Audience',
    type: 'select',
    options: ['Personal', 'Commercial'],
    required: true,
  },
  { name: 'currency', label: 'Currency', default: 'USD', required: true },
  {
    name: 'price_monthly',
    label: 'Monthly price',
    type: 'number',
    hint: 'Changing this mints a new Stripe price. Everyone already subscribed keeps paying the old one.',
  },
  { name: 'price_yearly', label: 'Yearly price', type: 'number', hint: 'Leave at 0 for a monthly-only plan.' },
  { name: 'storage_gb', label: 'File storage (GB)', type: 'number' },
  { name: 'database_gb', label: 'Database (GB)', type: 'number' },
  { name: 'max_users', label: 'Seats', type: 'number' },
  { name: 'monthly_credit_grant', label: 'Monthly credits', type: 'number', hint: 'Non-rollover. Expires at the end of each billing period.' },
  { name: 'background_workers', label: 'Background workers', type: 'number' },
  { name: 'press_site_plan', label: 'Frappe Cloud site plan', hint: 'Overrides the shard default when set.' },
  { name: 'sort_order', label: 'Sort order', type: 'number' },
  {
    name: 'is_active',
    label: 'Offered to new customers',
    type: 'checkbox',
    default: 1,
    hint: 'Turning this off retires the plan. Nobody loses it — existing workspaces keep the plan, the price and the limits they bought.',
  },
  { name: 'description', label: 'Description', type: 'textarea' },
]

// One column for the whole Stripe story, because there are only three states
// worth distinguishing: it failed, it is not sellable yet, or it is linked.
const stripeCell = (p) => {
  if (p.sync_error) return { value: 'Sync failed', badge: true, theme: 'red' }
  if (!p.stripe_price_id_monthly) return { value: 'No price', badge: true, theme: 'amber' }
  return { value: 'Linked', badge: true, theme: 'green' }
}

const cells = (p) => [
  { value: p.plan_name },
  { value: p.is_active ? p.audience : `${p.audience} · retired`, muted: true },
  { value: `$${p.price_monthly}/mo` },
  { value: `${p.storage_gb} GB / ${p.database_gb} GB`, muted: true },
  { value: String(p.max_users) },
  stripeCell(p),
]
</script>
