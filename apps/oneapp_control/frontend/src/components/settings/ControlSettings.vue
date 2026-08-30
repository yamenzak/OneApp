<template>
  <SettingsForm
    title="Frappe Cloud"
    description="Credentials for creating and managing tenant sites, and the address tenants call back on."
    doctype="OneSpace Control Settings"
    :fields="FIELDS"
  />
</template>

<script setup>
import SettingsForm from './SettingsForm.vue'

const FIELDS = [
  {
    name: 'press_api_url',
    label: 'API host',
    hint: 'cloud.frappe.io. frappecloud.com redirects here and the redirect drops the credential.',
  },
  { name: 'press_api_key', label: 'API key' },
  { name: 'press_api_secret', label: 'API secret', type: 'password' },
  {
    name: 'control_plane_url',
    label: 'Control plane URL',
    hint: 'Injected into every tenant site so it can reach us. A tenant provisioned without it is orphaned.',
  },
  { name: 'tenant_domain', label: 'Tenant domain', hint: 'Workspaces are addressed under this.' },
  {
    name: 'reserved_slugs',
    label: 'Reserved names',
    type: 'textarea',
    hint: 'Added to the built-in blocklist of infrastructure and phishing-adjacent names.',
  },
]
</script>
