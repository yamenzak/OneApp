<template>
  <!--
    The three things every list shows about a row whatever it is about: when it
    last changed, how many people have said something, and whether this person
    cares about it. All three cost nothing to carry — the count is parsed from
    `_comments` and the like from `_liked_by`, both already on the document.
  -->
  <!--
    `w-full` is load-bearing: the cell packs its content at the start, so
    without it this block is only as wide as what is in it and `justify-end`
    right-aligns inside a box that is itself floating left — which is the
    crooked column of hearts.
  -->
  <!--
    On a card the same three read the other way round: the counts sit under the
    fields where the eye already is, and the heart goes to the far corner.
  -->
  <!--
    `inverse` is the same three read over a photograph. White, and a drop shadow
    rather than a band behind it: a gallery card's picture goes to all four
    edges.
  -->
  <div
    class="flex w-full items-center gap-2 text-p-xs"
    :class="[spread ? '' : 'justify-end', inverse ? 'text-white drop-shadow' : 'text-ink-gray-5']"
  >
    <span class="whitespace-nowrap tabular-nums">{{ when }}</span>

    <!-- Always, including the zero: a count that appears only when there is one
         shifts everything after it, and the hearts stop lining up. -->
    <span class="flex items-center gap-1">
      <Icon name="lucide-message-circle" class="size-3.5" />
      <span class="tabular-nums">{{ meta.comments > 99 ? '99+' : meta.comments || 0 }}</span>
    </span>

    <!--
      The count is its own text and the heart is icon-only. `label` on a Button
      is both the visible text and the accessible name, so putting the count
      there named the button "1".
    -->
    <span v-if="meta.likes" class="tabular-nums">{{ meta.likes }}</span>

    <!--
      Who it is on. Faces rather than a count, because the question is "is
      anybody on this, and is it me".

      Only where the caller has room: a list's activity column is a fixed 176px
      track, so the list passes nothing and the card passes people.
    -->
    <AvatarStack
      v-if="people.length"
      :people="people"
      :limit="3"
      size="xs"
      slot-name="row-assignee"
    />

    <span v-if="spread" class="flex-1" />
    <!-- The heart is last, so it lines up with the one in the header. -->
    <!-- Its own theme rather than its own icon: lucide ships no filled heart. -->
    <Button
      variant="ghost"
      icon="lucide-heart"
      :label="likeLabel"
      :tooltip="likeLabel"
      :theme="meta.liked ? 'red' : 'gray'"
      :class="inverse && !meta.liked ? '!text-white drop-shadow' : ''"
      @click.stop="emit('like')"
    />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Icon, dayjsLocal } from '@/ui'
import AvatarStack from '../fields/AvatarStack.vue'

const props = defineProps({
  meta: { type: Object, default: () => ({}) },
  /** Counts at the start and the heart at the end, which is a card's shape. */
  spread: { type: Boolean, default: false },
  /** `row._assigned` — `[{ value, label, image }]`, already resolved. */
  people: { type: Array, default: () => [] },
  /** White, for a surface that is somebody's photograph rather than a card. */
  inverse: { type: Boolean, default: false },
})
const emit = defineEmits(['like'])

// `fromNow(true)` drops the "ago": a column of "7 hours" reads as a column of
// ages, where "7 hours ago" reads as a sentence repeated down the page.
const when = computed(() =>
  props.meta?.modified ? dayjsLocal(props.meta.modified).fromNow(true) : '',
)

const likeLabel = computed(() =>
  props.meta?.liked ? 'Remove from favourites' : 'Add to favourites',
)
</script>
