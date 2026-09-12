<template>
  <div>
    <!--
      Four things from four places, on one screen, because the question this
      answers is always the same: why is this workspace in the state it is in,
      and what happens to it next. Answering that from the doctype form meant
      reading eight date fields and knowing which window applied to which.
    -->
    <div class="flex flex-wrap items-start justify-between gap-3">
      <div class="min-w-0">
        <p class="text-base-medium text-ink-primary">{{ headline }}</p>
        <p class="mt-0.5 text-p-sm text-ink-muted">{{ detail }}</p>
      </div>

      <div class="flex shrink-0 flex-wrap gap-2">
        <Button
          :label="held ? __('Release') : __('Hold')"
          :icon-left="held ? 'unlock' : 'lock'"
          :loading="busy === 'hold'"
          @click="toggleHold"
        />
        <Button
          :label="__('Take a cold copy')"
          icon-left="package"
          :loading="busy === 'cold'"
          @click="run('cold', () => admin.takeColdCopy(tenant))"
        />
        <Button
          v-if="canRestore"
          :label="__('Restore')"
          theme="blue"
          variant="solid"
          icon-left="rotate-ccw"
          :loading="busy === 'restore'"
          @click="run('restore', () => admin.restoreFromCold(tenant))"
        />
        <Button
          :label="__('Apply now')"
          icon-left="play"
          :loading="busy === 'run'"
          @click="run('run', () => admin.runLifecycle(tenant))"
        />
      </div>
    </div>

    <Alert v-if="held" theme="amber" :title="__('Held out of the lifecycle')" class="mt-4">
      <template #description>
        {{ __('Nothing is suspended, archived or deleted while this is set. The clock keeps running underneath.') }}
      </template>
    </Alert>

    <Alert v-if="backup.error" theme="red" :title="__('The last backup did not finish')" class="mt-4">
      <template #description>{{ backup.error }}</template>
    </Alert>

    <div v-if="loading && !data" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-muted" />
    </div>

    <template v-else-if="data">
      <List :columns="fieldTracks" divider="full" class="mt-4">
        <ListRows :items="rows" row-key="label" v-slot="{ item: row, value }">
          <ListRow :value="value" class="py-3">
            <ListCell>
              <span class="text-p-sm text-ink-secondary">{{ row.label }}</span>
            </ListCell>
            <ListCell>
              <Badge v-if="row.badge" :theme="row.badge" :label="row.value" variant="subtle" />
              <span v-else class="truncate text-sm text-ink-primary">{{ row.value }}</span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>

      <p class="mt-6 text-base-medium text-ink-primary">{{ __('What has happened') }}</p>
      <EmptyState
        v-if="!events.length"
        icon="lucide-clock"
        :title="__('Nothing yet. This workspace has never been on the ladder.')"
        class="mt-3"
      />
      <List
        v-else
        :columns="eventTracks"
        :row-height="56"
        class="px-3 mt-3"
        divider="full"
      >
        <ListHeader>
          <ListHeaderCell v-for="c in eventCols" :key="c.key">{{ c.header }}</ListHeaderCell>
        </ListHeader>
        <ListRows :items="events" row-key="name" v-slot="{ item: row, value }">
          <ListRow :value="value">
            <ListCell>
              <div class="min-w-0">
                <p class="truncate text-base text-ink-primary">{{ row.event }}</p>
                <p class="truncate text-xs text-ink-muted">{{ row.reason || '—' }}</p>
              </div>
            </ListCell>
            <ListCell v-if="eventShows('by')">
              <Badge :label="row.triggered_by || __('Sweep')" theme="gray" variant="subtle" />
            </ListCell>
            <ListCell>
              <span class="truncate text-sm text-ink-secondary">{{ when(row.occurred_on) }}</span>
            </ListCell>
          </ListRow>
        </ListRows>
      </List>

      <!--
        Who has been in here, and why they said they were.

        On the workspace rather than only on the fleet-wide Support logins
        screen, because the question is asked about *one* workspace, usually
        on a call, and answering it used to mean leaving the record to filter
        a list. The fleet screen stays: "what did we do to everybody last
        week" is a different question and a real one.

        Silent when nobody has. An empty state here would be a heading and a
        shrug on every workspace nobody has ever had to help.
      -->
      <template v-if="logins.length">
        <p class="mt-6 text-base-medium text-ink-primary">{{ __('Who has signed in') }}</p>
        <List :columns="fieldTracks" divider="full" class="mt-3">
          <ListRows :items="logins" row-key="name" v-slot="{ item: row, value }">
            <ListRow :value="value" class="py-3">
              <ListCell>
                <div class="min-w-0">
                  <p class="truncate text-sm text-ink-primary">{{ row.operator }}</p>
                  <p class="truncate text-xs text-ink-muted">{{ row.reason || '—' }}</p>
                </div>
              </ListCell>
              <ListCell>
                <div class="flex min-w-0 items-center gap-2">
                  <Badge
                    v-if="!row.succeeded"
                    theme="red"
                    :label="__('Refused')"
                    variant="subtle"
                  />
                  <span class="truncate text-sm text-ink-secondary">
                    {{ when(row.logged_in_on) }}
                  </span>
                </div>
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import {
  Alert, Badge, Button, LoadingIndicator,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell, } from '@/ui'
import EmptyState from '@/shared/components/EmptyState.vue'
import { useListColumns } from '@/modules/onespace/lib/screen/list'
import { admin } from '@/modules/onespace/screens/ops/admin'
import { __ } from '@/shared/lib/runtime/translate'
import { date, moment } from '@/shared/lib/runtime/format'
import { sizeText } from '@/shared/lib/files/size'

const props = defineProps({
  tenant: { type: String, required: true },
})

const { columns: fieldTracks } = useListColumns([
  { key: 'label', header: '', track: '14rem', mobile: '9rem' },
  { key: 'value', header: '', track: 'minmax(0,1fr)' },
])

const { visible: eventCols, columns: eventTracks, shows: eventShows } = useListColumns([
  { key: 'event', header: __('Event'), track: 'minmax(0,1fr)' },
  { key: 'by', header: __('By'), track: '8rem', mobile: false },
  { key: 'when', header: __('When'), track: '11rem', mobile: '6rem' },
])

const data = ref(null)
const loading = ref(false)
const busy = ref('')

async function load() {
  if (!props.tenant) return
  loading.value = true
  try {
    data.value = await admin.tenantLifecycle(props.tenant)
  } finally {
    loading.value = false
  }
}
watch(() => props.tenant, load, { immediate: true })

/** Every action reloads: each one changes what this panel is showing. */
async function run(key, fn) {
  busy.value = key
  try {
    await fn()
    await load()
  } finally {
    busy.value = ''
  }
}

const ladder = computed(() => data.value?.ladder || {})
const cold = computed(() => data.value?.cold || {})
const backup = computed(() => data.value?.backup || {})
const quota = computed(() => data.value?.quota || {})
const windows = computed(() => data.value?.windows || {})
const events = computed(() => data.value?.events || [])
const logins = computed(() => data.value?.logins || [])

const held = computed(() => Boolean(ladder.value.held))
const canRestore = computed(() =>
  Boolean(cold.value.key) && data.value?.status === 'Archived',
)

const toggleHold = () =>
  run('hold', () =>
    held.value ? admin.releaseLifecycle(props.tenant) : admin.holdLifecycle(props.tenant),
  )

const headline = computed(() => {
  if (!data.value) return __('Lifecycle')
  if (!ladder.value.started_on) return __('Not on the lifecycle ladder')
  return __('On the ladder since {0}', [day(ladder.value.started_on)])
})

const detail = computed(() => {
  if (!data.value) return ''
  if (!ladder.value.started_on) {
    return __('This workspace is paid for, or has no subscription to be unpaid on.')
  }
  return {
    Grace: __('Working normally. Suspended after {0} days unpaid.', [
      windows.value.dunning_grace_days,
    ]),
    Suspended: __('Switched off and intact. Archived after {0} days.', [
      windows.value.suspended_days,
    ]),
    Archived: __('Site removed from Frappe Cloud. Restorable from the cold copy.'),
    Purged: __('Everything deleted. Nothing can be restored.'),
  }[ladder.value.stage] || __('Unpaid, and the next sweep decides what happens.')
})

// A dash where a workspace has not reached that rung yet — `date()`
// answers an empty string, and an empty cell in a ladder reads as a
// missing value rather than a stage nobody has got to.
const day = (value) => date(value) || '—'
const when = (value) => (value ? moment(value) : '—')

const bytes = (value) => sizeText(value, { blank: '—' })

const rows = computed(() => {
  if (!data.value) return []

  const out = [
    { label: __('Rung'), value: ladder.value.stage || __('Not on the ladder') },
    { label: __('Unpaid since'), value: day(ladder.value.started_on) },
    { label: __('Switched off'), value: day(ladder.value.suspended_on) },
    { label: __('Archived'), value: day(ladder.value.archived_on) },
  ]

  if (ladder.value.purge_after) {
    out.push({
      label: __('Deleted after'),
      value: day(ladder.value.purge_after),
      // Red rather than plain: this is the one date after which nothing can
      // be recovered, and it should not read like the others.
      badge: 'red',
    })
    out.push({ label: __('Warned on'), value: day(ladder.value.purge_warned_on) })
  }
  if (ladder.value.purged_on) {
    out.push({ label: __('Deleted'), value: when(ladder.value.purged_on), badge: 'red' })
  }
  if (ladder.value.restored_on) {
    out.push({ label: __('Restored'), value: when(ladder.value.restored_on), badge: 'green' })
  }

  out.push(
    {
      label: __('Cold copy'),
      value:
        cold.value.key ||
        (cold.value.requested_on ? __('Asked the site for one') : __('None')),
      // The absence of a copy is what stops an archive, so it is the one thing
      // on this list somebody has to be able to spot without reading.
      badge: cold.value.key ? 'green' : 'amber',
    },
    { label: __('Copy taken'), value: when(cold.value.stored_on) },
    { label: __('Copy size'), value: bytes(cold.value.bytes) },
    {
      label: __('Backups'),
      value: backup.value.per_day
        ? __('{0} a day, kept {1} days', [
            backup.value.per_day,
            backup.value.retention_days,
          ])
        : __('None on this plan'),
    },
    { label: __('Last backup'), value: when(backup.value.last_on) },
    { label: __('Last backup size'), value: bytes(backup.value.bytes) },
  )

  if (quota.value.over?.length) {
    out.push({
      label: __('Over quota'),
      value: quota.value.enforced
        ? __('{0} — enforced', [quota.value.over.join(', ')])
        : __('{0} — in grace until {1}', [
            quota.value.over.join(', '),
            date(quota.value.grace_until),
          ]),
      badge: quota.value.enforced ? 'red' : 'amber',
    })
  }

  return out
})
</script>
