<template>
  <!--
    A dialog that holds a form: pinned title, scrolling body, pinned actions.

    The shape is `SettingsPanel`'s — a flex column whose body takes `flex-1`, so
    Save pins to the bottom without any positioning. frappe-ui's `Dialog`
    renders its `#actions` slot as an ordinary block after the content inside a
    `fixed inset-0 overflow-y-auto` scroller, so on a doctype with twenty fields
    Create is below the fold.

    So: `bare` (which turns off frappe-ui's own header, padding and close
    button) and the three-part column built back on top, bounded to the viewport
    so the *body* scrolls rather than the dialog. Full-screen on a phone, where
    a floating card at 95% of the screen is a worse version of a page.
  -->
  <Dialog
    v-model="open"
    :size="size"
    bare
    :dismissible="dismissible"
    @after-leave="emit('after-leave')"
  >
    <div
      data-oneapp="form-dialog"
      class="flex h-[100dvh] flex-col md:h-auto md:max-h-[85dvh]"
    >
      <header
        class="flex shrink-0 items-center justify-between gap-3 border-b border-outline-gray-1 px-4 py-3 sm:px-6"
      >
        <h3 class="truncate text-lg font-semibold text-ink-gray-8">{{ title }}</h3>
        <!--
          Always here, and not only on a phone: while the form has something in
          it this dialog refuses to close on Escape or a click outside — see
          `dismissible` — so it carries the one way out that is unambiguous.
        -->
        <Button variant="ghost" icon="lucide-x" :label="closeLabel" :tooltip="closeLabel"
                @click="close" />
      </header>

      <!--
        `autofocus` here, on the body rather than on any one control.

        Without it reka's FocusScope focuses the first tabbable thing, which is
        the close button in the header — and that button's tooltip opened on
        focus as its own dismissable layer, so the first Escape closed the
        tooltip instead of the dialog.

        frappe-ui's `useAutofocusOnOpen` walks into a non-focusable wrapper and
        focuses the first focusable thing inside it, which is the form's first
        field.
      -->
      <div autofocus class="min-h-0 flex-1 overflow-y-auto px-4 py-5 sm:px-6">
        <slot />
      </div>

      <footer :class="FOOTER">
        <slot name="actions" :close="close" />
      </footer>
    </div>
  </Dialog>
</template>

<script setup>
import { Button, Dialog } from '@/ui'

// The same treatment the settings panels' footer carries, with this dialog's
// own gutter. Named here rather than imported from `settings/geometry`: that
// module exists to compensate for frappe-ui's SettingsDialog and should be
// deletable the day it stops needing to.
const FOOTER = [
  'flex shrink-0 items-center justify-end gap-2',
  'border-t border-outline-gray-1 bg-surface-elevation-1',
  'px-4 py-3 sm:px-6',
].join(' ')

defineProps({
  title: { type: String, required: true },
  size: { type: String, default: '3xl' },
  /**
   * Whether Escape and a click outside may close this. False while the form
   * holds anything worth losing — whatever reaches `interact-outside`, a stray
   * click or a portalled popover dismissed over the backdrop, no longer takes
   * the form with it.
   */
  dismissible: { type: Boolean, default: true },
  closeLabel: { type: String, default: 'Close' },
})

const open = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['after-leave', 'close'])

// The explicit way out, which always works. Escape being refused is only
// tolerable because this is never absent.
const close = () => {
  emit('close')
  open.value = false
}
</script>
