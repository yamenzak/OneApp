<template>
  <!--
    Which roles one person holds. A list of tick boxes, because the answer is
    usually more than one — the person who raises invoices and answers the phone
    — and a dropdown that allows one is a model that decides that for them.

    Grouped by the app a role came from, with the workspace's own roles last:
    those are the ones somebody here wrote, so they are the ones somebody here
    is looking for.
  -->
  <div class="flex flex-col gap-3">
    <div>
      <p class="text-p-sm text-ink-gray-7">Can do</p>
      <p class="text-p-xs text-ink-gray-5">
        Everyone gets the basics of each app this workspace has. Tick anything
        more this person needs.
      </p>
    </div>

    <div v-for="group in groups" :key="group.key" class="flex flex-col gap-1.5">
      <p class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
        {{ group.label }}
      </p>
      <Checkbox
        v-for="role in group.roles"
        :key="role.key"
        :model-value="held.includes(role.key)"
        :label="role.label"
        :disabled="role.is_default"
        :description="role.is_default
          ? 'Everyone in this workspace has this'
          : role.description || undefined"
        padded
        @update:model-value="toggle(role.key, $event)"
      />
    </div>

    <p v-if="!groups.length" class="text-p-sm text-ink-gray-5">
      This workspace has no apps yet, so there is nothing to hand out.
    </p>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Checkbox } from '@/ui'

const props = defineProps({
  /** Every role on offer, from `customer.roles`. */
  roles: { type: Array, default: () => [] },
})

// The keys this person holds. A default is never in here — it arrives with the
// entitlement, and storing it would leave it behind on everybody the day the
// app stops shipping it.
const held = defineModel({ type: Array, default: () => [] })

const groups = computed(() => {
  const spaces = new Map()
  const custom = []
  for (const role of props.roles) {
    if (role.custom) {
      custom.push(role)
      continue
    }
    const key = role.space || ''
    if (!spaces.has(key)) {
      spaces.set(key, { key, label: role.space_label || key, roles: [] })
    }
    spaces.get(key).roles.push(role)
  }
  const out = [...spaces.values()]
  if (custom.length) out.push({ key: '__custom', label: 'Your own roles', roles: custom })
  return out
})

const toggle = (key, on) => {
  const next = new Set(held.value || [])
  if (on) next.add(key)
  else next.delete(key)
  held.value = [...next]
}
</script>
