<template>
  <!--
    One tenant, seen from both sides.

    A component screen because almost none of it is stored here: the control
    plane holds intent — the plan, the quotas, who owns it — and Frappe Cloud
    holds what is actually running. The generic screen over the Tenant doctype
    shows the first; this is where the second lives, and where a disagreement
    between them is marked rather than left for somebody to spot by reading two
    columns.

    Which tenant is in the query, so this is a link an operator can send. The
    Tenants screen declares a record action that opens it — see
    `entitlements/actions.py`.
  -->
  <div v-if="!name" class="mx-auto w-full max-w-[940px] px-3 py-8 sm:px-5">
    <EmptyState
      icon="lucide-users"
      title="No workspace chosen"
      description="Open one from the Tenants screen, or name it in the address."
    />
  </div>

  <div v-else-if="!tenant" class="grid place-items-center py-16">
    <LoadingIndicator class="size-5 text-ink-gray-5" />
  </div>

  <template v-else>
  <div class="mx-auto flex w-full max-w-[940px] flex-wrap items-center gap-2 px-3 pt-5 sm:px-5">
    <div class="min-w-0 flex-1">
      <h2 class="truncate text-lg-semibold text-ink-gray-9">
        {{ tenant?.tenant_name || name }}
      </h2>
      <p class="truncate text-p-sm text-ink-gray-5">{{ tenant?.site_name || 'No site yet' }}</p>
    </div>

    <div class="flex shrink-0 items-center gap-2">
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
  </div>

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <Alert v-if="tenant.status === 'Failed'" theme="red" title="Provisioning failed" class="my-5">
      <template #description>
        {{ tenant.suspended_reason || 'See the provisioning job for the reason.' }}
      </template>
    </Alert>

    <!--
      Two screens of one site. The control plane holds intent — the plan, the
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
        <TabTrigger value="apps" label="Apps" icon-left="lucide-layout-grid" />
        <TabTrigger value="billing" label="Billing" icon-left="lucide-credit-card" />
        <TabTrigger value="activity" label="Activity" icon-left="lucide-activity" />
      </TabList>

      <TabPanel value="record">
        <List :columns="fieldTracks" divider="full" class="mt-4">
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
          <List :columns="fieldTracks" divider="full">
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
            :columns="domainTracks"
            :row-height="52"
            class="list-row-px-3"
            divider="full"
          >
            <ListHeader>
              <ListHeaderCell v-for="c in domainCols" :key="c.key">
                {{ c.header }}
              </ListHeaderCell>
            </ListHeader>
            <ListRows :items="domainRows" row-key="domain" v-slot="{ item: row, value }">
              <ListRow :value="value">
                <ListCell>
                  <span class="truncate text-base text-ink-gray-8">{{ row.domain }}</span>
                  <Badge v-if="row.primary" class="ml-2" theme="blue" label="Primary" variant="subtle" />
                </ListCell>
                <ListCell v-if="domainShows('certificate')">
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
                    :icon="domainShows('certificate') ? undefined : 'lucide-star'"
                    label="Make primary"
                    :loading="busy === row.domain"
                    @click="makePrimary(row.domain)"
                  />
                  <Button
                    v-if="!row.primary"
                    variant="ghost"
                    icon="lucide-trash-2"
                    :label="`Remove ${row.domain}`"
                    :tooltip="`Remove ${row.domain}`"
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
            :columns="backupTracks"
            :row-height="52"
            class="list-row-px-3"
            divider="full"
          >
            <ListHeader>
              <ListHeaderCell v-for="c in backupCols" :key="c.key">
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
                    v-if="!backupShows('size')"
                    class="ml-2 shrink-0 text-p-sm tabular-nums text-ink-gray-5"
                  >
                    {{ size(row) }}
                  </span>
                  <Badge v-if="row.with_files" class="ml-2" theme="gray" label="With files" variant="subtle" />
                </ListCell>
                <ListCell v-if="backupShows('size')">
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
                    :icon="backupShows('size') ? undefined : 'lucide-download'"
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

      <!-- Both panels fetch on mount, so they are rendered only once their tab
           is chosen — a tenant page should not make five press and billing
           calls to show a record. -->
      <TabPanel value="apps" class="pt-4">
        <TenantSpaces v-if="tab === 'apps'" :tenant="name" />
      </TabPanel>

      <TabPanel value="billing" class="pt-4">
        <TenantBilling v-if="tab === 'billing'" :tenant="name" />
      </TabPanel>

      <TabPanel value="activity">
        <PressPanel
          :state="jobs"
          empty="Frappe Cloud has done nothing to this site yet."
          class="mt-4"
          @retry="jobs.reload()"
        >
          <List
            :columns="jobTracks"
            :row-height="52"
            class="list-row-px-3"
            divider="full"
          >
            <ListHeader>
              <ListHeaderCell v-for="c in jobCols" :key="c.key">
                {{ c.header }}
              </ListHeaderCell>
            </ListHeader>
            <ListRows :items="jobRows" row-key="name" v-slot="{ item: row, value }">
              <ListRow :value="value">
                <ListCell>
                  <div class="min-w-0">
                    <p class="truncate text-base text-ink-gray-8">{{ row.job_type }}</p>
                    <p v-if="!jobShows('when')" class="truncate text-xs text-ink-gray-5">
                      {{ when(row.creation) }}
                    </p>
                  </div>
                </ListCell>
                <ListCell>
                  <Badge :theme="stateTheme(row.status)" :label="row.status || '—'" variant="subtle" />
                </ListCell>
                <ListCell v-if="jobShows('when')">
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
            :columns="loginTracks"
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
                    <p v-if="!loginShows('reason')" class="truncate text-xs text-ink-gray-5">
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
                <ListCell v-if="loginShows('reason')">
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
  </template>

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
import { useRoute } from 'vue-router'
import {
  Button, Alert, Badge, Dialog, ErrorMessage, FormControl, LoadingIndicator,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell,
  Tabs, TabList, TabTrigger, TabPanel, dayjsLocal, vFocus,
} from '@/ui'
import EmptyState from '../../components/EmptyState.vue'
import PressPanel from './PressPanel.vue'
import TenantSpaces from './TenantSpaces.vue'
import TenantBilling from './TenantBilling.vue'
import { useDocument } from '../../lib/resource'
import { useListColumns } from '../../lib/list'
import { admin } from './admin'
import { usePress } from './press'

// Fixed tracks sized for a desktop leave a phone about 20px for the column the
// row exists to name. Each list below says which columns a phone can spare;
// what they drop reappears beside or under the identity cell, so nothing a
// desktop shows is simply gone.
// A label/value list: the label track is fixed so the values line up, and a
// desktop-width label column leaves a phone about 130px for the value.
const { visible: fieldCols, columns: fieldTracks, shows: fieldShows } =
  useListColumns([
  { key: 'label', header: '', track: '12rem', mobile: '8rem' },
  { key: 'value', header: '', track: 'minmax(0,1fr)' },
])

const { visible: domainCols, columns: domainTracks, shows: domainShows } =
  useListColumns([
  { key: 'domain', header: 'Domain', track: 'minmax(0,1fr)' },
  { key: 'certificate', header: 'Certificate', track: '7rem', mobile: false },
  { key: 'actions', header: '', track: '11rem', mobile: '5rem' },
])

const { visible: backupCols, columns: backupTracks, shows: backupShows } =
  useListColumns([
  { key: 'taken', header: 'Taken', track: 'minmax(0,1fr)' },
  { key: 'size', header: 'Size', track: '7rem', mobile: false },
  { key: 'state', header: 'State', track: '6rem', mobile: '5.5rem' },
  { key: 'download', header: '', track: '7rem', mobile: '2.5rem' },
])

const { visible: jobCols, columns: jobTracks, shows: jobShows } =
  useListColumns([
  { key: 'job', header: 'Job', track: 'minmax(0,1fr)' },
  { key: 'state', header: 'State', track: '8rem', mobile: '6rem' },
  { key: 'when', header: 'When', track: '11rem', mobile: false },
])

const { visible: loginCols, columns: loginTracks, shows: loginShows } =
  useListColumns([
  { key: 'operator', header: 'Operator', track: '14rem', mobile: 'minmax(0,1fr)' },
  { key: 'reason', header: 'Reason', track: 'minmax(0,1fr)', mobile: false },
  { key: 'when', header: 'When', track: '11rem', mobile: '6rem' },
])

defineProps({
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

// Which workspace, from the address. A screen action on the Tenants list puts
// it there, and so does a link somebody pastes to a colleague.
const route = useRoute()
const name = computed(() => String(route.query.record || ''))

// Live: a status change from the provisioning worker lands here on its own.
const resource = useDocument('Tenant', () => name.value)
// useDoc exposes the document as `doc`, and shares it with any list that
// fetched the same record — a status change from either lands on both.
const tenant = computed(() => resource.doc)

const tab = ref('record')

// Each press read is its own panel, fetched when its tab is first opened rather
// than all at once: five calls to Frappe Cloud on page load would make the page
// as slow as the slowest of them, to show four things nobody looked at.
const site = usePress(() => admin.siteState(name.value), tab, 'site')
const domains = usePress(() => admin.siteDomains(name.value), tab, 'domains')
const backups = usePress(() => admin.siteBackups(name.value), tab, 'backups')
const jobs = usePress(() => admin.siteJobs(name.value), tab, 'activity')

const domainRows = computed(() => domains.data?.domains || [])
const backupRows = computed(() => backups.data?.backups || [])
const jobRows = computed(() => jobs.data?.jobs || [])

const logins = ref([])
watch(tab, async (value) => {
  if (value === 'activity') logins.value = (await admin.supportLogins(name.value)) || []
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

// Where the two screens disagree is the interesting part, so it is marked rather
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
  if (kind === 'suspend') await admin.suspend(name.value, 'Suspended by operator')
  if (kind === 'resume') await admin.resume(name.value)
  if (kind === 'provision') await admin.provision(name.value)
  resource.reload()
}

async function backup() {
  backingUp.value = true
  try {
    await admin.takeBackup(name.value)
    backups.reload()
  } finally {
    backingUp.value = false
  }
}

async function download(row) {
  busy.value = row.name
  try {
    const result = await admin.backupDownload(name.value, row.name, 'database')
    if (result?.url) window.open(result.url, '_blank', 'noopener')
  } finally {
    busy.value = ''
  }
}

async function makePrimary(domain) {
  busy.value = domain
  try {
    await admin.setPrimaryDomain(name.value, domain)
    domains.reload()
    resource.reload()
  } finally {
    busy.value = ''
  }
}

async function dropDomain(domain) {
  busy.value = domain
  try {
    await admin.removeSiteDomain(name.value, domain)
    domains.reload()
  } finally {
    busy.value = ''
  }
}

async function signIn() {
  signingIn.value = true
  supportError.value = ''
  try {
    const result = await admin.supportLogin(name.value, reason.value)
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
