<template>
  <!--
    What exists on the Frappe Cloud account: the servers a shard can point at,
    the bench groups it can track, and the site plans press will accept.

    A `component` screen because none of it is stored here — it is read live
    from press, which is the whole point. A shard naming a server press does
    not have fails at the first provision, several steps in, after a real site
    already exists.
  -->
  <div class="mx-auto max-w-4xl p-5">
    <div class="mb-4 flex items-center justify-between gap-3">
      <p class="text-p-sm text-ink-gray-5">
        Read from Frappe Cloud each time this opens, so it is never a stale copy.
      </p>
      <Button
        variant="ghost"
        icon="lucide-refresh-cw"
        label="Refresh"
        tooltip="Refresh"
        :loading="loading"
        @click="load()"
      />
    </div>

    <div v-if="loading && !loaded" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <!-- Named rather than blank. "Frappe Cloud is unreachable" is worth more
         than an empty table, which reads as "there is nothing here" — and an
         operator looking at this may be about to fix the credentials. -->
    <Alert v-else-if="error" theme="amber" title="Frappe Cloud did not answer">
      <template #description>{{ error }}</template>
      <template #actions>
        <Button label="Try again" :loading="loading" @click="load()" />
      </template>
    </Alert>

    <template v-else>
      <section v-for="group in GROUPS" :key="group.key" class="mb-8">
        <div class="mb-2 flex items-baseline justify-between">
          <h2 class="text-base-medium text-ink-gray-8">{{ group.label }}</h2>
          <span class="text-p-sm tabular-nums text-ink-gray-5">
            {{ (data?.[group.key] || []).length }}
          </span>
        </div>

        <EmptyState
          v-if="!(data?.[group.key] || []).length"
          class="!py-6"
          icon="lucide-inbox"
          :title="group.empty"
        />

        <List v-else :columns="['minmax(0,1fr)', 'minmax(0,1fr)']" divider="full">
          <ListRows
            :items="data[group.key]"
            :row-key="group.id"
            v-slot="{ item: row, value }"
          >
            <ListRow :value="value" class="py-2">
              <ListCell>
                <span class="truncate text-p-sm text-ink-gray-8">
                  {{ row[group.id] }}
                </span>
              </ListCell>
              <ListCell>
                <span class="truncate text-p-sm text-ink-gray-5">
                  {{ group.detail(row) }}
                </span>
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { Alert, Button, List, ListRows, ListRow, ListCell, LoadingIndicator } from '@/ui'
import EmptyState from '../../components/EmptyState.vue'
import { callMethod } from '../../lib/resource'

defineProps({
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

const GROUPS = [
  {
    key: 'servers',
    id: 'name',
    label: 'Servers',
    empty: 'No active servers on this account.',
    detail: (row) => [row.title, row.cluster, row.plan].filter(Boolean).join(' · '),
  },
  {
    key: 'groups',
    id: 'name',
    label: 'Bench groups',
    empty: 'No bench groups on this account.',
    detail: (row) => [row.title, row.version].filter(Boolean).join(' · '),
  },
  {
    key: 'plans',
    id: 'name',
    label: 'Site plans',
    empty: 'No site plans available.',
    detail: (row) => [row.title, row.price].filter(Boolean).join(' · '),
  },
]

const data = ref(null)
const error = ref('')
const loading = ref(false)
const loaded = ref(false)

// The endpoint reports a press failure in-band as `{error}` rather than
// raising, so a panel can say which part is missing and why. Kept here.
const load = async () => {
  loading.value = true
  error.value = ''
  try {
    const result = await callMethod(
      'oneapp_control.api.admin.press_capacity',
      {},
      { silent: true },
    )
    data.value = result
    error.value = result?.error || ''
  } catch (e) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
    loaded.value = true
  }
}

onMounted(load)
</script>
