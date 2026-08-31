<!--
  Ported from the portal SPA. The content and its reasoning are unchanged; what
  moved is the frame: a screen renders inside the shell's own header, so the
  PageHeader is gone and the workspace it is about is stated by WorkspaceBar
  rather than carried in the route.
-->
<template>
  <WorkspaceBar />

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <div v-if="resource.loading && !data" class="grid place-items-center py-16">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else-if="data" class="flex flex-col gap-6 py-5">
      <Alert v-if="!seatsLeft" theme="amber" title="Every seat is in use">
        <template #description>
          Your plan includes {{ seats.quota }}
          {{ seats.quota === 1 ? 'seat' : 'seats' }}. Change plan to invite more
          people, or remove someone who no longer needs access.
        </template>
        <template #actions>
          <Button label="See plans" @click="$router.push({ name: 'AccountBilling', params: { workspace } })" />
        </template>
      </Alert>

      <section>
        <div class="mb-3 flex items-baseline justify-between">
          <h3 class="text-base-medium text-ink-gray-8">Members</h3>
          <span class="text-p-sm tabular-nums text-ink-gray-5">
            {{ seats.used }}<template v-if="seats.quota"> of {{ seats.quota }}</template>
            {{ seats.used === 1 ? 'seat' : 'seats' }} used
          </span>
        </div>

        <!-- Narrowed rather than dropped: the access badge and the remove
             button are both short, and a desktop-sized track for them left the
             person's name about 120px. -->
        <List :columns="memberColumns" :row-height="56" class="list-row-px-3" divider="full">
          <ListHeader>
            <ListHeaderCell>Person</ListHeaderCell>
            <ListHeaderCell>Access</ListHeaderCell>
            <ListHeaderCell />
          </ListHeader>

          <ListRows :items="data.members" row-key="email" v-slot="{ item: person, value }">
            <ListRow :value="value">
              <ListCell>
                <Avatar :label="person.full_name || person.email" size="lg" />
                <div class="ml-3 min-w-0">
                  <p class="truncate text-base text-ink-gray-8">
                    {{ person.full_name || person.email }}
                  </p>
                  <p v-if="person.full_name" class="truncate text-p-sm text-ink-gray-5">
                    {{ person.email }}
                  </p>
                </div>
              </ListCell>
              <ListCell>
                <Badge
                  :theme="person.is_owner ? 'blue' : 'gray'"
                  :label="person.access"
                  variant="subtle"
                />
              </ListCell>
              <ListCell class="justify-end">
                <Button
                  v-if="!person.is_owner"
                  variant="ghost"
                  icon="lucide-trash-2"
                  :label="`Remove ${person.email}`"
                  :tooltip="`Remove ${person.email}`"
                  :loading="removing === person.email"
                  @click="remove(person)"
                />
              </ListCell>
            </ListRow>
          </ListRows>
        </List>

        <p class="mt-3 text-p-sm text-ink-gray-5">
          An invited person gets a welcome email from your workspace once it next
          syncs, usually within a few minutes. Removing someone disables their
          sign-in; the work they created stays in the workspace.
        </p>
      </section>
    </div>
  </div>

  <Dialog v-model="showInvite" title="Invite someone" size="lg">
    <div v-focus class="flex flex-col gap-4">
      <FormControl
        v-model="form.email"
        type="email"
        label="Email"
        placeholder="colleague@acme.test"
      />
      <FormControl v-model="form.full_name" label="Name" placeholder="Alex Rivera" />
      <FormControl
        v-model="form.access"
        type="select"
        label="Access"
        :options="accessOptions"
        :description="
          form.access === 'Admin'
            ? 'Can manage the workspace as well as use the apps.'
            : 'Can use the apps this workspace is entitled to.'
        "
      />
      <ErrorMessage v-if="error" :message="error" />
    </div>

    <template #actions>
      <Button
        variant="solid"
        label="Send invite"
        :loading="inviting"
        :disabled="!form.email"
        @click="invite"
      />
      <Button label="Cancel" @click="showInvite = false" />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
  Alert, Avatar, Badge, Button, Dialog, ErrorMessage,
  FormControl, LoadingIndicator, List, ListHeader, ListHeaderCell, ListRows,
  ListRow, ListCell, vFocus,
} from '@/ui'
import WorkspaceBar from './WorkspaceBar.vue'
import { useWorkspace } from './workspace'
import { useListColumns } from '../../lib/list'
import { useMembers, inviteMember, removeMember } from './customer'

const { columns: memberColumns } = useListColumns([
  { key: 'person', header: 'Person', track: 'minmax(0,1fr)' },
  { key: 'access', header: 'Access', track: '8rem', mobile: '5.5rem' },
  { key: 'remove', header: '', track: '3rem' },
])

defineProps({
  spaceCode: { type: String, default: '' },
  screen: { type: String, default: '' },
})

// Shared with every other account screen, so switching on the overview is
// still switched when you open this one.
const workspace = useWorkspace()

const resource = useMembers(workspace)
const data = computed(() => resource.data)
const seats = computed(() => data.value?.seats || { used: 0, quota: 0 })

// `remaining` is null on a plan with no seat cap, which is not the same as zero.
const seatsLeft = computed(() => {
  const left = data.value?.seats?.remaining
  return left === null || left === undefined || left > 0
})

const accessOptions = computed(() =>
  (data.value?.access_levels || ['Member']).map((level) => ({ label: level, value: level })),
)

const showInvite = ref(false)
const inviting = ref(false)
const removing = ref('')
const error = ref('')
const form = reactive({ email: '', full_name: '', access: 'Member' })

watch(showInvite, (open) => {
  if (!open) return
  error.value = ''
  Object.assign(form, { email: '', full_name: '', access: 'Member' })
})

async function invite() {
  inviting.value = true
  error.value = ''
  try {
    await inviteMember(workspace.value, { ...form })
    showInvite.value = false
    resource.reload()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    inviting.value = false
  }
}

async function remove(person) {
  removing.value = person.email
  try {
    await removeMember(workspace.value, person.email)
    resource.reload()
  } finally {
    removing.value = ''
  }
}
</script>
