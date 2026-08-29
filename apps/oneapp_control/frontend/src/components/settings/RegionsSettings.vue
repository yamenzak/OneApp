<template>
  <CatalogueList
    title="Regions"
    description="What customers choose at signup. Only regions with a shard that has headroom are offered, so a choice cannot fail after payment."
    doctype="Region"
    :fields="['name', 'region_name', 'country', 'sort_order', 'is_active', 'description']"
    order-by="sort_order asc"
    :columns="['minmax(0,1fr)', '10rem', '7rem']"
    :headers="['Region', 'Country', 'Status']"
    :cells="cells"
    :form="FORM"
    empty-title="No regions"
    empty-hint="Add a region and point a shard at it before opening signup."
  />
</template>

<script setup>
import CatalogueList from './CatalogueList.vue'

// Editable here because the desk is not part of this product: a control plane
// that can show its regions and never add one cannot open a second country.
const FORM = [
  {
    name: 'region_name',
    label: 'Name',
    required: true,
    hint: 'What a customer sees at signup, e.g. Germany.',
  },
  { name: 'country', label: 'Country' },
  { name: 'sort_order', label: 'Sort order', type: 'number' },
  {
    name: 'is_active',
    label: 'Offered at signup',
    type: 'checkbox',
    default: 1,
    hint: 'A region is only actually offered once a shard in it has headroom, so this hides it rather than enabling it.',
  },
  { name: 'description', label: 'Description', type: 'textarea' },
]

const cells = (r) => [
  { value: r.region_name },
  { value: r.country || '—', muted: true },
  r.is_active
    ? { value: 'Active', badge: true, theme: 'green' }
    : { value: 'Hidden', badge: true, theme: 'gray' },
]
</script>
