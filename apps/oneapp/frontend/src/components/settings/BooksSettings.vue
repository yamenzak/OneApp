<template>
  <SettingsHeader
    title="Books"
    description="Your company, its financial year, and the accounts everything is posted to. Answered once."
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <div v-if="loading" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <EmptyState
      v-else-if="!status?.available"
      class="!py-12"
      icon="lucide-book-open"
      title="No accounting app"
      description="This workspace is not entitled to Books, so there is nothing to set up."
    />

    <div v-else-if="status.ready" class="flex flex-col gap-4 pt-6">
      <!--
        Set up from what signup answered rather than by a person. Announced
        rather than left to be discovered: the country and currency are what
        they chose, but the chart of accounts and the financial year are
        defaults for that country, and only they know if those are right.
      -->
      <Alert
        v-if="status.assumed && status.can_reset"
        theme="amber"
        title="Set up from your signup answers"
      >
        <template #description>
          Your country and currency are what you chose. The chart of accounts
          and financial year below are the usual ones for {{ status.company?.country }} —
          check them before you invoice anything, because they are only easy to
          change until then.
        </template>
        <template #actions>
          <Button label="Start over" theme="red" :loading="resetting" @click="startOver" />
        </template>
      </Alert>

      <Alert v-else-if="status.assumed" theme="blue" title="Set up from your signup answers">
        <template #description>
          Entries have been posted, so the chart of accounts can no longer be
          replaced here. Ask support if it needs to change.
        </template>
      </Alert>

      <Alert v-else theme="green" title="Books are set up">
        <template #description>
          Changing a company's currency or chart of accounts after entries exist
          is a migration, not a setting, so this is shown rather than offered.
          Ask support if you need it changed.
        </template>
      </Alert>

      <div class="max-w-xl">
        <div
          v-for="row in summary"
          :key="row.label"
          class="flex items-baseline justify-between gap-4 border-b border-outline-gray-1 py-3"
        >
          <span class="text-p-sm text-ink-gray-6">{{ row.label }}</span>
          <span class="text-p-sm text-ink-gray-8">{{ row.value }}</span>
        </div>
      </div>
    </div>

    <div v-else class="flex max-w-xl flex-col gap-6 pt-6">
      <p class="text-p-base text-ink-gray-6">
        Nothing can be invoiced or paid until this exists. It is four answers,
        and it runs the same setup the accounting app would have asked for.
      </p>

      <div class="grid gap-4 sm:grid-cols-2">
        <FormControl v-model="form.company_name" label="Company name" />
        <FormControl
          v-model="form.abbr"
          label="Abbreviation"
          description="Appears on account names, e.g. Debtors - ACME."
        />
        <FormControl v-model="form.country" label="Country" />
        <FormControl v-model="form.currency" label="Currency" placeholder="USD" />
        <FormControl v-model="form.fy_start_date" type="date" label="Financial year starts" />
        <FormControl v-model="form.fy_end_date" type="date" label="Financial year ends" />
      </div>

      <FormControl
        v-model="form.chart_of_accounts"
        type="select"
        label="Chart of accounts"
        :options="chartOptions"
        description="A starting structure for your country. Accounts can be added later; the shape is hard to change once entries exist."
      />

      <ErrorMessage v-if="error" :message="error" />
    </div>
  </SettingsBody>

  <div v-if="status?.available && !status.ready" :class="PANEL_FOOTER">
    <Button
      variant="solid"
      label="Set up books"
      :loading="saving"
      :disabled="!complete"
      @click="create"
    />
    <span class="text-p-sm text-ink-gray-5">This takes a few seconds.</span>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  Alert, Button, ErrorMessage, FormControl, LoadingIndicator,
  SettingsHeader, SettingsBody,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import { PANEL_BODY, PANEL_FOOTER, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'

const status = ref(null)
const charts = ref([])
const loading = ref(true)
const saving = ref(false)
const resetting = ref(false)
const error = ref('')

const form = reactive({
  company_name: '',
  abbr: '',
  country: '',
  currency: '',
  chart_of_accounts: '',
  fy_start_date: '',
  fy_end_date: '',
})

const chartOptions = computed(() => charts.value.map((c) => ({ label: c, value: c })))

const complete = computed(() =>
  Boolean(
    form.company_name && form.abbr && form.country && form.currency &&
    form.chart_of_accounts && form.fy_start_date && form.fy_end_date,
  ),
)

const summary = computed(() => {
  const company = status.value?.company
  const fiscal = status.value?.fiscal_year
  if (!company) return []
  return [
    { label: 'Company', value: company.company_name },
    { label: 'Chart of accounts', value: status.value?.charts?.[0] || '—' },
    { label: 'Abbreviation', value: company.abbr },
    { label: 'Currency', value: company.default_currency },
    { label: 'Country', value: company.country },
    {
      label: 'Financial year',
      value: fiscal ? `${fiscal.year_start_date} to ${fiscal.year_end_date}` : '—',
    },
  ]
})

const load = async () => {
  loading.value = true
  try {
    status.value = await workspace.books()
    if (status.value?.available && !status.value.ready) {
      const defaults = status.value.defaults || {}
      // Prefilled from what signup already established. Asking again invites a
      // different answer, and a company whose country disagrees with the site's
      // is a support ticket about tax rules.
      form.company_name = defaults.company_name || ''
      form.abbr = (defaults.company_name || '').slice(0, 5).toUpperCase().replace(/[^A-Z]/g, '')
      form.country = defaults.country || ''
      form.currency = defaults.currency || ''
      form.fy_start_date = defaults.fy_start_date || ''
      form.fy_end_date = defaults.fy_end_date || ''
    }
  } finally {
    loading.value = false
  }
}

const loadCharts = async () => {
  if (!status.value?.available || status.value.ready || !form.country) return
  charts.value = (await workspace.charts(form.country)) || []
  if (!form.chart_of_accounts && charts.value.length) {
    form.chart_of_accounts = charts.value[0]
  }
}

onMounted(async () => {
  await load()
  await loadCharts()
})

watch(() => form.country, loadCharts)

async function startOver() {
  resetting.value = true
  error.value = ''
  try {
    status.value = await workspace.resetBooks()
    await load()
    await loadCharts()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    resetting.value = false
  }
}

async function create() {
  saving.value = true
  error.value = ''
  try {
    status.value = await workspace.setUpBooks({ ...form })
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}
</script>
