<template>
  <SettingsForm
    title="Billing"
    description="Stripe owns the recurring schedule, dunning and card updates. The secret key lives in the payments app so there is one place to rotate it."
    doctype="OneApp Control Settings"
    :fields="FIELDS"
  />
</template>

<script setup>
import SettingsForm from './SettingsForm.vue'

const FIELDS = [
  {
    name: 'stripe_webhook_secret',
    label: 'Webhook signing secret',
    type: 'password',
    hint: 'Without it the endpoint rejects everything, so payments never grant credits or activate subscriptions.',
  },
  {
    name: 'ai_gateway',
    label: 'AI gateway name',
    hint: 'Cloudflare AI Gateway. Per-request logging is how AI spend is attributed per tenant.',
  },
  { name: 'cf_account_id', label: 'Cloudflare account ID' },
  { name: 'ai_gateway_token', label: 'Gateway token', type: 'password' },
  { name: 'google_ai_key', label: 'Google AI key', type: 'password' },
  { name: 'cf_api_token', label: 'Workers AI token', type: 'password' },
  {
    name: 'ai_markup_multiplier',
    label: 'AI markup',
    type: 'number',
    hint: 'Applied to measured provider cost when converting to credits.',
  },
]
</script>
