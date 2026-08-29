<template>
  <CatalogueList
    title="Apps"
    description="The registry the launcher reads. Apps are seeded from the code that implements them, so their doctypes and roles are a manifest rather than a setting — what is editable here is whether an app is offered, and to whom."
    doctype="OneApp App"
    :fields="FIELDS"
    order-by="sort_order asc"
    :columns="['minmax(0,1fr)', '8rem', '9rem', '7rem']"
    :headers="['App', 'Module', 'Availability', 'Status']"
    :cells="cells"
    :form="FORM"
    empty-title="No apps registered"
    empty-hint="They are seeded on install. An empty list means the install hook did not run."
  />
</template>

<script setup>
import CatalogueList from './CatalogueList.vue'

const FIELDS = [
  'name', 'app_code', 'app_label', 'module', 'is_active', 'availability',
  'role_name', 'icon', 'sort_order', 'description',
]

// Not app_code, module, role_name or the doctype manifest: those describe code
// that exists or does not, and editing them here would describe an app that
// cannot be granted. Availability is the lever — General is every tenant,
// Restricted is only via an entitlement on the tenant's own page.
const FORM = [
  { name: 'app_label', label: 'Name', required: true },
  {
    name: 'availability',
    label: 'Availability',
    type: 'select',
    options: ['General', 'Restricted'],
    required: true,
    hint: 'General: every tenant. Restricted: only workspaces granted it individually.',
  },
  { name: 'sort_order', label: 'Sort order', type: 'number' },
  {
    name: 'is_active',
    label: 'Available',
    type: 'checkbox',
    default: 1,
    hint: 'Off hides the app from every launcher without revoking anything.',
  },
  { name: 'description', label: 'Description', type: 'textarea' },
]

const cells = (a) => [
  { value: a.app_label },
  { value: a.module, muted: true },
  {
    value: a.availability,
    badge: true,
    theme: a.availability === 'Restricted' ? 'amber' : 'gray',
  },
  a.is_active
    ? { value: 'Available', badge: true, theme: 'green' }
    : { value: 'Hidden', badge: true, theme: 'gray' },
]
</script>
