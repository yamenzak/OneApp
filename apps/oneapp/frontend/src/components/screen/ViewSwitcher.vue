<template>
  <!--
    Which saved view this screen is showing, and everything you can do to it.

    Frappe CRM puts this in the breadcrumb line rather than in a toolbar, and it
    is the right place: the view you are in *is* where you are, so it belongs
    with the rest of the trail rather than beside the filter controls. What sits
    behind it is the framework's own model — a named layout that belongs to one
    person or to the whole workspace — not CRM's parallel invention.

    Vocabulary, because three words are close enough to swap by accident: a
    **space** holds **screens**, a screen is looked at through a **view type**
    (list, board, …), and a saved arrangement of one is a **view** — a `layout`
    in the code, which is what Frappe's own framework calls it.
  -->
  <!--
    A named region, because the word in this button is also the word on a
    navigation tab: "Open" the screen and "Open" the view read identically to
    anything looking for one of them by name, a screen reader included.
  -->
  <div role="group" aria-label="Saved views" class="flex min-w-0 items-center">
    <span class="mx-0.5 text-base text-ink-gray-4" aria-hidden="true">/</span>
    <Dropdown :options="options">
      <template #default="{ open }">
        <Button
          variant="ghost"
          class="min-w-0"
          :label="label"
          :icon-right="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
        />
      </template>
    </Dropdown>
  </div>

  <!--
    Naming a view, whether it is a new one or a rename. One dialog for both
    because they ask the same question, and the only other thing worth asking
    at the same time is who it is for.
  -->
  <Dialog v-model="naming" :title="renaming ? 'Rename this view' : 'Save as a new view'">
    <form class="flex flex-col gap-4" @submit.prevent="confirmName">
      <FormControl
        v-model="draftLabel"
        type="text"
        label="Name"
        placeholder="Overdue and mine"
        autocomplete="off"
      />
      <FormControl
        v-if="canShare"
        v-model="draftShared"
        type="checkbox"
        label="Everyone on this workspace can use it"
        description="Otherwise it is yours alone. Sharing does not widen what the view can reach."
      />
    </form>
    <template #actions>
      <Button
        variant="solid"
        label="Save"
        :loading="busy"
        :disabled="!draftLabel.trim()"
        @click="confirmName"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Dialog, Dropdown, FormControl } from '@/ui'

const props = defineProps({
  // [{ name, label, shared, mine, is_default, opens }]
  layouts: { type: Array, default: () => [] },
  active: { type: String, default: '' },
  /**
   * How the screen is being drawn — "List", "Board". That is what "no saved
   * view" reads as, because the crumb before this one already says which
   * screen it is and saying it twice is not a trail.
   */
  viewLabel: { type: String, default: 'List' },
  canShare: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits(['open', 'save-as', 'rename', 'share', 'default', 'remove'])

const naming = ref(false)
const renaming = ref(false)
const draftLabel = ref('')
const draftShared = ref(false)

const current = computed(() => props.layouts.find((l) => l.name === props.active) || null)

// The view type when nothing is saved, so the line always reads as somewhere
// rather than as an empty control.
const label = computed(() => current.value?.label || props.viewLabel)

// Only a view you may write can be renamed, shared or deleted — and the server
// says the same thing again, because a menu is not a permission.
const writable = computed(() => !!current.value && (current.value.mine || props.canShare))

const askName = (rename) => {
  renaming.value = rename
  draftLabel.value = rename ? current.value?.label || '' : ''
  draftShared.value = rename ? !!current.value?.shared : false
  naming.value = true
}

const confirmName = () => {
  const name = draftLabel.value.trim()
  if (!name) return
  emit(renaming.value ? 'rename' : 'save-as', { label: name, shared: draftShared.value })
  naming.value = false
}

const options = computed(() => {
  const groups = []
  const mine = props.layouts.filter((l) => !l.shared)
  const shared = props.layouts.filter((l) => l.shared)

  const entry = (layout) => ({
    label: layout.label || 'Untitled view',
    selected: layout.name === props.active,
    // `opens`, not `is_default`: a personal default and a shared one can both
    // be set, and only one of them is what this screen actually opens with.
    icon: layout.opens ? 'lucide-pin' : undefined,
    onClick: () => emit('open', layout.name),
  })

  // The screen as its author wrote it is always reachable, and is what an empty
  // selection means. Without it there is no way back from a saved view except
  // deleting it.
  groups.push({
    group: 'Views',
    hideLabel: true,
    options: [
      {
        label: props.viewLabel,
        selected: !props.active,
        onClick: () => emit('open', ''),
      },
    ],
  })
  if (mine.length) groups.push({ group: 'Mine', options: mine.map(entry) })
  if (shared.length) groups.push({ group: 'Shared', options: shared.map(entry) })

  const actions = [
    { label: 'Save as a new view', icon: 'lucide-plus', onClick: () => askName(false) },
  ]
  if (writable.value) {
    actions.push({ label: 'Rename', icon: 'lucide-pencil', onClick: () => askName(true) })
    if (props.canShare) {
      actions.push({
        label: current.value.shared ? 'Make it mine alone' : 'Share with the workspace',
        icon: current.value.shared ? 'lucide-lock' : 'lucide-users',
        onClick: () => emit('share', !current.value.shared),
      })
    }
    if (!current.value.opens) {
      actions.push({
        label: 'Open this screen with it',
        icon: 'lucide-pin',
        onClick: () => emit('default'),
      })
    }
  }
  groups.push({ group: 'Actions', hideLabel: true, options: actions })

  if (writable.value) {
    groups.push({
      group: 'Delete',
      hideLabel: true,
      theme: 'red',
      options: [
        { label: 'Delete this view', icon: 'lucide-trash-2', onClick: () => emit('remove') },
      ],
    })
  }
  return groups
})
</script>
