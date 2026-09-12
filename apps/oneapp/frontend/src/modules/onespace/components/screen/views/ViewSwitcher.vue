<template>
  <!--
    Which saved view this screen is showing, and everything you can do to it.

    In the breadcrumb line rather than a toolbar, as Frappe CRM has it: the view
    you are in *is* where you are. What sits behind it is the framework's own
    model — a named layout belonging to one person or to the workspace.

    Vocabulary, because three words are close enough to swap by accident: a
    **space** holds **screens**, a screen is looked at through a **view type**,
    and a saved arrangement of one is a **view** — a `layout` in the code.
  -->
  <!--
    A named region, because the word in this button is also the word on a
    navigation tab: "Open" the screen and "Open" the view read identically to
    anything looking for one of them by name.
  -->
  <div role="group" :aria-label="__('Saved views')" class="flex min-w-0 items-center">
    <span class="mx-0.5 text-base text-ink-gray-4" aria-hidden="true">/</span>
    <Dropdown :options="options">
      <template #default="{ open }">
        <Button
          variant="ghost"
          class="min-w-0"
          :label="label"
          :icon-right="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
        >
          <!-- A view's own icon, where it has one. The prefix slot rather than
               `icon-left`, because an emoji is text and not a class. -->
          <template v-if="current?.icon" #prefix>
            <Icon :name="current.icon" class="size-4 text-ink-secondary" />
          </template>
          {{ label }}
        </Button>
      </template>
    </Dropdown>
  </div>

  <!-- Naming a view, whether new or a rename: one dialog, because they ask the
       same question. -->
  <Dialog v-model="naming" :title="editing ? __('Rename this view') : __('Save as a new view')">
    <form class="flex flex-col gap-4" @submit.prevent="confirmName">
      <!-- The icon against the name, which is the shape Frappe CRM uses: they
           are the two halves of what a view is called. A menu of five names is
           a list to read, and five icons a list to recognise. -->
      <div class="flex items-end gap-2">
        <IconPicker v-model="draftIcon" />
        <FormControl
          v-model="draftLabel"
          type="text"
          class="flex-1"
          :label="__('Name')"
          :placeholder="__('Overdue and mine')"
          autocomplete="off"
        />
      </div>
      <FormControl
        v-if="canShare"
        v-model="draftShared"
        type="checkbox"
        :label="__('Everyone on this workspace can use it')"
        :description="__('Otherwise it is yours alone. Sharing does not widen what the view can reach.')"
      />
    </form>
    <template #actions>
      <Button
        variant="solid"
        :label="__('Save')"
        :loading="busy"
        :disabled="!draftLabel.trim()"
        @click="confirmName"
      />
    </template>
  </Dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Button, Dialog, Dropdown, FormControl, Icon } from '@/ui'
import IconPicker from '@/modules/onespace/components/screen/fields/IconPicker.vue'
import { __ } from '@/shared/lib/runtime/translate'

const props = defineProps({
  // [{ name, label, icon, shared, mine, is_default, opens }]
  layouts: { type: Array, default: () => [] },
  active: { type: String, default: '' },
  /** How the screen is being drawn — "List", "Board". That is what "no saved
   *  view" reads as, because the crumb before this already says which screen. */
  viewLabel: { type: String, default: 'List' },
  canShare: { type: Boolean, default: false },
  // Whether there is something on screen that no view is carrying yet.
  dirty: { type: Boolean, default: false },
  // How many shared views this person has hidden. They are not in the list, so
  // the only way back is a count and an offer to undo all of it.
  hidden: { type: Number, default: 0 },
  busy: { type: Boolean, default: false },
})
const emit = defineEmits([
  'open', 'save-as', 'save-into', 'rename', 'share', 'default', 'remove', 'hide', 'show',
])

const naming = ref(false)
// Which view is being renamed, or null for a new one.
const editing = ref(null)
const draftLabel = ref('')
const draftIcon = ref('')
const draftShared = ref(false)

const current = computed(() => props.layouts.find((l) => l.name === props.active) || null)

// The view type when nothing is saved, so the line always reads as somewhere
// rather than as an empty control.
const label = computed(() => current.value?.label || props.viewLabel)

// Only a view you may write can be renamed, shared or deleted — and the server
// says the same thing again, because a menu is not a permission.
const writable = (view) => !!view && (view.mine || props.canShare)

const askName = (view) => {
  editing.value = view || null
  draftLabel.value = view?.label || ''
  draftIcon.value = view?.icon || ''
  draftShared.value = !!view?.shared
  naming.value = true
}

const confirmName = () => {
  const name = draftLabel.value.trim()
  if (!name) return
  const payload = { label: name, icon: draftIcon.value, shared: draftShared.value }
  if (editing.value) emit('rename', { layout: editing.value.name, ...payload })
  else emit('save-as', payload)
  naming.value = false
}

/**
 * What one view offers. A submenu rather than a row that only opens it, because
 * this menu is the only place a view is managed — renaming another view used to
 * mean opening it first.
 */
const submenuFor = (view) => {
  const mayWrite = writable(view)
  const items = []
  if (view.name !== props.active) {
    items.push({
      label: __('Open it'), icon: 'lucide-corner-down-right',
      onClick: () => emit('open', view.name),
    })
  }
  // Overwriting a view with what is on screen, the other half of "save".
  // Offered per view rather than only for the one you are in, so a change can
  // be put into another without opening it first.
  if (props.dirty && mayWrite) {
    items.push({
      label: __('Save the changes here'), icon: 'lucide-bookmark',
      onClick: () => emit('save-into', view.name),
    })
  }
  if (mayWrite) {
    items.push({ label: __('Rename'), icon: 'lucide-pencil', onClick: () => askName(view) })
    if (props.canShare) {
      items.push({
        label: view.shared ? __('Make it mine alone') : __('Share with the workspace'),
        icon: view.shared ? 'lucide-lock' : 'lucide-users',
        onClick: () => emit('share', { layout: view.name, shared: !view.shared }),
      })
    }
    // `opens`, not `is_default`: a personal default and a shared one can both
    // be set, and only one actually opens the screen.
    if (!view.opens) {
      items.push({
        label: __('Open this screen with it'), icon: 'lucide-pin',
        onClick: () => emit('default', view.name),
      })
    }
  }
  // Hiding is for a view somebody else shared. Never for your own — you made
  // it, and deleting is what you want — and never instead of deleting.
  if (view.shared) {
    items.push({
      label: __('Hide it from my menu'), icon: 'lucide-eye-off',
      onClick: () => emit('hide', view.name),
    })
  }
  if (mayWrite) {
    items.push({
      label: __('Delete it'), icon: 'lucide-trash-2', theme: 'red',
      onClick: () => emit('remove', view.name),
    })
  }
  return items
}

const options = computed(() => {
  const groups = []
  const mine = props.layouts.filter((l) => !l.shared)
  const shared = props.layouts.filter((l) => l.shared)

  const entry = (view) => ({
    label: view.label || __('Untitled view'),
    selected: view.name === props.active,
    // The view's own icon where it has one; the pin where it does not and this
    // is the one the screen opens with.
    icon: view.icon || (view.opens ? 'lucide-pin' : undefined),
    submenu: submenuFor(view),
  })

  // The screen as its author wrote it is always reachable, and is what an empty
  // selection means. No submenu: there is nothing to manage about a screen.
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
  if (mine.length) groups.push({ group: __('Mine'), options: mine.map(entry) })
  if (shared.length) groups.push({ group: __('Shared'), options: shared.map(entry) })

  const actions = [
    { label: __('Save as a new view'), icon: 'lucide-plus', onClick: () => askName(null) },
  ]
  // All of them at once. A hidden view is not in this menu, so this menu is the
  // wrong place to pick one out of.
  if (props.hidden) {
    actions.push({
      label: props.hidden === 1
        ? __('Show the hidden view')
        : __('Show {0} hidden views', [props.hidden]),
      icon: 'lucide-eye',
      onClick: () => emit('show'),
    })
  }
  groups.push({ group: 'Actions', hideLabel: true, options: actions })
  return groups
})
</script>
