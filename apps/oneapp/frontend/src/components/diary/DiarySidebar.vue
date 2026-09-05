<template>
  <!--
    Which calendars this diary is made of, and which are switched on.

    The rail's job on this route: the grid says *when*, and this says *whose*.
    Each row is a source the server merged — the reader's own events, and every
    screen in every space that declares a calendar — with the colour its
    entries carry on the grid beside it, so the two are the same fact rather
    than a legend somebody has to learn.

    The same `Sidebar` every other rail is. See `components/SpaceSidebar.vue`.
  -->
  <Sidebar
    v-model:collapsed="collapsed"
    :width="`${width}px`"
    class="border-r border-outline-gray-1"
  >
    <SidebarHeader title="Calendar" :subtitle="session.tenant?.name" :show-logo="false" />

    <ScrollArea class="min-h-0 flex-1" viewport-class="px-2 pb-6">
      <nav class="space-y-0.5">
        <SidebarItem
          v-for="one in diary.sources"
          :key="one.key"
          :active="false"
          data-slot="diary-source"
          @click="toggle(one.key)"
        >
          <template #prefix>
            <!-- The colour, not an icon: it is what the grid uses to say the
                 same thing, and a switched-off calendar shows the ring alone
                 so the row still says which colour it would be. -->
            <span
              class="size-3 shrink-0 rounded-full border"
              :style="dot(one.key)"
            />
          </template>
          <span class="flex-1 truncate text-sm" :class="isOn(one.key) ? '' : DIMMED">
            {{ one.label }}
          </span>
          <template v-if="one.space_label" #suffix>
            <span class="shrink-0 text-p-xs text-ink-gray-5">{{ one.space_label }}</span>
          </template>
        </SidebarItem>
      </nav>
    </ScrollArea>

    <div class="mt-auto shrink-0">
      <div class="p-2">
        <SidebarCollapseToggle />
      </div>
    </div>
  </Sidebar>

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
import {
  CalendarColorMap,
  ScrollArea,
  Sidebar,
  SidebarCollapseToggle,
  SidebarHeader,
  SidebarItem,
} from '@/ui'
import Resizer from '../Resizer.vue'
import { session } from '../../lib/session'
import { DEFAULT, MAX, MIN, useSidebar } from '../../lib/sidebar'
import { colourFor, diary, isOn, toggle } from '../../lib/diary'

const { collapsed, width } = useSidebar()

const DIMMED = 'text-ink-gray-5'

/**
 * The dot, from the grid's own palette rather than from ours.
 *
 * `CalendarColorMap` is exported for exactly this — frappe-ui documents it as
 * what to build a matching colour picker from — and it is the reason this is a
 * style rather than a class: the seven calendar colours are the component's
 * CSS variables, and half of them have no `bg-surface-*` token in our theme to
 * write instead. Taking ours would mean a dot that is nearly the colour of the
 * entries it stands for, which is worse than either.
 *
 * Filled where the calendar is on, outlined where it is off, so switching one
 * off leaves the row the same size and still says which colour it would be.
 */
const dot = (key) => {
  const found = CalendarColorMap[colourFor(key, diary.sources)]
  const edge = found?.color || 'var(--outline-gray-3)'
  return { borderColor: edge, backgroundColor: isOn(key) ? edge : 'transparent' }
}
</script>
