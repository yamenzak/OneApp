<template>
  <PageHeader>
    <Breadcrumbs
      :items="[
        { label: 'Tenants', route: { name: 'Tenants' } },
        { label: tenant?.tenant_name || name },
      ]"
    />

    <div class="flex items-center gap-2">
      <Button label="Sign in" icon-left="lucide-key-round" @click="showSupport = true" />
      <Button v-if="tenant?.status === 'Active'" label="Suspend" @click="act('suspend')" />
      <Button
        v-else-if="tenant?.status === 'Suspended'"
        variant="solid"
        label="Resume"
        @click="act('resume')"
      />
      <Button
        v-else-if="tenant?.status === 'Failed'"
        variant="solid"
        label="Retry provisioning"
        @click="act('provision')"
      />
    </div>
  </PageHeader>

  <div v-if="tenant" class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <Alert v-if="tenant.status === 'Failed'" theme="red" title="Provisioning failed" class="my-5">
      <template #description>
        {{ tenant.suspended_reason || 'See the provisioning job for the reason.' }}
      </template>
    </Alert>

    <!--
      Two views of one site. The control plane holds intent — the plan, the
      quotas, who owns it — and Frappe Cloud holds what is actually running. A
      disagreement between them is usually the bug an operator came to find, so
      they sit side by side rather than one being presented as the truth.
    -->
    <Tabs v-model="tab" class="mt-5">
      <TabList variant="underline">
        <TabTrigger value="record" label="Record" icon-left="lucide-file-text" />
        <TabTrigger value="site" label="Site" icon-left="lucide-server" />
        <TabTrigger value="domains" label="Domains" icon-left="lucide-globe" />
        <TabTrigger value="backups" label="Backups" icon-left="lucide-database" />
        <TabTrigger value="activity" label="Activity" icon-left="lucide-activity" />
      </TabList>

      <TabPanel value="record">
        <List :columns="fieldColumns.columns" divider="full" class="mt-4">
          <ListRows :items="rows" row-key="label" v-slot="{ item: row, value }">
            <ListRow :value="value" class="py-3">
              <ListCell>
                <span class="text-p-sm text-ink-gray-6">{{ row.label }}</span>
              </ListCell>
              <ListCell>
                <span class="truncate text-p-sm text-ink-gray-8">{{ row.value }}</span>
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
      </TabPanel>

      <TabPanel value="site">
        <PressPanel :state="site" empty="This tenant has no site yet." class="mt-4" @retry="site.reload()">
          <List :columns="fieldColumns.columns" divider="full">
            <ListRows :items="siteRows" row-key="label" v-slot="{ item: row, value }">
              <ListRow :value="value" class="py-3">
                <ListCell>
                  <span class="text-p-sm text-ink-gray-6">{{ row.label }}</span>
                </ListCell>
                <ListCell>
                  <Badge
                    v-if="row.mismatch"
                    theme="amber"
                    :label="`${row.value} — we hold ${row.ours}`"
                    variant="subtle"
                  />
                  <span v-else class="truncate text-p-sm text-ink-gray-8">{{ row.value }}</span>
                </ListCell>
              </ListRow>
            </ListRows>
          </List>
        </PressPanel>
      </TabPanel>

      <TabPanel value="domains">
        <PressPanel :state="domains" empty="No domains on this site yet." class="mt-4" @retry="domains.reload()">
          <List
            :columns="domainColumns.columns"
            :row-height="52"
            class="list-row-px-3"
            divider="full"
          >
            <ListHeader>
              <ListHeaderCell v-for="c in domainColumns.visible" :key="c.key">
                {{ c.header }}
              </ListHeaderCell>
            </ListHeader>
            <ListRows :items="domainRows" row-key="domain" v-slot="{ item: row, value }">
              <ListRow :value="value">
                <ListCell>
                  <span class="truncate text-base text-ink-gray-8">{{ row.domain }}</span>
                  <Badge v-if="row.primary" class="ml-2" theme="blue" label="Primary" variant="subtle" />
                </ListCell>
                <ListCell v-if="domainColumns.shows('certificate')">
                  <Badge
                    :theme="row.status === 'Active' ? 'green' : 'gray'"
                    :label="row.status || '—'"
                    variant="subtle"
                  />
                </ListCell>
                <ListCell class="justify-end">
                  <!-- The label goes on a phone, the action does not. `label` is
                       still the accessible name and the tooltip. -->
                  <Button
                    v-if="!row.primary"
                    variant="ghost"
                    :icon="domainColumns.shows('certificate') ? undefined : 'lucide-star'"
                    label="Make primary"
                    :loading="busy === row.domain"
                    @click="makePrimary(row.domain)"
                  />
                  <Button
                    v-if="!row.primary"
                    variant="ghost"
                    icon="lucide-trash-2"
                    :label="`Remove ${row.domain}`"
                    :loading="busy === row.domain"
                    @click="dropDomain(row.domain)"
                  />
                </ListCell>
              </ListRow>
            </ListRows>
          </List>
        </PressPanel>
      </TabPanel>

      <TabPanel value="backups">
        <div class="mt-4 flex items-center justify-between gap-4">
          <p class="text-p-sm text-ink-gray-6">
            Frappe Cloud runs the schedule; this is a window onto it. Take one
            before anything irreversible.
          </p>
          <Button class="shrink-0" label="Back up now" :loading="backingUp" @click="backup" />
        </div>

        <PressPanel :state="backups" empty="No backups yet." class="mt-3" @retry="backups.reload()">
          <List
            :columns="backupColumns.columns"
            :row-height="52"
            class="list-row-px-3"
            divider="full"
          >
            <ListHeader>
              <ListHeaderCell v-for="c in backupColumns.visible" :key="c.key">
                {{ c.header }}
              </ListHeaderCell>
            </ListHeader>
            <ListRows :items="backupRows" row-key="name" v-slot="{ item: row, value }">
              <ListRow :value="value">
                <ListCell>
                  <span class="truncate text-base text-ink-gray-8">{{ when(row.created_on) }}</span>
                  <!-- Size is a column where there is room and a suffix where
                       there is not, rather than something a phone never sees. -->
                  <span
                    v-if="!backupColumns.shows('size')"
                    class="ml-2 shrink-0 text-p-sm tabular-nums text-ink-gray-5"
                  >
                    {{ size(row) }}
                  </span>
                  <Badge v-if="row.with_files" class="ml-2" theme="gray" label="With files" variant="subtle" />
                </ListCell>
                <ListCell v-if="backupColumns.shows('size')">
                  <span class="text-p-sm tabular-nums text-ink-gray-6">{{ size(row) }}</span>
                </ListCell>
                <ListCell>
                  <Badge :theme="stateTheme(row.status)" :label="row.status || '—'" variant="subtle" />
                </ListCell>
                <ListCell class="justify-end">
                  <!-- Only an offsite copy has a link: a local backup lives on
                       the server and press has nothing to hand out. -->
                  <Button
                    v-if="row.offsite"
                    variant="ghost"
                    :icon="backupColumns.shows('size') ? undefined : 'lucide-download'"
                    label="Download"
                    :loading="busy === row.name"
                    @click="download(row)"
                  />
                </ListCell>
              </ListRow>
            </ListRows>
          </List>
        </PressPanel>
      </TabPanel>

      <TabPanel value="activity">
        <PressPanel
          :state="jobs"
          empty="Frappe Cloud has done nothing to this site yet."
          class="mt-4"
          @retry="jobs.reload()"
        >
          <List
            :columns="jobColumns.columns"
            :row-height="52"
            class="list-row-px-3"
            divider="full"
          >
            <ListHeader>
              <ListHeaderCell v-for="c in jobColumns.visible" :key="c.key">
                {{ c.header }}
              </ListHeaderCell>
            </ListHeader>
            <ListRows :items="jobRows" row-key="name" v-slot="{ item: row, value }">
              <ListRow :value="value">
                <ListCell>
                  <div class="min-w-0">
                    <p class="truncate text-base text-ink-gray-8">{{ row.job_type }}</p>
                    <p v-if="!jobColumns.shows('when')" class="truncate text-xs text-ink-gray-5">
                      {{ when(row.creation) }}
                    </p>
                  </div>
                </ListCell>
                <ListCell>
                  <Badge :theme="stateTheme(row.status)" :label="row.status || '—'" variant="subtle" />
                </ListCell>
                <ListCell v-if="jobColumns.shows('when')">
                  <span class="text-p-sm text-ink-gray-6">{{ when(row.creation) }}</span>
                </ListCell>
              </ListRow>
            </ListRows>
          </List>
        </PressPanel>

        <section v-if="logins.length" class="mt-8">
          <h3 class="mb-1 text-base-medium text-ink-gray-8">Support sign-ins</h3>
          <p class="mb-3 text-p-sm text-ink-gray-5">
            Every time one of us entered this workspace, and why.
          </p>
          <List
            :columns="loginColumns.columns"
            :row-height="48"
            class="list-row-px-3"
            divider="full"
          >
            <ListRows :items="logins" row-key="logged_in_on" v-slot="{ item: row, value }">
              <ListRow :value="value">
                <ListCell>
                  <div class="min-w-0">
                    <span class="truncate text-p-sm text-ink-gray-8">{{ row.operator }}</span>
                    <!-- Why they signed in is the point of the record, so on a
                         phone it moves under the name rather than disappearing. -->
                    <p v-if="!loginColumns.shows('reason')" class="truncate text-xs text-ink-gray-5">
                      {{ row.reason }}
                    </p>
                  </div>
                  <!-- An attempt that never got in stays on the record; it just
                       does not read as an entry. -->
                  <Badge
                    v-if="!row.succeeded"
                    class="ml-2"
                    theme="gray"
                    label="Did not sign in"
                    variant="subtle"
                  />
                </ListCell>
                <ListCell v-if="loginColumns.shows('reason')">
                  <span class="truncate text-p-sm text-ink-gray-6">{{ row.reason }}</span>
                </ListCell>
                <ListCell>
                  <span class="text-p-sm text-ink-gray-5">{{ when(row.logged_in_on) }}</span>
                </ListCell>
              </ListRow>
            </ListRows>
          </List>
        </section>
      </TabPanel>
    </Tabs>
  </div>

  <Dialog v-model="showSupport" title="Sign in to this workspace" size="lg">
    <div v-focus class="flex flex-col gap-4">
      <Alert theme="amber" title="This is someone else's data">
        <template #description>
          You will be signed in as an administrator of
          {{ tenant?.tenant_name || name }}. The reason below is recorded against
          your name and shown on this page.
        </template>
      </Alert>
      <FormControl
        v-model="reason"
        type="textarea"
        label="Why"
        placeholder="Investigating ticket #482 — invoices not sending"
      />
      <ErrorMessage v-if="supportError" :message="supportError" />
    </div>
    <template #actions>
      <Button
        variant="solid"
        label="Sign in"
        :loading="signingIn"
        :disabled="!reason.trim()"
        @click="signIn"
      />
      <Button label="Cancel" @click="showSupport = false" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  PageHeader, Breadcrumbs, Button, Alert, Badge, Dialog, ErrorMessage, FormControl,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell,
  Tabs, TabList, TabTrigger, TabPanel, dayjsLocal, vFocus,
} from '@/ui'
import PressPanel from '../components/PressPanel.vue'
import { api, useDocument } from '../lib/api'
import { useListColumns } from '../lib/list'
import { usePress } from '../lib/press'

// Fixed tracks sized for a desktop leave a phone about 20px for the column the
// row exists to name. Each list below says which columns a phone can spare;
// what they drop reappears beside or under the identity cell, so nothing a
// desktop shows is simply gone.
// A label/value list: the label track is fixed so the values line up, and a
// desktop-width label column leaves a phone about 130px for the value.
const fieldColumns = useListColumns([
  { key: 'label', header: '', track: '12rem', mobile: '8rem' },
  { key: 'value', header: '', track: 'minmax(0,1fr)' },
])

const domainColumns = useListColumns([
  { key: 'domain', header: 'Domain', track: 'minmax(0,1fr)' },
  { key: 'certificate', header: 'Certificate', track: '7rem', mobile: false },
  { key: 'actions', header: '', track: '11rem', mobile: '5rem' },
])

const backupColumns = useListColumns([
  { key: 'taken', header: 'Taken', track: 'minmax(0,1fr)' },
  { key: 'size', header: 'Size', track: '7rem', mobile: false },
  { key: 'state', header: 'State', track: '6rem', mobile: '5.5rem' },
  { key: 'download', header: '', track: '7rem', mobile: '2.5rem' },
])

const jobColumns = useListColumns([
  { key: 'job', header: 'Job', track: 'minmax(0,1fr)' },
  { key: 'state', header: 'State', track: '8rem', mobile: '6rem' },
  { key: 'when', header: 'When', track: '11rem', mobile: false },
])

const loginColumns = useListColumns([
  { key: 'operator', header: 'Operator', track: '14rem', mobile: 'minmax(0,1fr)' },
  { key: 'reason', header: 'Reason', track: 'minmax(0,1fr)', mobile: false },
  { key: 'when', header: 'When', track: '11rem', mobile: '6rem' },
])

const props = defineProps({ name: { type: String, required: true } })

// Live: a status change from the provisioning worker lands here on its own.
const resource = useDocument('Tenant', () => props.name)
// useDoc exposes the document as `doc`, and shares it with any list that
// fetched the same record — a status change from either lands on both.
const tenant = computed(() => resource.doc)

const tab = ref('record')

// Each press read is its own panel, fetched when its tab is first opened rather
// than all at once: five calls to Frappe Cloud on page load would make the page
// as slow as the slowest of them, to show four things nobody looked at.
const site = usePress(() => api.siteState(props.name), tab, 'site')
const domains = usePress(() => api.siteDomains(props.name), tab, 'domains')
const backups = usePress(() => api.siteBackups(props.name), tab, 'backups')
const jobs = usePress(() => api.siteJobs(props.name), tab, 'activity')

const domainRows = computed(() => domains.data?.domains || [])
const backupRows = computed(() => backups.data?.backups || [])
const jobRows = computed(() => jobs.data?.jobs || [])

const logins = ref([])
watch(tab, async (value) => {
  if (value === 'activity') logins.value = (await api.supportLogins(props.name)) || []
})

const when = (value) => (value ? dayjsLocal(value).format('D MMM YYYY, HH:mm') : '—')

const stateTheme = (status) =>
  ({ Success: 'green', Failure: 'red', Pending: 'blue', Running: 'blue' })[status] || 'gray'

const size = (row) => {
  const bytes = (row.database_size || 0) + (row.private_size || 0) + (row.public_size || 0)
  if (!bytes) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

const rows = computed(() => {
  const t = tenant.value
  if (!t) return []
  return [
    { label: 'Status', value: t.status },
    { label: 'Site', value: t.site_name || '—' },
    { label: 'Custom domain', value: t.primary_domain || '—' },
    { label: 'Plan', value: t.plan || '—' },
    { label: 'Shard', value: t.shard || '—' },
    { label: 'Owner', value: t.owner_email },
    { label: 'Users', value: `${t.user_count || 0} of ${t.max_users || '—'}` },
  ]
})

// Where the two views disagree is the interesting part, so it is marked rather
// than left for someone to spot by reading both columns.
const siteRows = computed(() => {
  const s = site.data
  if (!s?.site) return []
  const ours = s.control_plane || {}
  const differs = (theirs, mine) => Boolean(theirs && mine && theirs !== mine)
  return [
    { label: 'Site', value: s.site },
    {
      label: 'Status',
      value: s.status || '—',
      ours: ours.status,
      mismatch: differs(s.status, ours.status),
    },
    { label: 'Bench group', value: s.bench || '—' },
    { label: 'Server', value: s.server || '—' },
    { label: 'Region', value: s.region || '—' },
    {
      label: 'Frappe version',
      value: s.version || '—',
      ours: s.latest_version,
      // Not a fault, but worth seeing: a site behind the newest version is the
      // usual answer to "why does this one behave differently?".
      mismatch: differs(s.version, s.latest_version),
    },
    {
      label: 'Primary host',
      value: s.host_name || '—',
      ours: ours.primary_domain,
      mismatch: differs(s.host_name, ours.primary_domain),
    },
    { label: 'Setup wizard', value: s.setup_wizard_complete ? 'Complete' : 'Not finished' },
    { label: 'Created', value: when(s.created_on) },
    { label: 'Last deployed', value: when(s.last_deployed) },
  ]
})

const busy = ref('')
const backingUp = ref(false)
const showSupport = ref(false)
const signingIn = ref(false)
const reason = ref('')
const supportError = ref('')

watch(showSupport, (open) => {
  if (!open) return
  reason.value = ''
  supportError.value = ''
})

async function act(kind) {
  if (kind === 'suspend') await api.suspend(props.name, 'Suspended by operator')
  if (kind === 'resume') await api.resume(props.name)
  if (kind === 'provision') await api.provision(props.name)
  resource.reload()
}

async function backup() {
  backingUp.value = true
  try {
    await api.takeBackup(props.name)
    backups.reload()
  } finally {
    backingUp.value = false
  }
}

async function download(row) {
  busy.value = row.name
  try {
    const result = await api.backupDownload(props.name, row.name, 'database')
    if (result?.url) window.open(result.url, '_blank', 'noopener')
  } finally {
    busy.value = ''
  }
}

async function makePrimary(domain) {
  busy.value = domain
  try {
    await api.setPrimaryDomain(props.name, domain)
    domains.reload()
    resource.reload()
  } finally {
    busy.value = ''
  }
}

async function dropDomain(domain) {
  busy.value = domain
  try {
    await api.removeSiteDomain(props.name, domain)
    domains.reload()
  } finally {
    busy.value = ''
  }
}

async function signIn() {
  signingIn.value = true
  supportError.value = ''
  try {
    const result = await api.supportLogin(props.name, reason.value)
    showSupport.value = false
    // A new tab rather than a redirect: the operator is mid-investigation here,
    // and losing this page to go and look is its own small tax.
    if (result?.url) window.open(result.url, '_blank', 'noopener')
  } catch (e) {
    supportError.value = e.message || String(e)
  } finally {
    signingIn.value = false
  }
}
</script>
