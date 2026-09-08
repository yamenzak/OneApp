<template>
  <!--
    What this workspace could add, and what adding it would take.

    Only what it does not already have: a space they have is in the launcher,
    which is where a space they have belongs. And only what they are entitled
    to *see* — a marketplace that draws a locked card for every private space
    tells every customer the name of every bespoke solution built for every
    other one. `docs/MARKETPLACE.md` §4.

    Four states rather than two, and the middle one is the reason this is not a
    list of buttons: enabling a space whose app is already on the site is a row
    and a role, and enabling one whose app is not is patches against a live
    database. A card that said "enabled" through that would lie for minutes.
  -->
  <PageHeader>
    <nav data-slot="breadcrumb" aria-label="Breadcrumb" class="flex min-w-0 items-center">
      <Breadcrumbs :items="[{ label: __('Add a space'), route: { name: 'Marketplace' } }]" />
    </nav>
  </PageHeader>

  <div class="p-5">
    <div v-if="loading && !data" class="grid place-items-center py-20">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <Alert v-else-if="unreachable" theme="amber" :title="__('Cannot reach your account')">
      <template #description>
        {{ __('What this workspace could add is kept with your account, and it is not answering. Everything you already have is unaffected.') }}
      </template>
    </Alert>

    <ErrorMessage v-else-if="error" :message="error" />

    <div v-else-if="spaces.length" class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <article
        v-for="space in spaces"
        :key="space.code"
        data-slot="marketplace-card"
        :data-state="space.state"
        class="flex flex-col gap-3 rounded-6 border border-outline-gray-2 bg-surface-base p-4"
      >
        <div class="flex items-start gap-3">
          <SpaceFace :space="space" size="xl" />
          <div class="min-w-0 flex-1">
            <p class="truncate text-base-medium text-ink-gray-8">{{ space.label }}</p>
            <p v-if="space.description" class="mt-0.5 line-clamp-3 text-p-sm text-ink-gray-6">
              {{ space.description }}
            </p>
          </div>
        </div>

        <!-- The state, said rather than implied by a disabled button. -->
        <p
          v-if="space.state === 'installing'"
          data-slot="marketplace-state"
          class="text-p-xs text-ink-gray-5"
        >
          {{ __('Being added to your workspace. A few minutes.') }}
        </p>
        <p
          v-else-if="space.state === 'unavailable'"
          data-slot="marketplace-state"
          class="text-p-xs text-ink-gray-5"
        >
          {{ __('This one needs {0}, which your workspace cannot carry yet. Ask us and we will move it.', [space.missing_apps]) }}
        </p>
        <!--
          Not back to a button that would queue the same job to fail the same
          way. Said as what it means to them, and without asking them to do
          anything: a failed provisioning job is already on our own screen.
        -->
        <p
          v-else-if="space.state === 'failed'"
          data-slot="marketplace-state"
          class="text-p-xs text-ink-red-3"
        >
          {{ __('Adding this did not finish. We have been told and are looking at it.') }}
        </p>

        <div class="mt-auto flex">
          <Button
            v-if="space.state === 'available'"
            variant="solid"
            :label="__('Add to workspace')"
            :loading="adding === space.code"
            :disabled="!!adding"
            @click="add(space)"
          />
          <Button v-else variant="subtle" :disabled="true" :label="waiting(space)" />
        </div>
      </article>
    </div>

    <EmptyState
      v-else-if="!loading"
      icon="lucide-store"
      :title="__('Nothing to add right now')"
      :description="__('Your workspace already has everything on offer to it. When something new is, it appears here.')"
    />

    <!--
      What they already have, listed where what they could have is listed.
      Switching one off belongs beside switching one on: two addresses for the
      same decision is how somebody ends up looking for the off switch in the
      space they are trying to turn off.
    -->
    <section v-if="held.length && !unreachable" class="mt-8 flex flex-col gap-3">
      <h2 class="text-base-medium text-ink-gray-8">{{ __('In your workspace') }}</h2>
      <ul class="flex flex-col">
        <li
          v-for="space in held"
          :key="space.code"
          data-slot="held-space"
          class="flex items-center gap-3 border-b border-outline-gray-1 py-2.5"
        >
          <SpaceFace :space="space" size="lg" />
          <span class="flex min-w-0 flex-1 flex-col">
            <span class="truncate text-p-sm text-ink-gray-8">{{ space.label }}</span>
            <span v-if="space.description" class="truncate text-p-xs text-ink-gray-5">
              {{ space.description }}
            </span>
          </span>
          <Button
            :label="__('Switch off')"
            :loading="removing === space.code"
            :disabled="!!removing"
            @click="askOff(space)"
          />
        </li>
      </ul>
      <!-- Said once under the list rather than on every row. -->
      <p class="text-p-xs text-ink-gray-5">
        {{ __('Switching one off hides it and keeps everything in it. You can switch it back on here.') }}
      </p>
    </section>

    <!--
      Below the cards rather than above them, because most visits are somebody
      browsing what they were already offered and a code is the rarer errand.
      Shown even when the account is unreachable would be a box that cannot
      work, so it goes with the rest.
    -->
    <section v-if="!unreachable" class="mt-8 flex max-w-md flex-col gap-3">
      <h2 class="text-base-medium text-ink-gray-8">{{ __('Have a code?') }}</h2>
      <p class="text-p-sm text-ink-gray-6">
        {{ __('Some spaces are not listed. If you were given a code for one, it goes here and the space appears above.') }}
      </p>
      <div class="flex items-start gap-2">
        <FormControl
          v-model="code"
          class="flex-1"
          data-slot="claim-code"
          :placeholder="__('Your code')"
          @keyup.enter="redeem"
        />
        <Button
          :label="__('Use it')"
          :loading="redeeming"
          :disabled="!code.trim()"
          @click="redeem"
        />
      </div>
      <ErrorMessage v-if="codeError" :message="codeError" />
    </section>
  </div>

  <!--
    Asked rather than done, because the reader's next thought is "what happens
    to the records" and a button that answers it after the fact answers it too
    late.
  -->
  <Dialog v-model="confirming" :title="__('Switch off {0}?', [offering?.label || ''])">
    <template #default>
      <div class="flex flex-col gap-4">
        <p class="text-p-base text-ink-gray-7">
          {{ __('It leaves the rail and nobody can open it. Everything in it stays exactly as it is, and switching it back on brings it back unchanged.') }}
        </p>

        <!--
          The second half, and only where there is one. A space that shares its
          apps with something else frees nothing by being removed, so offering
          the destructive option there would be offering a risk with no reward.
        -->
        <div
          v-if="frees.length"
          data-slot="remove-offer"
          class="flex flex-col gap-3 rounded-6 border border-outline-gray-2 p-3"
        >
          <p class="text-p-sm text-ink-gray-7">
            {{ __('It can also be removed, which frees the room {0} takes. That deletes everything those hold, and the only way back is the backup we take first.', [frees.join(', ')]) }}
          </p>
          <FormControl
            v-model="typed"
            data-slot="remove-confirm"
            :label="__('Type {0} to remove it', [workspaceName])"
            :placeholder="workspaceName"
          />
        </div>
      </div>
    </template>
    <template #actions>
      <Button
        variant="solid"
        :label="__('Switch it off')"
        :loading="removing === offering?.code && !removingHard"
        @click="switchOff"
      />
      <Button
        v-if="frees.length"
        theme="red"
        variant="subtle"
        data-slot="remove-space"
        :label="__('Remove it and free the room')"
        :loading="removingHard"
        :disabled="typed.trim() !== workspaceName"
        @click="removeIt"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Alert, Breadcrumbs, Button, Dialog, ErrorMessage, FormControl,
  LoadingIndicator, PageHeader,
} from '@/ui'
import SpaceFace from '@/shared/components/brand/SpaceFace.vue'
import EmptyState from '@/shared/components/EmptyState.vue'
import { workspace } from '@/shared/lib/workspace'
import { session } from '@/modules/onespace/lib/shell/session'
import { notifySuccess } from '@/shared/lib/runtime/notify'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const router = useRouter()

const data = ref(null)
const loading = ref(false)
const unreachable = ref(false)
const adding = ref('')
const error = ref('')
const code = ref('')
const redeeming = ref(false)
const codeError = ref('')
const removing = ref('')
const removingHard = ref(false)
const confirming = ref(false)
const offering = ref(null)
const frees = ref([])
const workspaceName = ref('')
const typed = ref('')

const spaces = computed(() => data.value?.spaces || [])
const held = computed(() => data.value?.held || [])

/** What a card that cannot be pressed says on its button. */
const waiting = (space) => {
  if (space.state === 'installing') return __('Being added')
  if (space.state === 'failed') return __('Did not finish')
  return __('Not available here')
}

// Installing an app is patches against a live database — minutes — and the
// only thing that changes when it lands is on the server. A page that drew
// "being added" once and never looked again would say it until somebody
// reloaded, which is the same lie the state exists to avoid.
const LOOK_AGAIN = 15000
let timer = null

const load = async () => {
  loading.value = true
  try {
    const answer = await workspace.marketplace()
    unreachable.value = !!answer.unreachable
    data.value = answer
    again(answer)
  } catch (e) {
    error.value = errorText(e)
  } finally {
    loading.value = false
  }
}

const again = (answer) => {
  clearTimeout(timer)
  // Only while something is actually running: a page left open on a workspace
  // with nothing installing should cost nothing.
  if (answer?.working) timer = setTimeout(load, LOOK_AGAIN)
}

onBeforeUnmount(() => clearTimeout(timer))

const add = async (space) => {
  adding.value = space.code
  error.value = ''
  try {
    data.value = await workspace.enableSpace(space.code)
    again(data.value)
    // The server pulled the manifest before answering, so the space is really
    // there; the shell is what has not heard yet.
    await session.resource.reload()
    if ((session.spaces || []).some((one) => one.space_code === space.code)) {
      notifySuccess(__('{0} is in your workspace', [space.label]))
      router.push({ name: 'Screen', params: { spaceCode: space.code } })
      return
    }
    // Enabled, and its app is still being installed. The card says so now.
    notifySuccess(__('{0} is being added', [space.label]))
  } catch (e) {
    error.value = errorText(e)
  } finally {
    adding.value = ''
  }
}

const askOff = async (space) => {
  offering.value = space
  frees.value = []
  typed.value = ''
  confirming.value = true

  // Asked while the dialog is already open: the switch-off half needs no
  // answer, and waiting for one before drawing anything would make the safe
  // action wait on the dangerous one.
  try {
    const answer = await workspace.removable(space.code)
    frees.value = answer?.apps || []
    workspaceName.value = answer?.workspace_name || ''
  } catch {
    // No offer to remove, then. Switching off still works, which is the half
    // that matters and the half that cannot fail.
  }
}

const switchOff = async () => {
  const space = offering.value
  if (!space) return
  removing.value = space.code
  error.value = ''
  try {
    data.value = await workspace.disableSpace(space.code)
    await session.resource.reload()
    confirming.value = false
    notifySuccess(__('{0} is switched off', [space.label]))
  } catch (e) {
    error.value = errorText(e)
  } finally {
    removing.value = ''
  }
}

const removeIt = async () => {
  const space = offering.value
  if (!space) return
  removingHard.value = true
  removing.value = space.code
  error.value = ''
  try {
    const answer = await workspace.removeSpace(space.code, typed.value.trim())
    data.value = answer
    again(answer)
    await session.resource.reload()
    confirming.value = false
    notifySuccess(
      answer?.removing?.length
        ? __('{0} is being removed', [space.label])
        : __('{0} is switched off', [space.label]),
    )
  } catch (e) {
    error.value = errorText(e)
  } finally {
    removingHard.value = false
    removing.value = ''
  }
}

const redeem = async () => {
  if (!code.value.trim()) return
  redeeming.value = true
  codeError.value = ''
  try {
    const answer = await workspace.redeemClaimCode(code.value.trim())
    data.value = answer
    again(answer)
    code.value = ''
    notifySuccess(__('That code worked. The space is above.'))
  } catch (e) {
    codeError.value = errorText(e)
  } finally {
    redeeming.value = false
  }
}

load()
</script>
