<template>
  <!--
    A record you are looking at *from* another record — a variation from the job
    it hangs off, an invoice from the project it was raised against.

    Clicking one of those used to replace the page with it, which is correct
    navigation and the wrong thing to do: you were reading a job, you glanced at
    one of its lines, and the job was gone. So it slides over instead. It is in
    the URL like everything else here, so it can be linked and closed with the
    back button.
  -->
  <!--
    To `body`, and not because of where it looks: because of what it has to
    layer against. frappe-ui's Dialog portals itself to `body` at `z-50`, and
    this used to sit at the same `z-50` inside the page — which loses, every
    time, to anything appended after it. So a link peeked from inside the
    create dialog opened *behind* the dialog and could not be read.

    Teleported, both live in one pool at one depth and the order is simply who
    mounted last, which is the order a person opened them in. A drawer peeked
    from a dialog covers it; a dialog opened from the drawer covers that.
  -->
  <Teleport to="body">
  <div
    data-slot="record-drawer"
    class="pointer-events-auto fixed inset-0 z-50 flex justify-end"
  >
    <!--
      The scrim. Pressable, because on a surface where the thing behind is
      visible and inert, clicking it is what everybody tries first — and a
      `<button>` rather than a div with a handler so it is one thing to the
      keyboard as well.
    -->
    <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
    <button
      type="button"
      data-slot="drawer-scrim"
      aria-label="Close"
      class="absolute inset-0 bg-black/40 transition-opacity"
      @click="emit('close')"
    />

    <!--
      Full height, end-hand side, and wide — 896px rather than the 672 it
      started at, because a doctype that declares three form columns gets three
      whatever the container is, and at 672 that is 224px a column.

      Not resizable: the pane shares the window with a list you are working
      against, this with a page you are coming straight back to.

      `surface-elevation-2` and not `surface-base`: a shadow is how depth reads
      in light mode and fades to nothing on a dark ground, so in dark mode depth
      comes from a lighter surface. A raw surface under a shadow is flat in
      exactly one of the two themes.
    -->
    <div
      class="relative flex h-full w-full max-w-4xl flex-col border-s border-outline-gray-2 bg-surface-elevation-2 shadow-over"
    >
      <slot />
    </div>
  </div>
  </Teleport>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'

const emit = defineEmits(['close'])

/**
 * Escape closes it, and this is the one record surface where that is right: it
 * covers the page and it has a scrim. The pane deliberately does not take
 * Escape — the link picker inside it does not mark its own as handled, so
 * closing a dropdown closed the record under it.
 *
 * Still last-resort rather than eager: a control that handled the key already
 * has called `preventDefault`.
 */
const key = (event) => {
  if (event.key === 'Escape' && !event.defaultPrevented) emit('close')
}

onMounted(() => window.addEventListener('keydown', key))
onBeforeUnmount(() => window.removeEventListener('keydown', key))
</script>
