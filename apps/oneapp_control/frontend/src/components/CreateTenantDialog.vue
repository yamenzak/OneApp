<template>
  <!-- Title and size are props, and the body is the default slot. The
       `:options` object and `#body-content` are frappe-ui v0 spelling: both
       are silently ignored, so the dialog opened with no heading and an
       empty body. -->
  <Dialog v-model="open" title="New tenant" size="lg">
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

      <Alert theme="blue" title="This creates a real site">
        <template #description>
          Provisioning runs against Frappe Cloud and takes a few minutes. Progress
          shows under Provisioning.
        </template>
      </Alert>

      <ErrorMessage v-if="error" :message="error" />
    </div>
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
import { useDocList } from '../lib/resource'

const open = defineModel({ type: Boolean })
const emit = defineEmits(['created'])

const form = ref({ tenant_name: '', tenant_slug: '', owner_email: '', plan: '' })
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

// Fetched once and kept, rather than re-read on every open: the list is shared
// with the catalogue's own, so editing a plan in settings updates this too.
const plans = useDocList('Plan', {
  fields: ['name', 'plan_name'],
  filters: { is_active: 1 },
  orderBy: 'sort_order asc',
  silent: true,
})

const planOptions = computed(() =>
  (plans.data || []).map((p) => ({ label: p.plan_name, value: p.name })),
)

watch(open, (isOpen) => {
  if (isOpen) error.value = ''
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
