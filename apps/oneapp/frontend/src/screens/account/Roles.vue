<template>
  <WorkspaceBar />

  <div class="mx-auto w-full max-w-[940px] px-3 pb-10 sm:px-5">
    <div v-if="resource.loading && !data" class="grid place-items-center py-16">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else-if="data" class="flex flex-col gap-6 py-5">
      <!--
        Two lists, and the split is the whole idea: what the apps came with, and
        what this workspace decided it needed. Shipped roles are read-only on
        purpose — a preshipped role is part of what an app *is*, and a workspace
        that quietly redefined "Sales" would find it redefined again on the next
        release.
      -->
      <section>
        <div class="mb-1 flex items-baseline justify-between">
          <h3 class="text-base-medium text-ink-gray-8">Roles your apps came with</h3>
        </div>
        <p class="mb-3 text-p-sm text-ink-gray-5">
          These arrive with the apps this workspace is entitled to. Hand them out
          on the People screen.
        </p>

        <List :columns="['minmax(0,1fr)', 'auto']" :row-height="56"
              class="px-3" divider="full">
          <ListRows :items="shipped" row-key="key" v-slot="{ item: role, value }">
            <ListRow :value="value">
              <ListCell>
                <div class="flex min-w-0 flex-col">
                  <span class="truncate text-p-sm text-ink-gray-8">{{ role.label }}</span>
                  <span class="truncate text-p-xs text-ink-gray-5">
                    {{ role.space_label }}<template v-if="role.description"> ·
                    {{ role.description }}</template>
                  </span>
                </div>
              </ListCell>
              <ListCell>
                <!-- Said rather than left to be discovered: a default role is
                     not something anybody chose, and a manager wondering why
                     everyone can already open Books deserves the answer here. -->
                <Badge v-if="role.is_default" theme="gray" label="Everyone" />
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
        <EmptyState v-if="!shipped.length" title="No apps yet"
                    description="Roles appear here once this workspace has an app." />
      </section>

      <section>
        <div class="mb-1 flex items-baseline justify-between">
          <h3 class="text-base-medium text-ink-gray-8">Roles you built</h3>
          <Button variant="subtle" label="New role" @click="startNew" />
        </div>
        <p class="mb-3 text-p-sm text-ink-gray-5">
          A role of your own can reach anything your apps expose, and nothing else.
        </p>

        <List v-if="custom.length" :columns="['minmax(0,1fr)', 'auto', 'auto']"
              :row-height="56" class="px-3" divider="full">
          <ListRows :items="custom" row-key="name" v-slot="{ item: role, value }">
            <ListRow :value="value">
              <ListCell>
                <div class="flex min-w-0 flex-col">
                  <span class="truncate text-p-sm text-ink-gray-8">{{ role.role_label }}</span>
                  <span class="truncate text-p-xs text-ink-gray-5">
                    {{ role.grants.length }}
                    {{ role.grants.length === 1 ? 'permission' : 'permissions' }}
                  </span>
                </div>
              </ListCell>
              <ListCell>
                <Button variant="ghost" label="Edit" @click="startEdit(role)" />
              </ListCell>
              <ListCell>
                <Button variant="ghost" theme="red" icon="lucide-trash-2"
                        label="Delete role" tooltip="Delete role"
                        @click="remove(role)" />
              </ListCell>
            </ListRow>
          </ListRows>
        </List>
        <EmptyState
          v-else
          title="No roles of your own yet"
          description="Build one when the roles your apps came with are not the shape you need."
        />
      </section>
    </div>
  </div>

  <FormDialog
    v-model="editing"
    :title="draft.name ? 'Edit role' : 'New role'"
    size="3xl"
    :dismissible="!dirty"
  >
    <div class="flex flex-col gap-5">
      <FormControl v-model="draft.role_label" label="Name" placeholder="Bookkeeper" />
      <FormControl
        v-model="draft.description"
        type="textarea"
        label="What it is for"
        placeholder="Reads invoices and contacts, edits neither."
      />

      <!--
        One row per thing, grouped by the app it came from, named by the screen
        that shows it. A doctype is called `Sales Invoice` and the workspace's
        own navigation calls it `Invoices` — the second is the word this person
        has been looking at all week.
      -->
      <div v-for="group in grouped" :key="group.space" class="flex flex-col gap-2">
        <h4 class="text-p-sm font-medium text-ink-gray-7">{{ group.label }}</h4>
        <div class="flex flex-col divide-y divide-outline-gray-1 rounded-6 border border-outline-gray-2">
          <div
            v-for="row in group.rows"
            :key="row.document_type"
            class="flex items-center justify-between gap-3 px-3 py-2"
          >
            <div class="flex min-w-0 flex-col">
              <span class="truncate text-p-sm text-ink-gray-8">{{ row.label }}</span>
              <span v-if="row.label !== row.document_type"
                    class="truncate text-p-xs text-ink-gray-5">{{ row.document_type }}</span>
            </div>
            <!-- Four states, and "None" is one of them rather than an unticked
                 box: a role that grants nothing here should say so. -->
            <Select
              :model-value="levelFor(row.document_type)"
              :options="levelOptions"
              class="w-32 shrink-0"
              @update:model-value="setLevel(row, $event)"
            />
          </div>
        </div>
      </div>

      <ErrorMessage v-if="error" :message="error" />
    </div>

    <template #actions>
      <Button variant="solid" label="Save role" :loading="saving"
              :disabled="!draft.role_label || !chosen.length" @click="save" />
    </template>
  </FormDialog>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import {
  Badge, Button, ErrorMessage, FormControl, List, ListCell, ListRow, ListRows,
  LoadingIndicator, Select,
} from '@/ui'
import EmptyState from '../../components/EmptyState.vue'
import FormDialog from '../../components/screen/FormDialog.vue'
import WorkspaceBar from './WorkspaceBar.vue'
import { deleteRole, saveRole, useRoles } from './customer'
import { useWorkspace } from './workspace'

const workspace = useWorkspace()
const resource = useRoles(workspace)
const data = computed(() => resource.data)

const shipped = computed(() => (data.value?.offered || []).filter((r) => !r.custom))
const custom = computed(() => data.value?.custom || [])
const available = computed(() => data.value?.available || [])

// "None" first, because it is what every row starts as and the list reads as a
// ladder from there.
const NONE = 'None'
const levelOptions = computed(() =>
  [NONE, ...(data.value?.levels || [])].map((value) => ({ label: value, value })),
)

const grouped = computed(() => {
  const seen = new Map()
  for (const row of available.value) {
    if (!seen.has(row.space)) {
      seen.set(row.space, { space: row.space, label: row.space_label || row.space, rows: [] })
    }
    seen.get(row.space).rows.push(row)
  }
  return [...seen.values()]
})

const editing = ref(false)
const saving = ref(false)
const error = ref('')
const draft = reactive({ name: null, role_label: '', description: '' })
// fieldname -> level, so a Select can read and write one thing.
const levels = reactive({})

const chosen = computed(() =>
  Object.entries(levels)
    .filter(([, level]) => level && level !== NONE)
    .map(([document_type, access]) => ({
      document_type,
      access,
      space: available.value.find((r) => r.document_type === document_type)?.space || '',
    })),
)

// Enough to be worth not losing on a stray Escape. See FormDialog.
const dirty = computed(() => Boolean(draft.role_label || chosen.value.length))

const levelFor = (doctype) => levels[doctype] || NONE
const setLevel = (row, level) => {
  levels[row.document_type] = level
}

const blank = () => {
  error.value = ''
  Object.assign(draft, { name: null, role_label: '', description: '' })
  Object.keys(levels).forEach((key) => delete levels[key])
}

const startNew = () => {
  blank()
  editing.value = true
}

const startEdit = (role) => {
  blank()
  Object.assign(draft, {
    name: role.name,
    role_label: role.role_label,
    description: role.description || '',
  })
  for (const grant of role.grants || []) levels[grant.document_type] = grant.access
  editing.value = true
}

const save = async () => {
  saving.value = true
  error.value = ''
  try {
    await saveRole(workspace.value, {
      name: draft.name || undefined,
      role_label: draft.role_label,
      description: draft.description,
      grants: JSON.stringify(chosen.value),
    })
    editing.value = false
    resource.reload()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    saving.value = false
  }
}

const remove = async (role) => {
  await deleteRole(workspace.value, role.name)
  resource.reload()
}
</script>
