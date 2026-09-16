<template>
  <!--
    The assistant, floating over whatever you are looking at.

    A **widget**, and the fourth surface in this product's vocabulary after the
    pane, the page and the drawer (`docs/ONESPACE.md`): fixed to the viewport,
    over the content rather than beside it, movable, and not modal. The three
    record surfaces are all about a record you opened *from* somewhere; this is
    the one thing that is about wherever you happen to be, so it is the one
    thing that does not belong in the layout.

    It was a panel — a column in the shell's flex row — and the reason it is
    not any more is arithmetic rather than taste. A panel takes its width off
    the page beside it, and this product already puts two columns there: with
    the Drive's pane open the list came out at about seventy pixels, which is
    enough for a tick and a format mark and nothing at all for the name. A
    third column does not fit on a laptop, and the assistant is the one of the
    three that has no claim to the space.

    What it keeps from the panel is the thing that made it a panel rather than
    a popover: **it survives being ignored.** An answer here can be eight
    provider calls and forty seconds, and a popover dismisses on the outside
    click somebody makes to go and check the record they were asking about.
    Nothing here closes on an outside click. Escape does, because that is a
    person saying so.

    Mounted once, in the shell, so every page has it without every page
    knowing about it.

    Not on a phone: there is one surface there and the assistant is a page
    (`/one/chat`) like everything else.
  -->
  <template v-if="state.available">
    <!--
      The way in is the dock — `components/desk/Dock.vue`.

      There was a 64px mark fixed in the bottom corner, and it was the right
      answer while the assistant was the only thing that floated: a rail entry
      is a rail you can collapse, and this had to be reachable from anywhere.
      The dock is that, for every app rather than for one, and two permanent
      marks in the same corner meaning nearly the same thing is the shape
      `docs/UNIFICATION.md` F1 refuses. It also took the corner a list's own
      footer had to be told to keep clear of, which is a rule that can go with
      it.
    -->
    <!--
      A tenant of the one window there is — `components/desk/DeskWindow.vue`.
      The drag, the resize, the remembered corner, the fill and the close were
      all written here first and are all there now; what is left below is what
      makes this window the assistant rather than any other.
    -->
    <DeskWindow
      v-if="assistantShowing"
      id="assistant"
      :title="assistantName"
      :label="assistantName"
      :tint="colourOf('oneai')"
      aura
      @close="closeAssistant"
    >
      <template #title>
        <!-- The mark breathes with the window, at the same four seconds the
             dial in the corner uses. A face beside a name rather than a
             control, so it is `halo` and not `dial` — see `index.css`. -->
        <AiFace size="sm" class="oneapp-ai-halo" />
        <!-- Through `SpaceName`, like every other window's title: `One` is the
             part that is the same on all of them and is said quietly, and this
             one was the last place in the product writing it flat. A workspace
             that renamed its assistant is said whole — the name is theirs. -->
        <SpaceName
          brand="oneai"
          :renamed="assistantRenamed"
          :label="assistantName"
          class="truncate text-base font-medium"
        />
      </template>

      <template #controls>
        <Button
          variant="ghost"
          icon="lucide-plus"
          :label="__('New chat')"
          :tooltip="__('New chat')"
          data-slot="assistant-new"
          @click="state.session = ''"
        />
        <Dropdown :options="threads">
          <Button
            variant="ghost"
            icon="lucide-history"
            :label="__('Earlier chats')"
            :tooltip="__('Earlier chats')"
            data-slot="assistant-threads"
          />
        </Dropdown>
        <Dropdown :options="menu">
          <Button variant="ghost" icon="lucide-ellipsis" :label="__('More')" :tooltip="__('More')" />
        </Dropdown>
      </template>

      <template #under>
        <!--
          Everything open, one chip each, and which of them the question goes
          out with.

          It was one chip and it was a guess: the panel picked the front-most
          window and said nothing about the rest, so a question asked with a
          workbook, a letter and the record they are both about on screen was
          answered from whichever happened to be in front. Which is right about
          half the time and silent either way.

          So all of them are listed and the person decides. A lit chip goes
          with the question; a dim one does not. The first lit one is what
          "this" means — front-first is the desk's own order, so raising a
          window is how you change it, which is what raising a window already
          means.

          The mark is the file's own — the same artwork the Drive draws, so a
          workbook here and a workbook there are recognisably the same thing.
        -->
        <div
          v-if="openHere.length"
          class="flex flex-wrap items-center gap-1"
          data-slot="assistant-context"
          @pointerdown.stop
        >
          <button
            v-for="one in openHere"
            :key="one.owner"
            type="button"
            class="flex max-w-full items-center gap-1.5 rounded-full border py-0.5 pe-2 ps-2 transition"
            :class="one.on
              ? 'border-outline-gray-2 bg-surface-gray-1'
              : 'border-outline-gray-1 bg-surface-base opacity-60'"
            :data-slot="one.on ? 'context-chip-on' : 'context-chip-off'"
            :title="one.on
              ? __('{0} goes with your question', [one.label])
              : __('{0} is left out', [one.label])"
            @click="toggleContext(one.owner)"
          >
            <img
              v-if="one.file"
              :src="artForKind(one.kind)"
              :alt="''"
              aria-hidden="true"
              class="size-3.5 shrink-0"
              :class="one.on ? '' : 'grayscale'"
            />
            <Icon v-else name="lucide-layout-list" class="size-3.5 shrink-0 text-ink-muted" />
            <span class="min-w-0 flex-1 truncate text-xs"
                  :class="one.on ? 'text-ink-secondary' : 'text-ink-muted line-through'">
              {{ one.label }}
              <!--
                And what is highlighted, when anything is. It changes what the
                answer will be about — "summarise this" is the paragraph rather
                than the document — so it is said where the subject is said,
                and in words rather than implied: the passage is going into a
                request, and somebody ought to be able to see that it is.
              -->
              <template v-if="one.selection">
                · {{ highlightedIn(one) }}
              </template>
            </span>
          </button>
        </div>
      </template>

      <ChatPanel v-model="state.session" :on="shown" :sending="sending" framed />
    </DeskWindow>
  </template>
</template>

<script setup>
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Button, Dropdown, Icon } from '@/ui'
import { colourOf } from '@/shared/lib/brand/naming'
import AiFace from '@/shared/components/AiFace.vue'
import SpaceName from '@/shared/components/brand/SpaceName.vue'
import { artForKind } from '@/modules/onestorage/lib/art'
import { openContexts } from '@/modules/onespace/lib/shell/nav'
import { useShortcuts } from '@/modules/onespace/lib/shell/shortcuts'
import ChatPanel from '@/modules/onespace/components/chat/ChatPanel.vue'
import DeskWindow from '@/modules/onespace/components/desk/DeskWindow.vue'
import {
  assistant as state,
  assistantName,
  assistantRenamed,
  assistantShowing,
  closeAssistant,
  loadAssistant,
  openAssistant,
  pressAssistant,
} from '@/modules/onespace/lib/shell/assistant'
import { toggleContext } from '@/shared/lib/ai/context'
import { useAddress } from '@/shared/composables/useAddress'
import { workspace } from '@/shared/lib/workspace'
import { KIND, writeAt } from '@/shared/lib/url/at'
import { __ } from '@/shared/lib/runtime/translate'

const router = useRouter()
const route = useRoute()

/**
 * Anywhere, without reaching for the dock — which is the other half of "always
 * there". A shortcut costs no pixels.
 *
 * `mod+j` because `mod+k` is a command palette everywhere and taking it here
 * would be taking it from the thing people expect it to be.
 *
 * It folds rather than closes, which is what changed when there was somewhere
 * to fold to. Pressing it twice used to throw the conversation away and start
 * a new one on the way back; now the second press is the same thing the dock's
 * tile does, and the thread is where it was left.
 */
useShortcuts({
  'mod+j': () => pressAssistant(),
})

/**
 * Everything open, front-first, with a chip each.
 *
 * Live, and deliberately so. This used to be one stored subject: the panel
 * decided what it was about when it opened, `openAssistant` started a new
 * thread whenever that changed, and nothing revisited it afterwards — so a
 * conversation and a desk could disagree and only one of them was visible.
 *
 * With the chips on screen there is nothing to freeze. A person can see what
 * the next question will carry and change it before asking, which is a better
 * answer than a rule that guesses on their behalf; New chat is the button for
 * when the conversation really has moved on.
 */
const openHere = computed(() => openContexts(route))

/** What goes with the question: the lit chips, front-first. */
const sending = computed(() => openHere.value.filter((one) => one.on))

/** The one "this" means, for the panel's own opening line and its openers. */
const shown = computed(() => sending.value[0] || null)

/**
 * What is highlighted, counted in the unit that surface counts in.
 *
 * Words for prose, and the range itself for a workbook — "C3:E8" is what a
 * person selecting cells is looking at, and a word count of a pipe table is a
 * number about nothing. The digest's first line is the range, which is why it
 * is first.
 */
function highlightedIn(one) {
  const said = String(one?.selection || '')
  if (one?.kind === 'Sheet') return said.split('\n')[0]
  const count = said.trim().split(/\s+/).filter(Boolean).length
  return __('{0} words highlighted', [count])
}

/** The threads this person has, newest first, as a menu. */
const threads = computed(() => {
  const rows = state.sessions || []
  if (!rows.length) {
    return [{ label: __('No earlier chats'), icon: 'lucide-message-square', onClick: () => {} }]
  }
  return rows.slice(0, 12).map((one) => ({
    label: one.title,
    icon: 'lucide-message-square',
    selected: one.name === state.session,
    onClick: () => { state.session = one.name },
  }))
})

/**
 * The assistant has an address — `?ask=`, §C4.
 *
 * Empty means open on a new conversation; a session name means open on that
 * one. It is a panel and stays one — an answer here can be forty seconds and
 * a popover dismisses on the click somebody makes to go and check the record
 * they asked about — but a panel with an address is one a colleague can be
 * sent to.
 *
 * Not drawn on a phone, where the assistant is a page; the address there is
 * `/one/chat`, which is a route and already had one.
 */
useAddress('ask', {
  read: () => {
    if (!assistantShowing.value) return ''
    // A blank value is still an answer: `?ask=` is the assistant open on
    // nothing, which is what pressing the rail entry gives you. Vue Router
    // drops an empty string, so a new conversation says so with a word.
    return state.session || 'new'
  },
  write: (value) => {
    if (!value) {
      closeAssistant()
      return
    }
    // Order used to matter here and no longer does: `openAssistant` carried a
    // subject and started a new thread whenever it changed, so setting the
    // session first was setting one the call then threw away — a link to a
    // conversation opened an empty one. It carries nothing now, and what the
    // panel is about is whatever is open when the next question is asked.
    openAssistant()
    state.session = value === 'new' ? '' : value
  },
})

/**
 * The three things a conversation can be, beyond having it.
 *
 * "Open as a page" is the one that matters and it is why the page still exists:
 * a panel is 384px, and a long answer with four lookups under it wants a
 * column. The thread goes with it — the same conversation, wider.
 */
const menu = computed(() => [
  {
    label: __('New chat'),
    icon: 'lucide-plus',
    onClick: () => { state.session = '' },
  },
  {
    label: __('Open as a page'),
    icon: 'lucide-maximize-2',
    onClick: () => {
      // Navigate, and let the widget close because it did.
      //
      // Closing first looked obvious and cancelled the navigation: closing
      // writes `?ask=` out of the URL through `useAddress`, that write is a
      // `router.replace`, and a replace issued while a push is in flight
      // aborts the push — so "Open as a page" left the reader exactly where
      // they were, on a route with one fewer query parameter.
      //
      // Nothing has to close it either. The chat route carries no `ask`, so
      // the moment the URL changes `useAddress` reads a value that disagrees
      // with the state and writes the state back down to match: the widget
      // shuts itself, which is the same mechanism that closes it when
      // somebody presses Back.
      router.push({
        name: 'Chat',
        ...(state.session ? { query: { at: writeAt(KIND.CHAT, state.session) } } : {}),
      })
    },
  },
  ...(state.session
    ? [{
      label: __('Delete for ever'),
      icon: 'lucide-trash-2',
      onClick: async () => {
        await workspace.forgetChat(state.session)
        state.session = ''
        await loadAssistant({ reload: true })
      },
    }]
    : []),
])
</script>
