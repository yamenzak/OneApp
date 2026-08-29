<template>
  <CatalogueList
    title="Storage buckets"
    description="Buckets are capped and rotated. One bucket holding every tenant's files is a single credential and a single bad lifecycle rule away from losing everything — bounded buckets bound the worst case."
    doctype="Storage Bucket"
    :fields="['name', 'jurisdiction', 'status', 'tenant_count', 'max_tenants', 'bytes_used']"
    order-by="jurisdiction asc, creation asc"
    :columns="['minmax(0,1fr)', '7rem', '8rem', '9rem']"
    :headers="['Bucket', 'Jurisdiction', 'Tenants', 'Status']"
    :cells="cells"
    :form="FORM"
    empty-title="No buckets yet"
    empty-hint="The first one is created automatically when a tenant needs storage."
  />
</template>

<script setup>
import CatalogueList from './CatalogueList.vue'

// A bucket is created by the rotation when one is needed, so this is for
// changing how full one may get and for retiring one by hand — not for typing a
// bucket into existence, which would leave the credentials unset.
const FORM = [
  {
    name: 'max_tenants',
    label: 'Tenant cap',
    type: 'number',
    hint: 'Rotation opens the next bucket at this many. Bounded buckets bound the worst case.',
  },
  {
    name: 'status',
    label: 'Status',
    type: 'select',
    options: ['Active', 'Full', 'Provisioning', 'Retired'],
    hint: 'Retired stops new tenants being placed here. The files already in it stay.',
  },
]

const cells = (b) => [
  { value: b.name },
  { value: b.jurisdiction, muted: true },
  { value: `${b.tenant_count} of ${b.max_tenants || '∞'}` },
  {
    value: b.status,
    badge: true,
    theme: { Active: 'green', Full: 'amber', Provisioning: 'blue', Retired: 'gray' }[b.status] || 'gray',
  },
]
</script>
