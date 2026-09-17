<!--
  Who the assistant is, wherever it is named.

  `assistant.avatar` was settable, in the boot payload, in the reactive — and
  rendered by exactly one component: the settings form that sets it. A
  workspace uploaded a face for their assistant and never saw it again.

  So one component, and it goes everywhere the name goes: the panel header,
  every turn the assistant takes, the empty state, the moment an answer is
  arriving. A face and a name together are what make the thing a character
  rather than a feature, which is the whole of §E8's complaint.

  The `oneai` mark when nothing is set, rather than `Avatar`'s letter. A
  letter is what a *person* falls back to, and the assistant is not one; the
  mark is the product saying which of its own things this is.

  Drawn at the face's full size and without a ring behind it. It used to sit
  small inside a washed disc, which is what a flat glyph needs; the mark is a
  spectrum aperture with its own edge and its own shadow, so a disc behind it
  is a second ring around a drawing that already has one — and it made the
  thing read as a generic corner button rather than as the assistant.

  `docs/UNIFICATION.md` §E8.
-->
<template>
  <!--
    `thinking` is the one flourish: the same two hues the sheen travels in,
    breathing around the face while an answer is on its way. It is the part
    of §E8's "glows and colour" that is *about* something — the face is what
    is about to speak, so it is the thing that should look alive. Stopped
    under `prefers-reduced-motion`, like the sheen.
  -->
  <Avatar
    v-if="assistantAvatar"
    :size="avatarSize"
    :image="assistantAvatar"
    :label="assistantName"
    data-slot="ai-face"
    :class="thinking ? 'oneapp-ai-alive rounded-full' : ''"
  />
  <span
    v-else
    class="flex shrink-0 items-center justify-center rounded-full"
    :class="[BOX[size], thinking ? 'oneapp-ai-alive' : '']"
    data-slot="ai-face"
    role="img"
    :aria-label="assistantName"
  >
    <BrandMark name="oneai" decorative :class="BOX[size]" />
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { Avatar } from '@/ui'

import BrandMark from '@/shared/components/brand/BrandMark.vue'
import { assistantAvatar, assistantName } from '@/modules/oneai/lib/assistant'

//: frappe-ui's own Avatar sizes, so a face beside a person's face lines up.
//: The mark fills the box: it is drawn with its own margin inside its viewBox,
//: so a smaller class inside a larger one draws it twice inset.
const BOX = {
  xs: 'size-4', sm: 'size-5', md: 'size-6', lg: 'size-8', xl: 'size-10',
  '2xl': 'size-12',
  // The dial in the corner, which is the one place this is the whole control
  // rather than a face beside a name. `Avatar` has no size this big, so a
  // workspace that uploaded a picture gets the largest it does have.
  '3xl': 'size-16',
}

const props = defineProps({
  size: {
    type: String,
    default: 'sm',
    validator: (one) => ['xs', 'sm', 'md', 'lg', 'xl', '2xl', '3xl'].includes(one),
  },
  /** An answer is on its way. */
  thinking: { type: Boolean, default: false },
})

const avatarSize = computed(() => (props.size === '3xl' ? '2xl' : props.size))
</script>
