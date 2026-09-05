<template>
  <!--
    Whether to be notified, and what to be emailed about.

    On the account page rather than in workspace settings, because it is a
    person's own answer and not the workspace's — the settings dialog is the
    admin's, and half of a workspace cannot open it at all.

    Frappe's own `Notification Settings` underneath, unchanged: one row per
    user, its own permission rule, and the same email allow-list the desk
    writes. What is ours is that it is legible.
  -->
  <div class="flex flex-col gap-4">
    <div v-if="loading" class="flex flex-col gap-3">
      <Skeleton v-for="n in 3" :key="n" class="h-6 w-full" />
    </div>

    <template v-else>
      <Switch
        label="Notifications"
        description="Assignments, mentions and workspace notices, in the app."
        :model-value="prefs.enabled"
        @update:model-value="save({ enabled: $event })"
      />

      <Switch
        label="Email me as well"
        description="For the kinds ticked below. Off means the app only."
        :model-value="prefs.email"
        :disabled="!prefs.enabled"
        @update:model-value="save({ email: $event })"
      />

      <!--
        An allow-list, drawn as switches rather than as a picker. The framework
        treats an empty table as "email me about nothing", and an empty picker
        reads as "not set up yet" — which is the opposite of what it means.

        Only the kinds that can email. A type whose email something else owns —
        a workspace notice, which the control plane sends itself — never sends
        one from here, and a switch that changes nothing is a switch somebody
        flips once and stops trusting.
      -->
      <div v-if="prefs.email && prefs.enabled" class="flex flex-col gap-3 pl-1">
        <Switch
          v-for="kind in prefs.types"
          :key="kind.name"
          :label="kind.name"
          :model-value="kind.email"
          @update:model-value="toggle(kind, $event)"
        />
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { Skeleton, Switch } from '@/ui'

import { loadPreferences, savePreferences } from '../../lib/notifications'

const loading = ref(true)
const prefs = reactive({ enabled: true, email: true, types: [] })

const apply = (answer) => {
  prefs.enabled = !!answer?.enabled
  prefs.email = !!answer?.email
  prefs.types = answer?.types || []
}

onMounted(async () => {
  try {
    apply(await loadPreferences())
  } finally {
    loading.value = false
  }
})

const save = async (changes) => {
  apply(await savePreferences(changes))
}

// The whole list every time, because the server stores a list and not a set of
// flags: sending one name would be sending "email me about only this".
const toggle = (kind, on) => {
  const wanted = prefs.types
    .filter((one) => (one.name === kind.name ? on : one.email))
    .map((one) => one.name)
  save({ types: JSON.stringify(wanted) })
}
</script>
