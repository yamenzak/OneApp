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
        >
          <!-- A view's own icon, where it has one. The prefix slot rather than
               `icon-left`, because an emoji is text and not a class. -->
          <template v-if="current?.icon" #prefix>
            <Icon :name="current.icon" class="size-4 text-ink-gray-7" />
          </template>
          {{ label }}
        </Button>
      </template>
    </Dropdown>
  </div>

  <!--
    Naming a view, whether it is a new one or a rename. One dialog for both
    because they ask the same question, and the only other thing worth asking
    at the same time is who it is for.
  -->
  <Dialog v-model="naming" :title="editing ? 'Rename this view' : 'Save as a new view'">
    <form class="flex flex-col gap-4" @submit.prevent="confirmName">
      <!--
        The icon against the name, which is the shape Frappe CRM uses and the
        right one: they are the two halves of what a view is called. A view is
        worth an icon at all because a menu of five names is a list to read,
        and a menu of five icons is a list to recognise.
      -->
      <div class="flex items-end gap-2">
        <IconPicker v-model="draftIcon" />
        <FormControl
          v-model="draftLabel"
          type="text"
          class="flex-1"
          label="Name"
          placeholder="Overdue and mine"
          autocomplete="off"
        />
      </div>
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
import { Button, Dialog, Dropdown, FormControl, Icon } from '@/ui'
import IconPicker from './IconPicker.vue'

const props = defineProps({
  // [{ name, label, icon, shared, mine, is_default, opens }]
  layouts: { type: Array, default: () => [] },
  active: { type: String, default: '' },
  /**
   * How the screen is being drawn — "List", "Board". That is what "no saved
   * view" reads as, because the crumb before this one already says which
   * screen it is and saying it twice is not a trail.
   */
  viewLabel: { type: String, default: 'List' },
  canShare: { type: Boolean, default: false },
  // Whether there is something on screen that no view is carrying yet. It
  // decides whether a view offers to take it.
  dirty: { type: Boolean, default: false },
  // How many shared views this person has hidden. They are not in the list —
  // that is what hiding them did — so the only way back is a count and an
  // offer to undo all of it.
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
 * What one view offers.
 *
 * A submenu rather than a row that only opens it, because this menu is now the
 * only place a view is managed — it used to be here for the one you were in
 * and nowhere at all for the rest, so renaming another view meant opening it
 * first. Opening is the submenu's first item and stays one gesture away.
 */
const submenuFor = (view) => {
  const mayWrite = writable(view)
  const items = []
  if (view.name !== props.active) {
    items.push({
      label: 'Open it', icon: 'lucide-corner-down-right',
      onClick: () => emit('open', view.name),
    })
  }
  // Overwriting a view with what is on screen, which is the other half of
  // "save": one of these, or a new view. Offered per view rather than only for
  // the one you are in, so a change made while looking at one view can be put
  // into another without opening it first.
  if (props.dirty && mayWrite) {
    items.push({
      label: 'Save the changes here', icon: 'lucide-bookmark',
      onClick: () => emit('save-into', view.name),
    })
  }
  if (mayWrite) {
    items.push({ label: 'Rename', icon: 'lucide-pencil', onClick: () => askName(view) })
    if (props.canShare) {
      items.push({
        label: view.shared ? 'Make it mine alone' : 'Share with the workspace',
        icon: view.shared ? 'lucide-lock' : 'lucide-users',
        onClick: () => emit('share', { layout: view.name, shared: !view.shared }),
      })
    }
    // `opens`, not `is_default`: a personal default and a shared one can both
    // be set, and only one of them actually opens the screen.
    if (!view.opens) {
      items.push({
        label: 'Open this screen with it', icon: 'lucide-pin',
        onClick: () => emit('default', view.name),
      })
    }
  }
  // Hiding is for a view somebody else shared and you would rather not see.
  // Never for your own — you made it, and deleting is what you want — and
  // never instead of deleting, because a shared view is somebody else's too.
  if (view.shared) {
    items.push({
      label: 'Hide it from my menu', icon: 'lucide-eye-off',
      onClick: () => emit('hide', view.name),
    })
  }
  if (mayWrite) {
    items.push({
      label: 'Delete it', icon: 'lucide-trash-2', theme: 'red',
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
    label: view.label || 'Untitled view',
    selected: view.name === props.active,
    // The view's own icon where it has one; the pin where it does not and this
    // is the one the screen opens with.
    icon: view.icon || (view.opens ? 'lucide-pin' : undefined),
    submenu: submenuFor(view),
  })

  // The screen as its author wrote it is always reachable, and is what an empty
  // selection means. Without it there is no way back from a saved view except
  // deleting it. No submenu: there is nothing to manage about a screen.
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
    { label: 'Save as a new view', icon: 'lucide-plus', onClick: () => askName(null) },
  ]
  // All of them at once. A hidden view is not in this menu — that is what
  // hiding it did — so this menu is the wrong place to pick one out of.
  if (props.hidden) {
    actions.push({
      label: props.hidden === 1 ? 'Show the hidden view' : `Show ${props.hidden} hidden views`,
      icon: 'lucide-eye',
      onClick: () => emit('show'),
    })
  }
  groups.push({ group: 'Actions', hideLabel: true, options: actions })
  return groups
})
</script>
