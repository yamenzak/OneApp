<template>
  <!--
    Whether to be notified, and where each kind of notification arrives.

    Two masters and then a row per kind, because "notify me" and "how" are
    different questions: somebody wants assignments in the app and by email,
    and changes to a document they follow in the app only. One switch per kind
    could not say that — it meant email, and the app half was a single switch
    for everything.

    The kinds come from the server's registry (`onespace/notifications.py`),
    so a notification declared anywhere in the product appears here without an
    edit to this file.
  -->
  <div class="flex flex-col gap-4">
    <div v-if="loading" class="flex flex-col gap-3">
      <Skeleton v-for="n in 3" :key="n" class="h-6 w-full" />
    </div>

    <template v-else>
      <Switch
        :label="__('Notifications')"
        :description="__('Assignments, mentions and workspace notices, in the app.')"
        :model-value="prefs.enabled"
        @update:model-value="save({ enabled: $event })"
      />

      <Switch
        :label="__('Email me as well')"
        :description="__('Off means the app only, whatever is ticked below.')"
        :model-value="prefs.email"
        :disabled="!prefs.enabled"
        @update:model-value="save({ email: $event })"
      />

      <div v-if="prefs.enabled" class="flex flex-col gap-3">
        <div
          v-for="kind in prefs.types"
          :key="kind.name"
          class="flex flex-wrap items-center justify-between gap-3"
          data-slot="notification-kind"
        >
          <div class="min-w-0 flex-1">
            <p class="text-base text-ink-gray-8">{{ kind.name }}</p>
            <p class="text-p-sm text-ink-gray-5">{{ kind.about }}</p>
          </div>

          <!--
            A button each, not a Select and not one switch: the channels are
            independent, and a control that reads "In app, Email" at a glance
            is the answer to "where does this reach me" without opening
            anything. Solid is on; a channel that cannot be offered is disabled
            with the reason on it, because a missing control explains nothing.
          -->
          <div class="flex shrink-0 items-center gap-1">
            <Button
              v-for="channel in channels"
              :key="channel.key"
              size="sm"
              :variant="kind[channel.key] ? 'solid' : 'subtle'"
              :label="channel.label"
              :disabled="!offered(kind, channel)"
              :tooltip="reason(kind, channel)"
              :data-slot="`channel-${kind.name}-${channel.key}`"
              @click="flip(kind, channel)"
            />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Button, Skeleton, Switch } from '@/ui'

import { loadPreferences, savePreferences, setChannel } from '@/modules/onespace/lib/shell/notifications'
import { __ } from '@/shared/lib/runtime/translate'

/** The three the panel names. Push is offered and refused — see `reason`. */
const channels = computed(() => [
  { key: 'in_app', label: __('In app') },
  { key: 'email', label: __('Email') },
  { key: 'push', label: __('Push') },
])

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

/** Whether this channel can be pressed at all for this kind. */
const offered = (kind, channel) => {
  if (channel.key === 'in_app') return true
  if (channel.key === 'email') return prefs.email && kind.can_email
  return kind.can_push
}

/**
 * Why not, when not. Said on the control rather than by hiding it: "we do not
 * do this yet" is a more useful answer than a button nobody can find.
 */
const reason = (kind, channel) => {
  if (offered(kind, channel)) return ''
  if (channel.key === 'push') return __('Push notifications are not available yet')
  if (!prefs.email) return __('Turn on “Email me as well” first')
  return __('This one is emailed for you rather than by you')
}

const flip = async (kind, channel) => {
  apply(await setChannel(kind.name, channel.key, !kind[channel.key]))
}
</script>
