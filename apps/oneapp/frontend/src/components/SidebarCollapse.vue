<!--
  The control that folds the sidebar, in the reader's own language.

  frappe-ui ships `SidebarCollapseToggle` and it is four lines: a `SidebarItem`
  with a chevron and the label `'Collapse'` — a string literal, with no prop to
  override it and no `__()` around it, because frappe-ui is a component library
  and not a translated application. So on an Arabic screen it was the one
  English word left in the frame, on every page that has a sidebar.

  This is that component with the label translated and nothing else changed: the
  same `SidebarItem`, the same icon, and frappe-ui's own injection keys, which
  it exports. Not a reimplementation — a label.
-->
<template>
  <SidebarItem :label="collapsed ? __('Expand') : __('Collapse')" @click="toggle">
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
import { computed, inject } from 'vue'
import { SidebarItem, sidebarCollapsedKey, sidebarToggleKey } from '@/ui'
import { __ } from '@/lib/runtime/translate'

// The same two keys frappe-ui's own toggle injects, with the same fallbacks:
// a toggle rendered outside a `Sidebar` reads as expanded and does nothing,
// rather than throwing.
const collapsed = inject(
  sidebarCollapsedKey,
  computed(() => false),
)
const toggle = inject(sidebarToggleKey, () => {})
</script>
