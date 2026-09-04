<template>
  <!--
    Who wrote this, as a person.

    A list that says `h.nasser@alreem-consultants.ae` and a list that says
    **Hala Nasser** with her face beside it are the same data and not the same
    product. The image is one we hold on the Contact, or initials — never a
    third-party avatar service, because those work by sending a hash of every
    correspondent's address to a company the customer has never heard of.
  -->
  <HoverCard v-if="card" v-model:open="open">
    <template #trigger>
      <span class="flex min-w-0 items-center gap-2" data-slot="mail-sender">
        <Avatar :image="who.image" :label="who.label || sender" size="sm" />
        <span class="min-w-0 truncate" :class="nameClass">{{ who.label || sender }}</span>
      </span>
    </template>
    <div class="flex w-64 flex-col gap-2 p-1">
      <div class="flex items-center gap-2">
        <Avatar :image="who.image" :label="who.label || sender" size="lg" />
        <div class="flex min-w-0 flex-col">
          <span class="truncate text-base font-medium text-ink-gray-8">
            {{ who.label || sender }}
          </span>
          <span class="truncate text-p-xs text-ink-gray-5">{{ sender }}</span>
        </div>
      </div>

      <!-- Only what there is. A card with three empty rows labelled Company,
           Role and Phone says less than a card with none. -->
      <div v-if="detail.length" class="flex flex-col gap-0.5">
        <span v-for="line in detail" :key="line" class="truncate text-p-xs text-ink-gray-6">
          {{ line }}
        </span>
      </div>

      <div v-if="loaded?.threads?.length" class="flex flex-col gap-0.5 border-t border-outline-gray-1 pt-2">
        <span class="text-p-xs font-medium uppercase tracking-wide text-ink-gray-5">
          Recent
        </span>
        <RouterLink
          v-for="one in loaded.threads"
          :key="one.key"
          :to="{ name: 'Mail', query: { folder: 'all', thread: one.key } }"
          class="truncate text-p-xs text-ink-gray-7 hover:text-ink-gray-8"
        >
          {{ one.subject }}
        </RouterLink>
      </div>

      <span v-else-if="looking" class="text-p-xs text-ink-gray-5">Looking…</span>
    </div>
  </HoverCard>

  <span v-else class="flex min-w-0 items-center gap-2" data-slot="mail-sender">
    <Avatar :image="who.image" :label="who.label || sender" size="sm" />
    <span class="min-w-0 truncate" :class="nameClass">{{ who.label || sender }}</span>
  </span>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { Avatar, HoverCard } from '@/ui'
import { workspace } from '../lib/workspace'

const props = defineProps({
  /** The address it came from — the fallback, and always the truth. */
  sender: { type: String, default: '' },
  /** What the list already resolved: label, image, company, designation. */
  who: { type: Object, default: () => ({}) },
  /** Whether hovering opens a card. Off in a dense list of fifty rows. */
  card: { type: Boolean, default: false },
  nameClass: { type: String, default: '' },
})

const open = ref(false)
const loaded = ref(null)
const looking = ref(false)

// Fetched when the card first opens, not with the list: the recent
// conversations are a query per sender, and fifty rows would be fifty of them
// for a card almost nobody opens.
watch(open, (isOpen) => {
  if (isOpen) look()
})

const detail = computed(() =>
  [
    [props.who.designation, props.who.company].filter(Boolean).join(' · '),
    props.who.phone,
  ].filter(Boolean),
)

async function look() {
  if (loaded.value || looking.value || !props.sender) return
  looking.value = true
  try {
    loaded.value = await workspace.mailProfile(props.sender)
  } finally {
    looking.value = false
  }
}
</script>
