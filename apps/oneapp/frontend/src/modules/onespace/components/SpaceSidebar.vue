<template>
  <!--
    No border, and no header.

    No border because the bar, this column and the ground behind them are one
    surface, and a seam down the middle of it is a panel edge with no panel.

    No header because the switcher sits directly above it and is a board of
    every space in the workspace: a row under it naming the one you are in was
    the same word twice, 48px apart, and now that the switcher draws the space
    it is the same *face* twice as well.
  -->
  <Sidebar v-model:collapsed="collapsed" :width="`${width}px`">
    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pb-6">
      <nav data-slot="space-nav" class="space-y-0.5">
        <template v-for="item in nav" :key="item.label">
          <!--
            A heading, on the first screen of a run that shares one. Not a
            component and not clickable: it is a label over a group, and a
            heading that navigates is a destination competing with the items
            under it.

            Hidden when the rail is collapsed, where there is no room for a
            word and the icons are the whole of it.
          -->
          <p
            v-if="item.heading && !collapsed"
            data-slot="nav-heading"
            class="px-2 pb-1 pt-4 text-p-xs font-medium uppercase tracking-wide text-ink-gray-5 first:pt-1"
          >
            {{ __(item.heading) }}
          </p>
          <SidebarItem :icon="item.icon" :to="item.to" :active="item.active">
            <span class="flex-1 truncate text-sm">{{ item.label }}</span>
            <!--
              The chevron is in `#suffix`, which frappe-ui renders as a sibling
              of the link rather than inside it: a button nested in an anchor is
              invalid, and the browser swallows one of the two clicks.
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
            Two groups, not one list. "As a board or as a list" and "which slice
            of it" are different questions, and a run that mixes them reads as
            one set of alternatives.
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

    <!-- Sidebar has one slot, the default: a `#footer` template renders
         nothing at all, which is how the quota meter, the user menu and the
         setup card all silently disappeared. `ShellFoot` pins itself to the
         bottom and is the same three rows under every column. -->
    <ShellFoot />
  </Sidebar>

  <!-- Two roots rather than a wrapper: the shell lays its sidebar out as a
       flex child, so the handle is the next one along. -->
  <SidebarResizer />
</template>

<script setup>
import { reactive, watch } from 'vue'
import {
  Button,
  ScrollArea,
  Sidebar,
  SidebarItem,
  SidebarLabel,
} from '@/ui'
import ShellFoot from '@/modules/onespace/components/shell/ShellFoot.vue'
import SidebarResizer from '@/modules/onespace/components/SidebarResizer.vue'
import { useNav } from '@/modules/onespace/lib/shell/nav'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { __ } from '@/shared/lib/runtime/translate'

// The destinations live in `lib/shell/nav.js`: the phone's bottom bar renders
// the same list, and two declarations of it drift into two names for one page.
const { nav } = useNav()

// A sub-item says it is active by weight, not by a filled pill — the fill
// belongs to the screen above it. `:active="false"` and not simply omitting it:
// absence falls through to frappe-ui's route inference, which would fill it.
const SUB_ACTIVE = ['text-ink-gray-6', 'font-medium text-ink-gray-8']

// Shut or open, and how wide when it is open — shared with every other rail
// that fills this slot, in `lib/shell/sidebar.js`. On a laptop running a data
// grid, a fixed 224px of chrome sits between the reader and their columns with
// no way to take it back.
const { collapsed, width } = useSidebar()

// Which screens are showing their view types. Not persisted: it is a glance,
// not a preference.
const open = reactive({})

// Nothing to expand when there is one way to look at a screen and nobody has
// named a view of it — a chevron that opens a list of one lies about a choice.
const expandable = (item) => (item.viewTypes || []).length + (item.layouts || []).length > 1

const toggle = (item) => {
  open[item.key] = !open[item.key]
}

// The screen you are on opens itself, so arriving by any route shows which way
// you are looking at it.
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
