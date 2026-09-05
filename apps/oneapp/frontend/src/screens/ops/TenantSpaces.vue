<template>
  <div>
    <p class="mb-4 text-p-base text-ink-gray-6">
      Every plan carries every generally available app, so this is only about the
      restricted ones — the bespoke single-tenant work that entitlement exists
      for. Granting one adds its role on the next sync; revoking removes it.
    </p>

    <div v-if="loading && !rows.length" class="grid place-items-center py-12">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <List v-else :columns="columns" :row-height="56" class="px-3" divider="full">
      <ListHeader>
        <ListHeaderCell v-for="c in visible" :key="c.key">{{ c.header }}</ListHeaderCell>
      </ListHeader>

      <ListRows :items="rows" row-key="space_code" v-slot="{ item: app, value }">
        <ListRow :value="value">
          <ListCell>
            <Icon :name="spaceIcon(app.icon)" class="size-4 shrink-0 text-ink-gray-7" />
            <div class="ml-3 min-w-0">
              <p class="truncate text-base text-ink-gray-8">{{ app.space_label }}</p>
              <p class="truncate text-xs text-ink-gray-5">
                {{ said(app) }}
              </p>
            </div>
          </ListCell>
          <ListCell v-if="shows('access')">
            <Badge
              :theme="app.entitled ? 'green' : 'gray'"
              :label="app.entitled ? 'Enabled' : 'Not enabled'"
              variant="subtle"
            />
          </ListCell>
          <ListCell class="justify-end">
            <!-- Nothing to do for a generally available app: it is already on
                 every plan, and a disabled button with no reason reads as a
                 bug rather than as a rule. -->
            <span
              v-if="app.availability !== 'Restricted'"
              class="text-p-sm text-ink-gray-4"
            >
              Always on
            </span>
            <Button
              v-else
              :label="app.entitled ? 'Revoke' : 'Grant'"
              :theme="app.entitled ? 'red' : 'gray'"
              variant="subtle"
              :loading="busy === app.space_code"
              :disabled="!app.entitled && !!app.blocked_by?.length"
              :tooltip="blocked(app)"
              @click="toggle(app)"
            />
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import {
  Badge, Button, Icon, LoadingIndicator,
  List, ListHeader, ListHeaderCell, ListRows, ListRow, ListCell,
} from '@/ui'
// An icon name that only exists in the database emits no CSS, so anything
// outside the generated set falls back to one that does.
import { spaceIcon } from '../../lib/icons'
import { useListColumns } from '../../lib/list'
import { admin } from './admin'

const props = defineProps({ tenant: { type: String, required: true } })

// The line under the label. What a space needs of the site is the thing an
// operator wants to know before pressing Grant, and it beats "By entitlement
// only" — which they already knew, since that is the whole of this screen.
const said = (app) => {
  if (app.blocked_by?.length) return `Needs ${app.blocked_by.join(', ')} — not on this bench`
  if (app.requires?.length) return `Needs ${app.requires.join(', ')}`
  return app.availability === 'Restricted' ? 'By entitlement only' : 'On every plan'
}

const blocked = (app) =>
  app.entitled || !app.blocked_by?.length
    ? undefined
    : `The bench this workspace sits on does not carry ${app.blocked_by.join(', ')}. `
      + 'Move it to a shard whose bench has it, or add it to this one.'

const rows = ref([])
const loading = ref(false)
const busy = ref('')

const { visible, columns, shows } = useListColumns([
  { key: 'app', header: 'App', track: 'minmax(0,1fr)' },
  { key: 'access', header: 'Access', track: '9rem', mobile: false },
  { key: 'action', header: '', track: '7rem', mobile: '5rem' },
])

const load = async () => {
  loading.value = true
  try {
    rows.value = (await admin.tenantAppAccess(props.tenant)) || []
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => props.tenant, load)

async function toggle(app) {
  busy.value = app.space_code
  try {
    if (app.entitled) await admin.revokeApp(props.tenant, app.space_code)
    else await admin.grantApp(props.tenant, app.space_code)
    await load()
  } finally {
    busy.value = ''
  }
}
</script>
