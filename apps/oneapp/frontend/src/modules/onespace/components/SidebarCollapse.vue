<!--
  The control that folds the sidebar, in the reader's own language.

  frappe-ui ships `SidebarCollapseToggle` and it is four lines: a `SidebarItem`
  with a chevron and the label `'Collapse'` — a string literal, with no prop to
  override it and no `__()` around it, because frappe-ui is a component library
  and not a translated application. So on an Arabic screen it was the one
  English word left in the frame, on every page that has a sidebar.

  This is that component with the label translated and the state taken from
  ours rather than from the `Sidebar` it used to sit inside: the same
  `SidebarItem`, the same icon.
-->
<template>
  <!--
    Two renderings, because it is reached from two places and they are not the
    same shape. In the bar it is one control beside the switcher, so it is a
    Button with its name in a tooltip; in a column it is a row among rows, so
    it is the `SidebarItem` frappe-ui's own toggle is.
  -->
  <Button
    v-if="iconOnly"
    variant="ghost"
    :label="label"
    :tooltip="label"
    data-slot="sidebar-collapse"
    @click="toggle"
  >
    <template #icon>
      <span
        class="lucide-panel-right-open size-4 text-ink-gray-6 transition-transform duration-300 ease-in-out"
        :class="{ 'rotate-180': collapsed }"
      />
    </template>
  </Button>

  <SidebarItem v-else :label="label" data-slot="sidebar-collapse" @click="toggle">
    <template #prefix>
      <!-- rtl-ok: the panel this points at is the sidebar, and `dir` has
           already moved the sidebar; the glyph turns with it. -->
      <span
        class="lucide-panel-right-open size-4 text-ink-gray-6 transition-transform duration-300 ease-in-out"
        :class="{ 'rotate-180': collapsed }"
      />
    </template>
  </SidebarItem>
</template>

<script setup>
import { computed } from 'vue'
import { Button, SidebarItem } from '@/ui'
import { useSidebar } from '@/modules/onespace/lib/shell/sidebar'
import { __ } from '@/shared/lib/runtime/translate'

defineProps({
  /** True in the top bar, where it is one control rather than a row. */
  iconOnly: { type: Boolean, default: false },
})

// The shared state, not frappe-ui's injection. Its own toggle injects two keys
// the `Sidebar` provides, and this one now lives in the *bar* — outside every
// Sidebar, where those keys resolve to their fallbacks: reads as expanded, does
// nothing. `useSidebar()` is what each column binds its `v-model:collapsed` to,
// so it is the same value from either side of the tree.
const { collapsed } = useSidebar()

const toggle = () => {
  collapsed.value = !collapsed.value
}

const label = computed(() => (collapsed.value ? __('Expand') : __('Collapse')))
</script>
