<template>
  <Dialog v-model="open" :options="{ title: 'New tenant', size: 'lg' }">
    <template #body-content>
      <div v-focus class="flex flex-col gap-4">
        <FormControl
          v-model="form.tenant_name"
          label="Workspace name"
          placeholder="Acme Ltd"
        />

        <div>
          <FormControl
            v-model="form.tenant_slug"
            label="Subdomain"
            placeholder="acme"
            :description="slugPreview"
          />
          <ErrorMessage v-if="slugError" class="mt-1" :message="slugError" />
        </div>

        <FormControl
          v-model="form.owner_email"
          type="email"
          label="Owner email"
          placeholder="ops@acme.test"
        />

        <FormControl
          v-model="form.plan"
          type="select"
          label="Plan"
          :options="planOptions"
        />

        <Alert variant="info" title="This creates a real site">
          Provisioning runs against Frappe Cloud and takes a few minutes. Progress
          shows under Provisioning.
        </Alert>

        <ErrorMessage v-if="error" :message="error" />
      </div>
    </template>

    <template #actions>
      <Button
        variant="solid"
        label="Create and provision"
        :loading="submitting"
        :disabled="!valid"
        @click="submit"
      />
      <Button label="Cancel" @click="open = false" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Dialog, FormControl, Button, Alert, ErrorMessage, vFocus, debounce } from '@/ui'
import { api } from '../lib/api'
import { callMethod } from '../lib/resource'

const open = defineModel({ type: Boolean })
const emit = defineEmits(['created'])

const form = ref({ tenant_name: '', tenant_slug: '', owner_email: '', plan: '' })
const planOptions = ref([])
const slugError = ref('')
const error = ref('')
const submitting = ref(false)

const slugPreview = computed(() =>
  form.value.tenant_slug ? `${form.value.tenant_slug}.4dl.app` : 'Becomes the site hostname.',
)

const valid = computed(
  () =>
    form.value.tenant_name &&
    form.value.tenant_slug &&
    form.value.owner_email &&
    !slugError.value,
)

// Server-side check: the slug rules are a security boundary, not a formatting
// preference, so the client never decides on its own.
const checkSlug = debounce(async (slug) => {
  if (!slug) return (slugError.value = '')
  try {
    const { available } = await api.checkSlug(slug)
    slugError.value = available ? '' : 'That subdomain is reserved or already taken.'
  } catch {
    slugError.value = ''
  }
}, 400)

watch(() => form.value.tenant_slug, checkSlug)

watch(open, async (isOpen) => {
  if (!isOpen) return
  error.value = ''
  const plans = await callMethod('frappe.client.get_list', {
    doctype: 'Plan',
    fields: JSON.stringify(['name', 'plan_name']),
    filters: JSON.stringify({ is_active: 1 }),
    order_by: 'sort_order asc',
  }, { silent: true })
  planOptions.value = plans.map((p) => ({ label: p.plan_name, value: p.name }))
})

async function submit() {
  submitting.value = true
  error.value = ''
  try {
    await api.createTenant({ ...form.value, provision: true })
    emit('created')
    open.value = false
    form.value = { tenant_name: '', tenant_slug: '', owner_email: '', plan: '' }
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    submitting.value = false
  }
}
</script>
