<template>
  <!--
    Your own name, photograph and the two regional settings that are yours
    rather than the workspace's.

    The first tab in this dialog a member can open. Everything else under
    Workspace is the workspace's, so before this a colleague who was not an
    admin had nowhere at all to change their own name.
  -->
  <SettingsHeader
    title="Profile"
    description="Your name and how you are reached."
    :class="PANEL_HEADER"
  />

  <SettingsBody :class="PANEL_BODY">
    <div v-if="!loaded" class="grid place-items-center py-16">
      <LoadingIndicator class="size-5 text-ink-gray-5" />
    </div>

    <div v-else class="flex flex-col gap-5 pt-6">
      <!-- The address, shown and not offered. It is the account's identity and
           the seat is counted against it upstream, so changing it is a
           control-plane act rather than a field. A profile with no address on
           it looks like it forgot. -->
      <div class="flex items-center gap-3">
        <Avatar size="2xl" :label="data.full_name" :image="picture" />
        <div class="min-w-0">
          <p class="truncate text-p-base font-medium text-ink-gray-8">{{ data.full_name }}</p>
          <p class="truncate text-p-sm text-ink-gray-5">{{ data.email }}</p>
        </div>
      </div>

      <!-- A photograph is picked, not typed. It was a text box here for
           exactly as long as it took to notice: the ternary above it chose
           between 'text' and 'text'. -->
      <SettingsAttach
        v-for="field in files"
        :key="field.key"
        v-model="draft[field.key]"
        :label="field.label"
        :hint="field.hint"
        image
      />

      <FormControl
        v-for="field in text"
        :key="field.key"
        v-model="draft[field.key]"
        type="text"
        :label="field.label"
        :description="field.hint"
        :data-slot="`profile-${field.key}`"
      />

      <FormControl
        v-for="field in chosen"
        :key="field.key"
        v-model="draft[field.key]"
        type="select"
        :label="field.label"
        :options="offered(field)"
        :description="follows(field)"
        :data-slot="`profile-${field.key}`"
      />
    </div>
  </SettingsBody>

  <div :class="PANEL_FOOTER">
    <Button
      variant="solid"
      label="Save"
      data-slot="profile-save"
      :loading="saving"
      :disabled="!changed"
      @click="save"
    />
    <span v-if="changed" class="text-p-sm text-ink-gray-5">Unsaved changes</span>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { Avatar, Button, FormControl, LoadingIndicator, SettingsBody, SettingsHeader } from '@/ui'
import SettingsAttach from './SettingsAttach.vue'
import { PANEL_BODY, PANEL_FOOTER, PANEL_HEADER } from './geometry'
import { workspace } from '@/lib/workspace'
import { session } from '@/lib/shell/session'

const data = ref(null)
const draft = reactive({})
const saving = ref(false)

const loaded = computed(() => Boolean(data.value))
const fields = computed(() => data.value?.fields || [])

// Three shapes: a file is picked, a Select needs its options, everything else
// is a box. Split off the server's declared type rather than off the key, so a
// field added to `me.MINE` gets the right control without an edit here.
const isFile = (one) => one.type === 'Attach' || one.type === 'Attach Image'

const files = computed(() => fields.value.filter(isFile))
const chosen = computed(() => fields.value.filter((one) => one.type === 'Select'))
const text = computed(() =>
  fields.value.filter((one) => !isFile(one) && one.type !== 'Select'),
)

const picture = computed(() => draft.user_image || '')

const changed = computed(() =>
  fields.value.some((one) => (draft[one.key] || '') !== (one.value || '')),
)

/** Empty first, so "follows the workspace" is a choice somebody can make again. */
const offered = (field) => [
  { value: '', label: 'Follow the workspace' },
  ...(field.options || []).map((one) =>
    (typeof one === 'string' ? { value: one, label: one } : one),
  ),
]

const follows = (field) => {
  const theirs = data.value?.workspace?.[field.key]
  return draft[field.key] || !theirs ? field.hint : `${field.hint} Currently ${theirs}.`
}

async function load() {
  data.value = await workspace.profile()
  for (const one of data.value.fields) draft[one.key] = one.value || ''
}

async function save() {
  saving.value = true
  try {
    await workspace.saveProfile(
      Object.fromEntries(fields.value.map((one) => [one.key, draft[one.key] || ''])),
    )
    // Read back rather than trusting what `save` returned, which is the
    // convention every other panel here follows — and the one that survives
    // `callMethod` handing back something other than the endpoint's own dict,
    // which emptied this panel the moment anybody saved.
    await load()
    // The shell draws the name and the avatar from the session, so a rename
    // that does not reach it leaves the rail disagreeing with the dialog.
    session.reload()
  } finally {
    saving.value = false
  }
}

load()
</script>
