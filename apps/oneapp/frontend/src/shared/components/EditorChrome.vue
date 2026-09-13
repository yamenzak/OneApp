<!--
  The bar above an editor.

  Two editors and two answers: the document drew a `PageHeader` with the one
  trail in it, and the sheet drew `sn-topbar` inside the vendored file — a
  mark that was also the way back, a title you could type into, a save state,
  two badges and a three-dot menu, none of it shared with anything. They
  agreed on what they were for and on nothing else, so a person moving between
  them found the same five things in five different places, and the sheet —
  the product's most immersive surface — had no crumb and so no way home.

  This is the one bar. What it owns:

  * **the trail**, from `useCrumbs`, which is what gives the sheet a way out
    that is not a mark you have to guess is a button
  * **the title, renamed in place** — the sheet already worked this way and
    the document made you open a dialog for it, so the sheet's is the one that
    survived
  * **the mark and the product's name**, because the corner of a document is
    where a product gets to say what it is
  * **`#status`** for what is true of the file right now — saving, view-only,
    who else is here — and **`#actions`** for its verbs

  Through a link there is no trail: every crumb above the title is a place in
  a workspace this reader has no account in, so following one is a redirect to
  a sign-in page they cannot pass. The mark and the name stay; they are the
  only thing on the bar that is about the product rather than the workspace.

  `docs/UNIFICATION.md` §E2/E3.
-->
<template>
  <!-- The shell's header when this is a page, and a bar of its own when the
       editor is inside the Drive's pane: `PageHeader` is a teleport, so a
       hosted editor that drew one would put its title in the shell's header,
       above the file list it is sitting beside. -->
  <component
    :is="hosted ? 'header' : PageHeader"
    data-slot="editor-chrome"
    :class="hosted ? HOSTED : ''"
  >
    <!-- No trail, twice over. Through a link every crumb above the title is a
         place in a workspace this reader has no account in, so following one
         is a redirect to a sign-in page they cannot pass; and in the pane the
         trail is the Drive's own, drawn once above the list. Both keep the
         mark, which is the only thing on the bar that is about the product
         rather than the workspace. -->
    <nav
      v-if="shared || hosted"
      data-slot="breadcrumb"
      :aria-label="__('Breadcrumb')"
      class="flex min-w-0 flex-1 items-center gap-2"
    >
      <BrandMark :name="brand" class="size-6 shrink-0" />
      <component :is="TITLE" />
    </nav>

    <Trail v-else :items="crumbs">
      <!-- Not a control: the crumb beside it goes where a click on the mark
           would, and a logo that navigates where the word beside it navigates
           is one of them too many. The name as well as the mark, because a
           mark alone is recognisable to somebody who already knows it and
           says nothing to somebody who does not — which is everybody on their
           first day. Hidden on a phone, where the trail is the only thing
           there is room for. -->
      <template #before>
        <BrandMark :name="brand" class="size-6 shrink-0" />
        <SpaceName :brand="brand" class="hidden shrink-0 text-base font-medium md:block" />
        <span class="hidden shrink-0 text-ink-gray-3 md:block" aria-hidden="true">·</span>
      </template>

      <!-- The title is the subject, not the last crumb — §C1. A trail whose
           last segment is the answer rather than the way there is a trail
           with no end. -->
      <template #subject>
        <component :is="TITLE" />
      </template>
    </Trail>

    <div class="flex shrink-0 items-center gap-2">
      <slot name="status" />
      <slot name="actions" />
    </div>
  </component>
</template>

<script setup>
import { h, ref, watch } from 'vue'

import { PageHeader } from '@/ui'
import Trail from '@/shared/components/Trail.vue'
import BrandMark from '@/shared/components/brand/BrandMark.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import { HOVER } from '@/shared/lib/rowstate'
import { __ } from '@/shared/lib/runtime/translate'

//: A bar of our own, when there is no shell header to teleport into. The
//: shell's own is 48px and this matches it, so a file that opens in the pane
//: and a file that opens on a page do not step up and down as you switch.
const HOSTED = 'flex h-12 shrink-0 items-center gap-2 border-b border-outline-gray-1 px-3'

const props = defineProps({
  /** Which product this is — the mark and the name come off it. */
  brand: { type: String, required: true },
  /** From `composables/useCrumbs.js`, and from nowhere else. */
  crumbs: { type: Array, default: () => [] },
  title: { type: String, default: '' },
  /** What an untitled file is called, which differs per editor. */
  placeholder: { type: String, default: '' },
  /** Reached through a share link: no trail, and nothing to type into. */
  shared: { type: Boolean, default: false },
  renamable: { type: Boolean, default: false },
  /** Inside the Drive's pane rather than on a page of its own. */
  hosted: { type: Boolean, default: false },
})

const emit = defineEmits(['update:title'])

// The draft is local so a keystroke does not write, and it follows the prop so
// a rename from somewhere else — the Drive's own dialog, a collaborator — lands
// here rather than being held off by what is in the box.
const draft = ref(props.title)
watch(() => props.title, (now) => { draft.value = now })

/*
 * The title, in one place because it sits in two.
 *
 * A trail puts it in its `#subject` slot and a bar without one puts it beside
 * the mark, and a template that wrote it twice would be a rename that worked
 * on a page and not in the pane — which is exactly the class of drift §E2/E3
 * is about. A render function rather than a second component file: it is four
 * elements and it reads nothing but this component's own state.
 *
 * The input grows with its text. A hidden `::after` mirrors the value and
 * sizes the grid track, so the width comes out of real text layout rather
 * than out of a measurement that lags a keystroke behind the caret.
 */
const FIT = 'grid min-w-0 items-center [&::after]:invisible [&::after]:col-start-1'
  + ' [&::after]:row-start-1 [&::after]:whitespace-pre [&::after]:px-1 [&::after]:text-base'
  + ' [&::after]:font-medium [&::after]:content-[attr(data-value)]'
const BOX = 'col-start-1 row-start-1 min-w-0 truncate rounded-4 border-0 bg-transparent px-1'
  + ' text-base font-medium text-ink-primary shadow-none outline-none ring-0'
  + ' focus:bg-surface-gray-2 focus:ring-0'

const TITLE = () => (props.renamable
  ? h('span', { class: FIT, 'data-value': draft.value || props.placeholder }, [
    h('input', {
      value: draft.value,
      name: 'editor-title',
      'data-slot': 'editor-title',
      class: [HOVER, BOX],
      placeholder: props.placeholder,
      'aria-label': __('Name'),
      spellcheck: 'false',
      onInput: (event) => { draft.value = event.target.value },
      onKeyup: (event) => {
        if (event.key === 'Enter') event.target.blur()
        if (event.key === 'Escape') { draft.value = props.title; event.target.blur() }
      },
      onBlur: commit,
    }),
  ])
  : h('p', { class: 'min-w-0 truncate text-base font-medium text-ink-primary' },
    props.title || props.placeholder))

function commit() {
  const next = draft.value.trim()
  if (!next || next === props.title) {
    draft.value = props.title
    return
  }
  emit('update:title', next)
}
</script>
