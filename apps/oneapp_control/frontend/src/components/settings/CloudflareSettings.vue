<template>
  <SettingsForm
    title="Cloudflare"
    description="DNS, storage and mail routing. The DNS and KV tokens stay here and are never pushed to a bench — each can act across every tenant."
    doctype="OneApp Control Settings"
    :fields="FIELDS"
  />
</template>

<script setup>
import SettingsForm from './SettingsForm.vue'

const FIELDS = [
  { name: 'cf_zone_id', label: 'DNS zone ID', hint: 'Zone for the tenant domain.' },
  { name: 'cf_dns_token', label: 'DNS token', type: 'password', hint: 'Needs Zone.DNS: Edit.' },
  {
    name: 'cf_kv_namespace_id',
    label: 'KV namespace ID',
    hint: 'The map the inbound email worker reads to route a message to a tenant.',
  },
  { name: 'cf_kv_token', label: 'KV token', type: 'password', hint: 'Needs Workers KV Storage: Edit.' },
  { name: 'r2_account_id', label: 'R2 account ID' },
  {
    name: 'r2_admin_token',
    label: 'R2 admin token',
    type: 'password',
    hint: 'Creates buckets. Control plane only — the S3 keys below are what tenant sites use.',
  },
  { name: 'r2_access_key', label: 'R2 access key' },
  { name: 'r2_secret_key', label: 'R2 secret key', type: 'password' },
  { name: 'r2_public_base', label: 'CDN base URL', hint: 'Where public objects are served from.' },
  {
    name: 'bucket_max_tenants',
    label: 'Tenants per bucket',
    type: 'number',
    hint: 'Rotation threshold. Bounded buckets bound the blast radius of losing one.',
  },
  { name: 'cf_email_token', label: 'Email token', type: 'password', hint: 'Needs Email Sending: Edit.' },
  { name: 'mail_domain', label: 'Sending domain' },
  {
    name: 'mail_hourly_limit',
    label: 'Hourly send limit',
    type: 'number',
    hint: 'Per tenant. On a shared sending identity one tenant can degrade deliverability for all.',
  },
]
</script>
