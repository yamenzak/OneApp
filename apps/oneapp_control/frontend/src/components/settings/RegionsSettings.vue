<template>
  <CatalogueList
    title="Regions"
    description="What customers choose at signup. Only regions with a shard that has headroom are offered, so a choice cannot fail after payment."
    doctype="Region"
    :fields="['name', 'region_name', 'country', 'is_active', 'description']"
    order-by="sort_order asc"
    :columns="['minmax(0,1fr)', '10rem', '7rem']"
    :headers="['Region', 'Country', 'Status']"
    :cells="cells"
    empty-title="No regions"
    empty-hint="Add a region and point a shard at it before opening signup."
  />
</template>

<script setup>
import CatalogueList from './CatalogueList.vue'

const cells = (r) => [
  { value: r.region_name },
  { value: r.country || '—', muted: true },
  r.is_active
    ? { value: 'Active', badge: true, theme: 'green' }
    : { value: 'Hidden', badge: true, theme: 'gray' },
]
</script>
