<template>
  <!--
    The mail rail *is* the sidebar, not a third column beside it.

    Mail is not inside a space, so on this route the shell's sidebar has nothing
    space-shaped to show, and drawing the workspace's list beside a mailbox list
    gave the page two navigation columns arguing about which one you were in.
  -->
  <Sidebar
    v-model:collapsed="folded"
    :width="windowed ? `${WINDOW_RAIL}px` : `${width}px`"
    class="border-e border-outline-gray-1"
  >
    <!-- No header. The bar's corner names the workspace directly above this and
         the trail beside it names where you are, so a header here was a third
         telling of the same two words — and its own dropdown, which read as a
         second switcher. -->

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pb-6">
      <nav class="space-y-0.5">
        <!-- An address, and under it that mailbox's own folders — the
             Applicants and Suppliers somebody spent years sorting into. Read
             off the server itself; see `onemail/folders.py`. -->
        <template v-for="one in shown" :key="one.key">
          <SidebarItem
            :icon="one.icon"
            :to="windowed ? undefined : { name: 'Mail', query: { folder: one.key } }"
            :active="at === one.key"
            @click="windowed && emit('go', { folder: one.key })"
            :class="one.depth ? 'ms-3 border-s border-outline-gray-1 ps-1' : ''"
            data-slot="mail-folder"
          >
            <span class="flex-1 truncate text-sm" :class="one.depth ? SUB : ''">
              {{ one.label }}
            </span>
            <template v-if="one.unread || !one.depth" #suffix>
              <Badge v-if="one.unread" theme="blue" :label="String(one.unread)" />
              <!--
                A folder belongs to a mailbox, so making one is an action on that
                mailbox. In `#suffix` because frappe-ui renders it as a sibling
                of the link: a button inside an anchor is invalid.
              -->
              <Button
                v-if="!one.depth && !collapsed"
                variant="ghost"
                icon="lucide-folder-plus"
                :label="__('New folder in {0}', [one.label])"
                :tooltip="__('New folder in {0}', [one.label])"
                data-slot="mail-new-folder"
                @click="startFolder(one.address)"
              />
            </template>
          </SidebarItem>
        </template>

        <!-- Deleted mail, spam and drafts. Mirrored, because a mirror that
             silently omits folders is one nobody can trust, and behind a click,
             because a rail that opens on somebody's junk is a rail nobody
             wants. -->
        <SidebarItem
          v-if="quiet.length && !collapsed"
          :icon="showQuiet ? 'lucide-chevron-down' : 'lucide-chevron-right'"
          :active="false"
          data-slot="mail-more-folders"
          @click="showQuiet = !showQuiet"
        >
          <span class="flex-1 truncate text-sm text-ink-secondary">
            {{ showQuiet ? __('Fewer folders') : __('More folders') }}
          </span>
        </SidebarItem>
      </nav>
    </ScrollArea>

    <div class="mt-auto shrink-0">
      <div class="flex flex-col gap-1 p-2">
        <!--
          Where mailboxes are added. The rail lists what somebody has; adding one
          is a form with a password in it, which belongs in Settings beside the
          addresses the workspace itself owns.
        -->
        <!-- The *person's* tab, not the workspace's. `mail` is an admin tab
             and a member opening it was shown a door that does not open —
             which is exactly what settings audiences exist to stop. -->
        <SidebarItem
          v-if="!collapsed"
          icon="lucide-plus"
          :active="false"
          data-slot="mail-add-mailbox"
          @click="openSettings('mailbox')"
        >
          <span class="flex-1 truncate text-sm text-ink-secondary">{{ __('Add a mailbox') }}</span>
        </SidebarItem>
        <!-- Everything else about an address — the signature it signs with, the
             away message, where its mail files itself — is one dialog away
             rather than a second set of controls in here. -->
        <SidebarItem
          v-if="!collapsed && mail.folders.length"
          icon="lucide-sliders-horizontal"
          :active="false"
          data-slot="mail-open-settings"
          @click="openSettings('mailbox')"
        >
          <span class="flex-1 truncate text-sm text-ink-secondary">{{ __('Signature and away') }}</span>
        </SidebarItem>
        <SidebarItem
          v-if="mail.mailboxes.length && !collapsed"
          icon="lucide-refresh-cw"
          :active="false"
          data-slot="mail-refresh-folders"
          @click="refreshMail()"
        >
          <span class="flex-1 truncate text-sm text-ink-secondary">
            {{ mail.refreshing ? __('Refreshing…') : __('Refresh folders') }}
          </span>
        </SidebarItem>
      </div>
      <!-- You, the bell and the quota. The shell's own foot, and it belongs
           to the shell's column: in a window it would be a second copy of the
           corner the page behind already draws. -->
      <ShellFoot v-if="!windowed" />
    </div>
  </Sidebar>

  <Dialog v-model="making" :title="__('New folder')">
    <div class="flex flex-col gap-3">
      <!-- Which mailbox is settled by where the button was, not by a dropdown
           in here repeating a choice already made. -->
      <p class="text-p-sm text-ink-secondary">{{ __('In {0}', [draft.address]) }}</p>
      <FormControl v-model="draft.name" :label="__('Name')" :placeholder="__('Applicants')" />
      <!-- Said before it happens rather than discovered afterwards: whether this
           folder will exist in their other mail client depends on whether there
           is a server behind the address. -->
      <p class="text-p-xs text-ink-muted">{{ where }}</p>
      <ErrorMessage v-if="error" :message="error" />
    </div>
    <template #actions>
      <Button variant="solid" :label="__('Make it')" :loading="saving" @click="make()" />
    </template>
  </Dialog>

  <!-- The drag handle is the shell column's, not a window's: this rail is a
       fixed width in here and dragging it would resize the column on every
       page in the product. -->
  <SidebarResizer v-if="!windowed" />
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  Badge,
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  ScrollArea,
  Sidebar,
  SidebarItem,
} from '@/ui'
import ShellFoot from '@/modules/onespace/components/shell/ShellFoot.vue'
import SidebarResizer from '@/modules/onespace/components/SidebarResizer.vue'
import { loadMail, mail, refreshMail } from '@/modules/onespace/lib/shell/mail'
import { workspace } from '@/shared/lib/workspace'
import { openSettings } from '@/modules/onespace/lib/shell/settings'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { __ } from '@/shared/lib/runtime/translate'
import { errorText } from '@/shared/lib/runtime/errors'

const SUB = 'text-ink-secondary'

const props = defineProps({
  /** Drawn inside the mail window rather than as the shell's sidebar. */
  windowed: { type: Boolean, default: false },
  /** Which folder is open, when a window is keeping that rather than the URL. */
  folder: { type: String, default: '' },
})
const emit = defineEmits(['go'])

/**
 * How wide the rail is inside a window.
 *
 * Fixed, and narrower than the shell's: that one is a preference somebody set
 * for the column the whole product shares, and a window is not that column —
 * dragging its edge would resize the rail on every page too. The same answer
 * `DriveSidebar` gives, and for the same reason.
 */
const WINDOW_RAIL = 184

/**
 * Whether the rail is folded away.
 *
 * The shell's own state on the page, and never in a window: the control that
 * collapses this column lives in the shell's bar, which a window does not
 * have — so a window whose rail could fold would be a rail with no way back.
 * A writable computed rather than a ternary, because `v-model` needs
 * somewhere to write to.
 */
const folded = computed({
  get: () => (props.windowed ? false : collapsed.value),
  set: (value) => { if (!props.windowed) collapsed.value = value },
})

const route = useRoute()
const at = computed(() =>
  (props.windowed ? props.folder || 'all' : String(route.query.folder || 'all')))

const showQuiet = ref(false)

const making = ref(false)
const saving = ref(false)
const error = ref('')
const draft = reactive({ address: '', name: '' })

// Whether the address being added to has a server behind it — which decides
// whether this folder exists anywhere but here.
const where = computed(() => {
  const address = draft.address
  const connected = mail.mailboxes.some((one) => one.email_id === address)
  return connected
    ? __('Made on the mail server, so it appears in your other mail apps too.')
    : __('{0} has no mailbox server, so this folder lives in One.', [address])
})

function startFolder(address) {
  draft.address = address
  draft.name = ''
  error.value = ''
  making.value = true
}

async function make() {
  error.value = ''
  saving.value = true
  try {
    await workspace.mailAddFolder(draft.address, draft.name.trim())
    draft.name = ''
    making.value = false
    await loadMail({ reload: true })
  } catch (e) {
    error.value = errorText(e)
  } finally {
    saving.value = false
  }
}

// The quiet folders stay folded unless asked for — or unless one of them is the
// folder currently open, because collapsing the row somebody is standing on is
// how a rail loses them.
const shown = computed(() =>
  mail.folders.filter((one) => !one.quiet || showQuiet.value || at.value === one.key),
)
const quiet = computed(() => mail.folders.filter((one) => one.quiet))

// Mounted with the route, so connecting a mailbox and coming back reloads
// this on its own. It used to need a watch on the settings dialog's open
// state — the one thing that changed this list without the page moving — and
// settings are a page now, so coming back from one *is* the page moving.
onMounted(() => loadMail())

// The same width and collapse state as every other rail, because it is the same
// column. See `lib/shell/sidebar.js`.
const { collapsed, width } = useSidebar()
</script>
