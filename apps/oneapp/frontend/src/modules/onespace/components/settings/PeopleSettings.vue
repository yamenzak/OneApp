<template>
  <!--
    Who is in this workspace, inside the workspace.

    It used to be a screen on the control plane, at another address, which is
    where the rows still live — a person may own three workspaces and only the
    control plane knows that. What changed is where you stand to read them:
    `onespace/account.py` relays the question, and `docs/MARKETPLACE.md` §2
    is why this one moved and Billing did not.
  -->
  <SettingsHeader
    :title="__('People')"
    :description="__('Who can sign in to this workspace, and what each of them may do.')"
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <LoadingIndicator v-if="loading && !data" class="size-5 text-ink-muted" />

    <!-- The rows are the control plane's, so this is the one panel that has
         somewhere else to be unreachable. Said as what it means rather than as
         the exception: a workspace whose account cannot be reached is not a
         workspace with no people. -->
    <Alert v-else-if="unreachable" theme="amber" :title="__('Cannot reach your account')">
      <template #description>
        {{ __('Who is in this workspace is kept with your account, and it is not answering. Nobody has lost access; this page is what cannot be read.') }}
      </template>
    </Alert>

    <div v-else-if="data" class="flex flex-col gap-5">
      <Alert v-if="!seatsLeft" theme="amber" :title="__('Every seat is in use')">
        <template #description>
          {{ __('Change plan to invite more people, or remove somebody who no longer needs access. Plans are in your account.') }}
        </template>
      </Alert>

      <ul class="flex flex-col">
        <li
          v-for="person in data.members"
          :key="person.email"
          data-slot="member-row"
          class="flex items-center gap-3 border-b border-outline-gray-1 py-2.5"
        >
          <Avatar :label="person.full_name || person.email" size="lg" />

          <span class="flex min-w-0 flex-1 flex-col">
            <span class="truncate text-sm text-ink-primary">
              {{ person.full_name || person.email }}
            </span>
            <span class="truncate text-xs text-ink-muted">{{ person.email }}</span>
          </span>

          <!-- The owner is not a level somebody is set to; it is who the
               workspace belongs to, and there is no control for it here. -->
          <Badge v-if="person.is_owner" theme="gray" :label="__('Owner')" />
          <template v-else>
            <!-- Two halves of one question, side by side because they are
                 read as one: `access` is what somebody may do to the
                 *workspace* — invite people, change its settings — and the
                 roles are what they may do inside the apps. The server takes
                 both in one write for the same reason. -->
            <MemberRoles
              :roles="data.roles || []"
              :held="person.roles || []"
              :disabled="!!saving"
              :saving="saving === person.email"
              @change="setRoles(person, $event)"
            />
            <!-- Sized from outside, not by a class on the control:
                 FormControl computes `w-full` for every select-like type and
                 there is no prop to turn it off, so a width handed to it
                 loses to the library's own. Without this the select fills the
                 row and the name beside it, which has `min-w-0`, truncates to
                 nothing — a row of two dropdowns and an initial. -->
            <div class="w-32 shrink-0">
              <FormControl
                type="select"
                :model-value="person.access"
                :options="accessOptions"
                :disabled="!!saving"
                @update:model-value="setAccess(person, $event)"
              />
            </div>
          </template>

          <Button
            v-if="!person.is_owner"
            icon="lucide-user-minus"
            variant="ghost"
            :label="__('Remove {0}', [person.full_name || person.email])"
            :tooltip="__('Remove {0}', [person.full_name || person.email])"
            :loading="saving === person.email"
            @click="remove(person)"
          />
        </li>
      </ul>

      <p class="text-p-xs text-ink-muted">{{ seatLine }}</p>

      <section class="flex flex-col gap-3">
        <h3 class="text-base-medium text-ink-primary">{{ __('Invite somebody') }}</h3>
        <div class="grid gap-3 sm:grid-cols-2">
          <FormControl
            v-model="invite.email"
            type="email"
            :label="__('Email')"
            :placeholder="__('name@example.com')"
          />
          <FormControl v-model="invite.full_name" :label="__('Name')" />
        </div>
        <!-- Said rather than hidden: an invitation is not an account yet, and
             a person who tries to sign in immediately should know why it does
             not work. How long, not what runs — see `docs/LANGUAGE.md`. -->
        <p class="text-p-xs text-ink-muted">
          {{ __('They can sign in within about fifteen minutes.') }}
        </p>
      </section>

      <ErrorMessage v-if="error" :message="error" />
    </div>
  </SettingsBody>

  <div v-if="data" :class="PANEL_FOOTER">
    <Button
      variant="solid"
      :label="__('Send the invitation')"
      :loading="saving === 'invite'"
      :disabled="!invite.email.trim() || !seatsLeft"
      @click="send"
    />
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import {
  Alert, Avatar, Badge, Button, ErrorMessage, FormControl, LoadingIndicator,
  SettingsHeader, SettingsBody,
} from '@/ui'
import MemberRoles from '@/modules/onespace/components/settings/MemberRoles.vue'
import { PANEL_BODY, PANEL_FOOTER, PANEL_HEADER } from '@/modules/onespace/components/settings/geometry'
import { workspace } from '@/shared/lib/workspace'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const data = ref(null)
const loading = ref(false)
const unreachable = ref(false)
const saving = ref('')
const error = ref('')
const invite = reactive({ email: '', full_name: '' })

const seats = computed(() => data.value?.seats || {})
const seatsLeft = computed(() => !seats.value.quota || seats.value.used < seats.value.quota)

const seatLine = computed(() =>
  seats.value.quota
    ? __('{0} of {1} seats in use.', [seats.value.used, seats.value.quota])
    : '',
)

const accessOptions = computed(() =>
  (data.value?.access_levels || []).map((one) => ({ label: __(one), value: one })),
)

const load = async () => {
  loading.value = true
  try {
    const answer = await workspace.members()
    // A state of the answer rather than an exception: the account being
    // unreachable is not a fault in what anybody asked for.
    unreachable.value = !!answer.unreachable
    data.value = answer
  } catch (e) {
    error.value = errorText(e)
  } finally {
    loading.value = false
  }
}

const changing = async (who, change) => {
  saving.value = who
  error.value = ''
  try {
    await change()
    await load()
  } catch (e) {
    error.value = errorText(e)
  } finally {
    saving.value = ''
  }
}

const setAccess = (person, access) =>
  changing(person.email, () => workspace.setMemberAccess(person.email, access))

// The whole set, not the one that changed: `set_member_roles` replaces, which
// is what makes unticking mean something.
const setRoles = (person, roles) =>
  changing(person.email, () => workspace.setMemberRoles(person.email, roles))

const remove = (person) =>
  changing(person.email, () => workspace.removeMember(person.email))

const send = () =>
  changing('invite', async () => {
    await workspace.inviteMember(invite.email.trim(), invite.full_name.trim())
    invite.email = ''
    invite.full_name = ''
  })

load()
</script>
