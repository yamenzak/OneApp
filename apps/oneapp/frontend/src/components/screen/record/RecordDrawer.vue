<template>
  <!--
    A record you are looking at *from* another record.

    A variation opened from the job it hangs off, an invoice opened from the
    project it was raised against. Before this, clicking one of those replaced
    the page with it — which is correct navigation and the wrong thing to do: you
    were reading a job, you glanced at one of its lines, and the job was gone.
    Coming back meant the browser's back button and a re-read.

    So it slides over instead, and the thing underneath stays where it was.
    Which is the same argument the pane makes against a modal, one level in.

    It is in the URL like everything else here, so it can be linked, reloaded
    into, and closed with the back button.
  -->
  <div data-slot="record-drawer" class="fixed inset-0 z-50 flex justify-end">
    <!--
      The scrim. Pressable, because on a surface where the thing behind is
      visible and inert, clicking it is what everybody tries first — and it is
      a `<button>` rather than a div with a handler so that it is one thing to
      the keyboard as well.
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
      Full height, right-hand side, and wide — 896px rather than the 672 it
      started at, because a doctype that declares three form columns gets three
      of them above the `sm` breakpoint whatever the container is, and at 672
      that is 224px a column: half-width boxes and clipped labels. At 896 a
      column is what a column should be, and there is still enough of the page
      left to see what you came from.

      Not resizable. The pane is resizable because it shares the window with a
      list you are working against; this shares it with a page you are coming
      straight back to.

      `surface-elevation-2` and not `surface-base`: a shadow is how depth reads
      in light mode and it fades to nothing on a dark ground, so in dark mode
      depth comes from a lighter surface instead. The elevation tokens are the
      pair — white in light, a step lighter in dark — and the guard in
      `test_frappe_ui_usage.py` is there because a raw surface under a shadow is
      flat in exactly one of the two themes, which is the half nobody screenshots.
    -->
    <div
      class="relative flex h-full w-full max-w-4xl flex-col border-s border-outline-gray-2 bg-surface-elevation-2 shadow-2xl"
    >
      <slot />
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted } from 'vue'

const emit = defineEmits(['close'])

/**
 * Escape closes it, and this is the one record surface where that is right.
 *
 * The pane deliberately does not take Escape — it is not modal, and the link
 * picker inside it does not mark its own Escape as handled, so closing a
 * dropdown closed the record under it. This *is* modal: it covers the page, it
 * has a scrim, and Escape is what a covered page means.
 *
 * Still last-resort rather than eager: a control that handled the key already
 * has called `preventDefault`, and this leaves it alone.
 */
const key = (event) => {
  if (event.key === 'Escape' && !event.defaultPrevented) emit('close')
}

onMounted(() => window.addEventListener('keydown', key))
onBeforeUnmount(() => window.removeEventListener('keydown', key))
</script>
