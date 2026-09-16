<template>
  <!--
    OneMail on the desk — `docs/DESKTOP.md` stage 6, the half that was left.

    Mail was the last everyday surface that took the screen away. It is also
    the one where that hurt most: a reply is almost always *about* something
    else — the quotation on screen, the employee whose record you have open —
    and answering it meant leaving that, writing from memory, and coming back
    by the back button.

    The route stays as the maximised case, so a conversation is still somewhere
    a colleague can be sent.

    **The rail comes inside.** On the page mail borrows the shell's sidebar
    slot, because mail is not in a space and the workspace's own list has
    nothing to say beside a mailbox list. A window has no shell, so the rail
    and the list are one row in here — which is what every mail client looks
    like anyway. Fixed width and no drag: the shell's column is a preference
    somebody set for the whole product, and a window's edge is not the place to
    change it.

    **Wider than the Drive's**, because mail is three columns where a file
    manager is two: a rail, what has arrived, and what it says. Below 760 the
    reader takes the whole width and the list goes, which is the same fold the
    page does at `md:` and is why that is a class rather than a second state.
  -->
  <DeskWindow
    v-if="onDesk(MAIL)"
    :id="MAIL"
    :title="nameOf('onemail')"
    :width="1040"
    :height="700"
    :min-width="560"
    :min-height="380"
    :tint="colourOf('onemail')"
    @close="close(MAIL)"
  >
    <template #title>
      <BrandMark name="onemail" class="size-4 shrink-0" />
      <SpaceName brand="onemail" class="text-base" />
    </template>

    <div class="flex min-h-0 flex-1 overflow-hidden">
      <MailSidebar windowed :folder="at.folder" @go="goTo($event)" />
      <div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden p-2">
        <Mail windowed :at="at" @go="goTo($event)" />
      </div>
    </div>
  </DeskWindow>
</template>

<script setup>
import { computed } from 'vue'

import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import Mail from '@/modules/onemail/pages/Mail.vue'
import MailSidebar from '@/modules/onemail/components/MailSidebar.vue'
import { MAIL, goTo, whereIs } from '@/modules/onemail/lib/window'
import { close, onDesk } from '@/modules/onespace/lib/desk/windows'
import { colourOf, nameOf } from '@/shared/lib/brand/naming'

const at = computed(() => whereIs())
</script>
