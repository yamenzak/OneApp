<template>
  <CatalogueList
    title="Plans"
    description="Plans differ only in quotas — every feature is available on every plan, which is why no feature flags exist anywhere in the codebase."
    doctype="Plan"
    :fields="['name', 'plan_name', 'audience', 'price_monthly', 'storage_gb', 'database_gb', 'max_users', 'monthly_credit_grant', 'stripe_price_id_monthly']"
    order-by="sort_order asc"
    :columns="['minmax(0,1fr)', '7rem', '6rem', '9rem', '7rem', '8rem']"
    :headers="['Plan', 'Audience', 'Price', 'Storage / DB', 'Seats', 'Stripe']"
    :cells="cells"
    empty-title="No plans"
    empty-hint="Signup stays closed until at least one active plan has a Stripe price."
  />
</template>

<script setup>
import CatalogueList from './CatalogueList.vue'

const cells = (p) => [
  { value: p.plan_name },
  { value: p.audience, muted: true },
  { value: `$${p.price_monthly}/mo` },
  { value: `${p.storage_gb} GB / ${p.database_gb} GB`, muted: true },
  { value: String(p.max_users) },
  p.stripe_price_id_monthly
    ? { value: 'Linked', badge: true, theme: 'green' }
    : { value: 'No price', badge: true, theme: 'red' },
]
</script>
