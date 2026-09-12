<!--
  What you can do to this one thing, wherever the thing is.

  A file row had six of these and a record row had none: a record could be
  opened and hearted and that was the whole of it, so deleting one meant
  closing it, finding its row, ticking the box and using the bulk bar. The
  central object of the product had fewer row actions than a supporting one.

  What this owns is the affordance, not the verbs. Which verbs a row has is
  the surface's to say — a file's are not a record's — and the list arrives
  already built, in the same `{label, icon, theme, onClick}` shape a
  `Dropdown` has always taken here.

  Two things it does that a bare `Dropdown` at a call site did not:

  * **It appears on the row's hover**, off `group/row` from `lib/rowstate.js`,
    so forty rows are not forty sets of dots. It stays while its own menu is
    open — a trigger that fades out from under an open popover reads as
    broken — and it is always there on a phone, which has no hover to reveal
    it with.
  * **The destructive verb is last and in red**, sorted here rather than
    remembered at each call site. A menu whose destructive entry sits among
    the others is a menu somebody presses by accident.

  `docs/UNIFICATION.md` §B3.
-->
<template>
  <Dropdown :options="sorted" align="end">
    <template #default="{ open }">
      <Button
        variant="ghost"
        size="sm"
        icon="lucide-more-horizontal"
        data-slot="row-menu"
        :label="label || __('What to do with this')"
        :tooltip="label || __('What to do with this')"
        :class="[REVEAL, open ? 'opacity-100' : '']"
        @click.stop
      />
    </template>
  </Dropdown>
</template>

<script setup>
import { computed } from 'vue'

import { Button, Dropdown } from '@/ui'

import { __ } from '@/shared/lib/runtime/translate'

//: Hidden until the pointer is on the row — and only where there is a
//: pointer. `md:` is the one breakpoint (`lib/shell/breakpoint.js`), and
//: below it the dots are simply there, because a phone cannot hover and an
//: affordance it cannot reveal is one it does not have.
const REVEAL = 'transition-opacity md:opacity-0 md:group-hover/row:opacity-100 md:focus-visible:opacity-100'

const props = defineProps({
  /** `{label, icon, theme, onClick}` each, in the caller's own order. */
  items: { type: Array, default: () => [] },
  //: What this menu is about, for the reader who cannot see the row.
  label: { type: String, default: '' },
})

//: Red last, and stable otherwise. `Array.prototype.sort` is stable in every
//: engine this runs in, so the caller's order survives among the rest.
const sorted = computed(() =>
  [...props.items].sort((a, b) => (a.theme === 'red' ? 1 : 0) - (b.theme === 'red' ? 1 : 0)),
)
</script>
