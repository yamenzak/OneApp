<template>
  <Sidebar
    v-model:collapsed="collapsed"
    :width="`${width}px`"
    class="border-r border-outline-gray-1"
  >
    <!-- No logo: the rail already shows the active space's tile, so a header
         logo beside it would say the same thing twice. -->
    <SidebarHeader
      :title="activeSpace?.space_label || session.tenant?.name || TENANT_APP"
      :subtitle="activeSpace ? session.tenant?.name : session.tenant?.plan"
      :show-logo="false"
    />

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pb-6">
      <nav class="space-y-0.5">
        <template v-for="item in nav" :key="item.label">
          <SidebarItem :icon="item.icon" :to="item.to" :active="item.active">
            <span class="flex-1 truncate text-sm">{{ item.label }}</span>
            <!--
              The chevron is in `#suffix`, which frappe-ui renders as a sibling
              of the link rather than inside it — a button nested in an anchor
              is invalid, and the browser's own answer to it is to swallow one
              of the two clicks.
            -->
            <template v-if="expandable(item) && !collapsed" #suffix>
              <Button
                variant="ghost"
                :icon="open[item.key] ? 'lucide-chevron-down' : 'lucide-chevron-right'"
                :label="`Ways to see ${item.label}`"
                :tooltip="`Ways to see ${item.label}`"
                @click="toggle(item)"
              />
            </template>
          </SidebarItem>

          <!--
            Two groups, not one list. "As a board or as a list" and "which
            slice of it" are different questions, and a run of items that mixes
            them reads as one set of alternatives — when picking a layout
            leaves the view type exactly where it was.
          -->
          <div
            v-if="expandable(item) && open[item.key] && !collapsed"
            class="ms-3 border-s border-outline-gray-1 ps-1"
          >
            <SidebarItem
              v-for="type in item.viewTypes"
              :key="type.key"
              :icon="type.icon"
              :to="type.to"
              :active="false"
            >
              <span class="flex-1 truncate text-sm" :class="SUB_ACTIVE[+type.active]">
                {{ type.label }}
              </span>
            </SidebarItem>

            <template v-if="item.layouts.length">
              <SidebarLabel class="mt-2">Views</SidebarLabel>
              <SidebarItem
                v-for="layout in item.layouts"
                :key="layout.key"
                :icon="layout.icon"
                :to="layout.to"
                :active="false"
              >
                <span class="flex-1 truncate text-sm" :class="SUB_ACTIVE[+layout.active]">
                  {{ layout.label }}
                </span>
              </SidebarItem>
            </template>
          </div>
        </template>
      </nav>
    </ScrollArea>

    <!-- Sidebar has one slot, the default: it hands the whole body to the app.
         A `#footer` template renders nothing at all, which is how the quota
         meter, the user menu and the setup card all silently disappeared.
         `mt-auto` is what pins this to the bottom of the flex column. -->
    <div class="mt-auto shrink-0">
      <div class="p-2">
        <!-- A meter is a number and a bar, and neither survives 3rem of width.
             Collapsed, the sidebar is a column of icons. -->
        <QuotaMeter v-if="!collapsed" class="mb-2 px-1" />
        <!--
          frappe-ui's own toggle, which is a SidebarItem — so it collapses to
          its icon with everything else and stays where the eye already is when
          the sidebar is shut, rather than hiding in a corner of the header.
        -->
        <SidebarCollapseToggle />
      </div>
    </div>
  </Sidebar>

  <!--
    And how wide it is when it is open. Two roots rather than a wrapper: the
    shell lays its sidebar out as a flex child, so the handle is the next one
    along rather than something nested inside the sidebar's own scroll.

    Hidden while collapsed — a collapsed sidebar is one width by definition,
    and a handle that resizes something to a size it will not take is a handle
    that does nothing.
  -->
  <Resizer
    v-if="!collapsed"
    v-model="width"
    :min="MIN"
    :default-size="DEFAULT"
    :max="MAX"
    side="right"
    label="the sidebar"
    remember="onespace.sidebar"
    slot-name="sidebar-resizer"
  />
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { TENANT_APP } from '../lib/brand'
import {
  Button,
  ScrollArea,
  Sidebar,
  SidebarCollapseToggle,
  SidebarHeader,
  SidebarItem,
  SidebarLabel,
} from '@/ui'
import Resizer from './screen/Resizer.vue'
import QuotaMeter from './QuotaMeter.vue'
import { useNav } from '../lib/nav'
import { session } from '../lib/session'

// The destinations themselves live in lib/nav.js: the phone's bottom bar
// renders the same list, and two declarations of it drift into two different
// names for the same page. `activeSpace` comes back with it because the header
// names whichever space the list belongs to.
const { nav, activeSpace } = useNav()

// A sub-item says it is active by weight, not by a filled pill. The fill
// belongs to the screen — the navigation item — and a second one nested under
// it competes with its parent for the eye rather than saying something more.
// `:active="false"` and not simply omitting it: absence falls through to
// frappe-ui's route inference, which would fill it anyway.
const SUB_ACTIVE = ['text-ink-gray-6', 'font-medium text-ink-gray-8']

// Shut or open, remembered in this browser.
//
// The clearest shell win there is: on a laptop running a data grid, a fixed
// 224px of chrome sits between the reader and their columns with no way to
// take it back. frappe-ui's Sidebar already knows how to do this — SidebarItem
// shrinks to its icon on its own — so what was missing is the state and the
// toggle, not a layout.
//
// Explicitly boolean rather than left null: unset, Sidebar collapses itself
// below the `sm` breakpoint, and below that breakpoint this component is not
// rendered at all — the shell has switched to the phone's bar.
const REMEMBERED = 'onespace.sidebar-collapsed'

const stored = () => {
  try {
    return window.localStorage.getItem(REMEMBERED) === '1'
  } catch {
    // A private window, or site data turned off. Open is a fine answer.
    return false
  }
}

const collapsed = ref(stored())

watch(collapsed, (shut) => {
  try {
    window.localStorage.setItem(REMEMBERED, shut ? '1' : '0')
  } catch {
    // Nothing to do about it, and nothing worth saying.
  }
})

// How wide when it is open. Narrow enough that a screen name still fits, wide
// enough that "Provisioning queue" is not three lines.
const MIN = 176
const DEFAULT = 224
const MAX = 420

const width = ref(DEFAULT)

// Which screens are showing their view types. Not persisted: it is a glance,
// not a preference, and a sidebar that remembers what you opened last week is
// a sidebar you have to tidy.
const open = reactive({})

// Nothing to expand when there is one way to look at a screen and nobody has
// named a view of it — a chevron that opens a list of one is a control that
// lies about having a choice.
const expandable = (item) => (item.viewTypes || []).length + (item.layouts || []).length > 1

const toggle = (item) => {
  open[item.key] = !open[item.key]
}

// The screen you are on opens itself, so arriving by any route — a link, a
// bookmark, the bottom bar — shows which way you are looking at it.
watch(
  nav,
  (items) => {
    for (const item of items) {
      if (item.active && expandable(item)) open[item.key] = true
    }
  },
  { immediate: true },
)
</script>
