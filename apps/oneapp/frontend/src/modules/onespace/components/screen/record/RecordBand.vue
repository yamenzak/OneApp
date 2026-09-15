<template>
  <!--
    What you can do to this record, and where it stands.

    A band across the top and not a column down the side, which is the second
    answer to this and the right one. The first was a 288px sidebar, and a rail
    on the left plus a sidebar on the right is five hundred pixels of chrome on
    a 1280-wide window — the form got what was left, which is the pane's
    arithmetic wearing a different coat. `docs/DESKTOP.md` stage 5.

    So: height rather than width. Forty-four pixels, once, and none at all for a
    doctype that is neither submittable nor governed by a workflow — which is
    most of them. A pipeline is also a horizontal thing in every drawing anybody
    has ever made of one.

    **Everything that acts on the record is at the end of the band**, where the
    pipeline it acts on is pointing: the step forward, and the screen's own
    declared verbs. They were in the header, three feet from the state they
    advance and beside the things that *close* the record.

    What stays in the header is what the band is not about: what the record is,
    and the two kinds of verb nobody wants beside a green button — the ones that
    unwind it (Cancel) or destroy it (Delete), which live behind three dots and
    ask before they run.

    Drawn whenever there is any of it. A doctype with no pipeline and no
    declared actions has no band at all, which is most of them.
  -->
  <div
    data-slot="record-band"
    class="flex shrink-0 items-center gap-3 border-b border-outline-gray-1 px-4 py-2"
  >
    <!-- Scrolls rather than squeezes: a workflow with eight states is 880
         pixels, which fits a page and does not fit a window, and eight
         unreadable stumps is worse than six readable ones and a scroll. -->
    <ol v-if="pipeline.length" class="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
      <li
        v-for="(one, at) in pipeline"
        :key="one.state"
        class="flex shrink-0 items-center gap-1"
        :data-standing="one.standing"
      >
        <span class="flex items-center gap-1.5 rounded-full px-2 py-1 text-sm" :class="chip(one)">
          <Icon :name="glyph(one)" class="size-3.5 shrink-0" :class="ink(one)" />
          <span class="truncate">{{ one.state }}</span>
        </span>
        <!-- The arrow between, and never after the last: a pipeline that ends
             in an arrow is one that says there is something after it. -->
        <Icon
          v-if="at < pipeline.length - 1"
          name="lucide-chevron-right"
          class="size-3.5 shrink-0 text-ink-gray-4"
          aria-hidden="true"
        />
      </li>
    </ol>

    <!-- Pushed to the end even with no stepper beside them: a row of verbs
         starting at the left edge reads as a toolbar, and this is the end of a
         sentence about the record. -->
    <div v-else class="flex-1" />

    <div class="flex shrink-0 items-center gap-1">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { Icon } from '@/ui'

/*
 * The colours, written out.
 *
 * `bg-surface-${theme}-2` is a class Tailwind cannot see, so it emits nothing
 * for it and the lit state comes out with no colour at all — which is exactly
 * what happened, and what `test_every_class_emits_css` is for. It caught the
 * stray `'now'` beside it and could not catch these, because a class built at
 * runtime is not a string in the source for anything to find.
 *
 * Keyed by the five `docflow.STYLES` produces out of Frappe's own six Workflow
 * State styles.
 */
const LIT = {
  gray: 'bg-surface-gray-3 text-ink-primary',
  blue: 'bg-surface-blue-2 text-ink-blue-7',
  green: 'bg-surface-green-2 text-ink-green-7',
  orange: 'bg-surface-amber-2 text-ink-amber-7',
  red: 'bg-surface-red-2 text-ink-red-7',
}

const INK = {
  gray: 'text-ink-secondary',
  blue: 'text-ink-blue-6',
  green: 'text-ink-green-6',
  orange: 'text-ink-amber-6',
  red: 'text-ink-red-6',
}

/*
 * Both of these are worked out here rather than in the template, and the reason
 * is a guard rather than taste: `test_every_class_emits_css` reads every quoted
 * string inside a `:class` and asks Tailwind whether it emits anything. A
 * ternary comparing `one.standing === 'now'` there puts `now` and `ahead` in
 * front of it as if they were class names. Keeping the comparison in the script
 * leaves the template with nothing but the names of real classes, which is what
 * the guard is trying to read.
 */
const NOW = 'now'
const AHEAD = 'ahead'

const chip = (one) =>
  (one.standing === NOW ? ['font-medium', LIT[one.theme] || LIT.gray] : 'text-ink-muted')

const ink = (one) =>
  (one.standing === AHEAD ? 'text-ink-gray-4' : INK[one.theme] || INK.gray)

defineProps({
  /** `_state.pipeline` — every state, in order, each with a `standing` of
   *  done, now or ahead, worked out server-side from the index rather than
   *  from the words: a rejected applicant is at a state near the end and
   *  nothing before it was "done". */
  pipeline: { type: Array, default: () => [] },
})

/**
 * A tick for what is behind, a dot for where it is, an outline for ahead.
 *
 * Three shapes and not a colour alone, because the band is already one colour
 * per state — the workflow's own — and a reader would be asked to tell "amber
 * because it is a warning state" from "amber because it is the current one".
 * The shape says which of the three; the colour says which state.
 */
function glyph(one) {
  if (one.standing === NOW) return one.cancels ? 'lucide-circle-x' : 'lucide-circle-dot'
  if (one.standing === 'done') return 'lucide-circle-check'
  return 'lucide-circle'
}
</script>
