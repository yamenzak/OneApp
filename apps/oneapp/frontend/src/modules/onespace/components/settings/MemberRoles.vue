<template>
  <!--
    What one person may do inside the apps, beside their name.

    Two kinds of row and the difference is the whole design. A space's
    **default** role arrives with the entitlement — having OneMobility means
    every member can open OneMobility — so it is shown as already given and
    cannot be unticked. Unticking it would mean nothing: the next sync puts it
    straight back, and a control that undoes itself is worse than no control.
    Everything else is a real choice.

    A popover rather than a select, because a person holds a set and not one
    thing, and rather than chips on the row because a workspace with four apps
    has a dozen roles and a dozen chips per person is a wall.

    Saved on each tick, the same as the access select beside it. There is no
    Save in these rows and there should not be one — a settings row that needs
    confirming is a row people leave half-changed.
  -->
  <Popover v-model:open="open">
    <template #trigger>
      <Button
        data-slot="member-roles"
        class="max-w-40 shrink-0"
        icon-right="lucide-chevron-down"
        :label="summary"
        :disabled="disabled"
        :loading="saving"
      />
    </template>

    <template #default>
      <div class="flex max-h-96 w-72 flex-col gap-3 overflow-y-auto p-3">
        <section v-if="given.length" class="flex flex-col gap-1.5">
          <p class="text-p-xs text-ink-gray-5">{{ __('Comes with the app') }}</p>
          <div
            v-for="role in given"
            :key="role.key"
            class="flex items-center gap-2 text-p-sm text-ink-gray-6"
          >
            <Icon name="lucide-check" class="size-4 shrink-0 text-ink-gray-4" />
            <span class="truncate">{{ role.label }}</span>
          </div>
        </section>

        <section v-for="group in groups" :key="group.key" class="flex flex-col gap-1.5">
          <p class="text-p-xs text-ink-gray-5">{{ group.label }}</p>
          <Checkbox
            v-for="role in group.roles"
            :key="role.key"
            :model-value="held.includes(role.key)"
            :label="role.label"
            @update:model-value="toggle(role.key, $event)"
          />
        </section>

        <p v-if="!given.length && !groups.length" class="text-p-sm text-ink-gray-5">
          {{ __('This workspace has no apps yet, so there is nothing to hand out.') }}
        </p>
      </div>
    </template>
  </Popover>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Checkbox, Icon, Popover } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  // Every role this workspace may hand out: {key, label, space, space_label,
  // is_default, custom}. Sent with the members, because the two are read
  // together — you are looking at a person to decide what they may do.
  roles: { type: Array, default: () => [] },
  // The keys this person holds, minus any naming a role no longer offered.
  held: { type: Array, default: () => [] },
  disabled: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(['change'])

const open = ref(false)

const given = computed(() => props.roles.filter((one) => one.is_default))

/** The tickable ones, by the space they came from — and ours last. */
const groups = computed(() => {
  const byspace = new Map()
  const mine = []

  for (const role of props.roles) {
    if (role.is_default) continue
    if (role.custom) {
      mine.push(role)
      continue
    }
    const key = role.space || ''
    if (!byspace.has(key)) {
      byspace.set(key, { key, label: role.space_label || key, roles: [] })
    }
    byspace.get(key).roles.push(role)
  }

  // Last, because the shipped ones are the answer most of the time and the
  // workspace's own are the exception it built for itself.
  return [...byspace.values(), ...(mine.length
    ? [{ key: 'custom', label: __('Roles you made'), roles: mine }]
    : [])]
})

const chosen = computed(() =>
  props.roles.filter((one) => !one.is_default && props.held.includes(one.key)),
)

// What the button says. The defaults are not counted: everybody has them, so
// a number that never goes below three tells nobody anything.
const summary = computed(() => {
  const picked = chosen.value
  if (!picked.length) return __('Default access')
  if (picked.length === 1) return picked[0].label
  return __('{0} roles', [picked.length])
})

const toggle = (key, on) => {
  const next = on
    ? [...props.held, key]
    : props.held.filter((one) => one !== key)
  emit('change', [...new Set(next)])
}
</script>
