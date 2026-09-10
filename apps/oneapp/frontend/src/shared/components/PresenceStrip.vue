<template>
  <!--
    Who else is in this file, right now.

    Not "who has access" — that is the share panel, and it answers a different
    question about a different timescale. This is the row of faces that tells
    somebody about to rewrite a paragraph that the person who wrote it is
    reading it. Nothing when nobody else is here, which is most of the time
    and is why it must take no room in that case.

    The colour ring is the same colour as that person's caret in the prose, so
    a cursor in the middle of a sentence and a face at the top of the page are
    recognisably the same person. It comes from `onespace/live.py::colour_for`
    — hashed off the user id, so it is the same in every room and on every
    browser, and two sockets racing cannot be handed one seat.
  -->
  <div v-if="people.length" data-slot="presence" class="flex items-center -space-x-1.5">
    <Tooltip
      v-for="one in people.slice(0, MANY)"
      :key="one.user"
      :text="one.full_name || one.user"
    >
      <Avatar
        :label="one.full_name || one.user"
        :image="one.image || undefined"
        shape="circle"
        size="sm"
        class="ring-2"
        :style="{ '--tw-ring-color': one.colour }"
      />
    </Tooltip>
    <Tooltip v-if="people.length > MANY" :text="rest">
      <span class="ms-2.5 text-p-xs tabular-nums text-ink-gray-5">+{{ people.length - MANY }}</span>
    </Tooltip>
  </div>
</template>

<script setup>
import { computed } from 'vue'

import { Avatar, Tooltip } from '@/ui'
import { __ } from '@/shared/lib/runtime/translate'

// Three faces and a count. Four is where a header starts pushing the title
// around at a laptop width, and the count carries the rest.
const MANY = 3

const props = defineProps({
  people: { type: Array, default: () => [] },
})

const rest = computed(() =>
  props.people
    .slice(MANY)
    .map((one) => one.full_name || one.user)
    .join(__(', ')),
)
</script>
