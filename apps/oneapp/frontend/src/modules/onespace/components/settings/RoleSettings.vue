<template>
  <!--
    The roles this workspace hands out.

    A role is built out of *this* workspace's own screens, so it is a fact
    about the workspace and belongs here rather than at another address. The
    rows are the control plane's and `onespace/account.py` relays. See
    `docs/MARKETPLACE.md` §2.

    Beside People rather than inside it: a role exists whether or not anybody
    holds one, and building one is a different sitting from handing it out.
  -->
  <SettingsHeader
    :title="__('Roles')"
    :description="__('What a person may reach, as a set you can give somebody in one go.')"
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <LoadingIndicator v-if="loading && !data" class="size-5 text-ink-muted" />

    <Alert v-else-if="unreachable" theme="amber" :title="__('Cannot reach your account')">
      <template #description>
        {{ __('Your roles are kept with your account, and it is not answering. Everybody keeps the access they already have.') }}
      </template>
    </Alert>

    <div v-else-if="data" class="flex flex-col gap-6">
      <section v-if="shipped.length" class="flex flex-col gap-2">
        <h3 class="text-base-medium text-ink-primary">{{ __('What your apps ship') }}</h3>
        <!-- Shown and not editable, and worth showing: "why can they see that?"
             has no answer on a page that lists only what you built. -->
        <p class="text-p-xs text-ink-muted">
          {{ __('These come with the apps this workspace has. They cannot be changed here.') }}
        </p>
        <div class="flex flex-wrap gap-1.5">
          <Badge v-for="role in shipped" :key="role.key" theme="gray" :label="role.label" />
        </div>
      </section>

      <section class="flex flex-col gap-3">
        <div class="flex items-center justify-between gap-3">
          <h3 class="text-base-medium text-ink-primary">{{ __('Roles you made') }}</h3>
          <Button
            variant="subtle"
            icon-left="lucide-plus"
            :label="__('New role')"
            @click="build(null)"
          />
        </div>

        <!-- The frame is `DataList` — §B1. -->
        <DataList :source="source" :skeleton="2" skeleton-class="h-11 w-full">
          <template #row="{ row: role }">
          <div
            data-slot="workspace-role"
            class="flex items-center gap-3 border-b border-outline-gray-1 py-2.5"
          >
            <span class="flex min-w-0 flex-1 flex-col">
              <span class="truncate text-sm text-ink-primary">{{ role.role_label }}</span>
              <span class="truncate text-xs text-ink-muted">{{ reach(role) }}</span>
            </span>
            <Button
              icon="lucide-pencil"
              variant="ghost"
              :label="__('Edit {0}', [role.role_label])"
              :tooltip="__('Edit {0}', [role.role_label])"
              @click="build(role)"
            />
            <Button
              icon="lucide-trash-2"
              variant="ghost"
              theme="red"
              :label="__('Delete {0} for ever', [role.role_label])"
              :tooltip="__('Delete {0} for ever', [role.role_label])"
              :loading="saving === role.name"
              @click="remove(role)"
            />
          </div>
          </template>
        </DataList>
      </section>

      <ErrorMessage v-if="error" :message="error" />
    </div>
  </SettingsBody>

  <RoleBuilder
    v-model="building"
    :available="data?.available || []"
    :access-levels="data?.levels || []"
    :role="editing"
    @saved="load"
  />
</template>

<script setup>
import { computed, ref } from 'vue'
import {
  Alert, Badge, Button, ErrorMessage, LoadingIndicator,
  SettingsHeader, SettingsBody,
} from '@/ui'
import DataList from '@/shared/components/DataList.vue'
import { staticSource } from '@/shared/lib/list/source'
import RoleBuilder from '@/modules/onespace/components/settings/RoleBuilder.vue'
import { PANEL_BODY, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const data = ref(null)
const loading = ref(false)
const saving = ref('')

/**
 * The workspace's own roles, and what this panel can do with them — §B1.
 *
 * Nothing but draw them: a workspace has a handful, and a search box over
 * four rows is a control that costs a line and answers nothing.
 */
const source = computed(() => staticSource({
  rows: data.value?.custom || [],
  key: (role) => role.name,
  empty: {
    icon: 'lucide-user-round',
    title: __('No roles of your own yet'),
    description: __('For where the shipped roles are the wrong shape — read everything, change one part of it.'),
  },
}))
const unreachable = ref(false)
const error = ref('')
const building = ref(false)
// Null for a new one. Held beside the flag rather than inside the dialog so
// the dialog resets from a prop instead of remembering the last role it saw.
const editing = ref(null)

const build = (role) => {
  editing.value = role
  building.value = true
}

// What the apps ship, told apart from what this workspace built: only the
// second is anybody's to change, and mixing them makes the first look broken.
const shipped = computed(() =>
  (data.value?.offered || []).filter((role) => !role.is_custom),
)

/** A role's reach, in one line: how many things, and at what level. */
const reach = (role) => {
  const grants = role.grants || []
  if (!grants.length) return __('Reaches nothing yet')
  const levels = [...new Set(grants.map((one) => one.access))].join(', ')
  return grants.length === 1
    ? __('One screen — {0}', [levels])
    : __('{0} screens — {1}', [grants.length, levels])
}

const load = async () => {
  loading.value = true
  try {
    const answer = await workspace.workspaceRoles()
    unreachable.value = !!answer.unreachable
    data.value = answer
  } catch (e) {
    error.value = errorText(e)
  } finally {
    loading.value = false
  }
}

const remove = async (role) => {
  saving.value = role.name
  error.value = ''
  try {
    await workspace.deleteWorkspaceRole(role.name)
    await load()
  } catch (e) {
    error.value = errorText(e)
  } finally {
    saving.value = ''
  }
}

load()
</script>
